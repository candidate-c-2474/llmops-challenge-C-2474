from sentence_transformers import CrossEncoder
from rag_core.config import RetrievalConfig
from rag_core.models import RetrievedChunk


class CrossEncoderReranker:
    """Cross-encoder reranker.

    Loads the model lazily on first call. If the model cannot be loaded
    (offline environment, missing cache), the reranker silently degrades
    to pass-through ordering — the caller keeps the fused RRF ranking.
    """

    def __init__(self, config: RetrievalConfig | None = None):
        self._config = config or RetrievalConfig()
        self._model = None
        self._failed = False

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int = 5) -> list[RetrievedChunk]:
        if not chunks:
            return []
        if self._failed:
            return chunks[:top_k]
        if self._model is None:
            try:
                self._model = CrossEncoder(self._config.reranker_model, device="cpu")
            except Exception:
                self._failed = True
                return chunks[:top_k]

        pairs = [(query, chunk.content) for chunk in chunks]
        scores = self._model.predict(pairs)

        scored_chunks = []
        for chunk, score in zip(chunks, scores):
            scored_chunks.append(chunk.model_copy(update={"score": float(score), "source": "reranked"}))

        scored_chunks.sort(key=lambda c: c.score, reverse=True)
        return scored_chunks[:top_k]