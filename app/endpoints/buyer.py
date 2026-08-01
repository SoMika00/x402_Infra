from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.payments.x402_gateway import pay_dep
from app.payments.ledger import get_engine, get_or_create_buyer

router = APIRouter(prefix="/buyer")

@router.get("/balance")
async def get_balance(
    request: Request,
    _paid=Depends(pay_dep(settings.PRICE_BALANCE_CENTS, endpoint_label="balance")),
):
    payer = getattr(request.state, "payer", None) or "0xUnknown"
    engine = get_engine()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        buyer = await get_or_create_buyer(session, payer)
        return {
            "address": buyer.address,
            "balance_cents": buyer.balance_cents,
            "last_tx": buyer.last_tx_hash,
        }
