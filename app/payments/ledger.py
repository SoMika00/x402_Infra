import datetime as dt
import json
from typing import Optional, List

from sqlalchemy import Column, Integer, String, DateTime, JSON, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

from app.core.config import settings
from app.metrics import revenue_cents_total

Base = declarative_base()

class JobLog(Base):
    __tablename__ = "job_logs"
    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String, index=True)
    payer = Column(String, index=True)
    cents = Column(Integer)
    tx_hash = Column(String)
    latency_ms = Column(Integer)
    gpu_id = Column(String)
    batch_size = Column(Integer)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    extra = Column(JSON, default={})

# Engine handling (simplified for tests)
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine
        _engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    return _engine

async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def log_job(
    session: AsyncSession,
    *,
    endpoint: str,
    payer: str,
    cents: int,
    tx_hash: str,
    latency_ms: int,
    gpu_id: str,
    batch_size: int,
    extra: Optional[dict] = None,
) -> None:
    """Record a job execution in the ledger and update metrics.

    Parameters
    ----------
    session: AsyncSession
        The SQLAlchemy async session to use.
    endpoint: str
        The endpoint name (e.g., "embed", "parse_pdf").
    payer: str
        The address of the payer.
    cents: int
        Revenue in cents for this job.
    tx_hash: str
        Transaction hash associated with the payment.
    latency_ms: int
        Latency of the job in milliseconds.
    gpu_id: str
        Identifier of the GPU used.
    batch_size: int
        Number of items processed in the batch.
    extra: Optional[dict]
        Additional JSON data to store.
    """
    # Insert into DB
    job = JobLog(
        endpoint=endpoint,
        payer=payer,
        cents=cents,
        tx_hash=tx_hash,
        latency_ms=latency_ms,
        gpu_id=gpu_id,
        batch_size=batch_size,
        extra=extra or {},
    )
    session.add(job)
    await session.flush()

    # Update revenue metric
    revenue_cents_total.labels(endpoint=endpoint, asset=settings.X402_ASSET).inc(cents)

    # Note: jobs_total gauge is updated by background polling, not here.

async def get_jobs_by_payer(session: AsyncSession, payer: str, limit: int = 100) -> List[JobLog]:
    q = select(JobLog).where(JobLog.payer == payer).order_by(JobLog.created_at.desc()).limit(limit)
    result = await session.execute(q)
    return result.scalars().all()

async def get_job_summary(session: AsyncSession, payer: str) -> dict:
    q = select(func.count(), func.sum(JobLog.cents), func.max(JobLog.created_at)).where(JobLog.payer == payer)
    result = await session.execute(q)
    count, total_cents, last_at = result.one()
    return {
        "total_jobs": count or 0,
        "total_cents": total_cents or 0,
        "last_job_at": last_at.isoformat() if last_at else None,
    }
