"""Provider-neutral asynchronous speech transcription client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from ..errors import (
    ConfigurationError,
    MalformedProviderResponseError,
    OutputValidationError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import OperationContext
from ..providers import AsyncLifecycle, CapabilityId, ResourceManager
from ..routing import OrderedRouter, RouteRequirement
from .models import STTRequest, STTResult
from .protocols import StreamingSTTProvider, STTProvider
from .streaming import STTStream

_FALLBACK_ERRORS = (
    RateLimitError,
    ProviderTimeoutError,
    TransientProviderError,
    MalformedProviderResponseError,
    OutputValidationError,
)


class STTClient:
    def __init__(self, router: OrderedRouter) -> None:
        self._router = router
        self._resources: ResourceManager | None = None

    @property
    def router(self) -> OrderedRouter:
        return self._router

    async def start(self) -> None:
        resources: list[AsyncLifecycle] = [
            provider
            for provider in self._router.registry.all()
            if isinstance(provider, AsyncLifecycle)
        ]
        if resources:
            self._resources = ResourceManager(*resources)
            await self._resources.start()

    async def close(self) -> None:
        if self._resources is not None:
            await self._resources.close()
            self._resources = None

    async def __aenter__(self) -> STTClient:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @asynccontextmanager
    async def stream(
        self,
        *,
        language: LanguageTag | str | None = None,
        sampling_rate: int = 16000,
        provider: str | None = None,
        model_id: str | None = None,
    ) -> AsyncIterator[STTStream]:
        """Open one live PCM session; the chosen provider stays fixed for its lifetime."""
        if sampling_rate <= 0:
            raise ValueError("Sampling rate must be positive")
        tag = DEFAULT_LANGUAGE_REGISTRY.normalize(language) if language else None
        candidates = self._router.candidates(
            RouteRequirement(CapabilityId.SPEECH_TO_TEXT, source=tag)
        )
        for candidate in candidates:
            selected = candidate.provider
            if provider is not None and selected.identity.provider != provider:
                continue
            if not isinstance(selected, StreamingSTTProvider):
                continue
            request_id = OperationContext().request_id
            async with selected.open_stream(
                language=tag,
                sampling_rate=sampling_rate,
                request_id=request_id,
                model_id=model_id,
            ) as session:
                yield session
            return
        raise ConfigurationError("No configured STT provider supports streaming")

    async def transcribe(
        self,
        audio: bytes | STTRequest,
        *,
        language: LanguageTag | str | None = None,
        audio_format: str = "wav",
        sampling_rate: int = 16000,
    ) -> STTResult:
        if isinstance(audio, STTRequest):
            request = audio
        else:
            request = STTRequest(audio, language, audio_format, sampling_rate)
        return (await self.transcribe_batch((request,)))[0]

    async def transcribe_batch(self, requests: Sequence[STTRequest]) -> tuple[STTResult, ...]:
        if not requests:
            return ()
        # Bhashini can batch only audio with identical task configuration.
        results: list[STTResult] = []
        for request in requests:
            language = (
                DEFAULT_LANGUAGE_REGISTRY.normalize(request.language)
                if request.language is not None
                else None
            )
            candidates = self._router.candidates(
                RouteRequirement(CapabilityId.SPEECH_TO_TEXT, source=language)
            )
            for fallback_count, candidate in enumerate(candidates):
                provider = candidate.provider
                if not isinstance(provider, STTProvider):
                    continue
                try:
                    response = await provider.transcribe_batch(
                        (request.audio,),
                        language=language,
                        audio_format=request.audio_format,
                        sampling_rate=request.sampling_rate,
                        request_id=request.context.request_id,
                    )
                    if len(response) != 1 or not isinstance(response[0].text, str):
                        raise OutputValidationError(
                            "STT provider returned invalid output",
                            provider=provider.identity.provider,
                            capability=CapabilityId.SPEECH_TO_TEXT.value,
                        )
                    item = response[0]
                    results.append(
                        STTResult(
                            item.text,
                            language or item.detected_language,
                            provider.identity.provider,
                            item.model_id,
                            request.context.request_id,
                            item.request_id,
                            fallback_count,
                        )
                    )
                    break
                except _FALLBACK_ERRORS:
                    if fallback_count == len(candidates) - 1:
                        raise
            else:
                raise OutputValidationError(
                    "No STT provider implements transcription",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                )
        return tuple(results)
