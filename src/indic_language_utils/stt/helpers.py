"""Default Bhashini STT client factory."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..languages import LanguageRegistry
from ..providers import CapabilityId, ProviderRegistry
from ..providers.factories import ProviderFactoryRegistry, configured_provider_factories
from ..routing import OrderedRouter, RouteSelector
from .client import STTClient
from .protocols import STTProvider


def get_stt_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[STTProvider] | None = None,
    additional_providers: Sequence[STTProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    language_registry: LanguageRegistry | None = None,
    route_selector: RouteSelector | None = None,
) -> STTClient:
    use_configured_routes = providers is None or settings is not None
    settings = settings or Settings.load(env=env)
    registry = ProviderRegistry()
    if providers is not None:
        for provider in providers:
            registry.register(provider)
    else:
        values = os.environ if env is None else env
        for built_provider in configured_provider_factories(
            CapabilityId.SPEECH_TO_TEXT, settings, provider_factories
        ).build(CapabilityId.SPEECH_TO_TEXT, settings, values):
            registry.register(built_provider)

    for provider in additional_providers:
        registry.register(provider)

    default_route = tuple(provider.identity.provider for provider in registry.all())
    configured_route = (
        settings.routes.get(CapabilityId.SPEECH_TO_TEXT.value, default_route)
        if use_configured_routes
        else default_route
    )
    route = tuple(name for name in configured_route if name in default_route)
    router = OrderedRouter(registry, {CapabilityId.SPEECH_TO_TEXT: route}, selector=route_selector)
    return STTClient(router, language_registry=language_registry)
