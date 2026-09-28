import structlog
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from rag_core.models import CatalogUpdate, CatalogEvent

router = APIRouter(prefix="/admin/catalog", tags=["Admin Catalog"])
logger = structlog.get_logger(__name__)

class CatalogUpdateRequest(BaseModel):
    product_ids: list[str]
    event: CatalogEvent = CatalogEvent.CATALOG_BULK_UPDATE

@router.post("/apply-updates")
async def apply_catalog_updates(request: Request, payload: CatalogUpdateRequest):
    bus = request.app.state.event_bus
    repo = request.app.state.repository
    
    # Verify products exist
    products = await repo.get_products_by_ids(payload.product_ids)
    if not products:
        logger.warn("admin.catalog.update_ignored", reason="no_matching_products")
        return {"status": "ignored", "reason": "no_matching_products_found"}

    update_event = CatalogUpdate(
        event=payload.event,
        product_ids=[p.id for p in products]
    )
    
    # Publish to event bus for cache invalidation
    await bus.publish(update_event)
    
    return {
        "status": "success",
        "event": payload.event.value,
        "affected_products": len(update_event.product_ids)
    }