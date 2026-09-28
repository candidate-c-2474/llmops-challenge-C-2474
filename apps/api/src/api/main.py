import structlog
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.logging import StructuredLoggingMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.routes import health, admin, chat

from inference_gateway import (
    InferenceGateway, VLLMBackend, LlamaCppBackend, 
    MetricsBackend, RetryBackend, CircuitBreaker
)
from rag_core.config import RAGConfig
from rag_core.repository import PostgresCatalogRepository
from rag_core.cache import ExactCache, SemanticCache, CacheInvalidator, CatalogEventBus
from rag_core.retrieval import HybridRetrievalPipeline, BM25Retriever, DenseRetriever, CrossEncoderReranker
from rag_core.tools import (
    ToolRegistry, create_search_catalog_tool, create_get_product_tool,
    create_check_fit_tool, create_compare_products_tool
)
from rag_core.agent.loop import AgentLoop

logger = structlog.get_logger(__name__)
config = RAGConfig()

app = FastAPI(
    title="RoomFit Copilot API",
    description="LLMOps & RAG API with tool-calling agent, dual-backend failover, and SSE streaming.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

# Adapt the InferenceGateway to match the Agent's expected interface
class GatewayAgentAdapter:
    def __init__(self, gateway: InferenceGateway):
        self.gateway = gateway
        
    async def generate(self, messages, tools=None, temperature=0.3, max_tokens=1024, stream=False) -> dict:
        from inference_gateway import InferenceRequest
        # Map raw dictionary structures to Pydantic requirements
        req = InferenceRequest(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream
        )
        res = await self.gateway.generate(req)
        return {
            "message": {
                "role": res.role,
                "content": res.content,
                "tool_calls": res.tool_calls
            },
            "usage": res.usage
        }

@app.on_event("startup")
async def startup_event():
    # 1. Database Connection
    repo = PostgresCatalogRepository(config.postgres)
    await repo.initialize()
    app.state.repository = repo

    # 2. Redis Cache Setup
    redis_client = redis.from_url(config.redis.url, decode_responses=True)
    exact_cache = ExactCache(config.redis)
    semantic_cache = SemanticCache(config.redis)
    await exact_cache.initialize(client=redis_client)
    await semantic_cache.initialize(client=redis_client)
    
    # 3. Cache Invalidation Observer Setup
    bus = CatalogEventBus()
    invalidator = CacheInvalidator(exact_cache, semantic_cache)
    bus.subscribe(invalidator)
    app.state.event_bus = bus

    # 4. Hybrid Retrieval Pipeline Setup
    bm25 = BM25Retriever(repo)
    dense = DenseRetriever(repo, config.retrieval)
    reranker = CrossEncoderReranker(config.retrieval)
    pipeline = HybridRetrievalPipeline(retrievers=[bm25, dense], reranker=reranker, config=config.retrieval)

    # 5. Tool Registry Setup
    registry = ToolRegistry()
    create_search_catalog_tool(pipeline)
    create_get_product_tool(repo)
    create_check_fit_tool(repo)
    create_compare_products_tool(repo)

    # 6. Primary and Fallback Backends Setup
    raw_primary = VLLMBackend(base_url=config.vllm_url) if hasattr(config, 'vllm_url') else VLLMBackend()
    raw_fallback = LlamaCppBackend(base_url=config.llamacpp_url) if hasattr(config, 'llamacpp_url') else LlamaCppBackend()
    
    # Apply Decorators (Metrics and Retries)
    primary = MetricsBackend(RetryBackend(raw_primary, max_retries=2))
    fallback = MetricsBackend(raw_fallback)
    
    gateway = InferenceGateway(primary=primary, fallback=fallback)
    agent = AgentLoop(backend=GatewayAgentAdapter(gateway), tool_registry=registry, config=config.agent)
    
    app.state.agent = agent
    logger.info("api.startup", status="fully_initialized_production")

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.repository.close()
    logger.info("api.shutdown", status="completed")

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(admin.router)