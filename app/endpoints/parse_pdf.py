from fastapi import APIRouter, UploadFile, File, Request, Depends, HTTPException
from typing import List
import os
import time
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.payments.x402_gateway import pay_dep
from app.payments.ledger import get_engine, log_job

router = APIRouter(prefix="/parse/pdf")

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "text": {"type": "string"},
    },
    "required": ["ok", "text"],
}

async def _parse_one(file: UploadFile) -> dict:
    # Minimal stub: return dummy text
    content = await file.read()
    # In real implementation, parse PDF; here just return placeholder
    return {"ok": True, "text": f"Parsed {len(content)} bytes"}

@router.post("/")
async def parse_pdf(
    request: Request,
    file: UploadFile = File(...),
    _paid=Depends(pay_dep(settings.PRICE_PARSE_PDF_CENTS, endpoint_label="parse_pdf", output_schema=_OUTPUT_SCHEMA)),
):
    t0 = time.perf_counter()
    result = await _parse_one(file)
    dt = time.perf_counter() - t0
    # Record job in ledger
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        await log_job(
            session,
            endpoint="parse_pdf",
            payer= getattr(request.state, "payer", "0xUnknown"),
            cents= settings.PRICE_PARSE_PDF_CENTS,
            tx_hash= getattr(request.state, "tx_hash", "0xunknown"),
            latency_ms= int(dt * 1000),
            gpu_id= os.getenv("NVIDIA_VISIBLE_DEVICES", "unknown"),
            batch_size= 1,
        )
    return result
