import json
from rag_core.tools.registry import tool
from rag_core.repository import CatalogRepository

def create_compare_products_tool(repository: CatalogRepository):
    @tool(
        name="compare_products",
        description="Compare 2 to 4 products side-by-side by their product IDs.",
        parameters={
            "type": "object",
            "properties": {
                "product_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 4,
                    "description": "List of 2 to 4 product IDs to compare"
                }
            },
            "required": ["product_ids"]
        }
    )
    async def compare_products(product_ids: list[str]) -> str:
        if len(product_ids) < 2:
            return json.dumps({"error": "At least 2 product IDs are required for comparison."})
        if len(product_ids) > 4:
            return json.dumps({"error": "Maximum 4 products allowed for side-by-side comparison."})

        products = await repository.get_products_by_ids(product_ids)
        if not products:
            return json.dumps({"error": "No matching products found for the provided IDs."})

        comparison = []
        for p in products:
            entry = {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "price": f"{p.currency} {p.price:.2f}",
                "stock": p.stock,
                "dimensions": f"{p.dimensions.width}x{p.dimensions.depth}x{p.dimensions.height} cm" if p.dimensions else "N/A"
            }
            comparison.append(entry)

        return json.dumps({"comparison": comparison, "total": len(comparison)})

    return compare_products
