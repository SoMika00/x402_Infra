from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.payments.x402_gateway import pay_dep
from app.payments.ledger import get_engine, list_jobs_for_payer

router = APIRouter(prefix="/buyer")

@router.get("/balance")
async def buyer_balance(request: Request, _paid=Depends(pay_dep(0, endpoint_label="buyer_balance"))):
    payer = getattr(request.state, "payer", "0xUnknown")
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        from app.payments.ledger import get_or_create_buyer
        buyer = await get_or_create_buyer(session, payer)
        return {
            "address": buyer.address,
            "balance_cents": buyer.balance_cents,
            "last_tx": buyer.last_tx_hash or "",
        }

@router.get("/jobs")
async def buyer_jobs(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    _paid=Depends(pay_dep(0, endpoint_label="buyer_jobs")),
):
    payer = getattr(request.state, "payer", "0xUnknown")
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        jobs = await list_jobs_for_payer(session, payer, limit=limit)
    return [
        {
            "endpoint": j.endpoint,
            "cents": j.cents,
            "tx_hash": j.tx_hash,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "latency_ms": j.latency_ms,
        }
        for j in jobs
    ]
