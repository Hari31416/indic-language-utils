"""Async cache contracts, local implementations, keys, and request coalescing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

T = TypeVar("T")
Clock = Callable[[], float]


class AsyncCache(Protocol[T]):
    async def get(self, key: str) -> T | None: ...

    async def set(self, key: str, value: T, *, ttl: float | None = None) -> None: ...

    async def delete(self, key: str) -> bool: ...

    async def clear(self) -> None: ...


class NullCache(Generic[T]):
    async def get(self, key: str) -> T | None:
        return None

    async def set(self, key: str, value: T, *, ttl: float | None = None) -> None:
        return None

    async def delete(self, key: str) -> bool:
        return False

    async def clear(self) -> None:
        return None


@dataclass(slots=True)
class _Entry(Generic[T]):
    value: T
    expires_at: float | None


class MemoryCache(Generic[T]):
    """A process-local, bounded TTL cache with least-recently-used eviction."""

    def __init__(
        self,
        max_entries: int = 1024,
        default_ttl: float | None = 300,
        *,
        clock: Clock = time.monotonic,
    ) -> None:
        if max_entries < 1 or (default_ttl is not None and default_ttl < 0):
            raise ValueError("Cache size must be positive and TTL cannot be negative")
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._clock = clock
        self._entries: OrderedDict[str, _Entry[T]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at is not None and entry.expires_at <= self._clock():
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return entry.value

    async def set(self, key: str, value: T, *, ttl: float | None = None) -> None:
        effective_ttl = self._default_ttl if ttl is None else ttl
        if effective_ttl is not None and effective_ttl < 0:
            raise ValueError("TTL cannot be negative")
        expires_at = None if effective_ttl is None else self._clock() + effective_ttl
        async with self._lock:
            self._entries[key] = _Entry(value, expires_at)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            return self._entries.pop(key, None) is not None

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()


@dataclass(frozen=True, slots=True)
class CacheKeyBuilder:
    namespace: str
    tenant: str | None = None
    version: int = 1

    def build(self, capability: str, material: Mapping[str, object]) -> str:
        if not self.namespace or self.version < 1:
            raise ValueError("Cache namespace cannot be empty and version must be positive")
        envelope = {
            "version": self.version,
            "capability": capability,
            "material": material,
        }
        encoded = json.dumps(
            envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        boundary = (
            hashlib.sha256(self.tenant.encode()).hexdigest()[:16] if self.tenant else "shared"
        )
        return f"{self.namespace}:{boundary}:v{self.version}:{capability}:{digest}"

    @staticmethod
    def hash_content(content: str | bytes) -> str:
        raw = content.encode() if isinstance(content, str) else content
        return hashlib.sha256(raw).hexdigest()


class SingleFlight(Generic[T]):
    """Coalesce concurrent calls by key without letting a waiter cancel shared work."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[T]] = {}
        self._lock = asyncio.Lock()

    async def run(self, key: str, operation: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            task = self._tasks.get(key)
            if task is None:
                task = asyncio.create_task(self._invoke(operation))
                self._tasks[key] = task
                task.add_done_callback(self._callback(key))
        return await asyncio.shield(task)

    async def _invoke(self, operation: Callable[[], Awaitable[T]]) -> T:
        return await operation()

    def _callback(self, key: str) -> Callable[[asyncio.Task[T]], None]:
        def done(task: asyncio.Task[T]) -> None:
            self._remove(key, task)

        return done

    def _remove(self, key: str, task: asyncio.Task[T]) -> None:
        if self._tasks.get(key) is task:
            del self._tasks[key]
        if not task.cancelled():
            task.exception()
