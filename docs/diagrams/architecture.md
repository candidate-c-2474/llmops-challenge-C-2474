# System Architecture & Design Patterns

## Component Architecture

```mermaid
graph TD
    Client[Next.js Web App] -->|SSE Chat / POST| API[FastAPI Web Server]
    API --> Agent[Agent Loop]
    Agent --> Registry[Tool Registry]
    
    Registry --> SearchTool[search_catalog]
    Registry --> FitTool[check_fit]
    Registry --> GetTool[get_product]
    Registry --> CompareTool[compare_products]

    SearchTool --> Pipeline[Hybrid Retrieval Pipeline]
    Pipeline --> BM25[BM25 Retriever]
    Pipeline --> Dense[Dense Retriever]
    Pipeline --> Reranker[Cross-Encoder Reranker]

    BM25 --> Postgres[(Postgres + pgvector)]
    Dense --> Postgres

    Agent --> Gateway[Inference Gateway]
    Gateway --> Primary[vLLM Backend - GPU]
    Gateway --> Fallback[llama.cpp Backend - CPU]
    
    API --> ExactCache[Exact Cache - Redis]
    API --> SemanticCache[Semantic Cache - Redis]
```

## Pattern Proof Summary

1. **Strategy Pattern**: `InferenceBackend` interface with `VLLMBackend`, `LlamaCppBackend`, `FakeBackend`.
2. **Adapter Pattern**: `GatewayAdapter` converting inference requests to agent response contracts.
3. **Decorator Pattern**: `MetricsBackend` and `RetryBackend` wrapping backends; `ExactCache` and `SemanticCache` wrapping retrieval.
4. **Circuit Breaker Pattern**: `CircuitBreaker` in `InferenceGateway` managing state transitions (CLOSED, OPEN, HALF_OPEN).
5. **Pipeline/Chain Pattern**: `HybridRetrievalPipeline` chaining BM25 + Dense + RRF + Cross-Encoder Reranker.
6. **Repository Pattern**: `CatalogRepository` interface with `PostgresCatalogRepository` and `InMemoryCatalogRepository`.
7. **Registry/Factory Pattern**: `ToolRegistry` and `@tool` decorator dynamically dispatching tools by name.
8. **Observer Pattern**: `CatalogEventBus` publishing updates to `CacheInvalidator` on catalog changes.
