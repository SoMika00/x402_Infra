import datetime as dt
import time
import os

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.payments.x402_gateway import pay_dep
from app.payments.ledger import (
    get_engine,
    JobLog,
    get_daily_stats,
    job_leaf,
    hash_leaf,
    compute_merkle_root,
)
from app.metrics import latency_seconds

router = APIRouter(prefix="/stats")


@router.get("/daily/export")
async def stats_daily_export(
    request: Request,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="stats_daily_export")),
):
    """Export a self-contained, offline-verifiable daily audit bundle for a UTC day.

    The bundle covers ALL payers (platform-wide) and lets a third party recompute
    the Merkle root over every job of the day to confirm the totals were not
    tampered with.
    """
    try:
        query_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    t0 = time.perf_counter()

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        day_start = dt.datetime(query_date.year, query_date.month, query_date.day)
        day_end = day_start + dt.timedelta(days=1)

        jobs_res = await session.execute(
            select(JobLog)
            .where(
                JobLog.created_at >= day_start,
                JobLog.created_at < day_end,
            )
            .order_by(JobLog.id)
        )
        jobs = jobs_res.scalars().all()

        if not jobs:
            raise HTTPException(status_code=404, detail="No jobs found for the given date")

        leaves = [hash_leaf(job_leaf(j)) for j in jobs]
        root = compute_merkle_root(leaves)

        stats = await get_daily_stats(session, query_date)

        generated_at = dt.datetime.utcnow().isoformat() + "Z"

        bundle = {
            "version": 1,
            "date": date,
            "root": root,
            "leaf_count": len(jobs),
            "totals": {
                "total_jobs": stats["total_jobs"],
                "total_cents": stats["total_cents"],
                "unique_payers": stats["unique_payers"],
                "endpoints": stats["endpoints"],
            },
            "jobs": [
                {
                    "id": j.id,
                    "endpoint": j.endpoint,
                    "payer": j.payer,
                    "cents": j.cents,
                    "tx_hash": j.tx_hash,
                }
                for j in jobs
            ],
            "generated_at": generated_at,
            "root_source": "computed",
        }

    dt_elapsed = time.perf_counter() - t0
    latency_seconds.labels("stats_daily_export").observe(dt_elapsed)

    return bundle
