from fastapi import APIRouter, Depends, Request, HTTPException, Path
from typing import List
from datetime import date as dt_date
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.config import settings
from app.payments.x402_gateway import pay_dep
from app.payments.ledger import get_engine, MerkleRoot
from app.metrics import latency_seconds
import os, time

router = APIRouter(prefix="/audit")

@router.get("/merkle/{date}")
async def audit_merkle(
    request: Request,
    date: str = Path(..., description="Date in YYYY-MM-DD format"),
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="audit_merkle"))
):
    # Validate date format
    try:
        query_date = dt_date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    t0 = time.perf_counter()
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        stmt = MerkleRoot.select().where(MerkleRoot.c.date == query_date)
        result = await session.execute(stmt)
        rows = result.fetchall()
        if not rows:
            raise HTTPException(status_code=404, "Merkle root not found")
        # Return list of merkle roots for all payers on that date
        data = [{"payer": r["payer"], "merkle_root": r["merkle_root"], "job_count": r["job_count"]} for r in rows]
    dt = time.time() - t0
    latency_seconds.labels("audit_merkle").observe(dt)
    return {"date": date, "roots": data}
