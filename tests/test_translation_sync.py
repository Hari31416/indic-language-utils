from __future__ import annotations

import pytest

from indic_language_utils.errors import InvalidInputError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.translation import (
    SyncTranslationClient,
    TranslationClient,
    TranslationRequest,
)

from .translation_support import FakeTranslationProvider, router_for


def test_synchronous_facade() -> None:
    provider = FakeTranslationProvider(transform=str.upper)
    client = SyncTranslationClient(TranslationClient(router_for(provider)))
    request = TranslationRequest(
        "hello",
        DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
        DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
    )
    assert client.translate(request).text == "HELLO"


@pytest.mark.asyncio
async def test_synchronous_facade_rejects_active_loop() -> None:
    provider = FakeTranslationProvider()
    client = SyncTranslationClient(TranslationClient(router_for(provider)))
    request = TranslationRequest(
        "hello",
        DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
        DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
    )
    with pytest.raises(InvalidInputError):
        client.translate(request)
