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
        # Build ordered leaf list for this payer+date (order by JobLog.id)
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

        if not jobs:
            # Log job before raising 404 (billing consistency)
            gpu = os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown")
            await log_job(
                session,
                endpoint="buyer_merkle_export",
                payer=payer,
                cents=settings.PRICE_BALANCE_CENTS,
                tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
                latency_ms=int((time.perf_counter() - t0) * 1000),
                gpu_id=gpu,
                batch_size=1,
            )
            raise HTTPException(status_code=404, detail="no jobs for the given date")

        leaves = [hash_leaf(job_leaf(j)) for j in jobs]

        # Prefer stored MerkleRoot for this payer+date, otherwise compute on-the-fly
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
            root = compute_merkle_root(leaves)

        # Build jobs array with proofs
        jobs_out = []
        for idx, job in enumerate(jobs):
            leaf_hash = leaves[idx]
            proof = compute_merkle_proof(leaves, idx)
            jobs_out.append({
                "id": job.id,
                "endpoint": job.endpoint,
                "cents": job.cents,
                "tx_hash": job.tx_hash,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "leaf": leaf_hash,
                "proof": proof,
            })

        # Defensive self-check: re-verify every leaf proof against the returned root
        verified = all(
            verify_merkle_proof(j["leaf"], j["proof"], root) for j in jobs_out
        )

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
        "leaf_count": len(jobs_out),
        "jobs": jobs_out,
        "generated_at": datetime.utcnow().isoformat(),
        "verified": verified,
    }
