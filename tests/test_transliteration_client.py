from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from indic_language_utils.cache import MemoryCache
from indic_language_utils.errors import TransientProviderError
from indic_language_utils.languages import LanguageTag
from indic_language_utils.models import ProviderIdentity
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId, ProviderRegistry
from indic_language_utils.routing import OrderedRouter
from indic_language_utils.transliteration.client import TransliterationClient
from indic_language_utils.transliteration.models import (
    ProviderTransliterationResult,
    TransliterationOptions,
    TransliterationRequest,
    TransliterationResult,
)


@dataclass
class MockTransliterationProvider:
    identity: ProviderIdentity
    capabilities: tuple[CapabilityDeclaration, ...] = field(
        default_factory=lambda: (CapabilityDeclaration(CapabilityId.TRANSLITERATION),)
    )
    calls: list[tuple[str, str, str]] = field(default_factory=list)
    fail: bool = False
    delay: float = 0.0

    def __init__(self, name: str, *, fail: bool = False, delay: float = 0.0) -> None:
        self.identity = ProviderIdentity(name, name.title())
        self.capabilities = (CapabilityDeclaration(CapabilityId.TRANSLITERATION),)
        self.calls = []
        self.fail = fail
        self.delay = delay

    async def transliterate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TransliterationOptions,
        request_id: str,
    ) -> ProviderTransliterationResult:
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        for t in texts:
            self.calls.append((t, str(source), str(target)))
        if self.fail:
            raise TransientProviderError(
                f"Provider {self.identity.provider} failed",
                provider=self.identity.provider,
            )
        return ProviderTransliterationResult(
            transliterations=tuple(f"{t}-xlit" for t in texts),
            model_id=f"{self.identity.provider}-model",
            request_id=request_id,
        )


@pytest.mark.asyncio
async def test_transliteration_client_basic() -> None:
    provider = MockTransliterationProvider("mock-1")
    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("mock-1",)})
    client = TransliterationClient(router)

    result = await client.transliterate("namaste", source="en", target="hi")
    assert result.text == "namaste-xlit"
    assert result.provider.provider == "mock-1"
    assert result.provider.model_id == "mock-1-model"
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_transliteration_client_batch() -> None:
    provider = MockTransliterationProvider("mock-1")
    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("mock-1",)})
    client = TransliterationClient(router)

    results = await client.transliterate_batch(
        ("namaste", "duniya"), source=LanguageTag("en"), target=LanguageTag("hi")
    )
    assert len(results) == 2
    assert results[0].text == "namaste-xlit"
    assert results[1].text == "duniya-xlit"


@pytest.mark.asyncio
async def test_transliteration_client_caching() -> None:
    provider = MockTransliterationProvider("mock-1")
    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("mock-1",)})
    cache = MemoryCache[TransliterationResult](100, 300.0)
    client = TransliterationClient(router, cache=cache)

    res1 = await client.transliterate("namaste", source="en", target="hi")
    assert res1.cache.hit is False
    assert len(provider.calls) == 1

    res2 = await client.transliterate("namaste", source="en", target="hi")
    assert res2.cache.hit is True
    assert res2.text == "namaste-xlit"
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_transliteration_client_fallback() -> None:
    failing_provider = MockTransliterationProvider("failing", fail=True)
    working_provider = MockTransliterationProvider("working")
    registry = ProviderRegistry()
    registry.register(failing_provider)
    registry.register(working_provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("failing", "working")})
    client = TransliterationClient(router)

    result = await client.transliterate("namaste", source="en", target="hi")
    assert result.text == "namaste-xlit"
    assert result.provider.provider == "working"
    assert result.fallback_count == 1
    assert len(failing_provider.calls) == 1
    assert len(working_provider.calls) == 1


@pytest.mark.asyncio
async def test_transliteration_client_best_effort() -> None:
    failing_provider = MockTransliterationProvider("failing", fail=True)
    registry = ProviderRegistry()
    registry.register(failing_provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("failing",)})
    client = TransliterationClient(router)

    req = TransliterationRequest(
        "namaste",
        source="en",
        target="hi",
        options=TransliterationOptions(best_effort=True),
    )
    result = await client.transliterate(req)
    assert result.text == "namaste"
    assert result.provider.provider == "fallback-noop"
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "transliteration_fallback"


@pytest.mark.asyncio
async def test_transliteration_single_flight() -> None:
    slow_provider = MockTransliterationProvider("slow", delay=0.05)
    registry = ProviderRegistry()
    registry.register(slow_provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("slow",)})
    client = TransliterationClient(router)

    t1 = client.transliterate("namaste", source="en", target="hi")
    t2 = client.transliterate("namaste", source="en", target="hi")
    r1, r2 = await asyncio.gather(t1, t2)

    assert r1.text == "namaste-xlit"
    assert r2.text == "namaste-xlit"
    assert len(slow_provider.calls) == 1
