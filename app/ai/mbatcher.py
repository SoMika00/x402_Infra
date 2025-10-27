import asyncio
from typing import List, Tuple

from app.core.config import settings
from app.ai.models import embed_any

class TextEmbedBatcher:
    def __init__(self, max_batch: int = None, max_wait_ms: int = None):
        self.max_batch = max_batch or settings.EMBED_BATCH
        self.max_wait = (max_wait_ms or settings.EMBED_MAX_WAIT_MS) / 1000.0
        self._queue: List[Tuple[asyncio.Future, str]] = []
        self._lock = asyncio.Lock()
        self._task = None
        self._closed = False

    async def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def close(self):
        self._closed = True
        if self._task:
            await self._task

    async def embed_one(self, text: str) -> list:
        fut = asyncio.get_event_loop().create_future()
        async with self._lock:
            self._queue.append((fut, text))
        return await fut

    async def _loop(self):
        while not self._closed:
            await asyncio.sleep(self.max_wait)
            async with self._lock:
                if not self._queue:
                    continue
                batch = self._queue[: self.max_batch]
                self._queue = self._queue[self.max_batch:]
            futs, texts = zip(*batch)
            try:
                vecs = embed_any(list(texts))
                rows = [v.tolist() for v in vecs]
                for fut, vec in zip(futs, rows):
                    if not fut.cancelled():
                        fut.set_result(vec)
            except Exception as e:
                for fut in futs:
                    if not fut.cancelled():
                        fut.set_exception(e)

_batcher: TextEmbedBatcher = None

async def get_text_embed_batcher() -> TextEmbedBatcher:
    global _batcher
    if _batcher is None:
        _batcher = TextEmbedBatcher()
    await _batcher.start()
    return _batcher
