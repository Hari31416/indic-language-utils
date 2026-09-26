"""Async cache contracts, local implementations, keys, and request coalescing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")
Clock = Callable[[], float]


@runtime_checkable
class CacheCodec(Protocol[T]):
    """Encode cache values without tying the cache to pickle or a model library."""

    def encode(self, value: T) -> bytes: ...

    def decode(self, value: bytes) -> T: ...


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


class SQLiteCache(Generic[T]):
    """A persistent, bounded TTL/LRU cache backed by SQLite."""

    def __init__(
        self,
        path: str | Path,
        codec: CacheCodec[T],
        *,
        namespace: str = "indic-language-utils",
        max_entries: int = 10_000,
        default_ttl: float | None = 86_400,
        timeout_seconds: float = 5.0,
        clock: Clock = time.time,
    ) -> None:
        self._path = Path(path).expanduser().resolve()
        if not namespace:
            raise ValueError("Cache namespace cannot be empty")
        if max_entries < 1 or (default_ttl is not None and default_ttl < 0):
            raise ValueError("Cache size must be positive and TTL cannot be negative")
        if timeout_seconds <= 0:
            raise ValueError("SQLite timeout must be positive")
        self._codec = codec
        self._namespace = namespace
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        self._timeout_seconds = timeout_seconds
        self._clock = clock
        self._initialized = False
        self._initialization_lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        return self._path

    async def get(self, key: str) -> T | None:
        await self._ensure_initialized()
        encoded = await asyncio.to_thread(self._get_sync, key)
        if encoded is None:
            return None
        try:
            return self._codec.decode(encoded)
        except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            await self.delete(key)
            return None

    async def get_many(self, keys: Sequence[str]) -> dict[str, T]:
        """Read several entries with one SQLite transaction."""
        if not keys:
            return {}
        await self._ensure_initialized()
        encoded = await asyncio.to_thread(self._get_many_sync, tuple(dict.fromkeys(keys)))
        values: dict[str, T] = {}
        for key, value in encoded.items():
            try:
                values[key] = self._codec.decode(value)
            except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
                await self.delete(key)
        return values

    async def set(self, key: str, value: T, *, ttl: float | None = None) -> None:
        effective_ttl = self._default_ttl if ttl is None else ttl
        if effective_ttl is not None and effective_ttl < 0:
            raise ValueError("TTL cannot be negative")
        encoded = self._codec.encode(value)
        await self._ensure_initialized()
        await asyncio.to_thread(self._set_sync, key, encoded, effective_ttl)

    async def set_many(self, values: Mapping[str, T], *, ttl: float | None = None) -> None:
        """Write several entries and apply the LRU bound in one transaction."""
        if not values:
            return
        effective_ttl = self._default_ttl if ttl is None else ttl
        if effective_ttl is not None and effective_ttl < 0:
            raise ValueError("TTL cannot be negative")
        encoded = {key: self._codec.encode(value) for key, value in values.items()}
        await self._ensure_initialized()
        await asyncio.to_thread(self._set_many_sync, encoded, effective_ttl)

    async def delete(self, key: str) -> bool:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._delete_sync, key)

    async def clear(self) -> None:
        await self._ensure_initialized()
        await asyncio.to_thread(self._clear_sync)

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._initialization_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._initialize_sync)
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=self._timeout_seconds)
        connection.execute(f"PRAGMA busy_timeout = {int(self._timeout_seconds * 1_000)}")
        return connection

    def _initialize_sync(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self._path.exists()
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value BLOB NOT NULL,
                    expires_at REAL,
                    accessed_at REAL NOT NULL,
                    PRIMARY KEY (namespace, key)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS cache_entries_expiry
                ON cache_entries (namespace, expires_at)
                """
            )
        if is_new:
            os.chmod(self._path, 0o600)

    def _get_sync(self, key: str) -> bytes | None:
        now = self._clock()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT value, expires_at FROM cache_entries
                WHERE namespace = ? AND key = ?
                """,
                (self._namespace, key),
            ).fetchone()
            if row is None:
                return None
            value, expires_at = row
            if expires_at is not None and expires_at <= now:
                connection.execute(
                    "DELETE FROM cache_entries WHERE namespace = ? AND key = ?",
                    (self._namespace, key),
                )
                return None
            connection.execute(
                """
                UPDATE cache_entries SET accessed_at = ?
                WHERE namespace = ? AND key = ?
                """,
                (now, self._namespace, key),
            )
            return bytes(value)

    def _get_many_sync(self, keys: tuple[str, ...]) -> dict[str, bytes]:
        now = self._clock()
        results: dict[str, bytes] = {}
        with self._connect() as connection:
            for offset in range(0, len(keys), 400):
                group = keys[offset : offset + 400]
                placeholders = ",".join("?" for _ in group)
                rows = connection.execute(
                    f"SELECT key, value, expires_at FROM cache_entries "
                    f"WHERE namespace = ? AND key IN ({placeholders})",
                    (self._namespace, *group),
                ).fetchall()
                live_keys: list[str] = []
                expired_keys: list[str] = []
                for key, value, expires_at in rows:
                    if expires_at is not None and expires_at <= now:
                        expired_keys.append(key)
                    else:
                        live_keys.append(key)
                        results[key] = bytes(value)
                if live_keys:
                    live_placeholders = ",".join("?" for _ in live_keys)
                    connection.execute(
                        f"UPDATE cache_entries SET accessed_at = ? "
                        f"WHERE namespace = ? AND key IN ({live_placeholders})",
                        (now, self._namespace, *live_keys),
                    )
                if expired_keys:
                    expired_placeholders = ",".join("?" for _ in expired_keys)
                    connection.execute(
                        f"DELETE FROM cache_entries "
                        f"WHERE namespace = ? AND key IN ({expired_placeholders})",
                        (self._namespace, *expired_keys),
                    )
        return results

    def _set_sync(self, key: str, value: bytes, ttl: float | None) -> None:
        now = self._clock()
        expires_at = None if ttl is None else now + ttl
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM cache_entries WHERE namespace = ? AND expires_at <= ?",
                (self._namespace, now),
            )
            connection.execute(
                """
                INSERT INTO cache_entries (namespace, key, value, expires_at, accessed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value = excluded.value,
                    expires_at = excluded.expires_at,
                    accessed_at = excluded.accessed_at
                """,
                (self._namespace, key, value, expires_at, now),
            )
            connection.execute(
                """
                DELETE FROM cache_entries
                WHERE namespace = ? AND key IN (
                    SELECT key FROM cache_entries
                    WHERE namespace = ?
                    ORDER BY accessed_at DESC, key DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (self._namespace, self._namespace, self._max_entries),
            )

    def _set_many_sync(self, values: Mapping[str, bytes], ttl: float | None) -> None:
        now = self._clock()
        expires_at = None if ttl is None else now + ttl
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM cache_entries WHERE namespace = ? AND expires_at <= ?",
                (self._namespace, now),
            )
            connection.executemany(
                """
                INSERT INTO cache_entries (namespace, key, value, expires_at, accessed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value = excluded.value,
                    expires_at = excluded.expires_at,
                    accessed_at = excluded.accessed_at
                """,
                ((self._namespace, key, value, expires_at, now) for key, value in values.items()),
            )
            connection.execute(
                """
                DELETE FROM cache_entries
                WHERE namespace = ? AND key IN (
                    SELECT key FROM cache_entries
                    WHERE namespace = ?
                    ORDER BY accessed_at DESC, key DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (self._namespace, self._namespace, self._max_entries),
            )

    def _delete_sync(self, key: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM cache_entries WHERE namespace = ? AND key = ?",
                (self._namespace, key),
            )
            return cursor.rowcount > 0

    def _clear_sync(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM cache_entries WHERE namespace = ?", (self._namespace,))


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
