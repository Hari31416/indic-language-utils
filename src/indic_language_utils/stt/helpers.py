"""Default Bhashini STT client factory."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..providers import CapabilityId, ProviderRegistry
from ..providers.bhashini import BhashiniConfig
from ..routing import OrderedRouter
from .bhashini import BhashiniSTTProvider
from .client import STTClient
from .protocols import STTProvider


def get_stt_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[STTProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> STTClient:
    settings = settings or Settings.load(env=env)
    registry = ProviderRegistry()
    if providers is not None:
        for provider in providers:
            registry.register(provider)
    else:
        values = os.environ if env is None else env
        config = BhashiniConfig.from_settings(settings, env=values)
        if config.stt_model_id or config.stt_model_ids:
            registry.register(BhashiniSTTProvider(config))
    default_route = tuple(provider.identity.provider for provider in registry.all())
    route = settings.routes.get(CapabilityId.SPEECH_TO_TEXT.value, default_route)
    router = OrderedRouter(registry, {CapabilityId.SPEECH_TO_TEXT: route})
    return STTClient(router)
