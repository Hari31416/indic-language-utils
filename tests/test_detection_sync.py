from __future__ import annotations

import pytest

from indic_language_utils.detection.client import DetectionClient
from indic_language_utils.detection.models import DetectionRequest
from indic_language_utils.detection.sync import SyncDetectionClient
from indic_language_utils.errors import InvalidInputError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.models import ProviderIdentity
from tests.test_detection_client import FakeDetectionProvider, make_router


def test_sync_client_detect() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"), default_lang="gu")
    router = make_router([provider])
    async_client = DetectionClient(router)
    sync_client = SyncDetectionClient(async_client)

    result = sync_client.detect("કેમ છો")
    assert result.language == DEFAULT_LANGUAGE_REGISTRY.normalize("gu")
    assert len(result.candidates) == 1


def test_sync_client_detect_request() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"), default_lang="pa")
    router = make_router([provider])
    async_client = DetectionClient(router)
    sync_client = SyncDetectionClient(async_client)

    request = DetectionRequest("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ")
    result = sync_client.detect(request)
    assert result.language == DEFAULT_LANGUAGE_REGISTRY.normalize("pa")


def test_sync_client_detect_batch() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"), default_lang="bn")
    router = make_router([provider])
    async_client = DetectionClient(router)
    sync_client = SyncDetectionClient(async_client)

    results = sync_client.detect_batch(["text1", "text2"])
    assert len(results) == 2
    assert results[0].language == DEFAULT_LANGUAGE_REGISTRY.normalize("bn")

    # Empty batch returns empty tuple
    assert sync_client.detect_batch([]) == ()


@pytest.mark.asyncio
async def test_sync_client_fails_inside_running_loop() -> None:
    provider = FakeDetectionProvider(ProviderIdentity("p1"))
    router = make_router([provider])
    async_client = DetectionClient(router)
    sync_client = SyncDetectionClient(async_client)

    with pytest.raises(InvalidInputError, match="cannot run inside an active event loop"):
        sync_client.detect("test")
