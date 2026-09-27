import json
from rag_core.tools.registry import tool

def create_check_fit_tool(repository):
    @tool(
        name="check_fit",
        description="Check if a product physically fits in a given space.",
        parameters={"type": "object", "properties": {"product_id": {"type": "string"}, "space_width": {"type": "number"}, "space_height": {"type": "number"}, "space_depth": {"type": "number"}}, "required": ["product_id", "space_width", "space_height", "space_depth"]}
    )
    async def check_fit(product_id: str, space_width: float, space_height: float, space_depth: float) -> str:
        product = await repository.get_product(product_id)
        if not product or not product.dimensions: return json.dumps({"error": "Product or dimensions not found."})
        
        fits = product.dimensions.fits_in(space_width, space_height, space_depth)
        return json.dumps({
            "product_id": product_id, "product_name": product.name, "fits": fits,
            "product_dims": {"w": product.dimensions.width, "h": product.dimensions.height, "d": product.dimensions.depth}
        })
    return check_fit
