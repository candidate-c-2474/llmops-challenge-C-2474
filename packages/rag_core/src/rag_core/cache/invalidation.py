from abc import ABC, abstractmethod
from rag_core.models import CatalogUpdate, CatalogEvent
from rag_core.cache.exact_cache import ExactCache
from rag_core.cache.semantic_cache import SemanticCache

class CatalogObserver(ABC):
    @abstractmethod
    async def on_catalog_update(self, update: CatalogUpdate) -> None: ...

class CacheInvalidator(CatalogObserver):
    def __init__(self, exact_cache: ExactCache, semantic_cache: SemanticCache):
        self._exact = exact_cache
        self._semantic = semantic_cache

    async def on_catalog_update(self, update: CatalogUpdate) -> None:
        if update.event == CatalogEvent.PRODUCT_CREATED:
            return
        await self._exact.invalidate_all()
        await self._semantic.invalidate_all()

class CatalogEventBus:
    def __init__(self):
        self._observers = []
    def subscribe(self, observer: CatalogObserver):
        self._observers.append(observer)
    async def publish(self, update: CatalogUpdate):
        for observer in self._observers:
            try:
                await observer.on_catalog_update(update)
            except Exception:
                pass
