"""Builders for configured provider adapters."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import metadata
from typing import Literal, cast

from ..config import Settings
from ..errors import ConfigurationError, MissingOptionalDependencyError
from .base import CapabilityId, Provider

logger = logging.getLogger(__name__)

ProviderBuilder = Callable[[Settings, Mapping[str, str]], Provider | None]
FailurePolicy = Literal["raise", "skip", "skip_if_registered"]
ENTRY_POINT_GROUP_PREFIX = "indic_language_utils.providers."


@dataclass(frozen=True, slots=True)
class ProviderFactory:
    capability: CapabilityId
    provider_id: str
    build: ProviderBuilder
    failure_policy: FailurePolicy = "raise"
    plugin: bool = False


class ProviderFactoryRegistry:
    """Map a capability and provider ID to an adapter builder."""

    def __init__(self) -> None:
        self._factories: dict[tuple[CapabilityId, str], ProviderFactory] = {}

    def register(
        self,
        capability: CapabilityId,
        provider_id: str,
        builder: ProviderBuilder,
        *,
        failure_policy: FailurePolicy = "raise",
        plugin: bool = False,
    ) -> None:
        key = (capability, provider_id)
        if not provider_id or key in self._factories:
            raise ConfigurationError(f"Provider factory registration is invalid: {provider_id!r}")
        self._factories[key] = ProviderFactory(
            capability, provider_id, builder, failure_policy, plugin
        )

    def copy(self) -> ProviderFactoryRegistry:
        copied = ProviderFactoryRegistry()
        copied._factories.update(self._factories)
        return copied

    def get(self, capability: CapabilityId, provider_id: str) -> ProviderFactory | None:
        return self._factories.get((capability, provider_id))

    def for_capability(self, capability: CapabilityId) -> tuple[ProviderFactory, ...]:
        return tuple(
            factory
            for (registered_capability, _), factory in self._factories.items()
            if registered_capability == capability
        )

    def build(
        self, capability: CapabilityId, settings: Settings, env: Mapping[str, str]
    ) -> tuple[Provider, ...]:
        providers: list[Provider] = []
        for factory in self.for_capability(capability):
            try:
                provider = factory.build(settings, env)
            except (ConfigurationError, MissingOptionalDependencyError) as exc:
                if factory.plugin:
                    raise ConfigurationError(
                        f"Provider plugin could not be built: {factory.provider_id}"
                    ) from exc
                if factory.failure_policy == "raise" or (
                    factory.failure_policy == "skip_if_registered" and not providers
                ):
                    raise
                if factory.failure_policy == "skip_if_registered":
                    logger.warning("Provider %s is unavailable: %s", factory.provider_id, exc)
                continue
            except Exception as exc:
                if not factory.plugin:
                    raise
                raise ConfigurationError(
                    f"Provider plugin could not be built: {factory.provider_id}"
                ) from exc
            if provider is None:
                if factory.plugin:
                    raise ConfigurationError(
                        f"Provider plugin returned no adapter: {factory.provider_id}"
                    )
                continue
            if provider.identity.provider != factory.provider_id or not any(
                item.capability == capability for item in provider.capabilities
            ):
                raise ConfigurationError(
                    f"Provider factory returned an invalid adapter: {factory.provider_id}"
                )
            providers.append(provider)
        return tuple(providers)


def configured_provider_factories(
    capability: CapabilityId,
    settings: Settings,
    factories: ProviderFactoryRegistry | None = None,
) -> ProviderFactoryRegistry:
    """Add only explicitly configured entry point builders to a fresh registry."""
    result = factories.copy() if factories is not None else default_provider_factories()
    selected = set(settings.providers) | set(settings.routes.get(capability.value, ()))
    if not selected:
        return result
    group = ENTRY_POINT_GROUP_PREFIX + capability.value
    for entry_point in metadata.entry_points(group=group):
        if entry_point.name not in selected:
            continue
        try:
            loaded = entry_point.load()
        except Exception as exc:
            raise ConfigurationError(
                f"Provider plugin could not be loaded: {entry_point.name}"
            ) from exc
        if not callable(loaded):
            raise ConfigurationError(
                f"Provider plugin entry point is not callable: {entry_point.name}"
            )
        result.register(capability, entry_point.name, cast(ProviderBuilder, loaded), plugin=True)
    return result


def default_provider_factories() -> ProviderFactoryRegistry:
    """Return a fresh registry of lazy built-in adapter builders."""
    registry = ProviderFactoryRegistry()
    registry.register(
        CapabilityId.TRANSLATION, "bhashini", _translation_bhashini, failure_policy="skip"
    )
    registry.register(
        CapabilityId.TRANSLATION, "sarvam", _translation_sarvam, failure_policy="skip"
    )
    registry.register(
        CapabilityId.TRANSLATION, "googletrans", _translation_googletrans, failure_policy="skip"
    )
    registry.register(
        CapabilityId.TEXT_LANGUAGE_DETECTION,
        "bhashini",
        _detection_bhashini,
        failure_policy="skip",
    )
    registry.register(
        CapabilityId.TEXT_LANGUAGE_DETECTION,
        "sarvam",
        _detection_sarvam,
        failure_policy="skip",
    )
    registry.register(
        CapabilityId.TEXT_LANGUAGE_DETECTION,
        "fasttext",
        _detection_fasttext,
        failure_policy="skip",
    )
    registry.register(
        CapabilityId.TRANSLITERATION,
        "bhashini",
        _transliteration_bhashini,
        failure_policy="skip",
    )
    registry.register(
        CapabilityId.TRANSLITERATION,
        "aksharamukha",
        _transliteration_aksharamukha,
        failure_policy="skip",
    )
    registry.register(
        CapabilityId.TRANSLITERATION,
        "indicxlit",
        _transliteration_indicxlit,
        failure_policy="skip",
    )
    registry.register(CapabilityId.SPEECH_TO_TEXT, "bhashini", _stt_bhashini)
    registry.register(CapabilityId.SPEECH_TO_TEXT, "sarvam", _stt_sarvam)
    registry.register(CapabilityId.SPEECH_TO_TEXT, "google_free", _stt_google_free)
    registry.register(CapabilityId.SPEECH_TO_TEXT, "faster_whisper", _stt_faster_whisper)
    registry.register(CapabilityId.TEXT_TO_SPEECH, "bhashini", _tts_bhashini)
    registry.register(CapabilityId.TEXT_TO_SPEECH, "sarvam", _tts_sarvam)
    registry.register(
        CapabilityId.TEXT_TO_SPEECH,
        "edge_tts",
        _tts_edge,
        failure_policy="skip_if_registered",
    )
    return registry


def _configured(settings: Settings, env: Mapping[str, str], name: str, key: str) -> bool:
    return name in settings.providers or key in env


def _in_routes(settings: Settings, name: str) -> bool:
    return any(name in route for route in settings.routes.values())


def _translation_bhashini(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not _configured(settings, env, "bhashini", "BHASHINI_API_KEY"):
        return None
    from ..translation.bhashini_translate import BhashiniTranslationProvider
    from .bhashini import BhashiniConfig

    return BhashiniTranslationProvider(BhashiniConfig.from_settings(settings, env=env))


def _translation_sarvam(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not _configured(settings, env, "sarvam", "SARVAM_API_KEY"):
        return None
    from ..translation.sarvam_translate import SarvamTranslationProvider
    from .sarvam import SarvamConfig

    return SarvamTranslationProvider(SarvamConfig.from_settings(settings, env=env))


def _translation_googletrans(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not (
        "googletrans" in settings.providers
        or _in_routes(settings, "googletrans")
        or env.get("TRANSLATION_SERVICE_PROVIDER") in {"googletrans", "google"}
    ):
        return None
    from ..translation.google_translate import (
        HAVE_GOOGLETRANS,
        GoogleTranslateConfig,
        GoogleTranslateProvider,
    )

    if not HAVE_GOOGLETRANS:
        return None
    return GoogleTranslateProvider(GoogleTranslateConfig.from_settings(settings, env=env))


def _detection_bhashini(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not (
        _configured(settings, env, "bhashini", "BHASHINI_API_KEY")
        or "BHASHINI_DETECTION_SERVICE_ID" in env
        or "BHASHINI_TLD_SERVICE_ID" in env
    ):
        return None
    from ..detection.bhashini_detect import BhashiniDetectionProvider
    from .bhashini import BhashiniConfig

    config = BhashiniConfig.from_settings(settings, env=env)
    return BhashiniDetectionProvider(config) if config.detection_service_id else None


def _detection_sarvam(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not _configured(settings, env, "sarvam", "SARVAM_API_KEY"):
        return None
    from ..detection.sarvam_detect import SarvamDetectionProvider
    from .sarvam import SarvamConfig

    return SarvamDetectionProvider(SarvamConfig.from_settings(settings, env=env))


def _detection_fasttext(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    from ..detection.fasttext import (
        HAVE_FASTTEXT,
        FastTextDetectionConfig,
        FastTextDetectionProvider,
    )

    return FastTextDetectionProvider(FastTextDetectionConfig()) if HAVE_FASTTEXT else None


def _transliteration_bhashini(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not (
        _configured(settings, env, "bhashini", "BHASHINI_API_KEY")
        or "BHASHINI_TRANSLITERATION_SERVICE_ID" in env
    ):
        return None
    from ..transliteration.bhashini_transliterate import BhashiniTransliterationProvider
    from .bhashini import BhashiniConfig

    config = BhashiniConfig.from_settings(settings, env=env)
    if config.transliteration_service_id or config.transliteration_service_ids:
        return BhashiniTransliterationProvider(config)
    return None


def _transliteration_aksharamukha(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    from ..transliteration.aksharamukha import (
        HAVE_AKSHARAMUKHA,
        AksharamukhaConfig,
        AksharamukhaTransliterationProvider,
    )

    return AksharamukhaTransliterationProvider(AksharamukhaConfig()) if HAVE_AKSHARAMUKHA else None


def _transliteration_indicxlit(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    from ..transliteration.indicxlit import (
        HAVE_INDICXLIT,
        IndicXlitConfig,
        IndicXlitTransliterationProvider,
    )

    return IndicXlitTransliterationProvider(IndicXlitConfig()) if HAVE_INDICXLIT else None


def _stt_bhashini(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not env.get("BHASHINI_API_KEY"):
        return None
    from ..stt.bhashini import BhashiniSTTProvider
    from .bhashini import BhashiniConfig

    config = BhashiniConfig.from_settings(settings, env=env)
    return BhashiniSTTProvider(config) if config.stt_model_id or config.stt_model_ids else None


def _stt_sarvam(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not env.get("SARVAM_API_KEY"):
        return None
    from ..stt.sarvam import SarvamSTTProvider
    from .sarvam import SarvamConfig

    config = SarvamConfig.from_settings(settings, env=env)
    return SarvamSTTProvider(config) if config.stt_model_id or config.stt_model_ids else None


def _stt_google_free(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not (
        "google_free" in settings.providers
        or _in_routes(settings, "google_free")
        or env.get("STT_SERVICE_PROVIDER") in {"google_free", "google", "speechrecognition"}
    ):
        return None
    from ..stt.google_speech import GoogleFreeSTTConfig, GoogleFreeSTTProvider

    return GoogleFreeSTTProvider(GoogleFreeSTTConfig.from_settings(settings, env=env))


def _stt_faster_whisper(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not (
        "faster_whisper" in settings.providers
        or _in_routes(settings, "faster_whisper")
        or env.get("STT_SERVICE_PROVIDER") in {"faster_whisper", "whisper"}
    ):
        return None
    from ..stt.whisper import FasterWhisperSTTConfig, FasterWhisperSTTProvider

    return FasterWhisperSTTProvider(FasterWhisperSTTConfig.from_settings(settings, env=env))


def _tts_bhashini(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not env.get("BHASHINI_API_KEY"):
        return None
    from ..tts.bhashini import BhashiniTTSProvider
    from .bhashini import BhashiniConfig

    config = BhashiniConfig.from_settings(settings, env=env)
    return BhashiniTTSProvider(config) if config.tts_model_id or config.tts_model_ids else None


def _tts_sarvam(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    if not env.get("SARVAM_API_KEY"):
        return None
    from ..tts.sarvam import SarvamTTSProvider
    from .sarvam import SarvamConfig

    config = SarvamConfig.from_settings(settings, env=env)
    return SarvamTTSProvider(config) if config.tts_model_id or config.tts_model_ids else None


def _tts_edge(settings: Settings, env: Mapping[str, str]) -> Provider | None:
    from ..tts.edge_tts import HAVE_EDGE_TTS, EdgeTTSConfig, EdgeTTSProvider

    if not HAVE_EDGE_TTS:
        return None
    return EdgeTTSProvider(EdgeTTSConfig.from_settings(settings, env=env))
