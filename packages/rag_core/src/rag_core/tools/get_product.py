import json
from rag_core.tools.registry import ToolRegistry
from rag_core.repository import CatalogRepository


def create_get_product_tool(repository: CatalogRepository, registry: ToolRegistry):
    async def get_product(product_id: str) -> str:
        product = await repository.get_product(product_id)
        if not product:
            return json.dumps({"error": f"Product {product_id} not found."})

        return json.dumps({
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price": product.price,
            "currency": product.currency,
            "stock": product.stock,
            "description": product.description,
            "tags": product.tags,
            "dimensions": (
                {
                    "width": product.dimensions.width,
                    "height": product.dimensions.height,
                    "depth": product.dimensions.depth,
                    "weight_kg": product.dimensions.weight_kg,
                }
                if product.dimensions
                else None
            ),
        })

    registry.register(
        name="get_product",
        desc="Fetch full details for a single product by its ID.",
        params={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID, e.g. 'DESK-001'"},
            },
            "required": ["product_id"],
        },
        func=get_product,
    )
    return get_product