import hashlib
import json
import redis.asyncio as redis
from rag_core.config import RedisConfig
from rag_core.models import RetrievedChunk

class ExactCache:
    KEY_PREFIX = "rag:exact:"
    def __init__(self, config: RedisConfig | None = None):
        self._config = config or RedisConfig()
        self._client = None

    async def initialize(self, client: redis.Redis | None = None):
        self._client = client or redis.from_url(self._config.url, decode_responses=True)

    def _cache_key(self, query: str) -> str:
        query_hash = hashlib.sha256(query.strip().lower().encode()).hexdigest()
        return f"{self.KEY_PREFIX}{query_hash}"

    async def get(self, query: str) -> list[RetrievedChunk] | None:
        data = await self._client.get(self._cache_key(query))
        return [RetrievedChunk(**c) for c in json.loads(data)] if data else None

    async def set(self, query: str, chunks: list[RetrievedChunk], ttl: int | None = None):
        data = json.dumps([c.model_dump() for c in chunks])
        await self._client.set(self._cache_key(query), data, ex=ttl or self._config.exact_cache_ttl)

    async def invalidate_all(self) -> int:
        keys = [key async for key in self._client.scan_iter(match=f"{self.KEY_PREFIX}*")]
        if keys:
            await self._client.delete(*keys)
        return len(keys)
