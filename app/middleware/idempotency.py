import hashlib
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.requests import Request
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, insert
from app.payments.ledger import get_engine, Idempotency

def _hash_request(scope, body: bytes) -> str:
    m = hashlib.sha256()
    m.update(scope["method"].encode())
    m.update(scope["path"].encode())
    if scope.get("query_string"):
        m.update(scope["query_string"])
    m.update(body or b"")
    return m.hexdigest()

async def _restore_body(request: Request, body: bytes):
    """
    Ré-injecte le body dans le canal receive pour que FastAPI/Starlette
    puissent le relire (indispensable pour multipart/form-data).
    """
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    request._receive = receive  # Starlette internals: OK ici

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        key = request.headers.get("Idempotency-Key")
        if not key or request.method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        # 1) Lire le body une fois
        body = await request.body()
        digest = _hash_request(request.scope, body)

        # 2) Ré-injecter le body pour les handlers (JSON & multipart)
        await _restore_body(request, body)

        # 3) Lookup idempotency
        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
            res = await session.execute(
                select(Idempotency).where(Idempotency.key == key, Idempotency.req_hash == digest)
            )
            row = res.scalar_one_or_none()
            if row:
                headers = json.loads(row.headers_json)
                content = row.body or b""
                return Response(
                    content=content,
                    status_code=row.status_code,
                    headers=headers,
                    media_type=row.media_type,
                )

        # 4) Appel réel
        response = await call_next(request)

        # 5) Si succès, bufferiser la réponse et persister
        if 200 <= response.status_code < 300:
            raw_body = b""
            async for chunk in response.body_iterator:
                raw_body += chunk

            new_resp = Response(
                content=raw_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

            async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
                await session.execute(
                    insert(Idempotency).values(
                        key=key,
                        req_hash=digest,
                        status_code=new_resp.status_code,
                        headers_json=json.dumps(dict(new_resp.headers)),
                        media_type=new_resp.media_type or "application/json",
                        body=raw_body,
                    )
                )
                await session.commit()

            return new_resp

        return response
