from typing import AsyncIterator, Any
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse
from .circuit_breaker import CircuitBreaker

class InferenceGateway:
    def __init__(self, primary: InferenceBackend, fallback: InferenceBackend):
        self.primary = primary
        self.fallback = fallback
        self.cb = CircuitBreaker()

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        if self.cb.allow_request():
            try:
                res = await self.primary.generate(request)
                self.cb.record_success()
                return res
            except Exception:
                self.cb.record_failure()
        return await self.fallback.generate(request)

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        if self.cb.allow_request():
            try:
                async for chunk in self.primary.generate_stream(request):
                    yield chunk
                self.cb.record_success()
                return
            except Exception:
                self.cb.record_failure()
        async for chunk in self.fallback.generate_stream(request):
            yield chunk
