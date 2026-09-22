"""Canonical asynchronous translation client."""

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
from .catalog import LocalizationCatalog
from .models import (
    ProviderTranslationResult,
    TranslationOptions,
    TranslationProviderMetadata,
    TranslationRequest,
    TranslationResult,
)
from .processing import (
    DEFAULT_TRANSLATION_PROCESSORS,
    Segment,
    TranslationProcessorPipeline,
)
from .protocols import TranslationProvider

_FALLBACK_ERRORS = (
    RateLimitError,
    ProviderTimeoutError,
    TransientProviderError,
    MalformedProviderResponseError,
    OutputValidationError,
)


class TranslationClient:
    def __init__(
        self,
        router: OrderedRouter,
        *,
        cache: AsyncCache[TranslationResult] | None = None,
        cache_keys: CacheKeyBuilder | None = None,
        catalog: LocalizationCatalog | None = None,
        logger: EventLogger | None = None,
        metrics: MetricHook | None = None,
        tracing: TraceHook | None = None,
        processors: TranslationProcessorPipeline | None = None,
    ) -> None:
        self._router = router
        self._cache = cache or NullCache()
        self._cache_keys = cache_keys or CacheKeyBuilder("indic-language-utils")
        self._catalog = catalog or LocalizationCatalog()
        self._logger = logger
        self._metrics = metrics or NoOpMetrics()
        self._tracing = tracing or NoOpTracing()
        self._processors = processors or DEFAULT_TRANSLATION_PROCESSORS
        self._single_flight: SingleFlight[TranslationResult] = SingleFlight()
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

    async def __aenter__(self) -> TranslationClient:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @overload
    async def translate(self, request: TranslationRequest, /) -> TranslationResult: ...

    @overload
    async def translate(
        self,
        text: str,
        source: str | LanguageTag,
        target: str | LanguageTag,
        /,
        *,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
        message_id: str | None = None,
    ) -> TranslationResult: ...

    async def translate(
        self,
        request_or_text: TranslationRequest | str,
        source: str | LanguageTag | None = None,
        target: str | LanguageTag | None = None,
        *,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
        message_id: str | None = None,
    ) -> TranslationResult:
        if isinstance(request_or_text, TranslationRequest):
            request = request_or_text
        else:
            if source is None or target is None:
                raise ValueError("Source and target languages are required when translating text")
            request = TranslationRequest(
                request_or_text,
                source,
                target,
                options=options,
                context=context,
                message_id=message_id,
            )
        return (await self.translate_batch((request,)))[0]

    @overload
    async def translate_batch(
        self,
        requests: Sequence[TranslationRequest],
        /,
    ) -> tuple[TranslationResult, ...]: ...

    @overload
    async def translate_batch(
        self,
        texts: Sequence[str],
        source: str | LanguageTag,
        target: str | LanguageTag,
        /,
        *,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[TranslationResult, ...]: ...

    async def translate_batch(
        self,
        requests_or_texts: Sequence[TranslationRequest] | Sequence[str],
        source: str | LanguageTag | None = None,
        target: str | LanguageTag | None = None,
        *,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[TranslationResult, ...]:
        if not requests_or_texts:
            return ()
        first = requests_or_texts[0]
        if isinstance(first, TranslationRequest):
            requests: tuple[TranslationRequest, ...] = tuple(
                cast(Sequence[TranslationRequest], requests_or_texts)
            )
        else:
            if source is None or target is None:
                raise ValueError("Source and target languages are required when translating texts")
            requests = tuple(
                TranslationRequest(
                    text,
                    source,
                    target,
                    options=options,
                    context=context,
                )
                for text in cast(Sequence[str], requests_or_texts)
            )
        return tuple(await asyncio.gather(*(self._translate_one(request) for request in requests)))

    async def _translate_one(self, request: TranslationRequest) -> TranslationResult:
        started = time.monotonic()
        catalog_entry = self._catalog.lookup(
            request.message_id, request.text, request.source, request.target
        )
        if catalog_entry is not None:
            return TranslationResult(
                catalog_entry.translated_text,
                request.source,
                request.target,
                TranslationProviderMetadata("catalog", service_id=catalog_entry.version),
                request.context.request_id,
                time.monotonic() - started,
                CacheMetadata(True, "catalog", self._cache_keys.version),
                source_text=request.text,
            )
        if request.source == request.target:
            return TranslationResult(
                request.text,
                request.source,
                request.target,
                TranslationProviderMetadata("identity"),
                request.context.request_id,
                time.monotonic() - started,
                CacheMetadata(False, "none", self._cache_keys.version),
                source_text=request.text,
            )

        candidates = self._router.candidates(
            RouteRequirement(CapabilityId.TRANSLATION, request.source, request.target)
        )
        last_error: BaseException | None = None
        for fallback_count, candidate in enumerate(candidates):
            provider = cast(TranslationProvider, candidate.provider)
            resolver = getattr(provider, "service_id_for", None)
            service_id = (
                resolver(request.source, request.target)
                if callable(resolver)
                else getattr(provider, "service_id", None)
            )
            key = self._key(request, provider.identity.provider, service_id)
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
                    selected: TranslationProvider = provider,
                    cache_key: str = key,
                    count: int = fallback_count,
                ) -> TranslationResult:
                    return await self._execute(
                        request, selected, cache_key, started=started, fallback_count=count
                    )

                result = await self._single_flight.run(
                    key,
                    execute,
                )
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
                return TranslationResult(
                    request.text,
                    request.source,
                    request.target,
                    TranslationProviderMetadata("fallback-source", unofficial=True),
                    request.context.request_id,
                    time.monotonic() - started,
                    CacheMetadata(False, type(self._cache).__name__, self._cache_keys.version),
                    fallback_count=fallback_count,
                    warnings=(
                        WarningInfo(
                            "translation_fallback",
                            f"Translation failed ({last_error}); "
                            "returned source text in best-effort mode",
                        ),
                    ),
                    source_text=request.text,
                )
            raise last_error
        raise AssertionError("Router returned no candidates")

    async def _execute(
        self,
        request: TranslationRequest,
        provider: TranslationProvider,
        key: str,
        *,
        started: float,
        fallback_count: int,
    ) -> TranslationResult:
        prepared = self._processors.prepare(request.text, request.options)
        if not prepared.segments:
            result = TranslationResult(
                request.text,
                request.source,
                request.target,
                TranslationProviderMetadata("structure"),
                request.context.request_id,
                time.monotonic() - started,
                CacheMetadata(False, type(self._cache).__name__, self._cache_keys.version),
                fallback_count,
                source_text=request.text,
            )
            await self._cache.set(key, result)
            return result
        outputs: list[str] = []
        metadata: ProviderTranslationResult | None = None
        for offset in range(0, len(prepared.segments), request.options.max_batch_items):
            group = prepared.segments[offset : offset + request.options.max_batch_items]
            translated, metadata = await self._translate_group(provider, request, group)
            outputs.extend(translated)
        text = (
            self._processors.reconstruct(prepared, tuple(outputs), request.options)
            if prepared.segments
            else request.text
        )
        assert metadata is not None
        elapsed = time.monotonic() - started
        result = TranslationResult(
            text,
            request.source,
            request.target,
            TranslationProviderMetadata(
                provider.identity.provider,
                metadata.service_id,
                metadata.model_id,
                metadata.request_id,
                provider.identity.unofficial,
            ),
            request.context.request_id,
            elapsed,
            CacheMetadata(False, type(self._cache).__name__, self._cache_keys.version),
            fallback_count,
            metadata.warnings,
            source_text=request.text,
        )
        await self._cache.set(key, result)
        attributes = {
            "capability": CapabilityId.TRANSLATION.value,
            "provider": provider.identity.provider,
            "source_language": str(request.source),
            "target_language": str(request.target),
            "outcome": "success",
        }
        self._metrics.observe("translation.duration", elapsed, attributes)
        if self._logger:
            self._logger.emit(
                "translation.completed",
                {
                    **attributes,
                    "request_id": request.context.request_id,
                    "duration_seconds": elapsed,
                },
            )
        return result

    async def _translate_group(
        self,
        provider: TranslationProvider,
        request: TranslationRequest,
        segments: tuple[Segment, ...],
    ) -> tuple[tuple[str, ...], ProviderTranslationResult]:
        texts = tuple(segment.text for segment in segments)
        result = await provider.translate_batch(
            texts,
            source=request.source,
            target=request.target,
            options=request.options,
            request_id=request.context.request_id,
        )
        if len(result.translations) == len(texts):
            try:
                for output, segment in zip(result.translations, segments, strict=True):
                    self._processors.restore_segment(output, segment, request.options)
                return result.translations, result
            except OutputValidationError:
                pass

        outputs: list[str] = []
        latest = result
        for segment in segments:
            individual = await provider.translate_batch(
                (segment.text,),
                source=request.source,
                target=request.target,
                options=request.options,
                request_id=request.context.request_id,
            )
            if len(individual.translations) != 1:
                raise OutputValidationError("Provider returned the wrong number of translations")
            self._processors.restore_segment(individual.translations[0], segment, request.options)
            outputs.append(individual.translations[0])
            latest = individual
        return tuple(outputs), latest

    def _key(self, request: TranslationRequest, provider: str, service_id: object) -> str:
        return self._cache_keys.build(
            CapabilityId.TRANSLATION.value,
            {
                "input_hash": self._cache_keys.hash_content(request.text),
                "source": str(request.source),
                "target": str(request.target),
                "provider": provider,
                "service_id": service_id,
                "options": {
                    "format": request.options.text_format.value,
                    "max_segment_characters": request.options.max_segment_characters,
                    "max_batch_items": request.options.max_batch_items,
                    "allow_reordered_placeholders": request.options.allow_reordered_placeholders,
                    "best_effort": request.options.best_effort,
                },
                "processors": self._processors.cache_identity,
                "catalog": self._catalog.version,
            },
        )
