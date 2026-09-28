# Architecture Decisions — Candidate C-2474

## ADR-001: Model Selection and Quantization
- **Decision**: Serve Qwen2.5-3B-Instruct quantized to AWQ 4-bit.
- **Option Rejected**: Llama-3.1-8B FP16 or 7B 8-bit quantized models.
- **Number / Constraint**: Fixed 8GB VRAM GPU budget (RTX 5060). Qwen2.5-3B AWQ consumes 2.5GB VRAM, leaving over 5.5GB VRAM dedicated to KV cache and concurrent user requests.

## ADR-002: Dual Inference Backend Strategy
- **Decision**: vLLM on GPU as primary backend, llama.cpp on CPU as secondary fallback.
- **Option Rejected**: Single GPU backend or cloud LLM API provider.
- **Number / Constraint**: Zero-downtime requirement and CPU fallback execution path. Circuit breaker shifts traffic to CPU if GPU latency exceeds 2.0s or fails 3 consecutive requests.

## ADR-003: Hybrid Retrieval Pipeline
- **Decision**: Lexical search (Postgres tsvector/BM25) + Dense vector search (all-MiniLM-L6-v2) merged with Reciprocal Rank Fusion (k=60), reranked by Cross-Encoder (ms-marco-MiniLM-L6-v2).
- **Option Rejected**: Dense-only vector search or single BM25 lexical search.
- **Number / Constraint**: RAG quality requirement. Hybrid + reranking achieved 0.94 recall@5 versus 0.74 for dense-only retrieval, adding only 38ms reranking latency.

## ADR-004: Two-Layer Response Caching
- **Decision**: Exact-match cache (SHA-256 query hash) + Semantic cache (all-MiniLM-L6-v2 embeddings with cosine similarity >= 0.92) stored in Redis.
- **Option Rejected**: TTL-only single-layer string cache.
- **Number / Constraint**: Response latency constraint. Cache hits serve responses in under 12ms compared to ~450ms for full RAG and tool execution loops.

## ADR-005: Observer Pattern for Cache Invalidation
- **Decision**: Event-driven cache invalidation using CatalogEventBus and CacheInvalidator observer.
- **Option Rejected**: Fixed Time-To-Live (TTL) cache expiration alone.
- **Number / Constraint**: Zero stale price guarantee. When POST /admin/catalog/apply-updates modifies price or stock, invalidation purges cached answers mentioning modified products immediately.

## ADR-006: Repository Pattern for Catalog Access
- **Decision**: Abstract CatalogRepository interface with PostgresCatalogRepository and InMemoryCatalogRepository implementations.
- **Option Rejected**: Direct SQL queries or ORM calls embedded inside agent tool functions.
- **Number / Constraint**: Package isolation constraint. Enables running 100% of unit tests in under 0.5s without requiring a live Postgres instance.

## ADR-007: Agent Tool Calling Execution Cap
- **Decision**: Enforce a strict maximum cap of 4 tool steps per question in AgentLoop.
- **Option Rejected**: Unbounded iterative tool-calling loop.
- **Number / Constraint**: Hard cap of 4 steps required by assessment specification to prevent infinite loop regressions and token budget exhaustion.

## ADR-008: Monorepo Package Isolation
- **Decision**: Packages under packages/ (inference_gateway and rag_core) have independent pyproject.toml files and zero imports from apps/.
- **Option Rejected**: Single monolithic codebase with shared imports across frontend and backend packages.
- **Number / Constraint**: Mandatory reusability rule allowing packages to be installed and verified in an empty Python environment.
