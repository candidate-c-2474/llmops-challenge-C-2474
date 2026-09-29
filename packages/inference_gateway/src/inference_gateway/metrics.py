"""
Prometheus metrics for the inference gateway.

This module is intentionally independent of decorators.py and gateway.py to
keep the metrics surface additive: callers import `record_*` functions and
call them at well-defined points. If the metrics backend is unavailable
(the `prometheus_client` library is missing), all functions degrade to no-ops
so the inference path is never blocked by observability.
"""
from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram

    _BACKEND_SELECTED = Counter(
        "llm_backend_selected_total",
        "Number of inference requests routed to each backend.",
        labelnames=("backend", "role"),
    )

    _CIRCUIT_STATE = Counter(
        "llm_circuit_breaker_transitions_total",
        "Circuit breaker state transitions.",
        labelnames=("from_state", "to_state"),
    )

    _TTFT = Histogram(
        "llm_ttft_seconds",
        "Time to first token for streamed responses.",
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
        labelnames=("backend",),
    )

    _TOKENS_PER_SEC = Histogram(
        "llm_tokens_per_second",
        "Decode throughput per streamed response.",
        buckets=(1, 5, 10, 25, 50, 100, 200, 500, 1000),
        labelnames=("backend",),
    )

    _TOOL_CALLS = Counter(
        "llm_tool_calls_total",
        "Number of tool calls executed by the agent.",
        labelnames=("tool", "status"),
    )

    _METRICS_AVAILABLE = True
except Exception:  # pragma: no cover
    _METRICS_AVAILABLE = False


def record_backend_selected(backend: str, role: str) -> None:
    if _METRICS_AVAILABLE:
        _BACKEND_SELECTED.labels(backend=backend, role=role).inc()


def record_circuit_transition(from_state: str, to_state: str) -> None:
    if _METRICS_AVAILABLE:
        _CIRCUIT_STATE.labels(from_state=from_state, to_state=to_state).inc()


def record_ttft(backend: str, seconds: float) -> None:
    if _METRICS_AVAILABLE:
        _TTFT.labels(backend=backend).observe(seconds)


def record_tokens_per_second(backend: str, tps: float) -> None:
    if _METRICS_AVAILABLE:
        _TOKENS_PER_SEC.labels(backend=backend).observe(tps)


def record_tool_call(tool: str, status: str) -> None:
    if _METRICS_AVAILABLE:
        _TOOL_CALLS.labels(tool=tool, status=status).inc()


def metrics_available() -> bool:
    return _METRICS_AVAILABLE
