from fastapi import APIRouter, Depends, Request, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.payments.x402_gateway import pay_dep
from app.payments.ledger import (
    get_engine,
    log_job,
    MerkleRoot,
    JobLog,
    job_leaf,
    hash_leaf,
    compute_merkle_root,
    compute_merkle_proof,
    verify_merkle_proof,
)
from app.metrics import latency_seconds
import os, time

router = APIRouter(prefix="/buyer")


class ExportJob(BaseModel):
    id: int
    endpoint: str
    payer: str
    cents: int
    tx_hash: str


class ExportBundle(BaseModel):
    version: int
    date: str
    payer: str
    root: str
    leaf_count: int
    jobs: List[ExportJob]
    generated_at: Optional[str] = None


# Existing buyer endpoints (balance, jobs, summary) are defined elsewhere in this file.
# For brevity they are not shown here but remain unchanged.

@router.get("/merkle")
async def get_merkle(
    request: Request,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="buyer_merkle"))
):
    """Retrieve Merkle root and job count for a given date for the authenticated buyer.
    Returns 404 if no MerkleRoot entry exists for that date.
    """
    # Validate date format
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    t0 = time.perf_counter()
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        stmt = MerkleRoot.select().where(
            MerkleRoot.c.payer == getattr(request.state, "payer", "0xUnknown"),
            MerkleRoot.c.date == query_date
        )
        result = await session.execute(stmt)
        row = result.fetchone()
        if not row:
            # Log job before raising 404
            gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
            await log_job(
                session,
                endpoint="buyer_merkle",
                payer=getattr(request.state, "payer", "0xUnknown"),
                cents=settings.PRICE_BALANCE_CENTS,
                tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
                latency_ms=int((time.perf_counter() - t0) * 1000),
                gpu_id=gpu,
                batch_size=1,
            )
            raise HTTPException(status_code=404, detail="Merkle root not found for the given date")
        # row is a RowMapping; extract fields
        merkle_root = row["merkle_root"]
        job_count = row["job_count"]

    dt = time.perf_counter() - t0
    latency_seconds.labels("buyer_merkle").observe(dt)

    # Log successful job
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
        await log_job(
            session,
            endpoint="buyer_merkle",
            payer=getattr(request.state, "payer", "0xUnknown"),
            cents=settings.PRICE_BALANCE_CENTS,
            tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
            latency_ms=int(dt * 1000),
            gpu_id=gpu,
            batch_size=1,
        )

    return {
        "ok": True,
        "date": date,
        "merkle_root": merkle_root,
        "job_count": job_count,
    }


@router.get("/merkle/verify")
async def verify_merkle(
    request: Request,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    job_id: int = Query(..., description="JobLog id to verify"),
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="buyer_merkle_verify"))
):
    """Prove a specific job is included in the daily Merkle root for the payer.

    Returns {ok, date, job_id, leaf, proof, root, verified}.
    """
    # Validate date format
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    payer = getattr(request.state, "payer", "0xUnknown")
    t0 = time.perf_counter()

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        # Load the JobLog row by id
        job_res = await session.execute(select(JobLog).where(JobLog.id == job_id))
        job = job_res.scalar_one_or_none()
        if job is None:
            gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
            await log_job(
                session,
                endpoint="buyer_merkle_verify",
                payer=payer,
                cents=settings.PRICE_BALANCE_CENTS,
                tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
                latency_ms=int((time.perf_counter() - t0) * 1000),
                gpu_id=gpu,
                batch_size=1,
            )
            raise HTTPException(status_code=404, detail="Job not found")

        if job.payer != payer:
            raise HTTPException(status_code=403, detail="Job does not belong to the authenticated payer")

        # Load the stored MerkleRoot for this payer+date
        root_res = await session.execute(
            select(MerkleRoot).where(
                MerkleRoot.c.payer == payer,
                MerkleRoot.c.date == query_date,
            )
        )
        root_row = root_res.fetchone()
        if not root_row:
            gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
            await log_job(
                session,
                endpoint="buyer_merkle_verify",
                payer=payer,
                cents=settings.PRICE_BALANCE_CENTS,
                tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
                latency_ms=int((time.perf_counter() - t0) * 1000),
                gpu_id=gpu,
                batch_size=1,
            )
            raise HTTPException(status_code=404, detail="Merkle root not found for the given date")

        stored_root = root_row["merkle_root"]

        # Rebuild ordered leaf list for this payer+date (order by JobLog.id)
        day_start = datetime(query_date.year, query_date.month, query_date.day)
        day_end = day_start + timedelta(days=1)
        jobs_res = await session.execute(
            select(JobLog)
            .where(
                JobLog.payer == payer,
                JobLog.created_at >= day_start,
                JobLog.created_at < day_end,
            )
            .order_by(JobLog.id)
        )
        jobs = jobs_res.scalars().all()

        leaves = [hash_leaf(job_leaf(j)) for j in jobs]
        try:
            target_index = leaves.index(hash_leaf(job_leaf(job)))
        except ValueError:
            # The job exists but is not in the date range for this payer
            raise HTTPException(status_code=404, detail="Job not found for the given date")

        proof = compute_merkle_proof(leaves, target_index)
        leaf_hash = leaves[target_index]
        verified = verify_merkle_proof(leaf_hash, proof, stored_root)

    dt = time.perf_counter() - t0
    latency_seconds.labels("buyer_merkle_verify").observe(dt)

    # Log successful job
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
        await log_job(
            session,
            endpoint="buyer_merkle_verify",
            payer=payer,
            cents=settings.PRICE_BALANCE_CENTS,
            tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
            latency_ms=int(dt * 1000),
            gpu_id=gpu,
            batch_size=1,
        )

    return {
        "ok": True,
        "date": date,
        "job_id": job_id,
        "leaf": leaf_hash,
        "proof": proof,
        "root": stored_root,
        "verified": verified,
    }


@router.get("/merkle/proof")
async def get_merkle_proof(
    request: Request,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    job_id: int = Query(..., description="JobLog id to prove"),
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="buyer_merkle_proof"))
):
    """Return the Merkle proof for a specific job on a given date.

    Returns {ok, date, job_id, leaf, proof, root}.
    """
    # Validate date format
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    payer = getattr(request.state, "payer", "0xUnknown")
    t0 = time.perf_counter()

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        # Load the JobLog row by id
        job_res = await session.execute(select(JobLog).where(JobLog.id == job_id))
        job = job_res.scalar_one_or_none()
        if job is None:
            gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
            await log_job(
                session,
                endpoint="buyer_merkle_proof",
                payer=payer,
                cents=settings.PRICE_BALANCE_CENTS,
                tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
                latency_ms=int((time.perf_counter() - t0) * 1000),
                gpu_id=gpu,
                batch_size=1,
            )
            raise HTTPException(status_code=404, detail="Job not found")

        if job.payer != payer:
            raise HTTPException(status_code=403, detail="Job does not belong to the authenticated payer")

        # Rebuild ordered leaf list for this payer+date (order by creation time)
        day_start = datetime(query_date.year, query_date.month, query_date.day)
        day_end = day_start + timedelta(days=1)
        jobs_res = await session.execute(
            select(JobLog)
            .where(
                JobLog.payer == payer,
                JobLog.created_at >= day_start,
                JobLog.created_at < day_end,
            )
            .order_by(JobLog.created_at, JobLog.id)
        )
        jobs = jobs_res.scalars().all()

        leaves = [hash_leaf(job_leaf(j)) for j in jobs]
        try:
            target_index = leaves.index(hash_leaf(job_leaf(job)))
        except ValueError:
            raise HTTPException(status_code=404, detail="Job not found for the given date")

        proof = compute_merkle_proof(leaves, target_index)
        leaf_hash = leaves[target_index]

        # Determine the root: prefer stored MerkleRoot, otherwise compute on-the-fly
        root_res = await session.execute(
            select(MerkleRoot).where(
                MerkleRoot.c.payer == payer,
                MerkleRoot.c.date == query_date,
            )
        )
        root_row = root_res.fetchone()
        if root_row:
            root = root_row["merkle_root"]
        else:
            from app.payments.ledger import compute_merkle_root
            root = compute_merkle_root(leaves)

    dt = time.perf_counter() - t0
    latency_seconds.labels("buyer_merkle_proof").observe(dt)

    # Log successful job
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
        await log_job(
            session,
            endpoint="buyer_merkle_proof",
            payer=payer,
            cents=settings.PRICE_BALANCE_CENTS,
            tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
            latency_ms=int(dt * 1000),
            gpu_id=gpu,
            batch_size=1,
        )

    return {
        "ok": True,
        "date": date,
        "job_id": job_id,
        "leaf": leaf_hash,
        "proof": proof,
        "root": root,
    }


@router.get("/merkle/export")
async def export_merkle(
    request: Request,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="buyer_merkle_export"))
):
    """Export a full audit bundle for a given date for the authenticated buyer.

    Returns an ExportBundle (version, date, payer, root, leaf_count, jobs, generated_at).
    """
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    payer = getattr(request.state, "payer", "0xUnknown")
    t0 = time.perf_counter()

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        day_start = datetime(query_date.year, query_date.month, query_date.day)
        day_end = day_start + timedelta(days=1)
        jobs_res = await session.execute(
            select(JobLog)
            .where(
                JobLog.payer == payer,
                JobLog.created_at >= day_start,
                JobLog.created_at < day_end,
            )
            .order_by(JobLog.id)
        )
        jobs = jobs_res.scalars().all()

        leaves = [hash_leaf(job_leaf(j)) for j in jobs]
        root = compute_merkle_root(leaves)

        # Prefer stored MerkleRoot if present
        root_res = await session.execute(
            select(MerkleRoot).where(
                MerkleRoot.c.payer == payer,
                MerkleRoot.c.date == query_date,
            )
        )
        root_row = root_res.fetchone()
        if root_row:
            root = root_row["merkle_root"]

        export_jobs = [
            ExportJob(
                id=j.id,
                endpoint=j.endpoint,
                payer=j.payer,
                cents=j.cents,
                tx_hash=j.tx_hash,
            )
            for j in jobs
        ]

    dt = time.perf_counter() - t0
    latency_seconds.labels("buyer_merkle_export").observe(dt)

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
        await log_job(
            session,
            endpoint="buyer_merkle_export",
            payer=payer,
            cents=settings.PRICE_BALANCE_CENTS,
            tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
            latency_ms=int(dt * 1000),
            gpu_id=gpu,
            batch_size=1,
        )

    return {
        "version": 1,
        "date": date,
        "payer": payer,
        "root": root,
        "leaf_count": len(jobs),
        "jobs": [j.model_dump() for j in export_jobs],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


@router.post("/merkle/export/verify")
async def verify_export_bundle(
    request: Request,
    bundle: ExportBundle,
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="buyer_merkle_export_verify"))
):
    """Re-verify a previously exported audit bundle end-to-end.

    Returns {ok, verified, checks: {...}, errors: [...]}.
    """
    payer = getattr(request.state, "payer", "0xUnknown")
    t0 = time.perf_counter()

    errors: List[str] = []
    checks: dict = {}

    # 1. version must equal 1
    version_ok = bundle.version == 1
    checks["version"] = version_ok
    if not version_ok:
        errors.append(f"version mismatch: expected 1, got {bundle.version}")

    # 2. date must parse as YYYY-MM-DD (400 on bad format)
    try:
        query_date = datetime.strptime(bundle.date, "%Y-%m-%d").date()
        checks["date"] = True
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    # 3. payer must match request.state.payer (403 otherwise)
    if bundle.payer != payer:
        raise HTTPException(status_code=403, detail="Bundle payer does not match authenticated payer")
    checks["payer"] = True

    # 4. Recompute leaves from jobs (order by id ascending)
    ordered_jobs = sorted(bundle.jobs, key=lambda j: j.id)
    leaves = [hash_leaf(job_leaf(j)) for j in ordered_jobs]
    recomputed_root = compute_merkle_root(leaves)

    # 5. Compare recomputed root to bundle.root
    root_ok = recomputed_root == bundle.root
    checks["root"] = root_ok
    if not root_ok:
        errors.append("root mismatch: recomputed root does not match bundle.root")

    # 6. Compare len(jobs) to bundle.leaf_count
    leaf_count_ok = len(bundle.jobs) == bundle.leaf_count
    checks["leaf_count"] = leaf_count_ok
    if not leaf_count_ok:
        errors.append(
            f"leaf_count mismatch: bundle has {len(bundle.jobs)} jobs but leaf_count={bundle.leaf_count}"
        )

    # 7. Look up stored MerkleRoot for (payer, date)
    stored_root = None
    stored_job_count = None
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        root_res = await session.execute(
            select(MerkleRoot).where(
                MerkleRoot.c.payer == payer,
                MerkleRoot.c.date == query_date,
            )
        )
        root_row = root_res.fetchone()
        if root_row:
            stored_root = root_row["merkle_root"]
            stored_job_count = root_row["job_count"]

    if stored_root is not None:
        stored_root_ok = bundle.root == stored_root
        checks["stored_root"] = stored_root_ok
        if not stored_root_ok:
            errors.append("stored root mismatch: bundle.root does not match stored MerkleRoot")

        stored_count_ok = bundle.leaf_count == stored_job_count
        checks["stored_leaf_count"] = stored_count_ok
        if not stored_count_ok:
            errors.append(
                f"stored leaf_count mismatch: bundle.leaf_count={bundle.leaf_count} vs stored job_count={stored_job_count}"
            )
    else:
        checks["stored_root"] = "skipped"
        checks["stored_leaf_count"] = "skipped"

    verified = len(errors) == 0

    dt = time.perf_counter() - t0
    latency_seconds.labels("buyer_merkle_export_verify").observe(dt)

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
        await log_job(
            session,
            endpoint="buyer_merkle_export_verify",
            payer=payer,
            cents=settings.PRICE_BALANCE_CENTS,
            tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
            latency_ms=int(dt * 1000),
            gpu_id=gpu,
            batch_size=1,
        )

    return {
        "ok": True,
        "verified": verified,
        "checks": checks,
        "errors": errors,
    }
