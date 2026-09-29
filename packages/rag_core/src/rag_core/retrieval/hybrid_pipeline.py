import asyncio
from collections import defaultdict
from rag_core.config import RetrievalConfig
from rag_core.models import RetrievedChunk
from rag_core.retrieval.interfaces import Retriever
from rag_core.retrieval.reranker import CrossEncoderReranker

class HybridRetrievalPipeline:
    def __init__(self, retrievers: list[Retriever], reranker: CrossEncoderReranker | None = None, config: RetrievalConfig | None = None):
        self._retrievers = retrievers
        self._reranker = reranker
        self._config = config or RetrievalConfig()

    async def retrieve(self, query: str, top_k: int | None = None, skip_rerank: bool = False) -> list[RetrievedChunk]:
        top_k_retrieve = self._config.top_k_retrieve
        top_k_final = top_k or self._config.top_k_rerank

        # If any retriever is a DenseRetriever running in hash-fallback mode,
        # exclude it from the fusion — its similarity scores are noise and
        # would dominate the RRF. See docs/DECISIONS.md ADR-012.
        active_retrievers = []
        for r in self._retrievers:
            mode = getattr(r, "encoder_mode", None)
            if mode == "hash-fallback":
                continue  # skip noise source
            active_retrievers.append(r)
        if not active_retrievers:
            active_retrievers = list(self._retrievers)

        tasks = [r.retrieve(query, top_k=top_k_retrieve) for r in active_retrievers]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        retriever_results = [res if not isinstance(res, Exception) else [] for res in all_results]

        # Adjust weights to match active retrievers (BM25 keeps its weight,
        # dense is dropped when in fallback mode).
        if len(active_retrievers) < len(self._retrievers):
            self._active_weights = [self._config.bm25_weight] * len(active_retrievers)
        else:
            self._active_weights = None

        fused = self._reciprocal_rank_fusion(retriever_results)

        if self._reranker and not skip_rerank and fused:
            return await self._reranker.rerank(query, fused, top_k=top_k_final)

        return fused[:top_k_final]

    def _reciprocal_rank_fusion(self, result_lists: list[list[RetrievedChunk]]) -> list[RetrievedChunk]:
        k = self._config.rrf_k
        weights = getattr(self, "_active_weights", None) or [
            self._config.bm25_weight, self._config.dense_weight
        ]
        scores = defaultdict(float)
        best_chunk = {}

        for list_idx, chunks in enumerate(result_lists):
            weight = weights[list_idx] if list_idx < len(weights) else 1.0
            for rank, chunk in enumerate(chunks):
                rrf_score = weight / (k + rank + 1)
                scores[chunk.product_id] += rrf_score
                if chunk.product_id not in best_chunk or chunk.score > best_chunk[chunk.product_id].score:
                    best_chunk[chunk.product_id] = chunk

        fused = []
        for product_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            fused.append(best_chunk[product_id].model_copy(update={"score": score, "source": "hybrid"}))
        return fused
