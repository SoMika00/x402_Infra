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
    # reuse logic: minimal PDF text extraction stub (real impl would use pypdf etc.)
    content = await file.read()
    text = content.decode("latin-1", errors="ignore")[:2000]  # stub
    return {"ok": True, "text": text, "filename": file.filename}

@router.post("/")
async def parse_pdf(
    request: Request,
    file: UploadFile = File(...),
    _paid=Depends(pay_dep(settings.PRICE_PARSE_PDF_CENTS, endpoint_label="parse_pdf", output_schema=_OUTPUT_SCHEMA)),
):
    t0 = time.perf_counter()
    result = await _parse_one(file)
    dt = time.perf_counter() - t0
    try:
        gpu = os.environ.get("NVIDIA_VISIBLE_DEVICES", "unknown")
        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
            await log_job(
                session,
                endpoint="parse_pdf",
                payer=getattr(request.state, "payer", "0xUnknown"),
                cents=settings.PRICE_PARSE_PDF_CENTS,
                tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
                latency_ms=int(dt * 1000),
                gpu_id=gpu,
                batch_size=1,
            )
    except Exception:
        pass
    return result


@router.post("/batch")
async def parse_pdf_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    _paid=Depends(pay_dep(settings.PRICE_PARSE_PDF_BATCH_CENTS, endpoint_label="parse_pdf_batch")),
):
    t0 = time.perf_counter()
    results = []
    for f in files:
        res = await _parse_one(f)
        results.append(res)
    dt = time.perf_counter() - t0
    try:
        gpu = os.environ.get("NVIDIA_VISIBLE_DEVICES", "unknown")
        payer = getattr(request.state, "payer", "0xUnknown")
        tx = getattr(request.state, "tx_hash", "0xunknown")
        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
            for _ in files:  # one JobLog per file
                await log_job(
                    session,
                    endpoint="parse_pdf_batch",
                    payer=payer,
                    cents=settings.PRICE_PARSE_PDF_BATCH_CENTS,
                    tx_hash=tx,
                    latency_ms=int(dt * 1000),
                    gpu_id=gpu,
                    batch_size=len(files),
                )
    except Exception:
        pass
    return {"ok": True, "results": results}
