"""
ProofGreen MAS - Middleware Package
Error handling, rate limiting, and request processing middleware.
"""

from .error_handler import (
    ErrorHandlerMiddleware,
    ProofGreenException,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ExternalServiceError
)
from .rate_limiter import RateLimiterMiddleware, RateLimitConfig
from .request_logging import RequestLoggingMiddleware

__all__ = [
    # Error Handler
    "ErrorHandlerMiddleware",
    "ProofGreenException",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "RateLimitError",
    "ExternalServiceError",

    # Rate Limiter
    "RateLimiterMiddleware",
    "RateLimitConfig",

    # Request Logging
    "RequestLoggingMiddleware"
]
