"""
ProofGreen MAS - Retry Utilities
Exponential backoff retry logic for external service calls.
"""

import asyncio
import random
from typing import Callable, TypeVar, Any, List, Type
from functools import wraps
from dataclasses import dataclass
import structlog


logger = structlog.get_logger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)


def calculate_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    Calculate delay for next retry attempt.

    Uses exponential backoff with optional jitter.
    """
    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add random jitter (0-25% of delay)
        delay = delay * (1 + random.random() * 0.25)

    return delay


async def retry_async(
    func: Callable[..., Any],
    *args,
    config: RetryConfig = None,
    on_retry: Callable[[int, Exception], None] = None,
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        config: Retry configuration
        on_retry: Callback called on each retry
        **kwargs: Keyword arguments for func

    Returns:
        Result of successful function call

    Raises:
        Last exception if all retries fail
    """
    config = config or RetryConfig()
    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)

        except config.retryable_exceptions as e:
            last_exception = e

            if attempt < config.max_attempts - 1:
                delay = calculate_delay(attempt, config)

                logger.warning(
                    "retry_attempt",
                    function=func.__name__,
                    attempt=attempt + 1,
                    max_attempts=config.max_attempts,
                    delay=delay,
                    error=str(e)
                )

                if on_retry:
                    on_retry(attempt + 1, e)

                await asyncio.sleep(delay)
            else:
                logger.error(
                    "retry_exhausted",
                    function=func.__name__,
                    max_attempts=config.max_attempts,
                    error=str(e)
                )

    raise last_exception


def retry_sync(
    func: Callable[..., T],
    *args,
    config: RetryConfig = None,
    on_retry: Callable[[int, Exception], None] = None,
    **kwargs
) -> T:
    """
    Retry a sync function with exponential backoff.
    """
    import time

    config = config or RetryConfig()
    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return func(*args, **kwargs)

        except config.retryable_exceptions as e:
            last_exception = e

            if attempt < config.max_attempts - 1:
                delay = calculate_delay(attempt, config)

                logger.warning(
                    "retry_attempt",
                    function=func.__name__,
                    attempt=attempt + 1,
                    max_attempts=config.max_attempts,
                    delay=delay,
                    error=str(e)
                )

                if on_retry:
                    on_retry(attempt + 1, e)

                time.sleep(delay)
            else:
                logger.error(
                    "retry_exhausted",
                    function=func.__name__,
                    max_attempts=config.max_attempts,
                    error=str(e)
                )

    raise last_exception


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator to add retry logic to async functions.

    Usage:
        @with_retry(max_attempts=3, retryable_exceptions=(httpx.HTTPError,))
        async def fetch_data():
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(func, *args, config=config, **kwargs)
        return wrapper

    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern for external services.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests fail fast
    - HALF_OPEN: Testing if service has recovered
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_requests: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self.state = self.CLOSED
        self.failures = 0
        self.last_failure_time = 0
        self.half_open_successes = 0

    async def call(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        """Execute function through circuit breaker."""
        import time

        # Check if we should transition from OPEN to HALF_OPEN
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info("circuit_breaker_half_open")
                self.state = self.HALF_OPEN
                self.half_open_successes = 0
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker is open. Retry after {self.recovery_timeout}s"
                )

        try:
            result = await func(*args, **kwargs)

            # Success - update state
            if self.state == self.HALF_OPEN:
                self.half_open_successes += 1
                if self.half_open_successes >= self.half_open_requests:
                    logger.info("circuit_breaker_closed")
                    self.state = self.CLOSED
                    self.failures = 0

            return result

        except Exception as e:
            self._record_failure()
            raise

    def _record_failure(self):
        """Record a failure and potentially open the circuit."""
        import time

        self.failures += 1
        self.last_failure_time = time.time()

        if self.state == self.HALF_OPEN:
            logger.warning("circuit_breaker_reopened")
            self.state = self.OPEN
        elif self.failures >= self.failure_threshold:
            logger.warning(
                "circuit_breaker_opened",
                failures=self.failures,
                threshold=self.failure_threshold
            )
            self.state = self.OPEN


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass
