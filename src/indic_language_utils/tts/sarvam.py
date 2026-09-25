"""Sarvam JSON text to speech adapter."""

from __future__ import annotations

import base64
import binascii
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ..concurrency import ConcurrencyLimiter
from ..errors import InvalidInputError, MalformedProviderResponseError, UnsupportedLanguageError
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..providers.bhashini import JsonResponse, JsonTransport, _header
from ..providers.sarvam import (
    SarvamConfig,
    SarvamJsonTransport,
    _raise_sarvam_status,
    sarvam_language_code,
)
from ..retry import retry
from .bhashini import _audio_format
from .models import ProviderTTSResult, TTSOptions
from .sarvam_stream import SarvamTTSStream, open_sarvam_tts_stream

_TTS_LANGUAGES = frozenset({"bn", "en", "gu", "hi", "kn", "ml", "mr", "or", "pa", "ta", "te"})
_RESERVED = {"text", "language_code", "model"}


class SarvamTTSProvider:
    identity = ProviderIdentity("sarvam", "Sarvam AI")
    supports_unspecified_language = False
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(self, config: SarvamConfig, *, transport: JsonTransport | None = None) -> None:
        self.config = config
        self._transport = transport
        self._owns_transport = transport is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = (
            frozenset(
                item.tag
                for item in DEFAULT_LANGUAGE_REGISTRY.definitions()
                if item.tag.language in _TTS_LANGUAGES
            )
            if config.tts_model_id
            else frozenset(DEFAULT_LANGUAGE_REGISTRY.normalize(key) for key in config.tts_model_ids)
        )
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TEXT_TO_SPEECH, languages=languages),
        )

    async def start(self) -> None:
        if self._transport is None:
            self._transport = SarvamJsonTransport()

    async def close(self) -> None:
        if self._transport is not None and self._owns_transport:
            await self._transport.close()
            self._transport = None

    def model_id_for(self, language: LanguageTag | None) -> str:
        tag = str(DEFAULT_LANGUAGE_REGISTRY.normalize(language)) if language else None
        model_id = (self.config.tts_model_ids.get(tag) if tag else None) or self.config.tts_model_id
        if not model_id:
            raise UnsupportedLanguageError(
                "No Sarvam TTS model is configured for this language",
                provider="sarvam",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                details={"language": tag or "unspecified"},
            )
        return model_id

    @asynccontextmanager
    async def open_stream(
        self,
        *,
        language: LanguageTag,
        options: TTSOptions,
        request_id: str,
        model_id: str | None = None,
    ) -> AsyncIterator[SarvamTTSStream]:
        selected = model_id or self.model_id_for(language)
        async with self._limiter.slot("sarvam", CapabilityId.TEXT_TO_SPEECH):
            async with open_sarvam_tts_stream(
                self.config,
                language=language,
                options=options,
                model_id=selected,
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
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise InvalidInputError(
                "Sarvam TTS text cannot be empty", provider="sarvam", request_id=request_id
            )
        if language is None:
            raise InvalidInputError(
                "Sarvam TTS requires a language", provider="sarvam", request_id=request_id
            )
        if language.language not in _TTS_LANGUAGES:
            raise UnsupportedLanguageError(
                "Sarvam TTS does not support this language",
                provider="sarvam",
                request_id=request_id,
            )
        if _RESERVED.intersection(options.parameters):
            raise InvalidInputError(
                "Sarvam TTS options cannot override text, model, or language_code",
                provider="sarvam",
                request_id=request_id,
            )
        model_id = self.model_id_for(language)
        transport = self._transport
        owns_call_transport = transport is None
        if transport is None:
            transport = SarvamJsonTransport()
        results: list[ProviderTTSResult] = []
        try:
            for text in texts:
                payload = dict(options.parameters)
                payload.update(
                    {
                        "text": text,
                        "model": model_id,
                        "language_code": sarvam_language_code(language),
                    }
                )

                async def send(payload: dict[str, object] = payload) -> JsonResponse:
                    async with self._limiter.slot("sarvam", CapabilityId.TEXT_TO_SPEECH):
                        response = await transport.post(
                            f"{self.config.endpoint.rstrip('/')}/text-to-speech",
                            headers={"api-subscription-key": self.config.api_key.reveal()},
                            json=payload,
                            timeout_seconds=self.config.timeout_seconds,
                        )
                    _raise_sarvam_status(
                        "sarvam", CapabilityId.TEXT_TO_SPEECH, response, request_id
                    )
                    return response

                response = await retry(send, self.config.retry_policy)
                try:
                    data = response.data
                    if not isinstance(data, dict):
                        raise TypeError
                    audios = data["audios"]
                    if (
                        not isinstance(audios, list)
                        or len(audios) != 1
                        or not isinstance(audios[0], str)
                    ):
                        raise TypeError
                    raw = base64.b64decode(audios[0], validate=True)
                    if not raw:
                        raise ValueError
                except (KeyError, TypeError, ValueError, binascii.Error) as exc:
                    raise MalformedProviderResponseError(
                        "Sarvam returned a malformed TTS response",
                        provider="sarvam",
                        capability=CapabilityId.TEXT_TO_SPEECH.value,
                        request_id=request_id,
                    ) from exc
                response_id = data.get("request_id")
                results.append(
                    ProviderTTSResult(
                        raw,
                        _audio_format(raw, payload.get("output_audio_codec")),
                        model_id,
                        response_id
                        if isinstance(response_id, str)
                        else _header(response.headers, "x-request-id"),
                    )
                )
            return tuple(results)
        finally:
            if owns_call_transport:
                await transport.close()
