from __future__ import annotations

import pytest

from indic_language_utils import (
    BhashiniConfig,
    BhashiniSTTProvider,
    BhashiniTTSProvider,
    CapabilityId,
    RouteRequirement,
    Secret,
    Settings,
    get_detection_client,
    get_stt_client,
    get_sync_translation_client,
    get_translation_client,
    get_transliteration_client,
    get_tts_client,
)
from indic_language_utils.cache import MemoryCache
from indic_language_utils.errors import ConfigurationError
from indic_language_utils.models import ProviderIdentity
from indic_language_utils.translation import (
    DefaultTranslationStructureProcessor,
    TranslationProcessorPipeline,
    TranslationResult,
)

from .test_detection_client import FakeDetectionProvider
from .test_transliteration_helpers import DummyTransliterationProvider
from .translation_support import FakeTranslationProvider, PrefixProcessor


def test_translation_factory_combines_builtin_and_custom_in_configured_order() -> None:
    env = {
        "BHASHINI_API_KEY": "test-key",
        "BHASHINI_ENDPOINT_URL": "https://example.test",
        "BHASHINI_TRANSLATION_SERVICE_ID": "model",
    }
    settings = Settings(routes={"translation": ("custom", "bhashini")})
    custom = FakeTranslationProvider("custom")

    client = get_translation_client(settings, additional_providers=[custom], env=env)

    assert {provider.identity.provider for provider in client.router.registry.all()} == {
        "bhashini",
        "custom",
    }
    assert [
        item.provider.identity.provider
        for item in client.router.candidates(RouteRequirement(CapabilityId.TRANSLATION))
    ] == ["custom", "bhashini"]


def test_explicit_translation_providers_respect_route_order_in_sync_factory() -> None:
    first = FakeTranslationProvider("first")
    second = FakeTranslationProvider("second")
    settings = Settings(routes={"translation": ("second", "first")})

    client = get_sync_translation_client(settings, providers=[first, second])

    assert client.translate("hello", "en", "hi").provider.provider == "second"


def test_detection_and_transliteration_factories_accept_additional_providers() -> None:
    detection = FakeDetectionProvider(ProviderIdentity("custom-detection"))
    transliteration = DummyTransliterationProvider()

    detect_client = get_detection_client(
        Settings(routes={"text_language_detection": ("custom-detection",)}),
        additional_providers=[detection],
        env={},
    )
    transliterate_client = get_transliteration_client(
        Settings(routes={"transliteration": ("dummy",)}),
        additional_providers=[transliteration],
        env={},
    )

    assert detect_client.router.registry.get("custom-detection") is detection
    assert transliterate_client.router.registry.get("dummy") is transliteration


def test_speech_factories_apply_configured_routes_to_explicit_providers() -> None:
    config = BhashiniConfig(
        "https://example.test", Secret("test-key"), stt_model_id="asr", tts_model_id="voice"
    )
    stt_provider = BhashiniSTTProvider(config)
    tts_provider = BhashiniTTSProvider(config)
    settings = Settings(routes={"speech_to_text": ("bhashini",), "text_to_speech": ("bhashini",)})

    stt_client = get_stt_client(settings, additional_providers=[stt_provider], env={})
    tts_client = get_tts_client(settings, additional_providers=[tts_provider], env={})
    assert stt_client.router.registry.get("bhashini") is stt_provider
    assert tts_client.router.registry.get("bhashini") is tts_provider


def test_duplicate_additional_provider_name_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        get_translation_client(
            providers=[FakeTranslationProvider("duplicate")],
            additional_providers=[FakeTranslationProvider("duplicate")],
        )


@pytest.mark.asyncio
async def test_factory_passes_custom_processors_and_cache() -> None:
    provider = FakeTranslationProvider(transform=lambda text: text)
    cache: MemoryCache[TranslationResult] = MemoryCache()
    processors = TranslationProcessorPipeline(
        DefaultTranslationStructureProcessor(), (PrefixProcessor(),)
    )
    async with get_translation_client(
        providers=[provider], cache=cache, processors=processors, env={}
    ) as client:
        first = await client.translate("hello", "en", "hi")
        second = await client.translate("hello", "en", "hi")
    assert first.text == "hello"
    assert second.cache.hit
    assert provider.calls == [("X:hello",)]
