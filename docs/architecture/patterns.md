# Design Patterns Implementation & Proofs — Candidate C-XXXX

This document proves the application of all **8 Design Patterns** across `packages/inference_gateway`, `packages/rag_core`, and `apps/api`.

---

## Pattern Summary Table

| Pattern # | Pattern Name | Code Location | Class / Function | Purpose & Proof |
|---|---|---|---|---|
| **1** | **Strategy** | `packages/inference_gateway/src/inference_gateway/interfaces.py`<br>`packages/rag_core/src/rag_core/retrieval/interfaces.py` | `InferenceBackend`<br>`Retriever` | Defines common interfaces for inference backends (vLLM, llama.cpp, Fake) and search retrievers (BM25, Dense). Callers consume the abstract strategy without knowing concrete implementations. |
| **2** | **Adapter** | `apps/api/src/api/main.py`<br>`packages/inference_gateway/src/inference_gateway/vllm_backend.py` | `GatewayAdapter`<br>`VLLMBackend` | Adapts backend-specific response schemas (OpenAI JSON, llama.cpp JSON) into a unified `InferenceResponse` model and dict format required by `AgentLoop`. |
| **3** | **Decorator** | `packages/inference_gateway/src/inference_gateway/decorators.py`<br>`packages/rag_core/src/rag_core/cache/exact_cache.py` | `MetricsBackend`<br>`RetryBackend`<br>`ExactCache` | Dynamically adds cross-cutting concerns (latency tracking, automatic retry, Redis caching) around core implementations without modifying their code. |
| **4** | **Circuit Breaker** | `packages/inference_gateway/src/inference_gateway/circuit_breaker.py`<br>`gateway.py` | `CircuitBreaker`<br>`InferenceGateway` | Monitors primary backend health. On repeated failures, opens the circuit and fails over to secondary backend, recovering automatically when primary recovers. |
| **5** | **Pipeline** | `packages/rag_core/src/rag_core/retrieval/hybrid_pipeline.py` | `HybridRetrievalPipeline` | Executes retrieval as sequential stages: BM25 search → Dense vector search → Reciprocal Rank Fusion (RRF) → Cross-Encoder reranking. |
| **6** | **Repository** | `packages/rag_core/src/rag_core/repository.py` | `CatalogRepository`<br>`PostgresCatalogRepository`<br>`InMemoryCatalogRepository` | Abstracts catalog storage and pgvector distance queries. Ensures zero SQL/database logic leaks into agent or tool code. |
| **7** | **Registry / Factory** | `packages/rag_core/src/rag_core/tools/registry.py` | `ToolRegistry`<br>`@tool` decorator | Central registry mapping tool names to functions. LLM tool calls dynamically instantiate and execute registered tool factories by name. |
| **8** | **Observer / Pub-Sub** | `packages/rag_core/src/rag_core/cache/invalidation.py` | `CatalogEventBus`<br>`CacheInvalidator` | `CatalogEventBus` acts as Subject; `CacheInvalidator` acts as Observer. When catalog updates occur, observers invalidate stale exact and semantic cache entries. |

---

## Pattern Detailed Proofs

### 1. Strategy Pattern
- **Interface**: `InferenceBackend` (ABC) with `generate()` and `generate_stream()` methods.
- **Implementations**: `VLLMBackend`, `LlamaCppBackend`, `FakeBackend`.
- **Why**: Allows swapping inference servers (e.g., switching from vLLM on GPU to llama.cpp on CPU or FakeBackend for tests) without modifying `AgentLoop` or API code.

### 2. Adapter Pattern
- **Implementation**: `GatewayAdapter` in `apps/api/src/api/main.py`.
- **Why**: Translates between `InferenceGateway` responses and the dict signature expected by `AgentLoop`, decoupling API contracts from gateway internals.

### 3. Decorator Pattern
- **Implementations**: `MetricsBackend` (records latency histograms) and `RetryBackend` (retries failed HTTP calls).
- **Why**: Can be stacked around any `InferenceBackend` in a configurable order without altering base backend classes.

### 4. Circuit Breaker Pattern
- **Implementation**: `CircuitBreaker` with states `CLOSED`, `OPEN`, `HALF_OPEN`.
- **Why**: Prevents cascade failures when vLLM is down. `InferenceGateway` automatically shifts traffic to `LlamaCppBackend` during `OPEN` state.

### 5. Pipeline / Chain Pattern
- **Implementation**: `HybridRetrievalPipeline`.
- **Why**: Processes retrieval in configurable stages: BM25 lexical search + Dense vector search run in parallel, fused via RRF (k=60), then reranked with Cross-Encoder.

### 6. Repository Pattern
- **Interface**: `CatalogRepository`.
- **Implementations**: `PostgresCatalogRepository` (Postgres 16 + pgvector) and `InMemoryCatalogRepository` (for tests).
- **Why**: Agent tools (`get_product`, `check_fit`, `search_catalog`, `compare_products`) call domain methods like `repo.get_product()` with zero raw SQL.

### 7. Registry / Factory Pattern
- **Implementation**: `ToolRegistry` and `@tool` decorator.
- **Why**: Adding a new tool requires only decorating a function; the agent loop looks up tools by name from the registry dynamically.

### 8. Observer / Pub-Sub Pattern
- **Implementation**: `CatalogEventBus` (Subject) and `CacheInvalidator` (Observer).
- **Why**: When catalog price or stock updates occur via `POST /admin/catalog/apply-updates`, the event bus notifies observers to purge exact and semantic cache entries.
