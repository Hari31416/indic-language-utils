from __future__ import annotations

import asyncio

import pytest

from indic_language_utils.concurrency import ConcurrencyLimiter
from indic_language_utils.errors import AuthenticationError, ProviderTimeoutError, RateLimitError
from indic_language_utils.providers import CapabilityId
from indic_language_utils.retry import RetryPolicy, retry


@pytest.mark.asyncio
async def test_retry_uses_injected_delay_and_recovers() -> None:
    attempts = 0
    delays: list[float] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ProviderTimeoutError("safe")
        return "ok"

    async def delay(seconds: float) -> None:
        delays.append(seconds)

    result = await retry(operation, RetryPolicy(base_delay=1, jitter=0), delay=delay)
    assert result == "ok"
    assert delays == [1, 2]


@pytest.mark.asyncio
async def test_retry_after_is_bounded() -> None:
    attempts = 0
    delays: list[float] = []

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise RateLimitError("limited", retry_after=100)

    async def delay(seconds: float) -> None:
        delays.append(seconds)

    with pytest.raises(RateLimitError):
        await retry(operation, RetryPolicy(max_attempts=2, max_delay=3), delay=delay)
    assert delays == [3]


@pytest.mark.asyncio
async def test_non_retryable_error_is_immediate() -> None:
    attempts = 0

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise AuthenticationError("bad credentials")

    with pytest.raises(AuthenticationError):
        await retry(operation, RetryPolicy())
    assert attempts == 1


@pytest.mark.asyncio
async def test_retry_propagates_cancellation() -> None:
    async def operation() -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await retry(operation, RetryPolicy())


@pytest.mark.asyncio
async def test_concurrency_limit() -> None:
    limiter = ConcurrencyLimiter(2)
    active = peak = 0
    gate = asyncio.Event()

    async def worker() -> None:
        nonlocal active, peak
        async with limiter.slot("fake", CapabilityId.TRANSLATION):
            active += 1
            peak = max(peak, active)
            await gate.wait()
            active -= 1

    tasks = [asyncio.create_task(worker()) for _ in range(4)]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert peak == 2
    gate.set()
    await asyncio.gather(*tasks)
