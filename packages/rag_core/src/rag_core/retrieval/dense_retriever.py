"""
Dense retriever with a graceful fallback chain.

Order of preference for the query encoder:
  1. SentenceTransformer (semantic, requires HF cache or network).
  2. Deterministic hash-based encoder (offline; mirrors the embedding
     scheme used by scripts/seed_catalog.py so query and product vectors
     live in the same space).

The fallback preserves the interface and the rest of the pipeline. When the
semantic model becomes available (cached or online), the retriever upgrades
automatically on the next query. See docs/DECISIONS.md ADR-012.
"""
from __future__ import annotations

import math
import random

from rag_core.config import RetrievalConfig
from rag_core.models import RetrievedChunk
from rag_core.repository import CatalogRepository
from rag_core.retrieval.interfaces import Retriever
from rag_core.retrieval.bm25_retriever import BM25Retriever


def _deterministic_embedding(text: str, dim: int = 384) -> list[float]:
    """Deterministic, unit-normalized hash embedding.

    MUST stay byte-identical to scripts/seed_catalog.py's
    generate_deterministic_embedding so that query and product vectors live
    in the same space.
    """
    rng = random.Random(text)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [round(x / norm, 6) for x in vec]


class DenseRetriever(Retriever):
    def __init__(self, repository: CatalogRepository, config: RetrievalConfig | None = None):
        self._repo = repository
        self._config = config or RetrievalConfig()
        self._model = None
        self._encoder_mode: str = "uninitialized"  # 'semantic' | 'hash-fallback'

    @property
    def name(self) -> str:
        return "dense"

    def encode_query(self, query: str) -> list[float]:
        # Try the semantic model once. If it fails, fall back permanently
        # for the lifetime of this retriever instance.
        if self._encoder_mode == "uninitialized":
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._config.embedding_model, device="cpu")
                self._encoder_mode = "semantic"
            except Exception:
                self._model = None
                self._encoder_mode = "hash-fallback"

        if self._encoder_mode == "semantic" and self._model is not None:
            return self._model.encode(query, normalize_embeddings=True).tolist()

        return _deterministic_embedding(query, dim=self._config.embedding_dim)

    @property
    def encoder_mode(self) -> str:
        return self._encoder_mode

    async def retrieve(self, query: str, top_k: int = 20) -> list[RetrievedChunk]:
        query_embedding = self.encode_query(query)
        results = await self._repo.search_by_embedding(query_embedding, limit=top_k)
        chunks = []
        for product, similarity in results:
            content = BM25Retriever._product_to_chunk_text(product)
            chunks.append(
                RetrievedChunk(
                    product_id=product.id,
                    content=content,
                    score=similarity,
                    source="dense",
                )
            )
        return chunks
