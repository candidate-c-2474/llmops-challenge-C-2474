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

        tasks = [r.retrieve(query, top_k=top_k_retrieve) for r in self._retrievers]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        retriever_results = [res if not isinstance(res, Exception) else [] for res in all_results]
        fused = self._reciprocal_rank_fusion(retriever_results)

        if self._reranker and not skip_rerank and fused:
            return await self._reranker.rerank(query, fused, top_k=top_k_final)

        return fused[:top_k_final]

    def _reciprocal_rank_fusion(self, result_lists: list[list[RetrievedChunk]]) -> list[RetrievedChunk]:
        k = self._config.rrf_k
        weights = [self._config.bm25_weight, self._config.dense_weight]
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
