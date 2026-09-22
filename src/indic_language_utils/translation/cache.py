"""Persistent cache support for translation results."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..cache import AsyncCache, CacheCodec, MemoryCache, NullCache, SQLiteCache
from ..config import CacheSettings
from ..languages import DEFAULT_LANGUAGE_REGISTRY
from ..models import CacheMetadata, WarningInfo
from .models import TranslationProviderMetadata, TranslationResult


class TranslationResultCodec(CacheCodec[TranslationResult]):
    """Versioned JSON encoding for persistent translation results."""

    schema_version = 1

    def encode(self, value: TranslationResult) -> bytes:
        payload = {
            "schema_version": self.schema_version,
            "text": value.text,
            "source": str(value.source),
            "target": str(value.target),
            "provider": {
                "provider": value.provider.provider,
                "service_id": value.provider.service_id,
                "model_id": value.provider.model_id,
                "provider_request_id": value.provider.provider_request_id,
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
        }
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def decode(self, value: bytes) -> TranslationResult:
        payload = _mapping(json.loads(value.decode("utf-8")))
        if payload.get("schema_version") != self.schema_version:
            raise ValueError("Unsupported translation cache schema")
        provider = _mapping(payload["provider"])
        cache = _mapping(payload["cache"])
        warning_values = _list(payload["warnings"])
        return TranslationResult(
            text=_string(payload["text"]),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize(_string(payload["source"])),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize(_string(payload["target"])),
            provider=TranslationProviderMetadata(
                provider=_string(provider["provider"]),
                service_id=_optional_string(provider.get("service_id")),
                model_id=_optional_string(provider.get("model_id")),
                provider_request_id=_optional_string(provider.get("provider_request_id")),
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
        )


def create_translation_cache(settings: CacheSettings) -> AsyncCache[TranslationResult]:
    """Build a configured translation cache without changing the opt-in default."""
    if not settings.enabled or settings.backend == "null":
        return NullCache()
    if settings.backend == "memory":
        return MemoryCache(settings.max_entries, settings.ttl_seconds)
    if settings.backend == "sqlite":
        return SQLiteCache(
            Path(settings.path),
            TranslationResultCodec(),
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
