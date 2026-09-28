import json
from rag_core.tools.registry import ToolRegistry
from rag_core.repository import CatalogRepository


def create_check_fit_tool(repository: CatalogRepository, registry: ToolRegistry):
    async def check_fit(
        product_id: str,
        space_width: float,
        space_height: float,
        space_depth: float,
    ) -> str:
        product = await repository.get_product(product_id)
        if not product:
            return json.dumps({"error": f"Product {product_id} not found."})
        if not product.dimensions:
            return json.dumps({"error": f"Product {product_id} has no dimensions on file."})

        fits = product.dimensions.fits_in(space_width, space_height, space_depth)
        return json.dumps({
            "product_id": product_id,
            "fits": fits,
            "product_dimensions": {
                "width": product.dimensions.width,
                "height": product.dimensions.height,
                "depth": product.dimensions.depth,
            },
            "space": {
                "width": space_width,
                "height": space_height,
                "depth": space_depth,
            },
        })

    registry.register(
        name="check_fit",
        desc="Check whether a product fits within a given space (all dimensions in cm).",
        params={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID, e.g. 'DESK-001'"},
                "space_width": {"type": "number", "description": "Available space width in cm"},
                "space_height": {"type": "number", "description": "Available space height in cm"},
                "space_depth": {"type": "number", "description": "Available space depth in cm"},
            },
            "required": ["product_id", "space_width", "space_height", "space_depth"],
        },
        func=check_fit,
    )
    return check_fit