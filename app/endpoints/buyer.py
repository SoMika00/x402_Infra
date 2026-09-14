from fastapi import APIRouter, Depends, Request, Query
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.payments.x402_gateway import pay_dep
from app.payments.ledger import get_engine, JobLog

router = APIRouter(prefix="/buyer")

# Existing endpoints (balance, jobs) are assumed to be present; we will add summary endpoint below.

@router.get("/summary", tags=["buyer"])
async def buyer_summary(
    request: Request,
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="buyer_summary"))
):
    """Return aggregated job usage for the authenticated payer.
    Returns JSON with fields:
        ok: bool
        total_jobs: int
        total_cents: int
        last_job_at: Optional[str] (ISO timestamp) or null
    """
    payer = getattr(request.state, "payer", "0xUnknown")
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        # Aggregate total jobs and total cents
        stmt = select(
            func.count(JobLog.id),
            func.coalesce(func.sum(JobLog.cents), 0),
            func.max(JobLog.created_at)
        ).where(JobLog.payer == payer)
        result = await session.execute(stmt)
        total_jobs, total_cents, last_job_at = result.one()
        # Convert datetime to ISO string if present
        last_job_iso: Optional[str] = None
        if isinstance(last_job_at, datetime):
            last_job_iso = last_job_at.isoformat()
        return {
            "ok": True,
            "total_jobs": int(total_jobs),
            "total_cents": int(total_cents),
            "last_job_at": last_job_iso,
        }
