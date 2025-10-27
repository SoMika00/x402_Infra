# app/middleware/payment_response.py
import base64
import json
from starlette.middleware.base import BaseHTTPMiddleware

class PaymentResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Si le handler a stocké une réponse de règlement, on la propage
        pr = getattr(request.state, "payment_response", None)
        if pr:
            try:
                encoded = base64.b64encode(json.dumps(pr).encode("utf-8")).decode("utf-8")
                response.headers["X-PAYMENT-RESPONSE"] = encoded
            except Exception:
                pass

        # Infos pratiques (non standard mais utiles en debug/observabilité)
        payer = getattr(request.state, "payer", None)
        if payer:
            response.headers["X-PAYER"] = str(payer)
        tx = getattr(request.state, "tx_hash", None)
        if tx:
            response.headers["X-TX-HASH"] = str(tx)

        return response
