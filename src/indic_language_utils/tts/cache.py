"""Bounded cache values for complete text to speech results."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from pathlib import Path

from ..cache import AsyncCache, CacheCodec, MemoryCache, NullCache, SQLiteCache
from ..config import CacheSettings


@dataclass(frozen=True, slots=True)
class TTSCacheEntry:
    audio: bytes
    audio_format: str | None
    model_id: str | None


class TTSCacheEntryCodec(CacheCodec[TTSCacheEntry]):
    schema_version = 1

    def encode(self, value: TTSCacheEntry) -> bytes:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "audio_base64": base64.b64encode(value.audio).decode("ascii"),
                "audio_format": value.audio_format,
                "model_id": value.model_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def decode(self, value: bytes) -> TTSCacheEntry:
        payload = json.loads(value.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != self.schema_version:
            raise ValueError("Unsupported TTS cache schema")
        raw_audio = payload["audio_base64"]
        if not isinstance(raw_audio, str):
            raise TypeError("TTS cache audio must be base64 text")
        try:
            audio = base64.b64decode(raw_audio, validate=True)
        except binascii.Error as exc:
            raise ValueError("Invalid cached TTS audio") from exc
        if not audio:
            raise ValueError("Cached TTS audio cannot be empty")
        audio_format = payload.get("audio_format")
        model_id = payload.get("model_id")
        if audio_format is not None and not isinstance(audio_format, str):
            raise TypeError("TTS cache format must be text")
        if model_id is not None and not isinstance(model_id, str):
            raise TypeError("TTS cache model must be text")
        return TTSCacheEntry(audio, audio_format, model_id)


def create_tts_cache(settings: CacheSettings) -> AsyncCache[TTSCacheEntry]:
    """Create an opt-in TTS cache with an audio byte budget."""
    if not settings.enabled or settings.backend == "null":
        return NullCache()
    if settings.backend == "memory":
        return MemoryCache(
            settings.max_entries,
            settings.ttl_seconds,
            max_bytes=settings.tts_max_bytes,
            value_size=lambda entry: len(entry.audio),
        )
    if settings.backend == "sqlite":
        return SQLiteCache(
            Path(settings.path),
            TTSCacheEntryCodec(),
            namespace=f"{settings.namespace}:tts",
            max_entries=settings.max_entries,
            max_bytes=settings.tts_max_bytes,
            default_ttl=settings.ttl_seconds,
        )
    raise ValueError(f"Unsupported cache backend: {settings.backend}")
