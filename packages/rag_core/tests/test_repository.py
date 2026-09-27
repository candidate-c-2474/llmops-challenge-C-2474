import pytest
from rag_core.repository import InMemoryCatalogRepository
from rag_core.models import Product, Dimensions

@pytest.mark.asyncio
async def test_in_memory_repository_crud():
    repo = InMemoryCatalogRepository()
    product = Product(
        id="DESK-001",
        name="Modern Desk",
        category="desks",
        price=299.99,
        stock=10,
        dimensions=Dimensions(width=120, height=75, depth=60),
        description="Sleek modern work desk",
        tags=["desk", "modern"]
    )
    await repo.upsert_product(product)
    
    fetched = await repo.get_product("DESK-001")
    assert fetched is not None
    assert fetched.name == "Modern Desk"
    
    search_res = await repo.search_by_text("modern")
    assert len(search_res) == 1
    assert search_res[0].id == "DESK-001"
