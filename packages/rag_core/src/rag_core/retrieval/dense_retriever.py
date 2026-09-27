from sentence_transformers import SentenceTransformer
from rag_core.config import RetrievalConfig
from rag_core.models import RetrievedChunk
from rag_core.repository import CatalogRepository
from rag_core.retrieval.interfaces import Retriever
from rag_core.retrieval.bm25_retriever import BM25Retriever

class DenseRetriever(Retriever):
    def __init__(self, repository: CatalogRepository, config: RetrievalConfig | None = None):
        self._repo = repository
        self._config = config or RetrievalConfig()
        self._model = None

    @property
    def name(self) -> str:
        return "dense"

    def encode_query(self, query: str) -> list[float]:
        if self._model is None:
            self._model = SentenceTransformer(self._config.embedding_model, device="cpu")
        return self._model.encode(query, normalize_embeddings=True).tolist()

    async def retrieve(self, query: str, top_k: int = 20) -> list[RetrievedChunk]:
        query_embedding = self.encode_query(query)
        results = await self._repo.search_by_embedding(query_embedding, limit=top_k)
        chunks = []
        for product, similarity in results:
            content = BM25Retriever._product_to_chunk_text(product)
            chunks.append(RetrievedChunk(product_id=product.id, content=content, score=similarity, source="dense"))
        return chunks
