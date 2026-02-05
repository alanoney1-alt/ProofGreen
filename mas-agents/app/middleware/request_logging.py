"""
ProofGreen MAS - Request Logging Middleware
Structured request/response logging with performance metrics.
"""

import time
import uuid
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog
from prometheus_client import Histogram, Counter


logger = structlog.get_logger(__name__)

# Prometheus metrics
REQUEST_DURATION = Histogram(
    'proofgreen_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint', 'status_code'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

REQUEST_COUNT = Counter(
    'proofgreen_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status_code']
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Request logging middleware.

    Features:
    - Unique request ID tracking
    - Request/response timing
    - Structured logging
    - Prometheus metrics
    """

    # Endpoints to skip logging (health checks, metrics)
    SKIP_LOGGING = {"/health", "/health/live", "/metrics"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip logging for certain endpoints
        if request.url.path in self.SKIP_LOGGING:
            return await call_next(request)

        # Generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Extract user info if available
        user_id = getattr(request.state, "user_id", None)

        # Start timing
        start_time = time.time()

        # Log request
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
            user_id=user_id,
            client_ip=self._get_client_ip(request),
            user_agent=request.headers.get("User-Agent")
        )

        try:
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log response
            logger.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
                user_id=user_id
            )

            # Record metrics
            self._record_metrics(
                request.method,
                request.url.path,
                response.status_code,
                duration
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration = time.time() - start_time

            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration * 1000, 2),
                error=str(e)
            )

            self._record_metrics(
                request.method,
                request.url.path,
                500,
                duration
            )

            raise

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers (proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _record_metrics(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float
    ):
        """Record Prometheus metrics."""
        # Normalize path to prevent cardinality explosion
        normalized_path = self._normalize_path(path)

        REQUEST_DURATION.labels(
            method=method,
            endpoint=normalized_path,
            status_code=str(status_code)
        ).observe(duration)

        REQUEST_COUNT.labels(
            method=method,
            endpoint=normalized_path,
            status_code=str(status_code)
        ).inc()

    def _normalize_path(self, path: str) -> str:
        """Normalize path to prevent metric cardinality explosion."""
        # Replace UUIDs
        import re
        path = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{uuid}',
            path,
            flags=re.IGNORECASE
        )

        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)

        return path
