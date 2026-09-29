"""Reliability framework containing CircuitBreakers, Retries, and Rate Limits."""

import time
import logging
from enum import Enum
from functools import wraps
from typing import Callable, Any, Type, Optional
import asyncio

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failing, fast-fail requests
    HALF_OPEN = "HALF_OPEN"# Testing recovery


class CircuitBreakerError(Exception):
    """Raised when the circuit is OPEN."""
    pass


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time: Optional[float] = None

    def record_success(self):
        """Record a successful execution, reset failures if half-open."""
        if self.state == CircuitState.HALF_OPEN or self.failures > 0:
            logger.info(f"CircuitBreaker[{self.name}] recovered. State -> CLOSED")
            self.state = CircuitState.CLOSED
            self.failures = 0
            self.last_failure_time = None

    def record_failure(self):
        """Record a failure, potentially tripping the circuit."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Immediate trip back to open if it fails while half-open
            logger.warning(f"CircuitBreaker[{self.name}] failed during HALF_OPEN. State -> OPEN")
            self.state = CircuitState.OPEN
            
        elif self.state == CircuitState.CLOSED and self.failures >= self.failure_threshold:
            logger.error(f"CircuitBreaker[{self.name}] threshold reached ({self.failures}). State -> OPEN")
            self.state = CircuitState.OPEN

    def check_state(self):
        """Check the current state and transition HALF_OPEN if timeout passed."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"CircuitBreaker[{self.name}] timeout passed. State -> HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerError(f"Circuit {self.name} is OPEN.")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Wrap an async function call with circuit breaker logic."""
        self.check_state()
        
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            # Do not count expected business errors (like validation) as circuit breaker faults.
            # We can expand this, but for now any unhandled Exception trips it.
            if isinstance(e, CircuitBreakerError):
                raise
            self.record_failure()
            raise


# Global registry for circuit breakers
circuit_breakers: dict[str, CircuitBreaker] = {}

def get_circuit_breaker(name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0) -> CircuitBreaker:
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(name, failure_threshold, recovery_timeout)
    return circuit_breakers[name]


def with_retry(max_retries: int = 3, delay: float = 1.0, exceptions: tuple[Type[Exception], ...] = (Exception,)):
    """Async decorator for retrying a function upon specific transient exceptions."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Retry limit reached ({max_retries}) for {func.__name__}. Raising {e}")
                        raise
                    logger.warning(f"Transient error in {func.__name__}, retrying {retries}/{max_retries} in {delay}s: {e}")
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
