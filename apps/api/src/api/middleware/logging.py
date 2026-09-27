import uuid
import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

logger = structlog.get_logger(__name__)

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        
        start_time = time.monotonic()
        response = await call_next(request)
        process_time = time.monotonic() - start_time
        
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        
        logger.info(
            "http.request",
            request_id=request_id,
            method=request.method,
            url=str(request.url.path),
            status_code=response.status_code,
            duration=round(process_time, 4),
        )
        return response
