"""Provider-neutral asynchronous text to speech client."""

from __future__ import annotations

from collections.abc import Sequence

from ..errors import (
    MalformedProviderResponseError,
    OutputValidationError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from ..languages import LanguageTag
from ..providers import AsyncLifecycle, CapabilityId, ResourceManager
from ..routing import OrderedRouter, RouteRequirement
from .models import TTSOptions, TTSRequest, TTSResult
from .protocols import TTSProvider

_FALLBACK_ERRORS = (
    RateLimitError,
    ProviderTimeoutError,
    TransientProviderError,
    MalformedProviderResponseError,
    OutputValidationError,
)


class TTSClient:
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

    async def __aenter__(self) -> TTSClient:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def synthesize(
        self,
        text: str | TTSRequest,
        *,
        language: LanguageTag | str | None = None,
        options: TTSOptions | None = None,
    ) -> TTSResult:
        request = text if isinstance(text, TTSRequest) else TTSRequest(text, language, options)
        return (await self.synthesize_batch((request,)))[0]

    async def synthesize_batch(self, requests: Sequence[TTSRequest]) -> tuple[TTSResult, ...]:
        if not requests:
            return ()
        results: list[TTSResult] = []
        for request in requests:
            candidates = self._router.candidates(
                RouteRequirement(CapabilityId.TEXT_TO_SPEECH, source=request.language)
            )
            for fallback_count, candidate in enumerate(candidates):
                provider = candidate.provider
                if not isinstance(provider, TTSProvider):
                    continue
                try:
                    response = await provider.synthesize_batch(
                        (request.text,),
                        language=request.language,
                        options=request.options,
                        request_id=request.context.request_id,
                    )
                    if (
                        len(response) != 1
                        or not isinstance(response[0].audio, bytes)
                        or not response[0].audio
                    ):
                        raise OutputValidationError(
                            "TTS provider returned invalid audio",
                            provider=provider.identity.provider,
                            capability=CapabilityId.TEXT_TO_SPEECH.value,
                        )
                    item = response[0]
                    results.append(
                        TTSResult(
                            item.audio,
                            item.audio_format,
                            request.language,
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
                    "No TTS provider implements synthesis",
                    capability=CapabilityId.TEXT_TO_SPEECH.value,
                )
        return tuple(results)
