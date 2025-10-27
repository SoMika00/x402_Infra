# app/payments/x402_requirements.py
from fastapi import Request
from typing import Optional, Dict, Any
from app.core.config import settings

# USDC natif sur Base (6 décimales)
USDC_ON_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

def cents_to_atomic_usdc(cents: int) -> int:
    # 1 USDC = 1_000_000 unités; 1 cent = 0.01 USDC = 10_000 unités
    return int(cents) * 10_000

def resolve_usdc_contract() -> str:
    if settings.X402_ASSET_CONTRACT:
        return settings.X402_ASSET_CONTRACT
    if settings.X402_CHAIN.lower() == "base":
        return USDC_ON_BASE
    # fallback (mets ton contrat si tu changes de chaîne)
    return USDC_ON_BASE

def build_payment_requirements(
    request: Request,
    price_cents: int,
    description: str,
    mime_type: str = "application/json",
    output_schema: Optional[Dict[str, Any]] = None,
) -> dict:
    out = {
        "scheme": "exact",                         # cf. spec V1
        "network": settings.X402_CHAIN,            # ex: "base"
        "maxAmountRequired": str(cents_to_atomic_usdc(price_cents)),
        "resource": str(request.url),
        "description": description,
        "mimeType": mime_type,
        "payTo": settings.X402_MERCHANT,          # adresse marchant (à toi)
        "maxTimeoutSeconds": 60,
        "asset": resolve_usdc_contract(),         # contrat USDC (EIP-3009)
        "extra": {"name": "USDC", "version": "EIP-3009"},
    }
    if output_schema is not None:
        out["outputSchema"] = output_schema
    return out
