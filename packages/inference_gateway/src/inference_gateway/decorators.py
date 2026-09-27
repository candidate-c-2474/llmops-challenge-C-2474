from typing import AsyncIterator, Any
import time
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse

class MetricsBackend(InferenceBackend):
    def __init__(self, backend: InferenceBackend):
        self.backend = backend
        self.latency_samples = []

    @property
    def name(self) -> str:
        return self.backend.name

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        start = time.monotonic()
        res = await self.backend.generate(request)
        elapsed = time.monotonic() - start
        self.latency_samples.append(elapsed)
        return res

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        async for chunk in self.backend.generate_stream(request):
            yield chunk

class RetryBackend(InferenceBackend):
    def __init__(self, backend: InferenceBackend, max_retries: int = 2):
        self.backend = backend
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return self.backend.name

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        for attempt in range(self.max_retries + 1):
            try:
                return await self.backend.generate(request)
            except Exception as e:
                if attempt == self.max_retries:
                    raise e

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        async for chunk in self.backend.generate_stream(request):
            yield chunk
