"""
ProofGreen MAS - System Observability & Monitoring
OpenTelemetry integration with Prometheus metrics for 2026 compliance.

Tracks:
- Token consumption and costs per vertical
- Job completion latency
- Agent health and error rates
- Cost threshold alerts via webhooks
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
import httpx

# Prometheus client
try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary,
        start_http_server, generate_latest, CONTENT_TYPE_LATEST
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

# OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False

logger = logging.getLogger(__name__)


# =========================================================================
# Pricing Configuration (Claude 3.7 Sonnet rates as of 2026)
# =========================================================================

MODEL_PRICING = {
    "claude-3-opus": {"input": 0.000015, "output": 0.000075},
    "claude-3-sonnet": {"input": 0.000003, "output": 0.000015},
    "claude-3-haiku": {"input": 0.00000025, "output": 0.00000125},
    "claude-3.7-sonnet": {"input": 0.000003, "output": 0.000015},
    "claude-sonnet-4-20250514": {"input": 0.000003, "output": 0.000015},
    "gpt-4-turbo": {"input": 0.00001, "output": 0.00003},
    "gpt-4o": {"input": 0.000005, "output": 0.000015},
}

# Cost thresholds for alerts
COST_ALERT_THRESHOLDS = {
    "per_job": 0.50,       # Alert if single job costs > $0.50
    "hourly": 10.00,       # Alert if hourly spend > $10
    "daily": 100.00,       # Alert if daily spend > $100
}


# =========================================================================
# Prometheus Metrics
# =========================================================================

if HAS_PROMETHEUS:
    # Token metrics
    TOKEN_COUNTER = Counter(
        'proofgreen_agent_tokens_total',
        'Total tokens consumed by AI agents',
        ['model', 'vertical', 'operation']
    )

    # Cost metrics
    COST_COUNTER = Counter(
        'proofgreen_agent_cost_usd_total',
        'Total cost in USD',
        ['vertical', 'operation']
    )

    # Latency metrics
    LATENCY_HISTOGRAM = Histogram(
        'proofgreen_agent_request_latency_seconds',
        'Time to complete agent operations',
        ['vertical', 'operation'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
    )

    # Job metrics
    JOBS_PROCESSED = Counter(
        'proofgreen_jobs_processed_total',
        'Total jobs processed',
        ['vertical', 'status']
    )

    # Error metrics
    ERROR_COUNTER = Counter(
        'proofgreen_errors_total',
        'Total errors by type',
        ['error_type', 'vertical']
    )

    # Active jobs gauge
    ACTIVE_JOBS = Gauge(
        'proofgreen_active_jobs',
        'Currently processing jobs',
        ['vertical']
    )

    # Health check gauge
    SYSTEM_HEALTH = Gauge(
        'proofgreen_system_health',
        'System health status (1=healthy, 0=unhealthy)',
        ['component']
    )

    # Certificate generation
    CERTIFICATES_GENERATED = Counter(
        'proofgreen_certificates_generated_total',
        'Total certificates generated',
        ['vertical', 'tier']
    )

    # Rebate amounts
    REBATES_CALCULATED = Counter(
        'proofgreen_rebates_calculated_usd_total',
        'Total rebates calculated',
        ['program', 'vertical']
    )

    # Carbon metrics
    CARBON_AVOIDED = Counter(
        'proofgreen_carbon_avoided_kg_total',
        'Total carbon avoided in kg',
        ['vertical', 'scope']
    )


# =========================================================================
# Data Classes
# =========================================================================

@dataclass
class AgentMetrics:
    """Metrics for a single agent operation."""
    operation_id: str = field(default_factory=lambda: str(uuid4()))
    vertical: str = "unknown"
    operation: str = "unknown"
    model: str = "claude-sonnet-4-20250514"

    # Token counts
    tokens_in: int = 0
    tokens_out: int = 0

    # Timing
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_seconds: float = 0.0

    # Cost
    cost_usd: float = 0.0

    # Status
    success: bool = True
    error_message: Optional[str] = None

    # Context
    job_id: Optional[str] = None
    company_id: Optional[str] = None


@dataclass
class JobTrace:
    """OpenTelemetry trace for a complete job workflow."""
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    job_id: str = ""
    company_id: str = ""
    vertical: str = "hvac"

    # Timestamps
    fsm_closed_at: Optional[datetime] = None
    audit_started_at: Optional[datetime] = None
    compliance_checked_at: Optional[datetime] = None
    rebates_calculated_at: Optional[datetime] = None
    approval_requested_at: Optional[datetime] = None
    approval_received_at: Optional[datetime] = None
    certificate_generated_at: Optional[datetime] = None

    # Metrics
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0

    # Results
    is_compliant: bool = False
    rebate_amount: float = 0.0
    carbon_avoided_kg: float = 0.0
    certificate_id: Optional[str] = None


# =========================================================================
# System Monitor Class
# =========================================================================

class SystemMonitor:
    """
    Centralized system monitoring for ProofGreen MAS.

    Provides:
    - Prometheus metrics collection
    - OpenTelemetry distributed tracing
    - Cost tracking and alerting
    - Health checks
    """

    def __init__(
        self,
        metrics_port: int = 9464,
        alert_webhook_url: Optional[str] = None,
        enable_tracing: bool = True
    ):
        self.metrics_port = metrics_port
        self.alert_webhook_url = alert_webhook_url or os.getenv("ALERT_WEBHOOK_URL")
        self.enable_tracing = enable_tracing and HAS_OPENTELEMETRY

        # Cost tracking
        self._hourly_costs: Dict[str, float] = {}
        self._daily_costs: Dict[str, float] = {}
        self._job_costs: Dict[str, float] = {}

        # Active traces
        self._active_traces: Dict[str, JobTrace] = {}

        # HTTP client for webhooks
        self._client = httpx.AsyncClient(timeout=30.0)

        # Initialize OpenTelemetry
        if self.enable_tracing:
            self._init_opentelemetry()

        # Health check callbacks
        self._health_checks: Dict[str, Callable] = {}

    def _init_opentelemetry(self):
        """Initialize OpenTelemetry tracing."""
        if not HAS_OPENTELEMETRY:
            return

        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: "proofgreen-mas",
            ResourceAttributes.SERVICE_VERSION: "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development")
        })

        provider = TracerProvider(resource=resource)

        # Add OTLP exporter if configured
        otlp_endpoint = os.getenv("OTLP_ENDPOINT")
        if otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer(__name__)

        logger.info("OpenTelemetry tracing initialized")

    def start_metrics_server(self):
        """Start Prometheus metrics HTTP server."""
        if HAS_PROMETHEUS:
            start_http_server(self.metrics_port)
            logger.info(f"Prometheus metrics server started on port {self.metrics_port}")

    # =========================================================================
    # Metrics Recording
    # =========================================================================

    def record_agent_operation(
        self,
        vertical: str,
        operation: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        duration: float,
        job_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> AgentMetrics:
        """
        Record metrics for an agent operation.

        Args:
            vertical: Service vertical (hvac, plumbing, etc.)
            operation: Operation type (audit, rebate_calc, etc.)
            model: AI model used
            tokens_in: Input tokens
            tokens_out: Output tokens
            duration: Duration in seconds
            job_id: Associated job ID
            success: Whether operation succeeded
            error: Error message if failed

        Returns:
            AgentMetrics object with calculated costs
        """
        # Calculate cost
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])
        cost = (tokens_in * pricing["input"]) + (tokens_out * pricing["output"])

        metrics = AgentMetrics(
            vertical=vertical,
            operation=operation,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_seconds=duration,
            cost_usd=cost,
            job_id=job_id,
            success=success,
            error_message=error
        )

        # Update Prometheus metrics
        if HAS_PROMETHEUS:
            TOKEN_COUNTER.labels(model=model, vertical=vertical, operation=operation).inc(tokens_in + tokens_out)
            COST_COUNTER.labels(vertical=vertical, operation=operation).inc(cost)
            LATENCY_HISTOGRAM.labels(vertical=vertical, operation=operation).observe(duration)

            if not success:
                ERROR_COUNTER.labels(error_type=error or "unknown", vertical=vertical).inc()

        # Track costs for alerting
        self._track_costs(vertical, cost, job_id)

        # Log
        status = "✅" if success else "❌"
        logger.info(
            f"{status} Agent Operation | Vertical: {vertical} | Op: {operation} | "
            f"Cost: ${cost:.4f} | Tokens: {tokens_in + tokens_out} | Time: {duration:.2f}s"
        )

        return metrics

    def record_job_processed(
        self,
        vertical: str,
        status: str,
        rebate_amount: float = 0,
        carbon_avoided_kg: float = 0,
        certificate_tier: Optional[str] = None
    ):
        """Record job completion metrics."""
        if HAS_PROMETHEUS:
            JOBS_PROCESSED.labels(vertical=vertical, status=status).inc()

            if rebate_amount > 0:
                REBATES_CALCULATED.labels(program="total", vertical=vertical).inc(rebate_amount)

            if carbon_avoided_kg > 0:
                CARBON_AVOIDED.labels(vertical=vertical, scope="total").inc(carbon_avoided_kg)

            if certificate_tier:
                CERTIFICATES_GENERATED.labels(vertical=vertical, tier=certificate_tier).inc()

    def record_error(self, error_type: str, vertical: str = "system"):
        """Record an error occurrence."""
        if HAS_PROMETHEUS:
            ERROR_COUNTER.labels(error_type=error_type, vertical=vertical).inc()

    def set_active_jobs(self, vertical: str, count: int):
        """Set the number of active jobs for a vertical."""
        if HAS_PROMETHEUS:
            ACTIVE_JOBS.labels(vertical=vertical).set(count)

    def set_component_health(self, component: str, healthy: bool):
        """Set health status for a component."""
        if HAS_PROMETHEUS:
            SYSTEM_HEALTH.labels(component=component).set(1 if healthy else 0)

    # =========================================================================
    # Cost Tracking & Alerting
    # =========================================================================

    def _track_costs(self, vertical: str, cost: float, job_id: Optional[str] = None):
        """Track costs and check alert thresholds."""
        now = datetime.now(timezone.utc)
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")

        # Hourly tracking
        if hour_key not in self._hourly_costs:
            self._hourly_costs = {hour_key: 0.0}  # Reset old hours
        self._hourly_costs[hour_key] = self._hourly_costs.get(hour_key, 0.0) + cost

        # Daily tracking
        if day_key not in self._daily_costs:
            self._daily_costs = {day_key: 0.0}  # Reset old days
        self._daily_costs[day_key] = self._daily_costs.get(day_key, 0.0) + cost

        # Job tracking
        if job_id:
            self._job_costs[job_id] = self._job_costs.get(job_id, 0.0) + cost

            # Check per-job threshold
            if self._job_costs[job_id] > COST_ALERT_THRESHOLDS["per_job"]:
                asyncio.create_task(self._send_cost_alert(
                    alert_type="per_job",
                    value=self._job_costs[job_id],
                    threshold=COST_ALERT_THRESHOLDS["per_job"],
                    context={"job_id": job_id, "vertical": vertical}
                ))

        # Check hourly threshold
        if self._hourly_costs.get(hour_key, 0) > COST_ALERT_THRESHOLDS["hourly"]:
            asyncio.create_task(self._send_cost_alert(
                alert_type="hourly",
                value=self._hourly_costs[hour_key],
                threshold=COST_ALERT_THRESHOLDS["hourly"],
                context={"hour": hour_key}
            ))

        # Check daily threshold
        if self._daily_costs.get(day_key, 0) > COST_ALERT_THRESHOLDS["daily"]:
            asyncio.create_task(self._send_cost_alert(
                alert_type="daily",
                value=self._daily_costs[day_key],
                threshold=COST_ALERT_THRESHOLDS["daily"],
                context={"day": day_key}
            ))

    async def _send_cost_alert(
        self,
        alert_type: str,
        value: float,
        threshold: float,
        context: Dict[str, Any]
    ):
        """Send cost alert via webhook."""
        if not self.alert_webhook_url:
            logger.warning(f"Cost alert triggered but no webhook configured: {alert_type}=${value:.2f}")
            return

        alert_payload = {
            "alert_type": "cost_threshold_exceeded",
            "severity": "warning" if value < threshold * 1.5 else "critical",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Cost threshold exceeded: {alert_type} cost ${value:.2f} > ${threshold:.2f}",
            "details": {
                "alert_type": alert_type,
                "current_value": value,
                "threshold": threshold,
                "overage_percent": ((value - threshold) / threshold) * 100,
                **context
            }
        }

        try:
            response = await self._client.post(
                self.alert_webhook_url,
                json=alert_payload,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                logger.info(f"Cost alert sent: {alert_type}=${value:.2f}")
            else:
                logger.error(f"Failed to send cost alert: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending cost alert: {e}")

    # =========================================================================
    # Job Tracing (OpenTelemetry)
    # =========================================================================

    def start_job_trace(self, job_id: str, company_id: str, vertical: str) -> JobTrace:
        """Start a new job trace."""
        trace_obj = JobTrace(
            job_id=job_id,
            company_id=company_id,
            vertical=vertical,
            fsm_closed_at=datetime.now(timezone.utc)
        )

        self._active_traces[job_id] = trace_obj

        if self.enable_tracing and HAS_OPENTELEMETRY:
            # Create OpenTelemetry span
            with self._tracer.start_as_current_span(f"job_{job_id}") as span:
                span.set_attribute("job.id", job_id)
                span.set_attribute("company.id", company_id)
                span.set_attribute("vertical", vertical)

        logger.info(f"Started job trace: {job_id}")
        return trace_obj

    def update_job_trace(
        self,
        job_id: str,
        stage: str,
        tokens: int = 0,
        cost: float = 0,
        **kwargs
    ):
        """Update a job trace with stage completion."""
        if job_id not in self._active_traces:
            return

        trace_obj = self._active_traces[job_id]
        now = datetime.now(timezone.utc)

        # Update timestamps based on stage
        stage_timestamps = {
            "audit_started": "audit_started_at",
            "compliance_checked": "compliance_checked_at",
            "rebates_calculated": "rebates_calculated_at",
            "approval_requested": "approval_requested_at",
            "approval_received": "approval_received_at",
            "certificate_generated": "certificate_generated_at"
        }

        if stage in stage_timestamps:
            setattr(trace_obj, stage_timestamps[stage], now)

        # Update totals
        trace_obj.total_tokens += tokens
        trace_obj.total_cost_usd += cost

        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(trace_obj, key):
                setattr(trace_obj, key, value)

    def complete_job_trace(self, job_id: str) -> Optional[JobTrace]:
        """Complete a job trace and calculate totals."""
        if job_id not in self._active_traces:
            return None

        trace_obj = self._active_traces[job_id]

        # Calculate total duration
        if trace_obj.fsm_closed_at and trace_obj.certificate_generated_at:
            delta = trace_obj.certificate_generated_at - trace_obj.fsm_closed_at
            trace_obj.total_duration_seconds = delta.total_seconds()

        # Remove from active traces
        del self._active_traces[job_id]

        logger.info(
            f"Completed job trace: {job_id} | "
            f"Duration: {trace_obj.total_duration_seconds:.1f}s | "
            f"Cost: ${trace_obj.total_cost_usd:.4f}"
        )

        return trace_obj

    # =========================================================================
    # Health Checks
    # =========================================================================

    def register_health_check(self, name: str, check_func: Callable[[], bool]):
        """Register a health check function."""
        self._health_checks[name] = check_func

    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all health checks and return results."""
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_healthy": True,
            "checks": {}
        }

        for name, check_func in self._health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    healthy = await check_func()
                else:
                    healthy = check_func()

                results["checks"][name] = {
                    "healthy": healthy,
                    "status": "ok" if healthy else "failing"
                }

                self.set_component_health(name, healthy)

                if not healthy:
                    results["overall_healthy"] = False

            except Exception as e:
                results["checks"][name] = {
                    "healthy": False,
                    "status": "error",
                    "error": str(e)
                }
                results["overall_healthy"] = False
                self.set_component_health(name, False)

        return results

    async def automated_health_check(self, interval_seconds: int = 60):
        """Run automated health checks on an interval."""
        while True:
            results = await self.run_health_checks()

            if not results["overall_healthy"] and self.alert_webhook_url:
                await self._send_health_alert(results)

            await asyncio.sleep(interval_seconds)

    async def _send_health_alert(self, health_results: Dict[str, Any]):
        """Send health alert via webhook."""
        failing_checks = [
            name for name, result in health_results["checks"].items()
            if not result["healthy"]
        ]

        alert_payload = {
            "alert_type": "health_check_failed",
            "severity": "critical",
            "timestamp": health_results["timestamp"],
            "message": f"Health checks failing: {', '.join(failing_checks)}",
            "details": health_results
        }

        try:
            await self._client.post(
                self.alert_webhook_url,
                json=alert_payload
            )
        except Exception as e:
            logger.error(f"Failed to send health alert: {e}")

    # =========================================================================
    # Metrics Export
    # =========================================================================

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics."""
        now = datetime.now(timezone.utc)
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")

        return {
            "timestamp": now.isoformat(),
            "costs": {
                "current_hour": self._hourly_costs.get(hour_key, 0.0),
                "current_day": self._daily_costs.get(day_key, 0.0),
                "active_jobs": len(self._job_costs)
            },
            "traces": {
                "active": len(self._active_traces)
            },
            "thresholds": COST_ALERT_THRESHOLDS
        }

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


# =========================================================================
# Context Manager for Operation Timing
# =========================================================================

class MonitoredOperation:
    """Context manager for monitoring agent operations."""

    def __init__(
        self,
        monitor: SystemMonitor,
        vertical: str,
        operation: str,
        model: str = "claude-sonnet-4-20250514",
        job_id: Optional[str] = None
    ):
        self.monitor = monitor
        self.vertical = vertical
        self.operation = operation
        self.model = model
        self.job_id = job_id
        self.start_time = None
        self.tokens_in = 0
        self.tokens_out = 0

    def __enter__(self):
        self.start_time = time.time()
        if HAS_PROMETHEUS:
            ACTIVE_JOBS.labels(vertical=self.vertical).inc()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        success = exc_type is None
        error = str(exc_val) if exc_val else None

        self.monitor.record_agent_operation(
            vertical=self.vertical,
            operation=self.operation,
            model=self.model,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            duration=duration,
            job_id=self.job_id,
            success=success,
            error=error
        )

        if HAS_PROMETHEUS:
            ACTIVE_JOBS.labels(vertical=self.vertical).dec()

    def set_tokens(self, tokens_in: int, tokens_out: int):
        """Set token counts from API response."""
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out


# =========================================================================
# Global Monitor Instance
# =========================================================================

_monitor: Optional[SystemMonitor] = None


def get_monitor() -> SystemMonitor:
    """Get or create the global monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = SystemMonitor()
    return _monitor


def init_monitoring(
    metrics_port: int = 9464,
    alert_webhook_url: Optional[str] = None,
    enable_tracing: bool = True
) -> SystemMonitor:
    """Initialize the monitoring system."""
    global _monitor
    _monitor = SystemMonitor(
        metrics_port=metrics_port,
        alert_webhook_url=alert_webhook_url,
        enable_tracing=enable_tracing
    )
    _monitor.start_metrics_server()
    return _monitor


# =========================================================================
# Entry Point for Standalone Metrics Server
# =========================================================================

if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)

    monitor = init_monitoring(
        metrics_port=9464,
        alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL")
    )

    # Register default health checks
    monitor.register_health_check("database", lambda: True)  # Replace with real check
    monitor.register_health_check("api", lambda: True)

    print("ProofGreen Metrics Server started on port 9464")
    print("Prometheus metrics available at http://localhost:9464/metrics")

    # Run health check loop
    asyncio.run(monitor.automated_health_check(interval_seconds=60))
