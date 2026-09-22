from __future__ import annotations

import asyncio

import pytest

from indic_language_utils.cache import CacheKeyBuilder, MemoryCache, NullCache, SingleFlight


@pytest.mark.asyncio
async def test_memory_cache_expiry_and_lru() -> None:
    now = 0.0
    cache: MemoryCache[str] = MemoryCache(2, 10, clock=lambda: now)
    await cache.set("a", "A")
    await cache.set("b", "B")
    assert await cache.get("a") == "A"
    await cache.set("c", "C")
    assert await cache.get("b") is None
    now = 11
    assert await cache.get("a") is None


@pytest.mark.asyncio
async def test_null_cache_never_stores() -> None:
    cache: NullCache[str] = NullCache()
    await cache.set("key", "value")
    assert await cache.get("key") is None
    assert not await cache.delete("key")


def test_cache_keys_are_stable_namespaced_and_content_safe() -> None:
    content = "private grievance text"
    material = {"input_hash": CacheKeyBuilder.hash_content(content), "target": "hi-IN"}
    first = CacheKeyBuilder("app", tenant="tenant-a").build("translation", material)
    second = CacheKeyBuilder("app", tenant="tenant-a").build("translation", material)
    other = CacheKeyBuilder("app", tenant="tenant-b").build("translation", material)
    assert first == second
    assert first != other
    assert content not in first
    assert "tenant-a" not in first


@pytest.mark.asyncio
async def test_single_flight_coalesces_and_cleans_up() -> None:
    flight: SingleFlight[str] = SingleFlight()
    gate = asyncio.Event()
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        await gate.wait()
        return "done"

    tasks = [asyncio.create_task(flight.run("same", operation)) for _ in range(5)]
    await asyncio.sleep(0)
    gate.set()
    assert await asyncio.gather(*tasks) == ["done"] * 5
    assert calls == 1
    assert await flight.run("same", operation) == "done"
    assert calls == 2


@pytest.mark.asyncio
async def test_single_flight_waiter_cancellation_does_not_cancel_work() -> None:
    flight: SingleFlight[str] = SingleFlight()
    gate = asyncio.Event()

    async def operation() -> str:
        await gate.wait()
        return "done"

    cancelled = asyncio.create_task(flight.run("same", operation))
    survivor = asyncio.create_task(flight.run("same", operation))
    await asyncio.sleep(0)
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    gate.set()
    assert await survivor == "done"


@pytest.mark.asyncio
async def test_single_flight_exception_cleanup() -> None:
    flight: SingleFlight[str] = SingleFlight()

    async def operation() -> str:
        raise RuntimeError("failure")

    with pytest.raises(RuntimeError):
        await flight.run("key", operation)
    with pytest.raises(RuntimeError):
        await flight.run("key", operation)
