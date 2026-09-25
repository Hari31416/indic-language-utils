from __future__ import annotations

import asyncio

import pytest

from indic_language_utils.errors import (
    ConfigurationError,
    UnsupportedCapabilityError,
    UnsupportedLanguageError,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers import (
    CapabilityDeclaration,
    CapabilityId,
    ProviderRegistry,
    ResourceManager,
)
from indic_language_utils.routing import OrderedRouter, RouteRequirement
from indic_language_utils.testing import (
    assert_cancellation,
    assert_lifecycle,
    assert_valid_declaration,
)

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


def test_route_selector_can_order_eligible_providers_per_request() -> None:
    registry = ProviderRegistry()
    for name in ("first", "second"):
        registry.register(FakeProvider(name, (CapabilityDeclaration(CapabilityId.TRANSLATION),)))
    hi = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    router = OrderedRouter(
        registry,
        {CapabilityId.TRANSLATION: ("first", "second")},
        selector=lambda requirement, candidates: (
            tuple(reversed(candidates)) if requirement.target == hi else candidates
        ),
    )
    assert router.select(
        RouteRequirement(CapabilityId.TRANSLATION, target=hi)
    ).provider is registry.get("second")
    assert router.select(RouteRequirement(CapabilityId.TRANSLATION)).provider is registry.get(
        "first"
    )


def test_route_selector_cannot_add_or_repeat_providers() -> None:
    registry = ProviderRegistry()
    registry.register(FakeProvider("first", (CapabilityDeclaration(CapabilityId.TRANSLATION),)))
    routes: dict[CapabilityId, tuple[str, ...]] = {CapabilityId.TRANSLATION: ("first",)}
    duplicate = OrderedRouter(
        registry, routes, selector=lambda requirement, candidates: candidates * 2
    )
    with pytest.raises(ConfigurationError):
        duplicate.candidates(RouteRequirement(CapabilityId.TRANSLATION))
    empty = OrderedRouter(registry, routes, selector=lambda requirement, candidates: ())
    with pytest.raises(UnsupportedCapabilityError):
        empty.candidates(RouteRequirement(CapabilityId.TRANSLATION))


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
