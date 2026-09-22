"""HTTP-library-independent retry classification and scheduling."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from .errors import ProviderTimeoutError, RateLimitError, TransientProviderError

T = TypeVar("T")
Delay = Callable[[float], Awaitable[None]]
Random = Callable[[], float]


def _random_value() -> float:
    return float(random.random())


def is_retryable(error: BaseException) -> bool:
    return isinstance(error, (RateLimitError, ProviderTimeoutError, TransientProviderError))


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.25
    max_delay: float = 5.0
    jitter: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.base_delay < 0 or self.max_delay < self.base_delay:
            raise ValueError("Invalid retry policy bounds")
        if not 0 <= self.jitter <= 1:
            raise ValueError("jitter must be between zero and one")

    def delay_for(self, attempt: int, error: BaseException, random_value: float) -> float:
        if isinstance(error, RateLimitError) and error.retry_after is not None:
            return min(max(error.retry_after, 0), self.max_delay)
        raw = min(self.base_delay * float(2 ** max(attempt - 1, 0)), self.max_delay)
        return float(raw * (1.0 - self.jitter + 2.0 * self.jitter * random_value))


async def retry(
    operation: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    *,
    delay: Delay = asyncio.sleep,
    random_value: Random = _random_value,
) -> T:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await operation()
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            if attempt == policy.max_attempts or not is_retryable(exc):
                raise
            await delay(policy.delay_for(attempt, exc, random_value()))
    raise AssertionError("retry loop must return or raise")
