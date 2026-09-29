import asyncio
import structlog
from fastapi import APIRouter, Request

router = APIRouter(tags=["Health"])
logger = structlog.get_logger(__name__)

PROBE_TIMEOUT_S = 8.0  # RetryBackend uses 0.5 + 1.0 + 2.0 = 3.5s of backoff; probe must exceed it.


async def _probe_backend(backend) -> bool:
    """Best-effort liveness probe: send a 1-token request, expect any response.

    A backend that responds with a non-network error (e.g. 400 payload
    rejection) is still considered reachable — the goal here is TCP/HTTP
    reachability, not payload correctness.
    """
    if backend is None:
        return False
    try:
        from inference_gateway import InferenceRequest
        req = InferenceRequest(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        await asyncio.wait_for(backend.generate(req), timeout=PROBE_TIMEOUT_S)
        return True
    except asyncio.TimeoutError:
        logger.info("probe.timeout", backend=backend.name, timeout_s=PROBE_TIMEOUT_S)
        return False
    except Exception as e:
        # Reachable if we got an HTTP-level response, even a non-200.
        # httpx raises HTTPStatusError for non-2xx; that still means the
        # backend is up. Connection errors are the real failure signal.
        reachable = _is_reachable_error()
        logger.info("probe.error", backend=backend.name, error=str(e),
                    error_type=type(e).__name__, reachable=reachable)
        return reachable


def _is_reachable_error() -> bool:
    # Conservative: treat any non-timeout exception as "possibly reachable"
    # only if it is an httpx.HTTPStatusError. Everything else (ConnectError,
    # ConnectTimeout, DNS failure) means unreachable.
    import httpx
    import sys
    exc = sys.exc_info()[1]
    return isinstance(exc, httpx.HTTPStatusError)


@router.get("/health")
async def health_check(request: Request):
    gateway = getattr(request.app.state, "gateway", None)

    if gateway is None:
        return {
            "status": "degraded",
            "service": "roomfit-api",
            "version": "0.1.0",
            "reason": "gateway not initialized",
        }

    primary_ok = await _probe_backend(gateway.primary_backend)
    fallback_ok = await _probe_backend(gateway.fallback_backend)

    # Overall status: healthy if at least one backend responds.
    if primary_ok or fallback_ok:
        status = "healthy"
    else:
        status = "unhealthy"

    cb = gateway.circuit_breaker.snapshot()

    return {
        "status": status,
        "service": "roomfit-api",
        "version": "0.1.0",
        "backends": {
            "primary": {
                "name": gateway.primary_backend.name,
                "reachable": primary_ok,
            },
            "fallback": {
                "name": gateway.fallback_backend.name,
                "reachable": fallback_ok,
            },
        },
        "circuit_breaker": cb,
    }
