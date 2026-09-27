import json
from rag_core.tools.registry import tool
from rag_core.repository import CatalogRepository

def create_get_product_tool(repository: CatalogRepository):
    @tool(
        name="get_product",
        description="Retrieve full details for a specific product by its ID.",
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The unique product ID (e.g., DESK-001)"}
            },
            "required": ["product_id"]
        }
    )
    async def get_product(product_id: str) -> str:
        product = await repository.get_product(product_id)
        if product is None:
            return json.dumps({"error": f"Product '{product_id}' not found."})
        
        data = product.model_dump(exclude={"embedding"})
        if data.get("updated_at"):
            data["updated_at"] = str(data["updated_at"])
        return json.dumps(data)

    return get_product
