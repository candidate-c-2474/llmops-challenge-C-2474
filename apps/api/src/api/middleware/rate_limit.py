import time
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.client_records: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        
        timestamps = [t for t in self.client_records.get(client_ip, []) if now - t < 60.0]
        
        if len(timestamps) >= self.rpm:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait before sending more requests."
            )
            
        timestamps.append(now)
        self.client_records[client_ip] = timestamps
        
        return await call_next(request)
