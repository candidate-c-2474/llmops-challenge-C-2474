import hashlib
import json
import redis.asyncio as redis
from rag_core.config import RedisConfig
from rag_core.models import RetrievedChunk

class ExactCache:
    KEY_PREFIX = "rag:exact:"
    PRODUCT_MAP_PREFIX = "rag:exact:product:"

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
        key = self._cache_key(query)
        data = json.dumps([c.model_dump() for c in chunks])
        
        pipe = self._client.pipeline()
        pipe.set(key, data, ex=ttl or self._config.exact_cache_ttl)
        
        # Link the query to individual product IDs
        for chunk in chunks:
            product_set_key = f"{self.PRODUCT_MAP_PREFIX}{chunk.product_id}"
            pipe.sadd(product_set_key, key)
            pipe.expire(product_set_key, ttl or self._config.exact_cache_ttl)
        await pipe.execute()

    async def invalidate_by_product_id(self, product_id: str) -> int:
        product_set_key = f"{self.PRODUCT_MAP_PREFIX}{product_id}"
        keys = await self._client.smembers(product_set_key)
        if not keys:
            return 0
        
        pipe = self._client.pipeline()
        pipe.delete(*keys)
        pipe.delete(product_set_key)
        await pipe.execute()
        return len(keys)

    async def invalidate_all(self) -> int:
        keys = [key async for key in self._client.scan_iter(match=f"{self.KEY_PREFIX}*")]
        maps = [m async for m in self._client.scan_iter(match=f"{self.PRODUCT_MAP_PREFIX}*")]
        all_keys = keys + maps
        if all_keys:
            await self._client.delete(*all_keys)
        return len(keys)