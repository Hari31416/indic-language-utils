from __future__ import annotations

from pathlib import Path

import pytest

from indic_language_utils.cache import CacheKeyBuilder, SQLiteCache
from indic_language_utils.config import CacheSettings
from indic_language_utils.errors import AuthenticationError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.translation import (
    TextFormat,
    TranslationClient,
    TranslationOptions,
    TranslationRequest,
    TranslationResult,
    TranslationResultCodec,
    create_translation_cache,
    get_translation_client,
)

from .translation_support import FakeTranslationProvider, router_for

EN = DEFAULT_LANGUAGE_REGISTRY.normalize("en")
HI = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")


@pytest.mark.asyncio
async def test_translation_result_codec_round_trip(tmp_path: Path) -> None:
    provider = FakeTranslationProvider(transform=lambda _: "नतीजा")
    result = await TranslationClient(router_for(provider)).translate(
        TranslationRequest("private source", EN, HI)
    )
    encoded = TranslationResultCodec().encode(result)
    assert b"private source" in encoded
    decoded = TranslationResultCodec().decode(encoded)
    assert decoded == result
    assert decoded.source_text == "private source"

    cache: SQLiteCache[TranslationResult] = SQLiteCache(
        tmp_path / "translations.sqlite3", TranslationResultCodec()
    )
    await cache.set("key", result)
    restored = await cache.get("key")
    assert restored == result
    assert restored is not None
    assert restored.source_text == "private source"


@pytest.mark.asyncio
async def test_translation_client_uses_cache_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "translations.sqlite3"
    keys = CacheKeyBuilder("test")
    first_provider = FakeTranslationProvider(transform=lambda _: "stored translation")
    first_cache: SQLiteCache[TranslationResult] = SQLiteCache(
        path, TranslationResultCodec(), namespace="test"
    )
    request = TranslationRequest("source", EN, HI)
    first = await TranslationClient(
        router_for(first_provider), cache=first_cache, cache_keys=keys
    ).translate(request)
    assert not first.cache.hit

    unavailable = FakeTranslationProvider(
        fail_with=AuthenticationError("provider unavailable", provider="fake")
    )
    restarted_cache: SQLiteCache[TranslationResult] = SQLiteCache(
        path, TranslationResultCodec(), namespace="test"
    )
    second = await TranslationClient(
        router_for(unavailable), cache=restarted_cache, cache_keys=keys
    ).translate(request)
    assert second.text == "stored translation"
    assert second.cache.hit
    assert not unavailable.calls


def test_cache_factory_builds_configured_backends(tmp_path: Path) -> None:
    disabled = create_translation_cache(CacheSettings())
    assert type(disabled).__name__ == "NullCache"
    memory = create_translation_cache(CacheSettings(enabled=True, backend="memory"))
    assert type(memory).__name__ == "MemoryCache"
    sqlite_cache = create_translation_cache(
        CacheSettings(
            enabled=True,
            backend="sqlite",
            path=str(tmp_path / "translations.sqlite3"),
        )
    )
    assert isinstance(sqlite_cache, SQLiteCache)


@pytest.mark.asyncio
async def test_segment_cache_survives_client_restart(tmp_path: Path) -> None:
    from indic_language_utils.config import Settings

    settings = Settings(
        cache=CacheSettings(
            enabled=True,
            backend="sqlite",
            path=str(tmp_path / "translations.sqlite3"),
        )
    )
    options = TranslationOptions(text_format=TextFormat.MARKDOWN)
    first_provider = FakeTranslationProvider(transform=str.upper)
    first_client = get_translation_client(settings, providers=[first_provider])
    await first_client.translate("Keep\nOld\n", EN, HI, options=options)

    restarted_provider = FakeTranslationProvider(transform=str.upper)
    restarted_client = get_translation_client(settings, providers=[restarted_provider])
    result = await restarted_client.translate("Keep\nNew\n", EN, HI, options=options)

    assert result.text == "KEEP\nNEW\n"
    assert not result.cache.hit
    assert restarted_provider.calls == [("New",)]
