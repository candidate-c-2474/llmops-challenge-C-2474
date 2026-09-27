import pytest
from rag_core.models import CatalogUpdate, CatalogEvent, RetrievedChunk
from rag_core.cache.exact_cache import ExactCache
from rag_core.cache.invalidation import CacheInvalidator, CatalogEventBus

class FakeRedis:
    def __init__(self):
        self.store = {}
    async def get(self, k):
        return self.store.get(k)
    async def set(self, k, v, ex=None):
        self.store[k] = v
    async def delete(self, *ks):
        for k in ks:
            self.store.pop(k, None)
    async def scan_iter(self, match="*", count=100):
        for k in list(self.store.keys()):
            yield k

@pytest.mark.asyncio
async def test_price_update_invalidates_cache():
    redis_client = FakeRedis()
    exact_cache = ExactCache()
    await exact_cache.initialize(client=redis_client)

    class DummySemantic:
        async def invalidate_all(self):
            return 0

    bus = CatalogEventBus()
    bus.subscribe(CacheInvalidator(exact_cache, DummySemantic()))

    chunk = [RetrievedChunk(product_id="DESK-001", content="Desk price $499", score=0.9, source="hybrid")]
    await exact_cache.set("modern standing desk", chunk)
    
    assert await exact_cache.get("modern standing desk") is not None

    await bus.publish(CatalogUpdate(event=CatalogEvent.PRODUCT_UPDATED, product_ids=["DESK-001"]))
    
    assert await exact_cache.get("modern standing desk") is None
