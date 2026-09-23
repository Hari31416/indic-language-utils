"""Canonical asynchronous transliteration client."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import replace
from typing import cast, overload

from ..cache import AsyncCache, CacheKeyBuilder, NullCache, SingleFlight
from ..errors import (
    MalformedProviderResponseError,
    OutputValidationError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from ..languages import LanguageTag
from ..models import CacheMetadata, OperationContext, WarningInfo
from ..providers import AsyncLifecycle, CapabilityId, ResourceManager
from ..routing import OrderedRouter, RouteRequirement
from ..telemetry import EventLogger, MetricHook, NoOpMetrics, NoOpTracing, TraceHook
from .models import (
    TransliterationOptions,
    TransliterationProviderMetadata,
    TransliterationRequest,
    TransliterationResult,
)
from .protocols import TransliterationProvider

_FALLBACK_ERRORS = (
    RateLimitError,
    ProviderTimeoutError,
    TransientProviderError,
    MalformedProviderResponseError,
    OutputValidationError,
)


class TransliterationClient:
    def __init__(
        self,
        router: OrderedRouter,
        *,
        cache: AsyncCache[TransliterationResult] | None = None,
        cache_keys: CacheKeyBuilder | None = None,
        logger: EventLogger | None = None,
        metrics: MetricHook | None = None,
        tracing: TraceHook | None = None,
    ) -> None:
        self._router = router
        self._cache = cache or NullCache()
        self._cache_keys = cache_keys or CacheKeyBuilder("indic-language-utils")
        self._logger = logger
        self._metrics = metrics or NoOpMetrics()
        self._tracing = tracing or NoOpTracing()
        self._single_flight: SingleFlight[TransliterationResult] = SingleFlight()
        self._resources: ResourceManager | None = None

    @property
    def router(self) -> OrderedRouter:
        return self._router

    async def start(self) -> None:
        lifecycles: list[AsyncLifecycle] = [
            provider
            for provider in self._router.registry.all()
            if isinstance(provider, AsyncLifecycle)
        ]
        if lifecycles:
            self._resources = ResourceManager(*lifecycles)
            await self._resources.start()

    async def close(self) -> None:
        if self._resources is not None:
            await self._resources.close()
            self._resources = None

    async def __aenter__(self) -> TransliterationClient:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @overload
    async def transliterate(self, request: TransliterationRequest, /) -> TransliterationResult: ...

    @overload
    async def transliterate(
        self,
        text: str,
        /,
        *,
        source: LanguageTag | str,
        target: LanguageTag | str,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> TransliterationResult: ...

    async def transliterate(
        self,
        request_or_text: TransliterationRequest | str,
        *,
        source: LanguageTag | str | None = None,
        target: LanguageTag | str | None = None,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> TransliterationResult:
        if isinstance(request_or_text, TransliterationRequest):
            request = request_or_text
        else:
            if source is None or target is None:
                raise ValueError("source and target are required when providing text as string")
            request = TransliterationRequest(
                request_or_text, source=source, target=target, options=options, context=context
            )
        return (await self.transliterate_batch((request,)))[0]

    @overload
    async def transliterate_batch(
        self,
        requests: Sequence[TransliterationRequest],
        /,
    ) -> tuple[TransliterationResult, ...]: ...

    @overload
    async def transliterate_batch(
        self,
        texts: Sequence[str],
        /,
        *,
        source: LanguageTag | str,
        target: LanguageTag | str,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[TransliterationResult, ...]: ...

    async def transliterate_batch(
        self,
        requests_or_texts: Sequence[TransliterationRequest] | Sequence[str],
        *,
        source: LanguageTag | str | None = None,
        target: LanguageTag | str | None = None,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[TransliterationResult, ...]:
        if not requests_or_texts:
            return ()
        first = requests_or_texts[0]
        if isinstance(first, TransliterationRequest):
            requests: tuple[TransliterationRequest, ...] = tuple(
                cast(Sequence[TransliterationRequest], requests_or_texts)
            )
        else:
            if source is None or target is None:
                raise ValueError("source and target are required when providing texts as strings")
            requests = tuple(
                TransliterationRequest(
                    text, source=source, target=target, options=options, context=context
                )
                for text in cast(Sequence[str], requests_or_texts)
            )
        return tuple(
            await asyncio.gather(*(self._transliterate_one(request) for request in requests))
        )

    async def _transliterate_one(self, request: TransliterationRequest) -> TransliterationResult:
        started = time.monotonic()
        candidates = self._router.candidates(
            RouteRequirement(
                CapabilityId.TRANSLITERATION,
                source=request.source,
                target=request.target,
            )
        )
        last_error: BaseException | None = None
        fallback_count = 0
        for count, candidate in enumerate(candidates):
            fallback_count = count
            provider = cast(TransliterationProvider, candidate.provider)
            key = self._key(request, provider.identity.provider)
            cached = await self._cache.get(key)
            if cached is not None:
                return replace(
                    cached,
                    request_id=request.context.request_id,
                    elapsed_seconds=time.monotonic() - started,
                    cache=CacheMetadata(True, type(self._cache).__name__, self._cache_keys.version),
                    fallback_count=fallback_count,
                )
            try:

                async def execute(
                    selected: TransliterationProvider = provider,
                    cache_key: str = key,
                    c: int = fallback_count,
                ) -> TransliterationResult:
                    return await self._execute(
                        request, selected, cache_key, started=started, fallback_count=c
                    )

                result = await self._single_flight.run(key, execute)
                return replace(
                    result,
                    request_id=request.context.request_id,
                    elapsed_seconds=time.monotonic() - started,
                    fallback_count=fallback_count,
                )
            except _FALLBACK_ERRORS as exc:
                last_error = exc

        if last_error is not None:
            if request.options.best_effort:
                return TransliterationResult(
                    text=request.text,
                    source=request.source,
                    target=request.target,
                    provider=TransliterationProviderMetadata("fallback-noop", unofficial=True),
                    request_id=request.context.request_id,
                    elapsed_seconds=time.monotonic() - started,
                    cache=CacheMetadata(
                        False, type(self._cache).__name__, self._cache_keys.version
                    ),
                    fallback_count=fallback_count,
                    warnings=(
                        WarningInfo(
                            "transliteration_fallback",
                            f"Transliteration failed ({last_error}); "
                            "returned source text in best-effort mode",
                        ),
                    ),
                    source_text=request.text,
                )
            raise last_error
        raise AssertionError("Router returned no candidates")

    async def _execute(
        self,
        request: TransliterationRequest,
        provider: TransliterationProvider,
        key: str,
        *,
        started: float,
        fallback_count: int,
    ) -> TransliterationResult:
        results = await provider.transliterate_batch(
            (request.text,),
            source=request.source,
            target=request.target,
            options=request.options,
            request_id=request.context.request_id,
        )
        if len(results.transliterations) != 1:
            raise MalformedProviderResponseError(
                "Provider returned an unexpected number of transliteration results",
                provider=provider.identity.provider,
                capability=CapabilityId.TRANSLITERATION.value,
                request_id=request.context.request_id,
            )
        transliterated_text = results.transliterations[0]
        elapsed = time.monotonic() - started

        result = TransliterationResult(
            text=transliterated_text,
            source=request.source,
            target=request.target,
            provider=TransliterationProviderMetadata(
                provider.identity.provider,
                service_id=results.service_id,
                model_id=results.model_id,
                provider_request_id=results.request_id,
                unofficial=provider.identity.unofficial,
            ),
            request_id=request.context.request_id,
            elapsed_seconds=elapsed,
            cache=CacheMetadata(False, type(self._cache).__name__, self._cache_keys.version),
            fallback_count=fallback_count,
            warnings=results.warnings,
            source_text=request.text,
        )
        await self._cache.set(key, result)
        attributes = {
            "capability": CapabilityId.TRANSLITERATION.value,
            "provider": provider.identity.provider,
            "source": str(request.source),
            "target": str(request.target),
            "outcome": "success",
        }
        self._metrics.observe("transliteration.duration", elapsed, attributes)
        if self._logger:
            self._logger.emit(
                "transliteration.completed",
                {
                    **attributes,
                    "request_id": request.context.request_id,
                    "duration_seconds": elapsed,
                },
            )
        return result

    def _key(self, request: TransliterationRequest, provider: str) -> str:
        return self._cache_keys.build(
            CapabilityId.TRANSLITERATION.value,
            {
                "input_hash": self._cache_keys.hash_content(request.text),
                "source": str(request.source),
                "target": str(request.target),
                "provider": provider,
                "options": {
                    "best_effort": request.options.best_effort,
                },
            },
        )
