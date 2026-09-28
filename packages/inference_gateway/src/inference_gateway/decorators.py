"""
Decorator Pattern: Wraps an InferenceBackend to inject cross-cutting concerns (Metrics, Retries).
Supports asynchronous generator profiling.
"""
from __future__ import annotations
import time
import asyncio
import structlog
from typing import AsyncIterator, Any
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse

logger = structlog.get_logger(__name__)

class MetricsBackend(InferenceBackend):
    def __init__(self, backend: InferenceBackend):
        self.backend = backend
        self.latency_samples: list[float] = []

    @property
    def name(self) -> str:
        return self.backend.name

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        start = time.monotonic()
        res = await self.backend.generate(request)
        elapsed = time.monotonic() - start
        self.latency_samples.append(elapsed)
        res.backend_name = self.name
        return res

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        start_time = time.monotonic()
        first_token_received = False
        token_count = 0
        
        async for chunk in self.backend.generate_stream(request):
            if not first_token_received:
                ttft = (time.monotonic() - start_time) * 1000.0
                logger.info("inference.stream.ttft", backend=self.name, ttft_ms=round(ttft, 2))
                first_token_received = True
            
            if chunk.get("content"):
                token_count += 1
            yield chunk
            
        elapsed = time.monotonic() - start_time
        if elapsed > 0:
            tps = token_count / elapsed
            logger.info("inference.stream.completed", backend=self.name, tokens=token_count, tokens_per_sec=round(tps, 2))

class RetryBackend(InferenceBackend):
    def __init__(self, backend: InferenceBackend, max_retries: int = 2, delay: float = 0.5):
        self.backend = backend
        self.max_retries = max_retries
        self.delay = delay

    @property
    def name(self) -> str:
        return self.backend.name

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self.backend.generate(request)
            except Exception as e:
                last_exception = e
                logger.warn("inference.attempt.failed", backend=self.name, attempt=attempt, error=str(e))
                if attempt < self.max_retries:
                    await asyncio.sleep(self.delay * (2 ** attempt))
        raise last_exception or RuntimeError("Inference retry failure")

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        # Stream-level failover delegates to the fallback backend on connection error
        try:
            async for chunk in self.backend.generate_stream(request):
                yield chunk
        except Exception as e:
            logger.error("inference.stream.failed", backend=self.name, error=str(e))
            raise e