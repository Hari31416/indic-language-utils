"""Gnani REST speech transcription adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    InvalidInputError,
    MalformedProviderResponseError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..providers.gnani import GnaniConfig
from ..retry import retry
from .gnani_stream import GnaniSTTStream, open_gnani_stt_stream
from .models import ProviderSTTResult


class GnaniSTTProvider:
    identity = ProviderIdentity("gnani", "Gnani AI")
    capabilities: tuple[CapabilityDeclaration, ...] = (
        CapabilityDeclaration(
            CapabilityId.SPEECH_TO_TEXT,
            languages=frozenset(
                DEFAULT_LANGUAGE_REGISTRY.normalize(code)
                for code in ("bn", "en", "gu", "hi", "kn", "ml", "mr", "pa", "ta", "te")
            ),
        ),
    )

    def __init__(self, config: GnaniConfig, *, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client
        self._owns_client = client is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)

    @asynccontextmanager
    async def open_stream(
        self,
        *,
        language: LanguageTag | None,
        sampling_rate: int,
        request_id: str,
        model_id: str | None = None,
    ) -> AsyncIterator[GnaniSTTStream]:
        async with self._limiter.slot("gnani", CapabilityId.SPEECH_TO_TEXT):
            async with open_gnani_stt_stream(
                self.config, language=language, sampling_rate=sampling_rate, request_id=request_id
            ) as stream:
                yield stream

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient()

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

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
                "Gnani STT audio cannot be empty", provider="gnani", request_id=request_id
            )
        if language is None:
            raise InvalidInputError(
                "Gnani STT requires a BCP 47 language", provider="gnani", request_id=request_id
            )
        client = self._client
        owns_call_client = client is None
        if client is None:
            client = httpx.AsyncClient()
        try:
            results: list[ProviderSTTResult] = []
            for clip in audio:

                async def send(clip: bytes = clip) -> httpx.Response:
                    try:
                        async with self._limiter.slot("gnani", CapabilityId.SPEECH_TO_TEXT):
                            response = await client.post(
                                f"{self.config.endpoint.rstrip('/')}/stt/v3",
                                headers={"X-API-Key-ID": self.config.api_key.reveal()},
                                data={"language_code": str(language), "format": "transcribe"},
                                files={"audio_file": (f"audio.{audio_format}", clip)},
                                timeout=self.config.timeout_seconds,
                            )
                    except httpx.TimeoutException as exc:
                        raise ProviderTimeoutError(
                            "Gnani STT timed out", provider="gnani", request_id=request_id
                        ) from exc
                    except httpx.TransportError as exc:
                        raise TransientProviderError(
                            "Gnani STT transport failed", provider="gnani", request_id=request_id
                        ) from exc
                    if response.status_code == 429:
                        raise RateLimitError(
                            "Gnani STT rate limit exceeded", provider="gnani", request_id=request_id
                        )
                    if response.status_code >= 500:
                        raise TransientProviderError(
                            "Gnani STT request failed", provider="gnani", request_id=request_id
                        )
                    if response.status_code >= 400:
                        raise InvalidInputError(
                            "Gnani rejected the STT request",
                            provider="gnani",
                            request_id=request_id,
                        )
                    return response

                response = await retry(send, self.config.retry_policy)
                try:
                    data: object = response.json()
                except ValueError as exc:
                    raise MalformedProviderResponseError(
                        "Gnani returned malformed STT JSON", provider="gnani", request_id=request_id
                    ) from exc
                if not isinstance(data, Mapping) or not isinstance(data.get("transcript"), str):
                    raise MalformedProviderResponseError(
                        "Gnani returned a malformed STT response",
                        provider="gnani",
                        request_id=request_id,
                    )
                response_id = data.get("request_id")
                results.append(
                    ProviderSTTResult(
                        data["transcript"],
                        "gnani-stt",
                        response_id if isinstance(response_id, str) else None,
                    )
                )
            return tuple(results)
        finally:
            if owns_call_client:
                await client.aclose()
