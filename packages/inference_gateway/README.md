# inference-gateway (Candidate C-XXXX)

Standalone, reusable Python package providing a resilient LLM inference gateway.

## Design Patterns Applied
- **Strategy Pattern**: InferenceBackend interface implemented by VLLMBackend, LlamaCppBackend, and FakeBackend.
- **Adapter Pattern**: Translates API response formats into a standardized InferenceResponse model.
- **Decorator Pattern**: MetricsBackend (latency profiling) and RetryBackend (transient HTTP retries).
- **Circuit Breaker Pattern**: CircuitBreaker manages state transitions (CLOSED, OPEN, HALF_OPEN) to handle primary GPU backend failure with seamless fallback to CPU.

## Installation and Tests
```bash
pip install -e .
pytest
```
