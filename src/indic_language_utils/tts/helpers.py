"""Default Bhashini TTS client factory."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..languages import LanguageRegistry
from ..providers import CapabilityId, ProviderRegistry
from ..providers.factories import ProviderFactoryRegistry, configured_provider_factories
from ..routing import OrderedRouter
from .client import TTSClient
from .protocols import TTSProvider

logger = logging.getLogger(__name__)


def get_tts_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TTSProvider] | None = None,
    additional_providers: Sequence[TTSProvider] = (),
    provider_factories: ProviderFactoryRegistry | None = None,
    env: Mapping[str, str] | None = None,
    language_registry: LanguageRegistry | None = None,
) -> TTSClient:
    use_configured_routes = providers is None or settings is not None
    settings = settings or Settings.load(env=env)
    registry = ProviderRegistry()
    if providers is not None:
        for provider in providers:
            registry.register(provider)
    else:
        values = os.environ if env is None else env
        for built_provider in configured_provider_factories(
            CapabilityId.TEXT_TO_SPEECH, settings, provider_factories
        ).build(CapabilityId.TEXT_TO_SPEECH, settings, values):
            registry.register(built_provider)

    for provider in additional_providers:
        registry.register(provider)

    default_route = tuple(provider.identity.provider for provider in registry.all())
    registered_names = set(default_route)
    configured_route = (
        settings.routes.get(CapabilityId.TEXT_TO_SPEECH.value, default_route)
        if use_configured_routes
        else default_route
    )
    resolved_route: list[str] = []
    for name in configured_route:
        resolved_name = "edge_tts" if name == "edge" and "edge_tts" in registered_names else name
        if resolved_name in registered_names and resolved_name not in resolved_route:
            resolved_route.append(resolved_name)
    route = tuple(resolved_route) or default_route

    router = OrderedRouter(registry, {CapabilityId.TEXT_TO_SPEECH: route})
    return TTSClient(router, language_registry=language_registry)
