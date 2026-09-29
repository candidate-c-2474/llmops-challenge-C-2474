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

from prometheus_fastapi_instrumentator import Instrumentator

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


# Prometheus metrics exposure at /metrics.
# The package is mounted from the host's site-packages via
# /opt/prom-wheelhouse (see docker-compose.yml and ADR-011), because the
# offline build environment cannot pip install it.
Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


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
    create_search_catalog_tool(pipeline, registry)
    create_get_product_tool(repo, registry)
    create_check_fit_tool(repo, registry)
    create_compare_products_tool(repo, registry)

    # Fail-fast sanity check: the agent cannot work without registered tools.
    assert len(registry) == 4, f"Expected 4 tools, got {registry.tool_names()}"
    logger.info("api.tools_registered", tools=registry.tool_names())

    # 6. Primary and Fallback Backends Setup
    import os
    _use_fake = os.getenv("USE_FAKE_BACKEND", "false").lower() == "true"

    if _use_fake:
        from inference_gateway.fake_backend import FakeBackend
        raw_primary = FakeBackend(name="fake_primary")
        raw_fallback = FakeBackend(name="fake_fallback")
        logger.warn("api.backend.fake_mode", reason="USE_FAKE_BACKEND=true")
    else:
        vllm_url = os.getenv("VLLM_URL", "http://172.25.12.152:8001/v1")
        llamacpp_url = os.getenv("LLAMACPP_URL", vllm_url)
        raw_primary = VLLMBackend(base_url=vllm_url, model_name="Qwen/Qwen2.5-1.5B-Instruct")
        raw_fallback = VLLMBackend(base_url=llamacpp_url, model_name="Qwen/Qwen2.5-1.5B-Instruct")
        logger.info("api.backend.real_mode", primary=vllm_url, fallback=llamacpp_url)

    # Apply Decorators (Metrics and Retries)
    primary = MetricsBackend(RetryBackend(raw_primary, max_retries=2))
    fallback = MetricsBackend(raw_fallback)

    gateway = InferenceGateway(primary=primary, fallback=fallback)
    agent = AgentLoop(backend=GatewayAgentAdapter(gateway), tool_registry=registry, config=config.agent)

    app.state.gateway = gateway
    app.state.agent = agent
    logger.info("api.startup", status="fully_initialized_production")


@app.on_event("shutdown")
async def shutdown_event():
    await app.state.repository.close()
    logger.info("api.shutdown", status="completed")


app.include_router(health.router)
app.include_router(chat.router)
app.include_router(admin.router)