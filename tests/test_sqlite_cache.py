from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from indic_language_utils.cache import CacheCodec, SQLiteCache


class StringCodec(CacheCodec[str]):
    def encode(self, value: str) -> bytes:
        return json.dumps({"value": value}).encode()

    def decode(self, value: bytes) -> str:
        payload = json.loads(value)
        result = payload["value"]
        if not isinstance(result, str):
            raise TypeError
        return result


@pytest.mark.asyncio
async def test_sqlite_cache_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    first = SQLiteCache(path, StringCodec(), namespace="test")
    await first.set("key", "persistent")

    second = SQLiteCache(path, StringCodec(), namespace="test")
    assert await second.get("key") == "persistent"
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_sqlite_cache_expiry_and_lru_bound(tmp_path: Path) -> None:
    now = 100.0
    cache = SQLiteCache(
        tmp_path / "cache.sqlite3",
        StringCodec(),
        namespace="test",
        max_entries=2,
        default_ttl=10,
        clock=lambda: now,
    )
    await cache.set("a", "A")
    now += 1
    await cache.set("b", "B")
    now += 1
    assert await cache.get("a") == "A"
    now += 1
    await cache.set("c", "C")
    assert await cache.get("b") is None
    assert await cache.get("a") == "A"
    now = 111
    assert await cache.get("a") is None


@pytest.mark.asyncio
async def test_sqlite_namespaces_delete_and_clear_independently(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    first = SQLiteCache(path, StringCodec(), namespace="first")
    second = SQLiteCache(path, StringCodec(), namespace="second")
    await first.set("key", "one")
    await second.set("key", "two")
    assert await first.delete("key")
    assert not await first.delete("key")
    assert await second.get("key") == "two"
    await second.clear()
    assert await second.get("key") is None


@pytest.mark.asyncio
async def test_corrupt_entry_is_removed_and_treated_as_a_miss(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite3"
    cache = SQLiteCache(path, StringCodec(), namespace="test")
    await cache.set("key", "value")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE cache_entries SET value = ? WHERE namespace = ? AND key = ?",
            (b"not-json", "test", "key"),
        )
    assert await cache.get("key") is None
    assert not await cache.delete("key")


@pytest.mark.asyncio
async def test_concurrent_sqlite_writes_stay_bounded(tmp_path: Path) -> None:
    cache = SQLiteCache(tmp_path / "cache.sqlite3", StringCodec(), namespace="test", max_entries=5)
    await asyncio.gather(*(cache.set(f"key-{index}", str(index)) for index in range(20)))
    with sqlite3.connect(cache.path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM cache_entries WHERE namespace = ?", ("test",)
        ).fetchone()
    assert count == (5,)


@pytest.mark.asyncio
async def test_sqlite_bulk_read_write_honors_expiry_and_bound(tmp_path: Path) -> None:
    now = 100.0
    cache = SQLiteCache(
        tmp_path / "cache.sqlite3",
        StringCodec(),
        namespace="test",
        max_entries=2,
        default_ttl=10,
        clock=lambda: now,
    )
    await cache.set_many({"a": "A", "b": "B"})
    assert await cache.get_many(("a", "b", "missing")) == {"a": "A", "b": "B"}

    now = 101.0
    await cache.set_many({"c": "C"})
    assert len(await cache.get_many(("a", "b", "c"))) == 2

    now = 111.0
    assert await cache.get_many(("a", "b", "c")) == {}


@pytest.mark.asyncio
async def test_sqlite_cache_byte_limit_bounds_values(tmp_path: Path) -> None:
    codec = StringCodec()
    small = len(codec.encode("a"))
    cache = SQLiteCache(tmp_path / "cache.sqlite3", codec, namespace="audio", max_bytes=small * 2)
    await cache.set("one", "a")
    await cache.set("two", "a")
    await cache.set("three", "a")
    assert len(await cache.get_many(("one", "two", "three"))) == 2
    await cache.set("huge", "x" * 100)
    assert await cache.get("huge") is None
