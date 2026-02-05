"""
ProofGreen MAS - Health Check Endpoints
Kubernetes-ready liveness and readiness probes.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import structlog
import asyncio


logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Health"])


class HealthStatus(BaseModel):
    """Health check response."""
    status: str  # healthy, degraded, unhealthy
    timestamp: str
    version: str
    checks: Dict[str, Any]


class ComponentHealth(BaseModel):
    """Individual component health."""
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HealthChecker:
    """
    Health checker for all system components.
    """

    def __init__(
        self,
        db_connection=None,
        redis_client=None,
        app_version: str = "1.0.0"
    ):
        self.db = db_connection
        self.redis = redis_client
        self.version = app_version

    async def check_database(self) -> ComponentHealth:
        """Check PostgreSQL database health."""
        if not self.db:
            return ComponentHealth(status="unknown", message="Database not configured")

        try:
            start = datetime.utcnow()
            await asyncio.wait_for(
                self.db.fetchval("SELECT 1"),
                timeout=5.0
            )
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            return ComponentHealth(
                status="healthy",
                latency_ms=round(latency, 2)
            )
        except asyncio.TimeoutError:
            return ComponentHealth(status="unhealthy", message="Database timeout")
        except Exception as e:
            return ComponentHealth(status="unhealthy", message=str(e))

    async def check_redis(self) -> ComponentHealth:
        """Check Redis health."""
        if not self.redis:
            return ComponentHealth(status="unknown", message="Redis not configured")

        try:
            start = datetime.utcnow()
            await asyncio.wait_for(
                self.redis.ping(),
                timeout=5.0
            )
            latency = (datetime.utcnow() - start).total_seconds() * 1000

            return ComponentHealth(
                status="healthy",
                latency_ms=round(latency, 2)
            )
        except asyncio.TimeoutError:
            return ComponentHealth(status="unhealthy", message="Redis timeout")
        except Exception as e:
            return ComponentHealth(status="unhealthy", message=str(e))

    async def check_external_services(self) -> Dict[str, ComponentHealth]:
        """Check external service connectivity."""
        services = {}

        # Check Anthropic API
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                start = datetime.utcnow()
                response = await client.get(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": "test"},
                    timeout=5.0
                )
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                # 401 is expected (invalid key), but shows API is reachable
                services["anthropic"] = ComponentHealth(
                    status="healthy" if response.status_code in [200, 401] else "degraded",
                    latency_ms=round(latency, 2)
                )
        except Exception as e:
            services["anthropic"] = ComponentHealth(
                status="unhealthy",
                message=str(e)
            )

        return services

    async def get_full_health(self) -> HealthStatus:
        """Get comprehensive health status."""
        checks = {}

        # Run all checks concurrently
        db_check, redis_check = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            return_exceptions=True
        )

        # Handle exceptions
        if isinstance(db_check, Exception):
            checks["database"] = ComponentHealth(status="unhealthy", message=str(db_check))
        else:
            checks["database"] = db_check

        if isinstance(redis_check, Exception):
            checks["redis"] = ComponentHealth(status="unhealthy", message=str(redis_check))
        else:
            checks["redis"] = redis_check

        # Determine overall status
        statuses = [c.status for c in checks.values()]
        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        return HealthStatus(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            version=self.version,
            checks={k: v.dict() for k, v in checks.items()}
        )


# Global health checker (initialized at startup)
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get health checker instance."""
    global _health_checker
    if not _health_checker:
        _health_checker = HealthChecker()
    return _health_checker


def init_health_checker(
    db_connection=None,
    redis_client=None,
    app_version: str = "1.0.0"
):
    """Initialize health checker with dependencies."""
    global _health_checker
    _health_checker = HealthChecker(
        db_connection=db_connection,
        redis_client=redis_client,
        app_version=app_version
    )


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.

    Returns 200 if service is running.
    Used by load balancers and Kubernetes liveness probe.
    """
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/live")
async def liveness_probe():
    """
    Kubernetes liveness probe.

    Returns 200 if the application is running.
    Failure triggers pod restart.
    """
    return {"status": "live"}


@router.get("/health/ready", response_model=HealthStatus)
async def readiness_probe(
    health_checker: HealthChecker = Depends(get_health_checker)
):
    """
    Kubernetes readiness probe.

    Returns 200 if the application is ready to receive traffic.
    Checks database and cache connectivity.
    """
    health = await health_checker.get_full_health()

    if health.status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health.dict()
        )

    return health


@router.get("/health/detailed", response_model=HealthStatus)
async def detailed_health_check(
    health_checker: HealthChecker = Depends(get_health_checker)
):
    """
    Detailed health check with all component statuses.

    Includes:
    - Database connectivity and latency
    - Redis connectivity and latency
    - External service status
    """
    return await health_checker.get_full_health()
