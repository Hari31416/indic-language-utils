"""Canonical asynchronous text language detection client."""

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
from ..models import CacheMetadata, OperationContext, WarningInfo
from ..providers import AsyncLifecycle, CapabilityId, ResourceManager
from ..routing import OrderedRouter, RouteRequirement
from ..telemetry import EventLogger, MetricHook, NoOpMetrics, NoOpTracing, TraceHook
from .models import (
    DetectionOptions,
    DetectionProviderMetadata,
    DetectionRequest,
    DetectionResult,
)
from .protocols import DetectionProvider

_FALLBACK_ERRORS = (
    RateLimitError,
    ProviderTimeoutError,
    TransientProviderError,
    MalformedProviderResponseError,
    OutputValidationError,
)


class DetectionClient:
    def __init__(
        self,
        router: OrderedRouter,
        *,
        cache: AsyncCache[DetectionResult] | None = None,
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
        self._single_flight: SingleFlight[DetectionResult] = SingleFlight()
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

    async def __aenter__(self) -> DetectionClient:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @overload
    async def detect(self, request: DetectionRequest, /) -> DetectionResult: ...

    @overload
    async def detect(
        self,
        text: str,
        /,
        *,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> DetectionResult: ...

    async def detect(
        self,
        request_or_text: DetectionRequest | str,
        *,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> DetectionResult:
        if isinstance(request_or_text, DetectionRequest):
            request = request_or_text
        else:
            request = DetectionRequest(request_or_text, options=options, context=context)
        return (await self.detect_batch((request,)))[0]

    @overload
    async def detect_batch(
        self,
        requests: Sequence[DetectionRequest],
        /,
    ) -> tuple[DetectionResult, ...]: ...

    @overload
    async def detect_batch(
        self,
        texts: Sequence[str],
        /,
        *,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[DetectionResult, ...]: ...

    async def detect_batch(
        self,
        requests_or_texts: Sequence[DetectionRequest] | Sequence[str],
        *,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> tuple[DetectionResult, ...]:
        if not requests_or_texts:
            return ()
        first = requests_or_texts[0]
        if isinstance(first, DetectionRequest):
            requests: tuple[DetectionRequest, ...] = tuple(
                cast(Sequence[DetectionRequest], requests_or_texts)
            )
        else:
            requests = tuple(
                DetectionRequest(text, options=options, context=context)
                for text in cast(Sequence[str], requests_or_texts)
            )
        return tuple(await asyncio.gather(*(self._detect_one(request) for request in requests)))

    async def _detect_one(self, request: DetectionRequest) -> DetectionResult:
        started = time.monotonic()
        candidates = self._router.candidates(RouteRequirement(CapabilityId.TEXT_LANGUAGE_DETECTION))
        last_error: BaseException | None = None
        for fallback_count, candidate in enumerate(candidates):
            provider = cast(DetectionProvider, candidate.provider)
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
                    selected: DetectionProvider = provider,
                    cache_key: str = key,
                    count: int = fallback_count,
                ) -> DetectionResult:
                    return await self._execute(
                        request, selected, cache_key, started=started, fallback_count=count
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
                return DetectionResult(
                    language=None,
                    candidates=(),
                    script=None,
                    provider=DetectionProviderMetadata("fallback-unknown", unofficial=True),
                    request_id=request.context.request_id,
                    elapsed_seconds=time.monotonic() - started,
                    cache=CacheMetadata(
                        False, type(self._cache).__name__, self._cache_keys.version
                    ),
                    fallback_count=fallback_count,
                    warnings=(
                        WarningInfo(
                            "detection_fallback",
                            f"Language detection failed ({last_error}); "
                            "returned empty result in best-effort mode",
                        ),
                    ),
                    source_text=request.text,
                )
            raise last_error
        raise AssertionError("Router returned no candidates")

    async def _execute(
        self,
        request: DetectionRequest,
        provider: DetectionProvider,
        key: str,
        *,
        started: float,
        fallback_count: int,
    ) -> DetectionResult:
        results = await provider.detect_batch(
            (request.text,),
            options=request.options,
            request_id=request.context.request_id,
        )
        if len(results) != 1:
            raise MalformedProviderResponseError(
                "Provider returned an unexpected number of detection results",
                provider=provider.identity.provider,
                capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                request_id=request.context.request_id,
            )
        provider_result = results[0]
        elapsed = time.monotonic() - started

        all_candidates = provider_result.candidates[: request.options.max_candidates]
        top_candidate = (
            all_candidates[0]
            if all_candidates and all_candidates[0].confidence >= request.options.threshold
            else None
        )
        detected_language = top_candidate.language if top_candidate is not None else None
        detected_script = top_candidate.script if top_candidate is not None else None

        result = DetectionResult(
            language=detected_language,
            candidates=all_candidates,
            script=detected_script,
            provider=DetectionProviderMetadata(
                provider.identity.provider,
                provider_result.model_id,
                provider_result.request_id,
                provider.identity.unofficial,
            ),
            request_id=request.context.request_id,
            elapsed_seconds=elapsed,
            cache=CacheMetadata(False, type(self._cache).__name__, self._cache_keys.version),
            fallback_count=fallback_count,
            warnings=provider_result.warnings,
            source_text=request.text,
        )
        await self._cache.set(key, result)
        attributes = {
            "capability": CapabilityId.TEXT_LANGUAGE_DETECTION.value,
            "provider": provider.identity.provider,
            "detected_language": str(detected_language) if detected_language else "unknown",
            "outcome": "success",
        }
        self._metrics.observe("detection.duration", elapsed, attributes)
        if self._logger:
            self._logger.emit(
                "detection.completed",
                {
                    **attributes,
                    "request_id": request.context.request_id,
                    "duration_seconds": elapsed,
                },
            )
        return result

    def _key(self, request: DetectionRequest, provider: str) -> str:
        return self._cache_keys.build(
            CapabilityId.TEXT_LANGUAGE_DETECTION.value,
            {
                "input_hash": self._cache_keys.hash_content(request.text),
                "provider": provider,
                "options": {
                    "threshold": request.options.threshold,
                    "max_candidates": request.options.max_candidates,
                    "best_effort": request.options.best_effort,
                },
            },
        )
