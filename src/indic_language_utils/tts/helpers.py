"""Default Bhashini TTS client factory."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..errors import ConfigurationError
from ..providers import CapabilityId, ProviderRegistry
from ..providers.bhashini import BhashiniConfig
from ..providers.sarvam import SarvamConfig
from ..routing import OrderedRouter
from .bhashini import BhashiniTTSProvider
from .client import TTSClient
from .protocols import TTSProvider
from .sarvam import SarvamTTSProvider

logger = logging.getLogger(__name__)


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
        if values.get("BHASHINI_API_KEY"):
            config = BhashiniConfig.from_settings(settings, env=values)
            if config.tts_model_id or config.tts_model_ids:
                registry.register(BhashiniTTSProvider(config))
        if values.get("SARVAM_API_KEY"):
            sarvam = SarvamConfig.from_settings(settings, env=values)
            if sarvam.tts_model_id or sarvam.tts_model_ids:
                registry.register(SarvamTTSProvider(sarvam))

        from .edge_tts import HAVE_EDGE_TTS, EdgeTTSConfig, EdgeTTSProvider

        if HAVE_EDGE_TTS:
            try:
                edge_config = EdgeTTSConfig.from_settings(settings, env=values)
                registry.register(EdgeTTSProvider(edge_config))
            except ConfigurationError as exc:
                if not registry.all():
                    raise
                logger.warning("Edge TTS is unavailable: %s", exc)

    if providers is not None:
        route = tuple(provider.identity.provider for provider in registry.all())
    else:
        default_route = tuple(provider.identity.provider for provider in registry.all())
        registered_names = {p.identity.provider for p in registry.all()}
        configured_route = settings.routes.get(CapabilityId.TEXT_TO_SPEECH.value, default_route)
        resolved_route: list[str] = []
        for name in configured_route:
            resolved_name = (
                "edge_tts" if name == "edge" and "edge_tts" in registered_names else name
            )
            if resolved_name in registered_names and resolved_name not in resolved_route:
                resolved_route.append(resolved_name)
        route = tuple(resolved_route) or default_route

    router = OrderedRouter(registry, {CapabilityId.TEXT_TO_SPEECH: route})
    return TTSClient(router)
