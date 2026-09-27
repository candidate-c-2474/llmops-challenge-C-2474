from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rag_core.models import CatalogUpdate, CatalogEvent

router = APIRouter(prefix="/admin/catalog", tags=["Admin Catalog"])

class CatalogUpdateRequest(BaseModel):
    product_ids: list[str]
    event: CatalogEvent = CatalogEvent.CATALOG_BULK_UPDATE

@router.post("/apply-updates")
async def apply_catalog_updates(payload: CatalogUpdateRequest):
    update_event = CatalogUpdate(
        event=payload.event,
        product_ids=payload.product_ids
    )
    return {
        "status": "success",
        "event": payload.event.value,
        "affected_products": len(payload.product_ids)
    }
