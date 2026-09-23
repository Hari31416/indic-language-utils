"""Default Bhashini TTS client factory."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..providers import CapabilityId, ProviderRegistry
from ..providers.bhashini import BhashiniConfig
from ..routing import OrderedRouter
from .bhashini import BhashiniTTSProvider
from .client import TTSClient
from .protocols import TTSProvider


def get_tts_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[TTSProvider] | None = None,
    env: Mapping[str, str] | None = None,
) -> TTSClient:
    settings = settings or Settings.load(env=env)
    registry = ProviderRegistry()
    if providers is not None:
        for provider in providers:
            registry.register(provider)
    else:
        values = os.environ if env is None else env
        config = BhashiniConfig.from_settings(settings, env=values)
        if config.tts_model_id or config.tts_model_ids:
            registry.register(BhashiniTTSProvider(config))
    default_route = tuple(provider.identity.provider for provider in registry.all())
    route = settings.routes.get(CapabilityId.TEXT_TO_SPEECH.value, default_route)
    router = OrderedRouter(registry, {CapabilityId.TEXT_TO_SPEECH: route})
    return TTSClient(router)
