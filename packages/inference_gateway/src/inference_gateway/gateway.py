from typing import AsyncIterator, Any
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse
from .circuit_breaker import CircuitBreaker
from .metrics import record_backend_selected, record_circuit_transition

class InferenceGateway:
    def __init__(self, primary: InferenceBackend, fallback: InferenceBackend):
        self.primary = primary
        self.fallback = fallback
        self.cb = CircuitBreaker()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Public accessor for observability (see /health)."""
        return self.cb

    @property
    def primary_backend(self):
        return self.primary

    @property
    def fallback_backend(self):
        return self.fallback

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        if self.cb.allow_request():
            try:
                res = await self.primary.generate(request)
                self.cb.record_success()
                record_backend_selected(self.primary.name, role="primary")
                return res
            except Exception:
                self.cb.record_failure()
                record_circuit_transition(from_state="CLOSED_OR_HALF_OPEN", to_state="FAILURE")
        record_backend_selected(self.fallback.name, role="fallback")
        return await self.fallback.generate(request)

    async def generate_stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        if self.cb.allow_request():
            try:
                async for chunk in self.primary.generate_stream(request):
                    yield chunk
                self.cb.record_success()
                record_backend_selected(self.primary.name, role="primary")
                return
            except Exception:
                self.cb.record_failure()
                record_circuit_transition(from_state="CLOSED_OR_HALF_OPEN", to_state="FAILURE")
        record_backend_selected(self.fallback.name, role="fallback")
        async for chunk in self.fallback.generate_stream(request):
            yield chunk
