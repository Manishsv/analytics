"""
Rate limiting middleware for the agent API.
Simple token bucket implementation for basic rate limiting.
"""
import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter(BaseHTTPMiddleware):
    """
    Simple token bucket rate limiter.
    Allows N requests per time window per client IP.
    """
    
    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        # Store request timestamps per IP: {ip: [timestamps]}
        self.client_requests = defaultdict(list)
        # Cleanup old entries every N requests
        self._cleanup_counter = 0
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean up old entries periodically
        self._cleanup_counter += 1
        if self._cleanup_counter % 100 == 0:
            self._cleanup_old_entries(current_time)
        
        # Get recent requests for this IP
        recent_requests = self.client_requests[client_ip]
        
        # Remove requests older than 1 hour
        recent_requests[:] = [ts for ts in recent_requests if current_time - ts < 3600]
        
        # Check hourly limit
        if len(recent_requests) >= self.requests_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_hour} requests per hour. Please try again later."
            )
        
        # Check per-minute limit (requests in last 60 seconds)
        minute_ago = current_time - 60
        minute_requests = [ts for ts in recent_requests if ts > minute_ago]
        
        if len(minute_requests) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute. Please slow down."
            )
        
        # Record this request
        recent_requests.append(current_time)
        
        # Process request
        response = await call_next(request)
        return response
    
    def _cleanup_old_entries(self, current_time: float):
        """Remove IP entries with no recent requests (older than 1 hour)."""
        cutoff = current_time - 3600
        to_remove = []
        for ip, timestamps in self.client_requests.items():
            # Remove old timestamps
            self.client_requests[ip] = [ts for ts in timestamps if ts > cutoff]
            # Remove IP if no recent requests
            if not self.client_requests[ip]:
                to_remove.append(ip)
        for ip in to_remove:
            del self.client_requests[ip]
