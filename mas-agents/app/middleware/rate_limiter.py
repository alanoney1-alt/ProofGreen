"""
ProofGreen MAS - Rate Limiter Middleware
Token bucket rate limiting with Redis backend.
"""

import time
from typing import Optional, Dict
from dataclasses import dataclass
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from prometheus_client import Counter


logger = structlog.get_logger(__name__)

# Prometheus metrics
RATE_LIMIT_COUNTER = Counter(
    'proofgreen_rate_limit_total',
    'Total rate limit events',
    ['action', 'endpoint']  # action: allowed, blocked
)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    burst_size: int = 10
    key_prefix: str = "ratelimit"


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter using token bucket algorithm.

    For production, use Redis-based implementation.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.buckets: Dict[str, Dict] = {}

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check if request is allowed.

        Returns:
            (allowed, retry_after_seconds)
        """
        now = time.time()
        bucket = self.buckets.get(key)

        if not bucket:
            # Initialize new bucket
            self.buckets[key] = {
                "tokens": self.config.burst_size - 1,
                "last_update": now
            }
            return True, 0

        # Calculate tokens to add based on time elapsed
        elapsed = now - bucket["last_update"]
        tokens_to_add = elapsed * (self.config.requests_per_minute / 60)
        bucket["tokens"] = min(
            self.config.burst_size,
            bucket["tokens"] + tokens_to_add
        )
        bucket["last_update"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True, 0
        else:
            # Calculate retry after
            tokens_needed = 1 - bucket["tokens"]
            retry_after = int(tokens_needed * 60 / self.config.requests_per_minute) + 1
            return False, retry_after


class RedisRateLimiter:
    """
    Redis-based rate limiter for distributed environments.

    Uses sliding window log algorithm.
    """

    def __init__(self, redis_client, config: RateLimitConfig):
        self.redis = redis_client
        self.config = config

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check if request is allowed using Redis."""
        now = time.time()
        window_start = now - 60  # 1 minute window

        full_key = f"{self.config.key_prefix}:{key}"

        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(full_key, 0, window_start)

        # Count current window entries
        pipe.zcard(full_key)

        # Execute
        results = await pipe.execute()
        current_count = results[1]

        if current_count < self.config.requests_per_minute:
            # Add current request
            await self.redis.zadd(full_key, {str(now): now})
            await self.redis.expire(full_key, 120)  # 2 minute TTL
            return True, 0
        else:
            # Get oldest request to calculate retry after
            oldest = await self.redis.zrange(full_key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(60 - (now - oldest[0][1])) + 1
            else:
                retry_after = 60
            return False, max(1, retry_after)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.

    Features:
    - Per-user/IP rate limiting
    - Configurable limits per endpoint
    - Burst allowance
    - Retry-After header
    """

    # Endpoint-specific rate limits (more permissive for webhooks)
    ENDPOINT_LIMITS = {
        "/api/webhooks/": RateLimitConfig(requests_per_minute=120, burst_size=20),
        "/api/auth/login": RateLimitConfig(requests_per_minute=10, burst_size=5),
        "/health": RateLimitConfig(requests_per_minute=300, burst_size=50),
    }

    def __init__(self, app, redis_client=None, default_config: RateLimitConfig = None):
        super().__init__(app)
        self.default_config = default_config or RateLimitConfig()

        if redis_client:
            self.limiter = RedisRateLimiter(redis_client, self.default_config)
            self.use_redis = True
        else:
            self.limiter = InMemoryRateLimiter(self.default_config)
            self.use_redis = False

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks in some cases
        if request.url.path == "/health":
            return await call_next(request)

        # Get rate limit key (user ID or IP)
        key = self._get_rate_limit_key(request)

        # Get endpoint-specific config
        config = self._get_endpoint_config(request.url.path)

        # Check rate limit
        if self.use_redis:
            allowed, retry_after = await self.limiter.is_allowed(key)
        else:
            allowed, retry_after = self.limiter.is_allowed(key)

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                key=key,
                path=request.url.path,
                retry_after=retry_after
            )

            RATE_LIMIT_COUNTER.labels(
                action="blocked",
                endpoint=request.url.path
            ).inc()

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests",
                        "retry_after": retry_after
                    }
                },
                headers={"Retry-After": str(retry_after)}
            )

        RATE_LIMIT_COUNTER.labels(
            action="allowed",
            endpoint=request.url.path
        ).inc()

        return await call_next(request)

    def _get_rate_limit_key(self, request: Request) -> str:
        """Get rate limit key from request."""
        # Try to get user ID from auth
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"

    def _get_endpoint_config(self, path: str) -> RateLimitConfig:
        """Get rate limit config for endpoint."""
        for prefix, config in self.ENDPOINT_LIMITS.items():
            if path.startswith(prefix):
                return config
        return self.default_config
