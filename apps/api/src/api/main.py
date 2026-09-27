import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.logging import StructuredLoggingMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.routes import health, admin, chat

from inference_gateway import FakeBackend, InferenceGateway, VLLMBackend, LlamaCppBackend
from rag_core.repository import InMemoryCatalogRepository
from rag_core.agent.loop import AgentLoop
from rag_core.tools import (
    ToolRegistry,
    create_search_catalog_tool,
    create_get_product_tool,
    create_check_fit_tool,
    create_compare_products_tool
)
from rag_core.retrieval import HybridRetrievalPipeline, BM25Retriever

logger = structlog.get_logger(__name__)

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

repo = InMemoryCatalogRepository()
bm25 = BM25Retriever(repo)
pipeline = HybridRetrievalPipeline(retrievers=[bm25])

registry = ToolRegistry()
create_search_catalog_tool(pipeline)
create_get_product_tool(repo)
create_check_fit_tool(repo)
create_compare_products_tool(repo)

fake_backend = FakeBackend(default_response="Hello! I am RoomFit Copilot. How can I assist with your furniture shopping today?")

class GatewayAdapter:
    def __init__(self, backend):
        self.backend = backend
    async def generate(self, messages, tools=None, temperature=0.3, max_tokens=1024, stream=False):
        from inference_gateway import InferenceRequest
        req = InferenceRequest(messages=messages, tools=tools, temperature=temperature, max_tokens=max_tokens)
        res = await self.backend.generate(req)
        return {"message": {"content": res.content, "role": res.role}, "usage": res.usage}

agent = AgentLoop(backend=GatewayAdapter(fake_backend), tool_registry=registry)
app.state.agent = agent

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(admin.router)

@app.on_event("startup")
async def startup_event():
    logger.info("api.startup", status="ready")
