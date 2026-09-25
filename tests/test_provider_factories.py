from __future__ import annotations

import pytest

from indic_language_utils.config import Settings
from indic_language_utils.errors import ConfigurationError
from indic_language_utils.providers import CapabilityId
from indic_language_utils.providers.factories import (
    ProviderFactoryRegistry,
    default_provider_factories,
)

from .translation_support import FakeTranslationProvider


def test_default_factories_are_indexed_by_capability_and_provider() -> None:
    factories = default_provider_factories()

    assert factories.get(CapabilityId.TRANSLATION, "bhashini") is not None
    assert factories.get(CapabilityId.TEXT_TO_SPEECH, "bhashini") is not None
    assert factories.get(CapabilityId.TRANSLATION, "missing") is None
    assert [
        factory.provider_id for factory in factories.for_capability(CapabilityId.TRANSLATION)
    ] == [
        "bhashini",
        "sarvam",
        "googletrans",
    ]


def test_registry_builds_in_registration_order() -> None:
    factories = ProviderFactoryRegistry()
    first = FakeTranslationProvider("first")
    second = FakeTranslationProvider("second")
    factories.register(CapabilityId.TRANSLATION, "first", lambda settings, env: first)
    factories.register(CapabilityId.TRANSLATION, "second", lambda settings, env: second)

    assert factories.build(CapabilityId.TRANSLATION, Settings(), {}) == (first, second)


def test_registry_rejects_duplicate_and_mismatched_factories() -> None:
    factories = ProviderFactoryRegistry()
    factories.register(
        CapabilityId.TRANSLATION, "expected", lambda settings, env: FakeTranslationProvider("wrong")
    )

    with pytest.raises(ConfigurationError, match="invalid adapter"):
        factories.build(CapabilityId.TRANSLATION, Settings(), {})
    with pytest.raises(ConfigurationError, match="registration is invalid"):
        factories.register(CapabilityId.TRANSLATION, "expected", lambda settings, env: None)
