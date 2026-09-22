from __future__ import annotations

from pathlib import Path

import pytest

from indic_language_utils.cache import MemoryCache, NullCache, SQLiteCache
from indic_language_utils.config import CacheSettings
from indic_language_utils.detection.cache import DetectionResultCodec, create_detection_cache
from indic_language_utils.detection.models import (
    DetectionProviderMetadata,
    DetectionResult,
    LanguageCandidate,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.models import CacheMetadata, WarningInfo


def sample_detection_result() -> DetectionResult:
    return DetectionResult(
        language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        candidates=(
            LanguageCandidate(DEFAULT_LANGUAGE_REGISTRY.normalize("hi"), 0.92, script="Deva"),
            LanguageCandidate(DEFAULT_LANGUAGE_REGISTRY.normalize("mr"), 0.08, script="Deva"),
        ),
        script="Deva",
        provider=DetectionProviderMetadata("fasttext", "lid.176.ftz", "req-123", False),
        request_id="req-123",
        elapsed_seconds=0.015,
        cache=CacheMetadata(False, "none", 1),
        fallback_count=0,
        warnings=(WarningInfo("test_code", "test_message"),),
        source_text="नमस्ते दुनिया",
    )


def test_detection_codec_round_trip() -> None:
    codec = DetectionResultCodec()
    original = sample_detection_result()
    encoded = codec.encode(original)
    decoded = codec.decode(encoded)

    assert decoded.language == original.language
    assert decoded.script == original.script
    assert len(decoded.candidates) == 2
    assert decoded.candidates[0].language == original.candidates[0].language
    assert pytest.approx(decoded.candidates[0].confidence) == original.candidates[0].confidence
    assert decoded.candidates[0].script == "Deva"
    assert decoded.provider == original.provider
    assert decoded.request_id == original.request_id
    assert decoded.elapsed_seconds == original.elapsed_seconds
    assert decoded.fallback_count == original.fallback_count
    assert decoded.warnings == original.warnings
    assert decoded.source_text == original.source_text


def test_detection_codec_with_none_language() -> None:
    codec = DetectionResultCodec()
    result = DetectionResult(
        language=None,
        candidates=(),
        script=None,
        provider=DetectionProviderMetadata("fasttext"),
        request_id="req-none",
        elapsed_seconds=0.01,
        cache=CacheMetadata(False, "none", 1),
    )
    encoded = codec.encode(result)
    decoded = codec.decode(encoded)
    assert decoded.language is None
    assert decoded.candidates == ()
    assert decoded.script is None


def test_detection_codec_rejects_invalid_schema() -> None:
    codec = DetectionResultCodec()
    with pytest.raises(ValueError, match="Unsupported detection cache schema"):
        codec.decode(b'{"schema_version": 999}')


def test_create_detection_cache_null() -> None:
    cache = create_detection_cache(CacheSettings(enabled=False))
    assert isinstance(cache, NullCache)


def test_create_detection_cache_memory() -> None:
    cache = create_detection_cache(CacheSettings(enabled=True, backend="memory"))
    assert isinstance(cache, MemoryCache)


def test_create_detection_cache_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "detection_cache.sqlite3"
    cache = create_detection_cache(CacheSettings(enabled=True, backend="sqlite", path=str(db_path)))
    assert isinstance(cache, SQLiteCache)


@pytest.mark.asyncio
async def test_detection_sqlite_cache_persistence(tmp_path: Path) -> None:
    db_path = tmp_path / "test_detect.sqlite3"
    cache = create_detection_cache(CacheSettings(enabled=True, backend="sqlite", path=str(db_path)))
    result = sample_detection_result()
    await cache.set("key-1", result)

    cached = await cache.get("key-1")
    assert cached is not None
    assert cached.language == result.language
    assert cached.source_text == result.source_text


def test_detection_codec_non_registry_languages() -> None:
    codec = DetectionResultCodec()
    result = DetectionResult(
        language=None,
        candidates=(
            LanguageCandidate("hi", 0.85, script="Deva"),
            LanguageCandidate("bh", 0.10, script="Deva"),
            LanguageCandidate("es", 0.05, script="Latn"),
        ),
        script="Deva",
        provider=DetectionProviderMetadata("fasttext"),
        request_id="req-non-reg",
        elapsed_seconds=0.01,
        cache=CacheMetadata(False, "none", 1),
    )
    encoded = codec.encode(result)
    decoded = codec.decode(encoded)

    assert len(decoded.candidates) == 3
    assert str(decoded.candidates[0].language) == "hi-IN"
    assert str(decoded.candidates[1].language) == "bh"
    assert str(decoded.candidates[2].language) == "es"
