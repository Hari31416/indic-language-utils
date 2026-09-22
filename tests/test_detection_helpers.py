from __future__ import annotations

import pytest

from indic_language_utils.detection.helpers import (
    detect,
    detect_batch,
    detect_batch_sync,
    detect_sync,
    get_detection_client,
    get_sync_detection_client,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.models import ProviderIdentity
from tests.test_detection_client import FakeDetectionProvider


@pytest.mark.asyncio
async def test_detect_helper() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("fake"), default_lang="hi")
    result = await detect("नमस्ते", providers=[provider])
    assert result.language == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")


def test_detect_sync_helper() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("fake"), default_lang="ta")
    result = detect_sync("வணக்கம்", providers=[provider])
    assert result.language == DEFAULT_LANGUAGE_REGISTRY.normalize("ta")


@pytest.mark.asyncio
async def test_detect_batch_helper() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("fake"), default_lang="te")
    results = await detect_batch(["నమస్కారం"], providers=[provider])
    assert len(results) == 1
    assert results[0].language == DEFAULT_LANGUAGE_REGISTRY.normalize("te")


def test_detect_batch_sync_helper() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("fake"), default_lang="kn")
    results = detect_batch_sync(["ನಮಸ್ಕಾರ"], providers=[provider])
    assert len(results) == 1
    assert results[0].language == DEFAULT_LANGUAGE_REGISTRY.normalize("kn")


def test_get_clients() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("fake"))
    client = get_detection_client(providers=[provider])
    assert client is not None

    sync_client = get_sync_detection_client(providers=[provider])
    assert sync_client is not None
