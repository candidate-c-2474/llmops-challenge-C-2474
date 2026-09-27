from sentence_transformers import CrossEncoder
from rag_core.config import RetrievalConfig
from rag_core.models import RetrievedChunk

class CrossEncoderReranker:
    def __init__(self, config: RetrievalConfig | None = None):
        self._config = config or RetrievalConfig()
        self._model = None

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int = 5) -> list[RetrievedChunk]:
        if not chunks:
            return []
        if self._model is None:
            self._model = CrossEncoder(self._config.reranker_model, device="cpu")
        
        pairs = [(query, chunk.content) for chunk in chunks]
        scores = self._model.predict(pairs)
        
        scored_chunks = []
        for chunk, score in zip(chunks, scores):
            scored_chunks.append(chunk.model_copy(update={"score": float(score), "source": "reranked"}))
            
        scored_chunks.sort(key=lambda c: c.score, reverse=True)
        return scored_chunks[:top_k]
