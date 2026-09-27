from rag_core.models import RetrievedChunk
from rag_core.repository import CatalogRepository
from rag_core.retrieval.interfaces import Retriever

class BM25Retriever(Retriever):
    def __init__(self, repository: CatalogRepository):
        self._repo = repository

    @property
    def name(self) -> str:
        return "bm25"

    async def retrieve(self, query: str, top_k: int = 20) -> list[RetrievedChunk]:
        products = await self._repo.search_by_text(query, limit=top_k)
        chunks = []
        for rank, product in enumerate(products):
            content = self._product_to_chunk_text(product)
            chunks.append(RetrievedChunk(product_id=product.id, content=content, score=1.0/(rank+1), source="bm25"))
        return chunks

    @staticmethod
    def _product_to_chunk_text(product) -> str:
        parts = [f"Product: {product.name} (ID: {product.id})", f"Category: {product.category}", f"Price: {product.currency} {product.price:.2f}", f"Stock: {product.stock} units"]
        if product.dimensions:
            d = product.dimensions
            parts.append(f"Dimensions: {d.width}×{d.depth}×{d.height} cm")
        if product.description:
            parts.append(f"Description: {product.description}")
        return "\n".join(parts)
