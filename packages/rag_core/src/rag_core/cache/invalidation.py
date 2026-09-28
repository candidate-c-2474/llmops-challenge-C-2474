from abc import ABC, abstractmethod
import structlog
from rag_core.models import CatalogUpdate, CatalogEvent
from rag_core.cache.exact_cache import ExactCache
from rag_core.cache.semantic_cache import SemanticCache

logger = structlog.get_logger(__name__)

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
        
        # Use 'event_type' instead of 'event' to avoid structlog argument collision
        logger.info("cache.invalidation.start", event_type=update.event.value, products=update.product_ids)
        invalidated_count = 0
        for pid in update.product_ids:
            count_exact = await self._exact.invalidate_by_product_id(pid)
            count_semantic = await self._semantic.invalidate_by_product_id(pid)
            invalidated_count += (count_exact + count_semantic)
        logger.info("cache.invalidation.completed", total_purged=invalidated_count)

class CatalogEventBus:
    def __init__(self):
        self._observers = []
    def subscribe(self, observer: CatalogObserver):
        self._observers.append(observer)
    async def publish(self, update: CatalogUpdate):
        for observer in self._observers:
            try:
                await observer.on_catalog_update(update)
            except Exception as e:
                logger.error("event_bus.publish.error", observer=observer.__class__.__name__, error=str(e))
