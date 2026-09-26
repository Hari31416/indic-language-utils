"""Provider-neutral asynchronous text to speech client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from ..cache import AsyncCache, CacheKeyBuilder, NullCache, SingleFlight
from ..errors import (
    ConfigurationError,
    MalformedProviderResponseError,
    OutputValidationError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
    UnsupportedLanguageError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageRegistry, LanguageTag
from ..models import CacheMetadata, OperationContext
from ..providers import AsyncLifecycle, CapabilityId, ResourceManager
from ..routing import OrderedRouter, RouteRequirement
from .cache import TTSCacheEntry
from .models import ProviderTTSResult, TTSOptions, TTSRequest, TTSResult
from .protocols import StreamingTTSProvider, TTSProvider
from .streaming import TTSStream

_FALLBACK_ERRORS = (
    RateLimitError,
    ProviderTimeoutError,
    TransientProviderError,
    MalformedProviderResponseError,
    OutputValidationError,
)


class TTSClient:
    def __init__(
        self,
        router: OrderedRouter,
        *,
        cache: AsyncCache[TTSCacheEntry] | None = None,
        cache_keys: CacheKeyBuilder | None = None,
        language_registry: LanguageRegistry | None = None,
    ) -> None:
        self._router = router
        self._cache = cache if cache is not None else NullCache()
        self._cache_keys = cache_keys or CacheKeyBuilder("indic-language-utils")
        self._single_flight: SingleFlight[ProviderTTSResult] = SingleFlight()
        self._language_registry = language_registry or DEFAULT_LANGUAGE_REGISTRY
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

    @asynccontextmanager
    async def stream(
        self,
        *,
        language: LanguageTag | str,
        options: TTSOptions | None = None,
        provider: str | None = None,
        model_id: str | None = None,
    ) -> AsyncIterator[TTSStream]:
        """Open a live text-input, audio-output session."""
        tag = self._language_registry.normalize(language)
        candidates = self._router.candidates(
            RouteRequirement(CapabilityId.TEXT_TO_SPEECH, source=tag)
        )
        for candidate in candidates:
            selected = candidate.provider
            if provider is not None and selected.identity.provider != provider:
                continue
            if not isinstance(selected, StreamingTTSProvider):
                continue
            request_id = OperationContext().request_id
            provider_options = (options or TTSOptions()).for_provider(
                selected.identity.provider, primary=True
            )
            async with selected.open_stream(
                language=tag,
                options=provider_options,
                request_id=request_id,
                model_id=model_id,
            ) as session:
                yield session
            return
        raise ConfigurationError("No configured TTS provider supports streaming")

    async def synthesize(
        self,
        text: str | TTSRequest,
        *,
        language: LanguageTag | str | None = None,
        options: TTSOptions | None = None,
    ) -> TTSResult:
        request = (
            text
            if isinstance(text, TTSRequest)
            else TTSRequest(text, language, options, language_registry=self._language_registry)
        )
        return (await self.synthesize_batch((request,)))[0]

    async def synthesize_batch(self, requests: Sequence[TTSRequest]) -> tuple[TTSResult, ...]:
        if not requests:
            return ()
        results: list[TTSResult] = []
        for request in requests:
            candidates = self._router.candidates(
                RouteRequirement(CapabilityId.TEXT_TO_SPEECH, source=request.language)
            )
            if request.language is None:
                candidates = tuple(
                    candidate
                    for candidate in candidates
                    if getattr(candidate.provider, "supports_unspecified_language", True)
                )
                if not candidates:
                    raise UnsupportedLanguageError(
                        "No configured TTS provider accepts an unspecified language",
                        capability=CapabilityId.TEXT_TO_SPEECH.value,
                    )
            for fallback_count, candidate in enumerate(candidates):
                provider = candidate.provider
                if not isinstance(provider, TTSProvider):
                    continue
                try:
                    provider_options = request.options.for_provider(
                        provider.identity.provider, primary=fallback_count == 0
                    )
                    key = self._key(request, provider, provider_options)
                    cached = await self._cache.get(key)
                    if cached is not None:
                        results.append(
                            TTSResult(
                                cached.audio,
                                cached.audio_format,
                                request.language,
                                provider.identity.provider,
                                cached.model_id,
                                request.context.request_id,
                                None,
                                fallback_count,
                                CacheMetadata(
                                    True, type(self._cache).__name__, self._cache_keys.version
                                ),
                            )
                        )
                        break

                    async def execute(
                        selected: TTSProvider = provider,
                        options: TTSOptions = provider_options,
                        cache_key: str = key,
                        selected_request: TTSRequest = request,
                    ) -> ProviderTTSResult:
                        response = await selected.synthesize_batch(
                            (selected_request.text,),
                            language=selected_request.language,
                            options=options,
                            request_id=selected_request.context.request_id,
                        )
                        if (
                            len(response) != 1
                            or not isinstance(response[0].audio, bytes)
                            or not response[0].audio
                        ):
                            raise OutputValidationError(
                                "TTS provider returned invalid audio",
                                provider=selected.identity.provider,
                                capability=CapabilityId.TEXT_TO_SPEECH.value,
                            )
                        item = response[0]
                        await self._cache.set(
                            cache_key, TTSCacheEntry(item.audio, item.audio_format, item.model_id)
                        )
                        return item

                    item = await self._single_flight.run(key, execute)
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
                            CacheMetadata(
                                False,
                                (
                                    "none"
                                    if isinstance(self._cache, NullCache)
                                    else type(self._cache).__name__
                                ),
                                self._cache_keys.version,
                            ),
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

    def _key(self, request: TTSRequest, provider: TTSProvider, options: TTSOptions) -> str:
        model_resolver = getattr(provider, "model_id_for", None)
        voice_resolver = getattr(provider, "resolve_voice", None)
        if callable(model_resolver):
            model_id = model_resolver(request.language)
        elif callable(voice_resolver):
            model_id = voice_resolver(request.language, options)
        else:
            model_id = None
        config = getattr(provider, "config", None)
        secret = getattr(config, "api_key", None)
        reveal = getattr(secret, "reveal", None)
        credential_hash = self._cache_keys.hash_content(reveal()) if callable(reveal) else None
        return self._cache_keys.build(
            CapabilityId.TEXT_TO_SPEECH.value,
            {
                "text_hash": self._cache_keys.hash_content(request.text),
                "language": str(request.language) if request.language else None,
                "provider": provider.identity.provider,
                "model_id": model_id,
                "options": dict(options.parameters),
                "config_hash": self._cache_keys.hash_content(repr(config)) if config else None,
                "credential_hash": credential_hash,
                "tenant_hash": (
                    self._cache_keys.hash_content(request.context.tenant_id)
                    if request.context.tenant_id
                    else None
                ),
            },
        )
