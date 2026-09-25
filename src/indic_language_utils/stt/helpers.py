"""Default Bhashini STT client factory."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from ..config import Settings
from ..providers import CapabilityId, ProviderRegistry
from ..providers.bhashini import BhashiniConfig
from ..providers.sarvam import SarvamConfig
from ..routing import OrderedRouter
from .bhashini import BhashiniSTTProvider
from .client import STTClient
from .protocols import STTProvider
from .sarvam import SarvamSTTProvider


def get_stt_client(
    settings: Settings | None = None,
    *,
    providers: Sequence[STTProvider] | None = None,
    additional_providers: Sequence[STTProvider] = (),
    env: Mapping[str, str] | None = None,
) -> STTClient:
    use_configured_routes = providers is None or settings is not None
    settings = settings or Settings.load(env=env)
    registry = ProviderRegistry()
    if providers is not None:
        for provider in providers:
            registry.register(provider)
    else:
        values = os.environ if env is None else env
        if values.get("BHASHINI_API_KEY"):
            config = BhashiniConfig.from_settings(settings, env=values)
            if config.stt_model_id or config.stt_model_ids:
                registry.register(BhashiniSTTProvider(config))
        if values.get("SARVAM_API_KEY"):
            sarvam = SarvamConfig.from_settings(settings, env=values)
            if sarvam.stt_model_id or sarvam.stt_model_ids:
                registry.register(SarvamSTTProvider(sarvam))

        has_google_free = (
            "google_free" in settings.providers
            or any("google_free" in p_list for p_list in settings.routes.values())
            or values.get("STT_SERVICE_PROVIDER") in {"google_free", "google", "speechrecognition"}
        )
        if has_google_free:
            from .google_speech import GoogleFreeSTTConfig, GoogleFreeSTTProvider

            gf_config = GoogleFreeSTTConfig.from_settings(settings, env=values)
            registry.register(GoogleFreeSTTProvider(gf_config))

        has_faster_whisper = (
            "faster_whisper" in settings.providers
            or any("faster_whisper" in p_list for p_list in settings.routes.values())
            or values.get("STT_SERVICE_PROVIDER") in {"faster_whisper", "whisper"}
        )
        if has_faster_whisper:
            from .whisper import FasterWhisperSTTConfig, FasterWhisperSTTProvider

            whisper_config = FasterWhisperSTTConfig.from_settings(settings, env=values)
            registry.register(FasterWhisperSTTProvider(whisper_config))

    for provider in additional_providers:
        registry.register(provider)

    default_route = tuple(provider.identity.provider for provider in registry.all())
    configured_route = (
        settings.routes.get(CapabilityId.SPEECH_TO_TEXT.value, default_route)
        if use_configured_routes
        else default_route
    )
    route = tuple(name for name in configured_route if name in default_route)
    router = OrderedRouter(registry, {CapabilityId.SPEECH_TO_TEXT: route})
    return STTClient(router)
