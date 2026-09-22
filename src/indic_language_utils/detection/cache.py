"""Persistent cache support for language detection results."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..cache import AsyncCache, CacheCodec, MemoryCache, NullCache, SQLiteCache
from ..config import CacheSettings
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import CacheMetadata, WarningInfo
from .models import (
    DetectionProviderMetadata,
    DetectionResult,
    LanguageCandidate,
)


class DetectionResultCodec(CacheCodec[DetectionResult]):
    """Versioned JSON encoding for persistent language detection results."""

    schema_version = 1

    def encode(self, value: DetectionResult) -> bytes:
        payload = {
            "schema_version": self.schema_version,
            "language": str(value.language) if value.language is not None else None,
            "candidates": [
                {
                    "language": str(candidate.language),
                    "confidence": candidate.confidence,
                    "script": candidate.script,
                }
                for candidate in value.candidates
            ],
            "script": value.script,
            "provider": {
                "provider": value.provider.provider,
                "model_id": value.provider.model_id,
                "request_id": value.provider.request_id,
                "unofficial": value.provider.unofficial,
            },
            "request_id": value.request_id,
            "elapsed_seconds": value.elapsed_seconds,
            "cache": {
                "hit": value.cache.hit,
                "backend": value.cache.backend,
                "key_version": value.cache.key_version,
            },
            "fallback_count": value.fallback_count,
            "warnings": [
                {"code": warning.code, "message": warning.message} for warning in value.warnings
            ],
            "source_text": value.source_text,
        }
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def decode(self, value: bytes) -> DetectionResult:
        payload = _mapping(json.loads(value.decode("utf-8")))
        if payload.get("schema_version") != self.schema_version:
            raise ValueError("Unsupported detection cache schema")
        provider = _mapping(payload["provider"])
        cache = _mapping(payload["cache"])
        warning_values = _list(payload["warnings"])
        candidate_values = _list(payload["candidates"])
        raw_lang = _optional_string(payload.get("language"))
        if raw_lang is None:
            language: LanguageTag | None = None
        elif raw_lang in DEFAULT_LANGUAGE_REGISTRY:
            language = DEFAULT_LANGUAGE_REGISTRY.normalize(raw_lang)
        else:
            try:
                language = LanguageTag.parse(raw_lang)
            except Exception:
                language = LanguageTag(raw_lang.strip().lower())

        candidates = tuple(
            LanguageCandidate(
                language=_string(_mapping(c)["language"]),
                confidence=_number(_mapping(c)["confidence"]),
                script=_optional_string(_mapping(c).get("script")),
            )
            for c in candidate_values
        )
        return DetectionResult(
            language=language,
            candidates=candidates,
            script=_optional_string(payload.get("script")),
            provider=DetectionProviderMetadata(
                provider=_string(provider["provider"]),
                model_id=_optional_string(provider.get("model_id")),
                request_id=_optional_string(provider.get("request_id")),
                unofficial=_boolean(provider["unofficial"]),
            ),
            request_id=_string(payload["request_id"]),
            elapsed_seconds=_number(payload["elapsed_seconds"]),
            cache=CacheMetadata(
                hit=_boolean(cache["hit"]),
                backend=_string(cache["backend"]),
                key_version=_integer(cache["key_version"]),
            ),
            fallback_count=_integer(payload["fallback_count"]),
            warnings=tuple(
                WarningInfo(_string(_mapping(item)["code"]), _string(_mapping(item)["message"]))
                for item in warning_values
            ),
            source_text=_string(payload.get("source_text", "")),
        )


def create_detection_cache(settings: CacheSettings) -> AsyncCache[DetectionResult]:
    """Build a configured detection cache matching configuration."""
    if not settings.enabled or settings.backend == "null":
        return NullCache()
    if settings.backend == "memory":
        return MemoryCache(settings.max_entries, settings.ttl_seconds)
    if settings.backend == "sqlite":
        return SQLiteCache(
            Path(settings.path),
            DetectionResultCodec(),
            namespace=settings.namespace,
            max_entries=settings.max_entries,
            default_ttl=settings.ttl_seconds,
        )
    raise ValueError(f"Unsupported cache backend: {settings.backend}")


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Expected a JSON object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("Expected a JSON array")
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected a string")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _string(value)


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError("Expected a boolean")
    return value


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("Expected an integer")
    return value


def _number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError("Expected a number")
    return float(value)
