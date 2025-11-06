"""Retry and circuit breaker utilities for the forex signal agent."""

import asyncio
import random
from functools import wraps
from typing import Callable, Type, Tuple, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

logger = logging.getLogger(__name__)


def circuit_breaker_decorator(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_failures: int = 5,
    timeout: int = 60
):
    """
    Circuit breaker decorator to prevent cascade failures.
    """
    def decorator(func):
        failures = 0
        last_failure_time = 0
        open_state = False

        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal failures, last_failure_time, open_state

            # Check if circuit is open
            if open_state:
                current_time = asyncio.get_event_loop().time()
                if current_time - last_failure_time >= timeout:
                    # Half-open state: allow one trial
                    try:
                        result = await func(*args, **kwargs)
                        # Success, close the circuit
                        open_state = False
                        failures = 0
                        return result
                    except exceptions:
                        # Failure, keep circuit open
                        last_failure_time = current_time
                        raise
                else:
                    # Still in open state, raise exception
                    logger.warning(f"Circuit breaker open for {func.__name__}, failing fast")
                    raise Exception(f"Circuit breaker open for {func.__name__}")

            # Circuit is closed, execute normally
            try:
                result = await func(*args, **kwargs)
                # Reset failures on success
                failures = 0
                return result
            except exceptions as e:
                failures += 1
                if failures >= max_failures:
                    # Open the circuit
                    open_state = True
                    last_failure_time = asyncio.get_event_loop().time()
                    logger.error(f"Circuit breaker opened for {func.__name__} after {failures} failures")
                raise e
        return wrapper
    return decorator


def retryable_async(
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0
):
    """
    Decorator for async functions that adds retry logic with exponential backoff.
    """
    def decorator(func):
        @wraps(func)
        @retry(
            retry=retry_if_exception_type(retry_exceptions),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=base_delay,
                min=base_delay,
                max=max_delay,
                exp_base=exponential_base
            )
        )
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator