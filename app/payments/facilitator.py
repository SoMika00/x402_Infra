# app/payments/facilitator.py
import httpx
from app.core.config import settings
from app.payments.types import PaymentResult

def _verify_url() -> str:
    u = settings.X402_FACILITATOR_URL.strip()
    return u if u.endswith("/verify") else (u.rstrip("/") + "/verify")

def _settle_url() -> str:
    u = settings.X402_FACILITATOR_URL.strip()
    return u.replace("/verify", "/settle") if u.endswith("/verify") else (u.rstrip("/") + "/settle")

async def verify_with_facilitator(proof: str) -> PaymentResult:
    """
    Compat STUB: { "proof": "pay:<addr>" } supporté par ton facilitator.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(_verify_url(), json={"proof": proof})
            r.raise_for_status()
            data = r.json() if r.content else {}
            ok = bool(data.get("ok") or data.get("valid") or data.get("isValid"))
            if not ok:
                return PaymentResult(False, reason=data.get("invalidReason") or "invalid_proof")
            payer = data.get("payer") or data.get("address") or data.get("from") or "0xUnknown"
            # NB: /verify CDP ne retourne pas de txHash
            return PaymentResult(True, payer=payer, tx_hash=None)
    except Exception:
        return PaymentResult(False, reason="verify_failed")

async def verify_x402_with_facilitator(payment_payload: dict, payment_requirements: dict) -> PaymentResult:
    """
    x402 réel : POST { x402Version, paymentPayload, paymentRequirements } -> /verify
    """
    body = {
        "x402Version": int(payment_payload.get("x402Version", 1)),
        "paymentPayload": payment_payload,
        "paymentRequirements": payment_requirements,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(_verify_url(), json=body)
            r.raise_for_status()
            data = r.json() if r.content else {}
            ok = bool(data.get("isValid") or data.get("ok") or data.get("valid"))
            if not ok:
                return PaymentResult(False, reason=data.get("invalidReason", "verify_failed"))
            payer = data.get("payer") or data.get("address") or "0xUnknown"
            return PaymentResult(True, payer=payer, tx_hash=None)
    except Exception:
        return PaymentResult(False, reason="verify_failed")

async def settle_x402_with_facilitator(payment_payload: dict, payment_requirements: dict) -> dict:
    """
    x402 réel : POST { x402Version, paymentPayload, paymentRequirements } -> /settle
    Retourne un dict {success, txHash, networkId, payer} (valeurs par défaut si absentes).
    """
    body = {
        "x402Version": int(payment_payload.get("x402Version", 1)),
        "paymentPayload": payment_payload,
        "paymentRequirements": payment_requirements,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(_settle_url(), json=body)
            ok = (200 <= r.status_code < 300)
            data = r.json() if (ok and r.content) else {}
            return {
                "success": bool(data.get("success") or data.get("ok") or ok),
                "txHash": data.get("txHash") or data.get("tx_hash") or "",
                "networkId": data.get("networkId") or payment_requirements.get("network"),
                "payer": data.get("payer") or "",
                "raw": data,
            }
    except Exception:
        return {"success": False, "txHash": "", "networkId": payment_requirements.get("network"), "payer": "", "raw": {}}
