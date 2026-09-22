from __future__ import annotations

from indic_language_utils.config import ProviderSettings, Settings
from indic_language_utils.detection.helpers import get_detection_client
from indic_language_utils.detection.sarvam_detect import SarvamDetectionProvider
from indic_language_utils.providers import CapabilityId
from indic_language_utils.routing import RouteRequirement
from indic_language_utils.translation.helpers import get_translation_client
from indic_language_utils.translation.sarvam_translate import (
    SarvamTranslationProvider,
)


def test_get_translation_client_with_sarvam_env() -> None:
    client = get_translation_client(
        Settings(),
        env={"SARVAM_API_KEY": "test-sarvam-key"},
    )
    sarvam_provider = client.router.registry.get("sarvam")
    assert isinstance(sarvam_provider, SarvamTranslationProvider)
    assert sarvam_provider.config.api_key.reveal() == "test-sarvam-key"


def test_get_translation_client_with_sarvam_settings() -> None:
    settings = Settings(
        providers={
            "sarvam": ProviderSettings(
                endpoint="https://api.sarvam.ai",
                model="mayura:v1",
            )
        }
    )
    client = get_translation_client(
        settings,
        env={"SARVAM_API_KEY": "test-sarvam-key"},
    )
    sarvam_provider = client.router.registry.get("sarvam")
    assert isinstance(sarvam_provider, SarvamTranslationProvider)
    assert sarvam_provider.config.model == "mayura:v1"


def test_translation_service_provider_sarvam_priority() -> None:
    settings = Settings(
        providers={
            "bhashini": ProviderSettings(
                endpoint="https://example.test",
                translation_service_id="dummy",
            ),
            "sarvam": ProviderSettings(),
        },
        routes={"translation": ("bhashini", "sarvam")},
    )
    client = get_translation_client(
        settings,
        env={
            "BHASHINI_API_KEY": "bhashini-key",
            "BHASHINI_TRANSLATION_SERVICE_ID": "svc",
            "SARVAM_API_KEY": "sarvam-key",
            "TRANSLATION_SERVICE_PROVIDER": "sarvam",
        },
    )
    candidates = client.router.candidates(RouteRequirement(CapabilityId.TRANSLATION))
    assert candidates[0].provider.identity.provider == "sarvam"


def test_get_detection_client_with_sarvam_env() -> None:
    client = get_detection_client(
        Settings(),
        env={"SARVAM_API_KEY": "test-sarvam-key"},
    )
    sarvam_provider = client.router.registry.get("sarvam")
    assert isinstance(sarvam_provider, SarvamDetectionProvider)
    assert sarvam_provider.config.api_key.reveal() == "test-sarvam-key"


def test_get_detection_client_with_sarvam_settings() -> None:
    settings = Settings(
        providers={
            "sarvam": ProviderSettings(
                endpoint="https://api.sarvam.ai",
            )
        }
    )
    client = get_detection_client(
        settings,
        env={"SARVAM_API_KEY": "test-sarvam-key"},
    )
    sarvam_provider = client.router.registry.get("sarvam")
    assert isinstance(sarvam_provider, SarvamDetectionProvider)
