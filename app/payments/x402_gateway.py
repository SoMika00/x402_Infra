import uuid, base64, json
from fastapi import Request, HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.payments.ledger import get_engine, get_or_create_buyer, credit_min_pay, charge_cents
from app.payments.x402_requirements import build_payment_requirements
from app.payments.types import PaymentResult
from app.payments.facilitator import (
    verify_with_facilitator,
    verify_x402_with_facilitator,
    settle_x402_with_facilitator,
)

try:
    from app.metrics import revenue_cents_total
except Exception:
    revenue_cents_total = None

def pay_dep(price_cents: int, endpoint_label: str = "generic", *, output_schema: dict | None = None):
    """
    - X-PAYMENT: x402 réel (verify -> ledger -> settle [sync/async])
    - X-402-Proof: stub dev 'pay:<addr>'
    - Sinon: 402 avec PaymentRequirements (incluant outputSchema si fourni)
    """
    async def _dep(request: Request):
        engine = get_engine()
        xpayment_b64 = request.headers.get("X-PAYMENT")
        stub = request.headers.get("X-402-Proof")

        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            # --- x402 réel ---
            if xpayment_b64:
                try:
                    payload = json.loads(base64.b64decode(xpayment_b64).decode())
                except Exception:
                    raise HTTPException(status_code=400, detail="invalid X-PAYMENT header (base64/json)")

                reqs = build_payment_requirements(
                    request, price_cents, description=f"x402:{endpoint_label}", output_schema=output_schema
                )
                result: PaymentResult = await verify_x402_with_facilitator(payload, reqs)
                if not result.ok:
                    raise HTTPException(
                        status_code=402,
                        detail={"x402Version": 1, "accepts": [reqs], "error": result.reason or "verify_failed"},
                    )

                buyer = await get_or_create_buyer(session, result.payer or "0xUnknown")
                if buyer.balance_cents == 0:
                    await credit_min_pay(session, buyer, "0xmint", settings.X402_MIN_PAY_CENTS)
                    buyer = await get_or_create_buyer(session, result.payer or "0xUnknown")

                ok = await charge_cents(session, buyer, price_cents)
                if not ok:
                    raise HTTPException(
                        status_code=402,
                        detail={"x402Version": 1, "accepts": [reqs], "error": "insufficient_balance"},
                    )

                if revenue_cents_total is not None:
                    try:
                        revenue_cents_total.labels(endpoint_label, settings.X402_ASSET).inc(price_cents)
                    except Exception:
                        pass

                # settle
                if settings.X402_SYNC_SETTLE:
                    settle = await settle_x402_with_facilitator(payload, reqs)
                    request.state.payment_response = {
                        "success": bool(settle.get("success")),
                        "txHash": settle.get("txHash", ""),
                        "networkId": settle.get("networkId") or settings.X402_CHAIN,
                        "payer": result.payer or "",
                    }
                    request.state.tx_hash = settle.get("txHash") or ""
                else:
                    try:
                        import asyncio
                        asyncio.create_task(settle_x402_with_facilitator(payload, reqs))
                    except Exception:
                        pass

                request.state.payer = result.payer
                return True

            # --- stub dev ---
            if stub:
                result: PaymentResult = await verify_with_facilitator(stub)
                if not result.ok:
                    raise HTTPException(
                        status_code=402,
                        detail={
                            "x402Version": 1,
                            "accepts": [build_payment_requirements(request, price_cents, f"x402:{endpoint_label}", output_schema=output_schema)],
                            "error": "verify_failed",
                        },
                    )
                buyer = await get_or_create_buyer(session, result.payer)
                if buyer.balance_cents == 0:
                    await credit_min_pay(session, buyer, "0xmint", settings.X402_MIN_PAY_CENTS)
                    buyer = await get_or_create_buyer(session, result.payer)
                ok = await charge_cents(session, buyer, price_cents)
                if not ok:
                    raise HTTPException(
                        status_code=402,
                        detail={
                            "x402Version": 1,
                            "accepts": [build_payment_requirements(request, price_cents, f"x402:{endpoint_label}", output_schema=output_schema)],
                            "error": "insufficient_balance",
                        },
                    )

                fake_tx = f"0xstub{uuid.uuid4().hex}"
                request.state.payment_response = {
                    "success": True,
                    "txHash": fake_tx,
                    "networkId": settings.X402_CHAIN,
                    "payer": result.payer,
                }
                request.state.payer = result.payer
                request.state.tx_hash = fake_tx
                return True

            # --- 402 canonical ---
            reqs = build_payment_requirements(request, price_cents, f"x402:{endpoint_label}", output_schema=output_schema)
            raise HTTPException(
                status_code=402,
                detail={"x402Version": 1, "accepts": [reqs], "error": "payment_required"},
            )

    return _dep
