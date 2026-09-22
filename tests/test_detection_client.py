from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from indic_language_utils.cache import MemoryCache
from indic_language_utils.detection.client import DetectionClient
from indic_language_utils.detection.models import (
    DetectionOptions,
    DetectionResult,
    LanguageCandidate,
    ProviderDetectionResult,
)
from indic_language_utils.detection.protocols import DetectionProvider
from indic_language_utils.errors import RateLimitError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.models import ProviderIdentity
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId, ProviderRegistry
from indic_language_utils.routing import OrderedRouter


@dataclass
class FakeDetectionProvider:
    identity: ProviderIdentity
    capabilities: tuple[CapabilityDeclaration, ...] = field(
        default_factory=lambda: (CapabilityDeclaration(CapabilityId.TEXT_LANGUAGE_DETECTION),)
    )
    calls: list[tuple[tuple[str, ...], DetectionOptions, str]] = field(default_factory=list)
    delay_seconds: float = 0.0
    failure: Exception | None = None
    default_lang: str = "hi"
    default_confidence: float = 0.95
    default_script: str | None = "Deva"

    async def detect_batch(
        self,
        texts: tuple[str, ...],
        *,
        options: DetectionOptions,
        request_id: str,
    ) -> tuple[ProviderDetectionResult, ...]:
        self.calls.append((texts, options, request_id))
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.failure is not None:
            raise self.failure
        return tuple(
            ProviderDetectionResult(
                candidates=(
                    LanguageCandidate(
                        DEFAULT_LANGUAGE_REGISTRY.normalize(self.default_lang),
                        self.default_confidence,
                        script=self.default_script,
                    ),
                ),
                model_id="fake-v1",
                request_id=request_id,
            )
            for _ in texts
        )


def make_router(
    providers: list[DetectionProvider],
    route: tuple[str, ...] | None = None,
) -> OrderedRouter:
    registry = ProviderRegistry()
    for p in providers:
        registry.register(p)
    names = route or tuple(p.identity.provider for p in providers)
    return OrderedRouter(registry, {CapabilityId.TEXT_LANGUAGE_DETECTION: names})


@pytest.mark.asyncio
async def test_detect_single_text() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"))
    router = make_router([provider])
    client = DetectionClient(router)

    result = await client.detect("नमस्ते")
    assert result.language == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    assert result.script == "Deva"
    assert len(result.candidates) == 1
    assert result.candidates[0].confidence == 0.95
    assert result.provider.provider == "p1"
    assert result.provider.model_id == "fake-v1"
    assert result.cache.hit is False
    assert result.fallback_count == 0


@pytest.mark.asyncio
async def test_detect_threshold_filtering() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"), default_confidence=0.5)
    router = make_router([provider])
    client = DetectionClient(router)

    # Threshold higher than confidence -> result.language should be None
    result = await client.detect("test text", options=DetectionOptions(threshold=0.8))
    assert result.language is None
    assert len(result.candidates) == 1
    assert result.candidates[0].confidence == 0.5


@pytest.mark.asyncio
async def test_detect_batch() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"))
    router = make_router([provider])
    client = DetectionClient(router)

    results = await client.detect_batch(["text1", "text2"])
    assert len(results) == 2
    assert results[0].language == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    assert results[1].language == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")


@pytest.mark.asyncio
async def test_detect_fallback() -> None:
    p1 = FakeDetectionProvider(
        ProviderIdentity("p1"),
        failure=RateLimitError("Quota exceeded", provider="p1"),
    )
    p2 = FakeDetectionProvider(ProviderIdentity("p2"), default_lang="ta")
    router = make_router([p1, p2])
    client = DetectionClient(router)

    result = await client.detect("test text")
    assert result.language == DEFAULT_LANGUAGE_REGISTRY.normalize("ta")
    assert result.provider.provider == "p2"
    assert result.fallback_count == 1


@pytest.mark.asyncio
async def test_detect_best_effort_on_failure() -> None:
    p1 = FakeDetectionProvider(
        ProviderIdentity("p1"),
        failure=RateLimitError("Quota exceeded", provider="p1"),
    )
    router = make_router([p1])
    client = DetectionClient(router)

    result = await client.detect("test text", options=DetectionOptions(best_effort=True))
    assert result.language is None
    assert result.candidates == ()
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "detection_fallback"


@pytest.mark.asyncio
async def test_detect_caching() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"))
    router = make_router([provider])
    cache: MemoryCache[DetectionResult] = MemoryCache()
    client = DetectionClient(router, cache=cache)

    res1 = await client.detect("नमस्ते")
    assert res1.cache.hit is False
    assert len(provider.calls) == 1

    res2 = await client.detect("नमस्ते")
    assert res2.cache.hit is True
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_detect_single_flight_coalescing() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"), delay_seconds=0.05)
    router = make_router([provider])
    client = DetectionClient(router)

    results = await asyncio.gather(
        client.detect("नमस्ते"),
        client.detect("नमस्ते"),
    )
    assert len(results) == 2
    assert results[0].language == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    assert results[1].language == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    # Only 1 call was executed due to single-flight coalescing
    assert len(provider.calls) == 1
