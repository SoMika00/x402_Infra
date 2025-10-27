# app/middleware/ratelimit.py
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit:int=120, window:int=60):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.buckets = {}  # key -> (count, reset_ts)

    async def dispatch(self, request, call_next):
        key = request.client.host  # simple; tu pourras passer sur Redis par payer
        now = time.time()
        count, reset = self.buckets.get(key, (0, now + self.window))
        if now > reset:
            count, reset = 0, now + self.window
        count += 1
        self.buckets[key] = (count, reset)
        if count > self.limit:
            retry = int(reset - now)
            return JSONResponse(
                {"detail": "rate_limited", "retry_after": retry},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
        return await call_next(request)
