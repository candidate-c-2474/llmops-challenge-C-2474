# rag-core (Candidate C-2474)

Standalone, reusable Python package providing the hybrid RAG retrieval pipeline, multi-layer Redis caching, catalog repository, and agent tool-calling loop.

## Design Patterns Applied
- **Strategy and Pipeline Patterns**: Retriever interface implemented by BM25Retriever and DenseRetriever. HybridRetrievalPipeline chains lexical search, dense search, Reciprocal Rank Fusion (RRF k=60), and Cross-Encoder reranking.
- **Repository Pattern**: CatalogRepository abstracts Postgres/pgvector queries behind domain interfaces.
- **Registry / Factory Patterns**: ToolRegistry and @tool decorator enable self-registering agent tools (search_catalog, get_product, check_fit, compare_products).
- **Observer / Pub-Sub Patterns**: CatalogEventBus notifies CacheInvalidator on catalog updates to flush stale Redis cache entries.

## Installation and Tests
```bash
pip install -e .
pytest
```
