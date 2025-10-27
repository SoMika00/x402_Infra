from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.core.config import settings
from app.payments.x402_gateway import pay_dep
from app.ai.mbatcher import get_text_embed_batcher
from app.metrics import latency_seconds
import os, time

router = APIRouter(prefix="/embed")

class EmbedIn(BaseModel):
    text: str

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "model": {"type": "string"},
        "dim": {"type": "integer"},
        "embedding": {"type": "array", "items": {"type": "number"}},
    },
    "required": ["ok", "embedding"],
}

@router.post("/fast")
async def embed_fast(body: EmbedIn, request: Request,
                     _paid=Depends(pay_dep(settings.PRICE_EMBED_CENTS, endpoint_label="embed_fast", output_schema=_OUTPUT_SCHEMA))):
    t0 = time.perf_counter()
    batcher = await get_text_embed_batcher()
    vec = await batcher.embed_one(body.text)
    dt = time.perf_counter() - t0
    latency_seconds.labels("embed_fast").observe(dt)

    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from app.payments.ledger import get_engine, log_job
        gpu = os.environ.get("NVIDIA_VISIBLE_DEVICES", "unknown")
        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
            await log_job(session,
                endpoint="embed_fast",
                payer=getattr(request.state, "payer", "0xUnknown"),
                cents=settings.PRICE_EMBED_CENTS,
                tx_hash=getattr(request.state, "tx_hash", "0xunknown"),
                latency_ms=int(dt*1000),
                gpu_id=gpu,
                batch_size=1
            )
    except Exception:
        pass

    return {
        "ok": True,
        "model": os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        "dim": len(vec),
        "embedding": vec
    }
