"""Sarvam multipart speech transcription adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    InvalidInputError,
    MalformedProviderResponseError,
    ProviderTimeoutError,
    TransientProviderError,
    UnsupportedLanguageError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..providers.bhashini import JsonResponse, _header
from ..providers.sarvam import SarvamConfig, _raise_sarvam_status, sarvam_language_code
from ..retry import retry
from .models import ProviderSTTResult
from .sarvam_stream import SarvamSTTStream, open_sarvam_stt_stream


class SarvamSTTProvider:
    identity = ProviderIdentity("sarvam", "Sarvam AI")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(self, config: SarvamConfig, *, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client
        self._owns_client = client is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = (
            frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
            if config.stt_model_id
            else frozenset(DEFAULT_LANGUAGE_REGISTRY.normalize(key) for key in config.stt_model_ids)
        )
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.SPEECH_TO_TEXT, languages=languages),
        )

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient()

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def model_id_for(self, language: LanguageTag | None) -> str:
        tag = str(DEFAULT_LANGUAGE_REGISTRY.normalize(language)) if language else None
        model_id = (self.config.stt_model_ids.get(tag) if tag else None) or self.config.stt_model_id
        if not model_id:
            raise UnsupportedLanguageError(
                "No Sarvam STT model is configured for this language",
                provider="sarvam",
                capability=CapabilityId.SPEECH_TO_TEXT.value,
                details={"language": tag or "unspecified"},
            )
        return model_id

    @asynccontextmanager
    async def open_stream(
        self,
        *,
        language: LanguageTag | None,
        sampling_rate: int,
        request_id: str,
        model_id: str | None = None,
    ) -> AsyncIterator[SarvamSTTStream]:
        configured = self.model_id_for(language)
        selected = model_id or (configured if configured == "saaras:v4" else "saaras:v3-realtime")
        async with self._limiter.slot("sarvam", CapabilityId.SPEECH_TO_TEXT):
            async with open_sarvam_stt_stream(
                self.config,
                language=language,
                sampling_rate=sampling_rate,
                model_id=selected,
                request_id=request_id,
            ) as stream:
                yield stream

    async def transcribe_batch(
        self,
        audio: tuple[bytes, ...],
        *,
        language: LanguageTag | None,
        audio_format: str,
        sampling_rate: int,
        request_id: str,
    ) -> tuple[ProviderSTTResult, ...]:
        if not audio or any(not isinstance(item, bytes) or not item for item in audio):
            raise InvalidInputError(
                "Sarvam STT audio cannot be empty", provider="sarvam", request_id=request_id
            )
        model_id = self.model_id_for(language)
        client = self._client
        owns_call_client = client is None
        if client is None:
            client = httpx.AsyncClient()
        results: list[ProviderSTTResult] = []
        try:
            for clip in audio:
                form = {"model": model_id, "mode": "transcribe"}
                if language is not None:
                    form["language_code"] = sarvam_language_code(language)

                async def send(form: dict[str, str] = form, clip: bytes = clip) -> JsonResponse:
                    async with self._limiter.slot("sarvam", CapabilityId.SPEECH_TO_TEXT):
                        try:
                            response = await client.post(
                                f"{self.config.endpoint.rstrip('/')}/speech-to-text",
                                headers={"api-subscription-key": self.config.api_key.reveal()},
                                data=form,
                                files={"file": (f"audio.{audio_format}", clip)},
                                timeout=self.config.timeout_seconds,
                            )
                        except httpx.TimeoutException as exc:
                            raise ProviderTimeoutError(
                                "Sarvam STT timed out", provider="sarvam"
                            ) from exc
                        except httpx.TransportError as exc:
                            raise TransientProviderError(
                                "Sarvam STT transport failed", provider="sarvam"
                            ) from exc
                    try:
                        data: object = response.json()
                    except ValueError:
                        data = None
                    wrapped = JsonResponse(response.status_code, data, response.headers)
                    _raise_sarvam_status("sarvam", CapabilityId.SPEECH_TO_TEXT, wrapped, request_id)
                    return wrapped

                response = await retry(send, self.config.retry_policy)
                data = response.data
                if not isinstance(data, Mapping) or not isinstance(data.get("transcript"), str):
                    raise MalformedProviderResponseError(
                        "Sarvam returned a malformed STT response",
                        provider="sarvam",
                        capability=CapabilityId.SPEECH_TO_TEXT.value,
                        request_id=request_id,
                    )
                response_id = data.get("request_id")
                raw_language = data.get("language_code")
                detected_language = (
                    DEFAULT_LANGUAGE_REGISTRY.normalize(raw_language)
                    if isinstance(raw_language, str) and raw_language != "unknown"
                    else None
                )
                results.append(
                    ProviderSTTResult(
                        data["transcript"],
                        model_id,
                        response_id
                        if isinstance(response_id, str)
                        else _header(response.headers, "x-request-id"),
                        detected_language,
                    )
                )
            return tuple(results)
        finally:
            if owns_call_client:
                await client.aclose()
