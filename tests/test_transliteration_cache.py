from __future__ import annotations

from pathlib import Path

import pytest

from indic_language_utils.cache import MemoryCache, NullCache, SQLiteCache
from indic_language_utils.config import CacheSettings
from indic_language_utils.languages import LanguageTag
from indic_language_utils.models import CacheMetadata, WarningInfo
from indic_language_utils.transliteration.cache import (
    TransliterationResultCodec,
    create_transliteration_cache,
)
from indic_language_utils.transliteration.models import (
    TransliterationProviderMetadata,
    TransliterationResult,
)


def test_transliteration_result_codec_roundtrip() -> None:
    codec = TransliterationResultCodec()
    result = TransliterationResult(
        text="नमस्ते",
        source=LanguageTag("en"),
        target=LanguageTag("hi"),
        provider=TransliterationProviderMetadata(
            provider="bhashini",
            service_id="svc-1",
            model_id="ai4bharat/indicxlit",
            provider_request_id="req-p1",
            unofficial=False,
        ),
        request_id="req-123",
        elapsed_seconds=0.1234,
        cache=CacheMetadata(hit=False, backend="memory", key_version=1),
        fallback_count=1,
        warnings=(WarningInfo("code1", "warning message"),),
        source_text="namaste",
    )

    encoded = codec.encode(result)
    assert isinstance(encoded, bytes)

    decoded = codec.decode(encoded)
    assert decoded.text == result.text
    assert decoded.source == result.source
    assert decoded.target == result.target
    assert decoded.provider.provider == "bhashini"
    assert decoded.provider.service_id == "svc-1"
    assert decoded.provider.model_id == "ai4bharat/indicxlit"
    assert decoded.provider.provider_request_id == "req-p1"
    assert decoded.provider.unofficial is False
    assert decoded.request_id == "req-123"
    assert decoded.elapsed_seconds == 0.1234
    assert decoded.cache.hit is False
    assert decoded.fallback_count == 1
    assert len(decoded.warnings) == 1
    assert decoded.warnings[0].code == "code1"
    assert decoded.source_text == "namaste"


def test_create_transliteration_cache(tmp_path: Path) -> None:
    # Disabled / Null
    null_cache = create_transliteration_cache(CacheSettings(enabled=False))
    assert isinstance(null_cache, NullCache)

    # Memory
    mem_cache = create_transliteration_cache(CacheSettings(enabled=True, backend="memory"))
    assert isinstance(mem_cache, MemoryCache)

    # SQLite
    db_path = str(tmp_path / "test_cache.sqlite3")
    sqlite_cache = create_transliteration_cache(
        CacheSettings(enabled=True, backend="sqlite", path=db_path)
    )
    assert isinstance(sqlite_cache, SQLiteCache)

    # Unsupported
    with pytest.raises(ValueError):
        create_transliteration_cache(CacheSettings(enabled=True, backend="redis"))


@pytest.mark.asyncio
async def test_transliteration_memory_cache_get_set() -> None:
    cache = MemoryCache[TransliterationResult](max_entries=10, default_ttl=300.0)
    result = TransliterationResult(
        text="नमस्ते",
        source=LanguageTag("en"),
        target=LanguageTag("hi"),
        provider=TransliterationProviderMetadata("mock"),
        request_id="req-1",
        elapsed_seconds=0.05,
        cache=CacheMetadata(False, "memory", 1),
    )

    assert await cache.get("k1") is None
    await cache.set("k1", result)
    cached = await cache.get("k1")
    assert cached is not None
    assert cached.text == "नमस्ते"
