import datetime as dt
import hashlib
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, DateTime, LargeBinary, Text, UniqueConstraint, select, insert, update, Date, desc
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

Base = declarative_base()
_engine: Optional[AsyncEngine] = None

class Buyer(Base):
    __tablename__ = "buyers"
    id = Column(Integer, primary_key=True)
    address = Column(String(128), unique=True, nullable=False)
    balance_cents = Column(Integer, default=0)
    last_tx_hash = Column(String(128), nullable=True)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

class Tx(Base):
    __tablename__ = "tx"
    id = Column(Integer, primary_key=True)
    payer = Column(String(128), nullable=False)
    tx_hash = Column(String(128), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

class Idempotency(Base):
    __tablename__ = "idempotency"
    id = Column(Integer, primary_key=True)
    key = Column(String(128), nullable=False)
    req_hash = Column(String(64), nullable=False)
    status_code = Column(Integer, nullable=False)
    headers_json = Column(Text, nullable=False)
    media_type = Column(String(64), nullable=False)
    body = Column(LargeBinary, nullable=True)
    __table_args__ = (UniqueConstraint("key","req_hash", name="uq_key_hash"),)

# ✅ nouveau: journal des jobs exécutés (base du Merkle root quotidien)
class JobLog(Base):
    __tablename__ = "joblog"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    endpoint = Column(String(64), nullable=False)
    payer = Column(String(128), nullable=False)
    cents = Column(Integer, nullable=False)
    tx_hash = Column(String(128), nullable=False)
    latency_ms = Column(Integer, nullable=False)
    gpu_id = Column(String(8), nullable=True)
    batch_size = Column(Integer, nullable=False, default=1)
    ok = Column(Integer, default=1)  # 1/0

class MerkleRoot(Base):
    __tablename__ = "merkleroot"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True)
    root = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    return _engine

async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_or_create_buyer(session: AsyncSession, address: str) -> Buyer:
    res = await session.execute(select(Buyer).where(Buyer.address==address))
    buyer = res.scalar_one_or_none()
    if buyer:
        return buyer
    await session.execute(insert(Buyer).values(address=address, balance_cents=0))
    await session.commit()
    res = await session.execute(select(Buyer).where(Buyer.address==address))
    return res.scalar_one()

async def credit_min_pay(session: AsyncSession, buyer: Buyer, tx_hash: str, amount_cents: int):
    await session.execute(
        update(Buyer).where(Buyer.id==buyer.id).values(
            balance_cents=Buyer.balance_cents + amount_cents,
            last_tx_hash=tx_hash
        )
    )
    await session.execute(insert(Tx).values(payer=buyer.address, tx_hash=tx_hash, amount_cents=amount_cents))
    await session.commit()

async def charge_cents(session: AsyncSession, buyer: Buyer, amount_cents: int) -> bool:
    res = await session.execute(select(Buyer).where(Buyer.id==buyer.id))
    b = res.scalar_one()
    if b.balance_cents < amount_cents:
        return False
    await session.execute(
        update(Buyer).where(Buyer.id==buyer.id).values(balance_cents=b.balance_cents - amount_cents)
    )
    await session.commit()
    return True

# helper pour écrire un JobLog
async def log_job(session: AsyncSession, *, endpoint: str, payer: str, cents: int, tx_hash: str, latency_ms: int, gpu_id: str, batch_size: int = 1, ok: bool = True):
    await session.execute(insert(JobLog).values(
        endpoint=endpoint,
        payer=payer,
        cents=cents,
        tx_hash=tx_hash,
        latency_ms=int(latency_ms),
        gpu_id=gpu_id,
        batch_size=batch_size,
        ok=1 if ok else 0,
    ))
    await session.commit()


async def list_jobs_for_payer(session: AsyncSession, payer: str, limit: int = 20) -> List[JobLog]:
    q = select(JobLog).where(JobLog.payer == payer).order_by(desc(JobLog.created_at)).limit(limit)
    res = await session.execute(q)
    return res.scalars().all()


def compute_merkle_root(leaves: List[str]) -> str:
    """Compute deterministic SHA256 Merkle root from list of hex strings (sorted)."""
    if not leaves:
        return ""
    # sort for determinism
    level = sorted(leaves)
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i+1] if i+1 < len(level) else a
            h = hashlib.sha256((a + b).encode()).hexdigest()
            next_level.append(h)
        level = next_level
    return level[0]
