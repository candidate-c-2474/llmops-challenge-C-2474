import json
import hashlib
import time
import numpy as np
import redis.asyncio as redis
from rag_core.config import RedisConfig
from rag_core.models import RetrievedChunk

class SemanticCache:
    ENTRIES_PREFIX = "rag:sem:entries:"
    INDEX_KEY = "rag:sem:index"

    def __init__(self, config: RedisConfig | None = None):
        self._config = config or RedisConfig()
        self._client = None
        self._threshold = self._config.semantic_similarity_threshold

    async def initialize(self, client: redis.Redis | None = None):
        self._client = client or redis.from_url(self._config.url, decode_responses=True)

    async def get(self, query: str, query_embedding: list[float]) -> tuple[list[RetrievedChunk] | None, float]:
        query_vec = np.array(query_embedding, dtype=np.float32)
        entry_ids = await self._client.smembers(self.INDEX_KEY)
        best_sim, best_results = 0.0, None

        for entry_id in entry_ids:
            data = await self._client.hgetall(f"{self.ENTRIES_PREFIX}{entry_id}")
            if not data:
                continue
            cached_emb = np.array(json.loads(data["embedding"]), dtype=np.float32)
            sim = float(np.dot(query_vec, cached_emb) / (np.linalg.norm(query_vec) * np.linalg.norm(cached_emb) + 1e-10))
            if sim > best_sim:
                best_sim = sim
                if sim >= self._threshold:
                    best_results = [RetrievedChunk(**c) for c in json.loads(data["results"])]
                    
        return best_results, best_sim

    async def set(self, query: str, query_embedding: list[float], chunks: list[RetrievedChunk]):
        entry_id = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]
        key = f"{self.ENTRIES_PREFIX}{entry_id}"
        data = {
            "embedding": json.dumps(query_embedding),
            "results": json.dumps([c.model_dump() for c in chunks])
        }
        pipe = self._client.pipeline()
        pipe.hset(key, mapping=data)
        pipe.expire(key, self._config.semantic_cache_ttl)
        pipe.sadd(self.INDEX_KEY, entry_id)
        await pipe.execute()

    async def invalidate_all(self) -> int:
        entry_ids = await self._client.smembers(self.INDEX_KEY)
        if not entry_ids:
            return 0
        pipe = self._client.pipeline()
        for eid in entry_ids:
            pipe.delete(f"{self.ENTRIES_PREFIX}{eid}")
        pipe.delete(self.INDEX_KEY)
        await pipe.execute()
        return len(entry_ids)
