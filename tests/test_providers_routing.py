from __future__ import annotations

import asyncio

import pytest

from indic_language_utils.errors import ConfigurationError, UnsupportedLanguageError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers import (
    CapabilityDeclaration,
    CapabilityId,
    ProviderRegistry,
    ResourceManager,
)
from indic_language_utils.routing import OrderedRouter, RouteRequirement

from .provider_contract import assert_cancellation, assert_lifecycle, assert_valid_declaration
from .support import FakeProvider


def test_registration_and_deterministic_routing() -> None:
    hi = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en = DEFAULT_LANGUAGE_REGISTRY.normalize("en")
    first = FakeProvider(
        "first", (CapabilityDeclaration(CapabilityId.TRANSLATION, languages=frozenset({hi})),)
    )
    second = FakeProvider(
        "second", (CapabilityDeclaration(CapabilityId.TRANSLATION, languages=frozenset({hi, en})),)
    )
    registry = ProviderRegistry()
    registry.register(first)
    registry.register(second)
    assert_valid_declaration(first)
    router = OrderedRouter(registry, {CapabilityId.TRANSLATION: ("first", "second")})

    assert (
        router.select(RouteRequirement(CapabilityId.TRANSLATION, source=en, target=hi)).provider
        is second
    )


def test_router_checks_features() -> None:
    provider = FakeProvider("plain", (CapabilityDeclaration(CapabilityId.TRANSLATION),))
    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLATION: ("plain",)})
    with pytest.raises(UnsupportedLanguageError):
        router.select(RouteRequirement(CapabilityId.TRANSLATION, features=frozenset({"batch"})))


def test_duplicate_registration_fails() -> None:
    provider = FakeProvider("fake", (CapabilityDeclaration(CapabilityId.TRANSLATION),))
    registry = ProviderRegistry()
    registry.register(provider)
    with pytest.raises(ConfigurationError):
        registry.register(provider)


@pytest.mark.asyncio
async def test_resource_manager_lifecycle() -> None:
    first = FakeProvider("first", ())
    second = FakeProvider("second", ())
    async with ResourceManager(first, second):
        assert first.started and second.started
        assert not first.closed and not second.closed
    assert first.closed and second.closed


@pytest.mark.asyncio
async def test_reusable_lifecycle_contract() -> None:
    provider = FakeProvider("fake", ())
    await assert_lifecycle(provider, lambda: provider.started, lambda: provider.closed)


@pytest.mark.asyncio
async def test_reusable_cancellation_contract() -> None:
    provider = FakeProvider("fake", ())
    await assert_cancellation(lambda: provider.operation(asyncio.Event()))
