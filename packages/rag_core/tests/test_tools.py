import pytest
import json
from rag_core.repository import InMemoryCatalogRepository
from rag_core.models import Product, Dimensions, ToolCall
from rag_core.tools import (
    ToolRegistry,
    get_registry,
    create_check_fit_tool,
    create_get_product_tool,
    create_compare_products_tool
)

@pytest.mark.asyncio
async def test_check_fit_tool():
    repo = InMemoryCatalogRepository()
    product = Product(
        id="DESK-001",
        name="Modern Standing Desk",
        category="desks",
        price=499.99,
        stock=5,
        dimensions=Dimensions(width=120, height=75, depth=60),
        description="Adjustable standing desk"
    )
    await repo.upsert_product(product)

    # Factory registers check_fit into global registry
    create_check_fit_tool(repo)
    registry = get_registry()

    tool_call = ToolCall(
        name="check_fit",
        arguments={
            "product_id": "DESK-001",
            "space_width": 150.0,
            "space_height": 100.0,
            "space_depth": 80.0
        }
    )

    result = await registry.execute(tool_call)
    assert result.error is None
    res_data = json.loads(result.content)
    assert res_data["fits"] is True
    assert res_data["product_id"] == "DESK-001"
