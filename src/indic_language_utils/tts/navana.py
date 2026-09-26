"""Navana Bodhi non-streaming text-to-speech adapter."""

from __future__ import annotations

import json
import logging
import struct
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    AuthenticationError,
    InvalidInputError,
    MalformedProviderResponseError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
    UnsupportedLanguageError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..providers.navana import NavanaConfig
from ..retry import retry
from .models import ProviderTTSResult, TTSOptions
from .navana_stream import open_navana_tts_stream
from .streaming import TTSStream

logger = logging.getLogger(__name__)
_LANGUAGES = frozenset({"bn", "en", "gu", "hi", "kn", "ml", "mr", "or", "ta", "te"})
_RESERVED = {"text", "lang"}


class NavanaTTSProvider:
    identity = ProviderIdentity("navana", "Navana AI")
    supports_unspecified_language = True
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: NavanaConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client
        self._owns_client = client is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = frozenset(
            item.tag
            for item in DEFAULT_LANGUAGE_REGISTRY.definitions()
            if item.tag.language in _LANGUAGES
        )
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TEXT_TO_SPEECH, languages=languages),
        )

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient()

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    @asynccontextmanager
    async def open_stream(
        self,
        *,
        language: LanguageTag,
        options: TTSOptions,
        request_id: str,
        model_id: str | None = None,
    ) -> AsyncIterator[TTSStream]:
        if language.language not in _LANGUAGES:
            raise UnsupportedLanguageError(
                "Navana TTS does not support this language",
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            )
        async with self._limiter.slot("navana", CapabilityId.TEXT_TO_SPEECH):
            async with open_navana_tts_stream(
                self.config,
                language=language,
                options=(
                    TTSOptions({**options.parameters, "voice": model_id}) if model_id else options
                ),
                request_id=request_id,
            ) as stream:
                yield stream

    async def synthesize_batch(
        self,
        texts: tuple[str, ...],
        *,
        language: LanguageTag | None,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]:
        if (
            not texts
            or any(not isinstance(text, str) or not text.strip() for text in texts)
            or any(len(text) > 10000 for text in texts)
        ):
            raise InvalidInputError(
                "Navana TTS text cannot be empty",
                provider="navana",
                request_id=request_id,
            )
        if language is not None and language.language not in _LANGUAGES:
            raise UnsupportedLanguageError(
                "Navana TTS does not support this language",
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            )
        if _RESERVED.intersection(options.parameters):
            raise InvalidInputError(
                "Navana TTS options cannot override text or lang",
                provider="navana",
                request_id=request_id,
            )

        client = self._client
        owns_call_client = client is None
        if client is None:
            client = httpx.AsyncClient()
        results: list[ProviderTTSResult] = []
        try:
            for text in texts:
                payload = dict(options.parameters)
                payload.setdefault("output_format", "24000:pcm16")
                payload["text"] = text
                if language is not None:
                    payload["lang"] = language.language

                async def send(payload: dict[str, object] = payload) -> httpx.Response:
                    try:
                        async with self._limiter.slot("navana", CapabilityId.TEXT_TO_SPEECH):
                            return await client.post(
                                f"{self.config.endpoint.rstrip('/')}/tts/bytes",
                                headers={
                                    "X-API-Key": self.config.api_key.reveal(),
                                    "Content-Type": "application/json",
                                },
                                json=payload,
                                timeout=self.config.timeout_seconds,
                            )
                    except httpx.TimeoutException as exc:
                        raise ProviderTimeoutError(
                            "Navana request timed out", provider="navana", request_id=request_id
                        ) from exc
                    except httpx.TransportError as exc:
                        raise TransientProviderError(
                            "Navana transport failed", provider="navana", request_id=request_id
                        ) from exc

                response = await retry(send, self.config.retry_policy)
                self._raise_status(response, request_id)
                encoding = response.headers.get("x-encoding", "pcm16").lower()
                audio = response.content
                if not audio:
                    raise MalformedProviderResponseError(
                        "Navana returned empty audio",
                        provider="navana",
                        capability=CapabilityId.TEXT_TO_SPEECH.value,
                        request_id=request_id,
                    )
                try:
                    sample_rate = _sample_rate(response.headers.get("x-sample-rate"))
                    wrapped = _wav(audio, sample_rate, encoding)
                except (ValueError, struct.error) as exc:
                    raise MalformedProviderResponseError(
                        "Navana returned malformed PCM audio",
                        provider="navana",
                        capability=CapabilityId.TEXT_TO_SPEECH.value,
                        request_id=request_id,
                    ) from exc
                results.append(
                    ProviderTTSResult(
                        wrapped,
                        "wav",
                        None,
                        response.headers.get("x-request-id"),
                    )
                )
            return tuple(results)
        finally:
            if owns_call_client:
                await client.aclose()

    @staticmethod
    def _raise_status(response: httpx.Response, request_id: str) -> None:
        if response.status_code < 400:
            return
        logger.warning("Navana request failed with status %d", response.status_code)
        detail = ""
        try:
            body = response.json()
            if isinstance(body, Mapping) and isinstance(body.get("error"), str):
                detail = body["error"].strip()[:300]
        except (json.JSONDecodeError, ValueError):
            pass
        message = f"Navana request failed: {detail}" if detail else "Navana request failed"
        if response.status_code == 401:
            raise AuthenticationError(
                "Navana authentication failed" + (f": {detail}" if detail else ""),
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            )
        if response.status_code == 429:
            raise RateLimitError(
                message,
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            )
        if response.status_code in {408, 504}:
            raise ProviderTimeoutError(
                message,
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            )
        if response.status_code >= 500:
            raise TransientProviderError(
                message,
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            )
        raise InvalidInputError(
            message,
            provider="navana",
            capability=CapabilityId.TEXT_TO_SPEECH.value,
            request_id=request_id,
        )


def _sample_rate(value: str | None) -> int:
    try:
        sample_rate = int(value or "24000")
    except ValueError as exc:
        raise ValueError("Invalid sample rate") from exc
    if sample_rate not in {8000, 16000, 24000}:
        raise ValueError("Unsupported sample rate")
    return sample_rate


def _wav(pcm: bytes, sample_rate: int, encoding: str) -> bytes:
    if encoding == "pcm16":
        if len(pcm) % 2:
            raise ValueError("16-bit PCM must contain complete samples")
        byte_rate, block_align, bits, format_code = sample_rate * 2, 2, 16, 1
    elif encoding == "float32":
        if len(pcm) % 4:
            raise ValueError("32-bit float PCM must contain complete samples")
        byte_rate, block_align, bits, format_code = sample_rate * 4, 4, 32, 3
    else:
        raise ValueError("Unsupported Navana audio encoding")
    if len(pcm) > 0xFFFFFFFF - 36:
        raise ValueError("Audio is too large for a WAV container")
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        format_code,
        1,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        len(pcm),
    )
    return header + pcm
