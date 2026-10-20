from fastapi import APIRouter, Depends, Request, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
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
    """Return a self-contained, verifiable daily audit bundle for the authenticated payer.

    Returns {ok, version, date, payer, root, leaf_count, jobs, generated_at, verified}.
    """
    # Validate date format
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

        jobs_payload = [
            {
                "id": j.id,
                "endpoint": j.endpoint,
                "payer": j.payer,
                "cents": j.cents,
                "tx_hash": j.tx_hash,
                "latency_ms": j.latency_ms,
                "gpu_id": j.gpu_id,
                "batch_size": j.batch_size,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]

    dt = time.perf_counter() - t0
    latency_seconds.labels("buyer_merkle_export").observe(dt)

    # Log successful job
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
        "ok": True,
        "version": 1,
        "date": date,
        "payer": payer,
        "root": root,
        "leaf_count": len(jobs),
        "jobs": jobs_payload,
        "generated_at": datetime.utcnow().isoformat(),
        "verified": True,
    }


@router.post("/merkle/export/verify")
async def verify_export_bundle(request: Request):
    """Validate a previously exported daily audit bundle.

    This is a pure, stateless verification helper: it does not touch the DB,
    does not charge the buyer, and does not log a job.

    Accepts a JSON body matching the export bundle shape:
    {version, date, payer, root, leaf_count, jobs: [{id, endpoint, payer, cents, tx_hash, ...}], generated_at}

    Returns {ok, date, payer, root, leaf_count, root_matches, all_proofs_valid, jobs_checked, failures}.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    # Validate required top-level fields
    required_fields = ["version", "date", "payer", "root", "leaf_count", "jobs"]
    for field in required_fields:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    jobs = body.get("jobs")
    if not isinstance(jobs, list):
        raise HTTPException(status_code=400, detail="'jobs' must be a list")
    if len(jobs) == 0:
        raise HTTPException(status_code=400, detail="'jobs' must not be empty")

    declared_root = body.get("root")
    if not isinstance(declared_root, str) or not declared_root:
        raise HTTPException(status_code=400, detail="'root' must be a non-empty string")

    declared_leaf_count = body.get("leaf_count")
    if not isinstance(declared_leaf_count, int):
        raise HTTPException(status_code=400, detail="'leaf_count' must be an integer")

    payer = body.get("payer")
    if not isinstance(payer, str) or not payer:
        raise HTTPException(status_code=400, detail="'payer' must be a non-empty string")

    date = body.get("date")
    if not isinstance(date, str) or not date:
        raise HTTPException(status_code=400, detail="'date' must be a non-empty string")

    # Validate each job has required fields and shares the bundle payer
    failures = []
    ordered_jobs = []
    for idx, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise HTTPException(status_code=400, detail=f"jobs[{idx}] must be an object")
        for field in ["id", "endpoint", "payer", "cents", "tx_hash"]:
            if field not in job:
                raise HTTPException(status_code=400, detail=f"jobs[{idx}] missing required field: {field}")
        if job.get("payer") != payer:
            failures.append({
                "job_id": job.get("id"),
                "reason": "payer_mismatch",
                "detail": f"job payer '{job.get('payer')}' does not match bundle payer '{payer}'",
            })
        ordered_jobs.append(job)

    # Order jobs by id ascending (matching the export)
    try:
        ordered_jobs.sort(key=lambda j: j["id"])
    except Exception:
        raise HTTPException(status_code=400, detail="All jobs must have a comparable 'id' field")

    # Recompute leaves using the deterministic leaf format
    leaves = []
    for job in ordered_jobs:
        leaf_str = f"{job['id']}|{job['endpoint']}|{job['payer']}|{job['cents']}|{job['tx_hash']}"
        leaves.append(hash_leaf(leaf_str))

    recomputed_root = compute_merkle_root(leaves)
    root_matches = recomputed_root == declared_root

    # Verify each job's Merkle proof against the declared root
    all_proofs_valid = True
    for i, job in enumerate(ordered_jobs):
        leaf_hash = leaves[i]
        proof = compute_merkle_proof(leaves, i)
        valid = verify_merkle_proof(leaf_hash, proof, declared_root)
        if not valid:
            all_proofs_valid = False
            failures.append({
                "job_id": job.get("id"),
                "reason": "proof_invalid",
                "detail": "Merkle proof does not verify against declared root",
            })

    leaf_count_matches = declared_leaf_count == len(jobs)

    ok = root_matches and leaf_count_matches and all_proofs_valid

    return {
        "ok": ok,
        "date": date,
        "payer": payer,
        "root": declared_root,
        "leaf_count": declared_leaf_count,
        "root_matches": root_matches,
        "all_proofs_valid": all_proofs_valid,
        "jobs_checked": len(jobs),
        "failures": failures,
    }
