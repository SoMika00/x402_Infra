import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.ratelimit import RateLimitMiddleware
from app.middleware.payment_response import PaymentResponseMiddleware
from app.core.config import settings
from app.core.logging import setup_logging

try:
    from app.metrics import start_gpu_polling
except Exception:
    start_gpu_polling = None

app = FastAPI(title="x402 API", version="0.1.5")

# CORS + expose des headers de paiement
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-PAYMENT-RESPONSE", "X-PAYER", "X-TX-HASH"],
)
app.add_middleware(RateLimitMiddleware, limit=int(os.getenv("RATE_LIMIT_PER_MIN", "300")), window=60)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(PaymentResponseMiddleware)

from app.endpoints.health import router as health_router
from app.endpoints.embed import router as embed_router
from app.endpoints.embed_batch import router as embed_batch_router
from app.endpoints.embed_fast import router as embed_fast_router
from app.endpoints.parse_pdf import router as parse_router
from app.endpoints.debug_ai import router as debug_ai_router
from app.endpoints.audit import router as audit_router

Instrumentator().instrument(app).expose(app)

app.include_router(health_router, tags=["health"])
app.include_router(embed_router,  tags=["embed"])
app.include_router(embed_batch_router, tags=["embed"])
app.include_router(embed_fast_router, tags=["embed"])
app.include_router(parse_router,  tags=["parse"])
app.include_router(debug_ai_router, tags=["debug"])
app.include_router(audit_router, tags=["audit"])

from app.payments.ledger import init_db
from app.ai.models import get_embedder

@app.on_event("startup")
async def startup_event():
    setup_logging(settings.LOG_LEVEL)
    attempts = int(os.getenv("DB_INIT_RETRIES", "30"))
    delay = float(os.getenv("DB_INIT_DELAY", "1.0"))
    for i in range(1, attempts + 1):
        try:
            await init_db()
            break
        except Exception:
            if i == attempts:
                raise
            await asyncio.sleep(delay)

    if os.getenv("WARMUP", "0") == "1":
        get_embedder()

    if start_gpu_polling:
        try:
            start_gpu_polling(period=5.0)
        except Exception:
            pass
