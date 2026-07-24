from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.payments.ledger import get_engine, MerkleRoot
from app.payments.x402_gateway import pay_dep

router = APIRouter(prefix="/audit")


@router.get("/merkle/{date_str}")
async def get_merkle(
    date_str: str,
    _paid=Depends(pay_dep(settings.PRICE_EMBED_CENTS, endpoint_label="audit_merkle")),
):
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid date")
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        res = await session.execute(select(MerkleRoot).where(MerkleRoot.date == d))
        row = res.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        return {"date": str(d), "root": row.root}
