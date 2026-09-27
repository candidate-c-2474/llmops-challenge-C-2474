from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class Dimensions(BaseModel):
    width: float
    height: float
    depth: float
    weight_kg: float | None = None

    @property
    def volume_cm3(self) -> float:
        return self.width * self.height * self.depth

    def fits_in(self, space_width: float, space_height: float, space_depth: float) -> bool:
        product_dims = sorted([self.width, self.depth])
        space_dims = sorted([space_width, space_depth])
        return (product_dims[0] <= space_dims[0] and product_dims[1] <= space_dims[1] and self.height <= space_height)

class Product(BaseModel):
    id: str
    name: str
    category: str
    price: float
    currency: str = "USD"
    stock: int = 0
    dimensions: Dimensions | None = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = Field(default=None, exclude=True)
    updated_at: datetime | None = None

class RetrievedChunk(BaseModel):
    product_id: str
    content: str
    score: float = 0.0
    source: str = ""
    metadata: dict = Field(default_factory=dict)

class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    arguments: dict = Field(default_factory=dict)

class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    content: str
    error: str | None = None

class ChatMessage(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

class CatalogEvent(str, Enum):
    PRODUCT_CREATED = "product.created"
    PRODUCT_UPDATED = "product.updated"
    PRODUCT_DELETED = "product.deleted"
    CATALOG_BULK_UPDATE = "catalog.bulk_update"

class CatalogUpdate(BaseModel):
    event: CatalogEvent
    product_ids: list[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
