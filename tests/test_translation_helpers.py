from __future__ import annotations

import pytest

from indic_language_utils.config import Settings
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.translation import (
    SyncTranslationClient,
    TranslationClient,
    get_sync_translation_client,
    get_translation_client,
    translate,
    translate_batch,
    translate_batch_sync,
    translate_sync,
)

from .translation_support import FakeTranslationProvider


@pytest.mark.asyncio
async def test_get_translation_client_with_provider() -> None:
    provider = FakeTranslationProvider(transform=lambda s: f"hi:{s}")
    client = get_translation_client(providers=[provider])
    assert isinstance(client, TranslationClient)

    async with client:
        result = await client.translate("Namaste", "en", "hi")
        assert result.text == "hi:Namaste"
        assert result.source == DEFAULT_LANGUAGE_REGISTRY.normalize("en")
        assert result.target == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")


@pytest.mark.asyncio
async def test_get_translation_client_batch() -> None:
    provider = FakeTranslationProvider(transform=lambda s: f"hi:{s}")
    client = get_translation_client(providers=[provider])

    async with client:
        results = await client.translate_batch(["Namaste", "Danyavad"], "en", "hi")
        assert len(results) == 2
        assert results[0].text == "hi:Namaste"
        assert results[1].text == "hi:Danyavad"


def test_get_sync_translation_client() -> None:
    provider = FakeTranslationProvider(transform=lambda s: f"hi:{s}")
    client = get_sync_translation_client(providers=[provider])
    assert isinstance(client, SyncTranslationClient)

    result = client.translate("Namaste", "en", "hi")
    assert result.text == "hi:Namaste"

    results = client.translate_batch(["Namaste", "Danyavad"], "en", "hi")
    assert len(results) == 2
    assert results[0].text == "hi:Namaste"
    assert results[1].text == "hi:Danyavad"


@pytest.mark.asyncio
async def test_translate_one_liner_async() -> None:
    provider = FakeTranslationProvider(transform=lambda s: f"hi:{s}")
    result = await translate("Hello world", "en", "hi", providers=[provider])
    assert result.text == "hi:Hello world"


def test_translate_one_liner_sync() -> None:
    provider = FakeTranslationProvider(transform=lambda s: f"hi:{s}")
    result = translate_sync("Hello world", "en", "hi", providers=[provider])
    assert result.text == "hi:Hello world"


@pytest.mark.asyncio
async def test_translate_batch_one_liner_async() -> None:
    provider = FakeTranslationProvider(transform=lambda s: f"hi:{s}")
    results = await translate_batch(["Hello", "World"], "en", "hi", providers=[provider])
    assert [r.text for r in results] == ["hi:Hello", "hi:World"]


def test_translate_batch_one_liner_sync() -> None:
    provider = FakeTranslationProvider(transform=lambda s: f"hi:{s}")
    results = translate_batch_sync(["Hello", "World"], "en", "hi", providers=[provider])
    assert [r.text for r in results] == ["hi:Hello", "hi:World"]


def test_get_translation_client_bhashini_registration() -> None:
    settings = Settings.load(
        env={
            "BHASHINI_ENDPOINT_URL": "https://example.com/bhashini",
            "BHASHINI_API_KEY": "dummy-key",
            "BHASHINI_TRANSLATION_SERVICE_ID": "service-1",
        }
    )
    client = get_translation_client(
        settings,
        env={
            "BHASHINI_ENDPOINT_URL": "https://example.com/bhashini",
            "BHASHINI_API_KEY": "dummy-key",
            "BHASHINI_TRANSLATION_SERVICE_ID": "service-1",
        },
    )
    assert "bhashini" in [p.identity.provider for p in client.router.registry.all()]
