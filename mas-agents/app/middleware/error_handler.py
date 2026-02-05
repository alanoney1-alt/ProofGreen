"""
ProofGreen MAS - Error Handler Middleware
Centralized error handling with structured logging and monitoring.
"""

import traceback
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from prometheus_client import Counter


logger = structlog.get_logger(__name__)

# Prometheus metrics
ERROR_COUNTER = Counter(
    'proofgreen_errors_total',
    'Total number of errors',
    ['error_type', 'status_code', 'endpoint']
)


class ProofGreenException(Exception):
    """Base exception for ProofGreen application."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = None,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ProofGreenException):
    """Validation error."""

    def __init__(self, message: str, field: str = None, details: Dict = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details={"field": field, **(details or {})}
        )


class AuthenticationError(ProofGreenException):
    """Authentication error."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR"
        )


class AuthorizationError(ProofGreenException):
    """Authorization error."""

    def __init__(self, message: str = "Access denied", required_role: str = None):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            details={"required_role": required_role} if required_role else {}
        )


class NotFoundError(ProofGreenException):
    """Resource not found error."""

    def __init__(self, resource: str, resource_id: str = None):
        super().__init__(
            message=f"{resource} not found",
            status_code=404,
            error_code="NOT_FOUND",
            details={"resource": resource, "id": resource_id}
        )


class RateLimitError(ProofGreenException):
    """Rate limit exceeded error."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after}
        )


class ExternalServiceError(ProofGreenException):
    """External service error (FSM, AI, etc.)."""

    def __init__(self, service: str, message: str, original_error: str = None):
        super().__init__(
            message=f"{service} error: {message}",
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, "original_error": original_error}
        )


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    Features:
    - Catches all unhandled exceptions
    - Converts to consistent JSON error response
    - Logs errors with context
    - Records metrics
    - Masks sensitive data
    """

    SENSITIVE_FIELDS = {"password", "token", "api_key", "secret", "authorization"}

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except ProofGreenException as e:
            return self._handle_proofgreen_exception(request, e)

        except Exception as e:
            return self._handle_unexpected_exception(request, e)

    def _handle_proofgreen_exception(
        self,
        request: Request,
        exc: ProofGreenException
    ) -> JSONResponse:
        """Handle known ProofGreen exceptions."""

        # Log with appropriate level
        log_method = logger.warning if exc.status_code < 500 else logger.error
        log_method(
            "handled_exception",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
            details=exc.details
        )

        # Record metric
        ERROR_COUNTER.labels(
            error_type=exc.error_code,
            status_code=str(exc.status_code),
            endpoint=request.url.path
        ).inc()

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    "timestamp": datetime.utcnow().isoformat(),
                    "path": request.url.path
                }
            }
        )

    def _handle_unexpected_exception(
        self,
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""

        # Log full traceback
        logger.error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            message=str(exc),
            path=request.url.path,
            method=request.method,
            traceback=traceback.format_exc()
        )

        # Record metric
        ERROR_COUNTER.labels(
            error_type="UNHANDLED_ERROR",
            status_code="500",
            endpoint=request.url.path
        ).inc()

        # Return generic error (don't expose internal details)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "timestamp": datetime.utcnow().isoformat(),
                    "path": request.url.path
                }
            }
        )

    def _mask_sensitive_data(self, data: Dict) -> Dict:
        """Mask sensitive fields in request/response data."""
        if not isinstance(data, dict):
            return data

        masked = {}
        for key, value in data.items():
            if key.lower() in self.SENSITIVE_FIELDS:
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_data(value)
            else:
                masked[key] = value

        return masked
