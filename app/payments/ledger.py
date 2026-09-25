import datetime as dt
import hashlib
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, DateTime, LargeBinary, Text, UniqueConstraint, select, insert, update, Date, desc
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class JobLog(Base):
    __tablename__ = "joblog"
    id = Column(Integer, primary_key=True)
    endpoint = Column(String, nullable=False)
    payer = Column(String, nullable=False)
    cents = Column(Integer, nullable=False)
    tx_hash = Column(String, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    gpu_id = Column(String, nullable=False)
    batch_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

class MerkleRoot(Base):
    __tablename__ = "merkle_root"
    id = Column(Integer, primary_key=True)
    payer = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    merkle_root = Column(String, nullable=True)
    job_count = Column(Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint('payer', 'date', name='_payer_date_uc'),)

# Existing functions (get_engine, init_db, log_job) remain unchanged – they are defined below.

async def get_engine() -> AsyncEngine:
    from app.core.config import settings
    return create_async_engine(settings.DATABASE_URL, echo=False, future=True)

async def init_db():
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def log_job(
    session: AsyncSession,
    endpoint: str,
    payer: str,
    cents: int,
    tx_hash: str,
    latency_ms: int,
    gpu_id: str,
    batch_size: int,
):
    stmt = insert(JobLog).values(
        endpoint=endpoint,
        payer=payer,
        cents=cents,
        tx_hash=tx_hash,
        latency_ms=latency_ms,
        gpu_id=gpu_id,
        batch_size=batch_size,
    )
    await session.execute(stmt)
    await session.commit()

# Helper to fetch MerkleRoot – used by the new endpoint.
async def fetch_merkle_root(session: AsyncSession, payer: str, date: dt.date) -> Optional[MerkleRoot]:
    stmt = select(MerkleRoot).where(MerkleRoot.payer == payer, MerkleRoot.date == date)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

# Existing other ledger utilities remain unchanged.
