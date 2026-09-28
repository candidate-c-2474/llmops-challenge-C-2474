import pytest
from rag_core.models import CatalogUpdate, CatalogEvent, RetrievedChunk
from rag_core.cache.exact_cache import ExactCache
from rag_core.cache.invalidation import CacheInvalidator, CatalogEventBus

class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.cmds = []

    def set(self, k, v, ex=None):
        self.cmds.append(("set", k, v, ex))
        return self

    def sadd(self, s, v):
        self.cmds.append(("sadd", s, v))
        return self

    def expire(self, k, ttl):
        self.cmds.append(("expire", k, ttl))
        return self

    def delete(self, *ks):
        self.cmds.append(("delete", ks))
        return self

    async def execute(self):
        for cmd in self.cmds:
            action = cmd[0]
            if action == "set":
                await self.client.set(cmd[1], cmd[2], cmd[3])
            elif action == "sadd":
                await self.client.sadd(cmd[1], cmd[2])
            elif action == "delete":
                await self.client.delete(*cmd[1])
        self.cmds = []

class FakeRedis:
    def __init__(self):
        self.store = {}
        self.sets = {}

    async def get(self, k):
        return self.store.get(k)

    async def set(self, k, v, ex=None):
        self.store[k] = v

    async def delete(self, *ks):
        for k in ks:
            self.store.pop(k, None)
            self.sets.pop(k, None)

    async def sadd(self, key, val):
        if key not in self.sets:
            self.sets[key] = set()
        self.sets[key].add(val)

    async def smembers(self, key):
        return list(self.sets.get(key, set()))

    async def scan_iter(self, match="*", count=100):
        for k in list(self.store.keys()):
            yield k

    def pipeline(self):
        return FakePipeline(self)

@pytest.mark.asyncio
async def test_price_update_invalidates_cache():
    redis_client = FakeRedis()
    exact_cache = ExactCache()
    await exact_cache.initialize(client=redis_client)

    class DummySemantic:
        async def invalidate_by_product_id(self, product_id):
            return 0
        async def invalidate_all(self):
            return 0

    bus = CatalogEventBus()
    bus.subscribe(CacheInvalidator(exact_cache, DummySemantic()))

    chunk = [RetrievedChunk(product_id="DESK-001", content="Desk price $499", score=0.9, source="hybrid")]
    await exact_cache.set("modern standing desk", chunk)
    
    assert await exact_cache.get("modern standing desk") is not None

    await bus.publish(CatalogUpdate(event=CatalogEvent.PRODUCT_UPDATED, product_ids=["DESK-001"]))
    
    assert await exact_cache.get("modern standing desk") is None
