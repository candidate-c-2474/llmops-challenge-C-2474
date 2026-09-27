"""
inference_gateway — Resilience wrapper for LLM inference backends.
Contains Strategy, Adapter, Decorator, and Circuit Breaker patterns.
"""
from .interfaces import InferenceBackend, InferenceRequest, InferenceResponse
from .vllm_backend import VLLMBackend
from .llamacpp_backend import LlamaCppBackend
from .fake_backend import FakeBackend
from .circuit_breaker import CircuitBreaker, CircuitState
from .decorators import MetricsBackend, RetryBackend
from .gateway import InferenceGateway

__all__ = [
    "InferenceBackend", "InferenceRequest", "InferenceResponse",
    "VLLMBackend", "LlamaCppBackend", "FakeBackend",
    "CircuitBreaker", "CircuitState", "MetricsBackend", "RetryBackend", "InferenceGateway"
]
