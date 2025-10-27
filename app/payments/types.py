# app/payments/types.py
from typing import Optional
from dataclasses import dataclass

@dataclass
class PaymentResult:
    ok: bool
    payer: Optional[str] = None
    tx_hash: Optional[str] = None
    reason: Optional[str] = None
