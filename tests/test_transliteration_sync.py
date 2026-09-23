from __future__ import annotations

import concurrent.futures

import pytest

from indic_language_utils.errors import InvalidInputError
from indic_language_utils.languages import LanguageTag
from indic_language_utils.models import ProviderIdentity
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId, ProviderRegistry
from indic_language_utils.routing import OrderedRouter
from indic_language_utils.transliteration.client import TransliterationClient
from indic_language_utils.transliteration.models import (
    ProviderTransliterationResult,
    TransliterationOptions,
    TransliterationRequest,
)
from indic_language_utils.transliteration.sync import SyncTransliterationClient


class SyncMockProvider:
    identity = ProviderIdentity("sync-mock", "Sync Mock")
    capabilities: tuple[CapabilityDeclaration, ...] = (
        CapabilityDeclaration(CapabilityId.TRANSLITERATION),
    )

    async def transliterate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TransliterationOptions,
        request_id: str,
    ) -> ProviderTransliterationResult:
        return ProviderTransliterationResult(
            transliterations=tuple(f"{t}-sync" for t in texts),
            model_id="sync-model",
            request_id=request_id,
        )


def _build_sync_client() -> SyncTransliterationClient:
    registry = ProviderRegistry()
    registry.register(SyncMockProvider())
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("sync-mock",)})
    async_client = TransliterationClient(router)
    return SyncTransliterationClient(async_client)


@pytest.mark.asyncio
async def test_sync_client_raises_in_active_loop() -> None:
    sync_client = _build_sync_client()
    with pytest.raises(InvalidInputError) as exc_info:
        sync_client.transliterate("namaste", source="en", target="hi")
    assert "cannot run inside an active event loop" in str(exc_info.value)

    with pytest.raises(InvalidInputError):
        sync_client.transliterate_batch(("namaste",), source="en", target="hi")


def test_sync_client_outside_event_loop() -> None:
    def worker() -> None:
        sync_client = _build_sync_client()
        result = sync_client.transliterate("namaste", source="en", target="hi")
        assert result.text == "namaste-sync"

        req = TransliterationRequest("duniya", source="en", target="hi")
        res2 = sync_client.transliterate(req)
        assert res2.text == "duniya-sync"

        batch_res = sync_client.transliterate_batch(
            ("a", "b"), source=LanguageTag("en"), target=LanguageTag("hi")
        )
        assert len(batch_res) == 2
        assert batch_res[0].text == "a-sync"
        assert batch_res[1].text == "b-sync"

        req_batch = sync_client.transliterate_batch((req,))
        assert len(req_batch) == 1
        assert req_batch[0].text == "duniya-sync"

        empty_res = sync_client.transliterate_batch(())
        assert empty_res == ()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        future.result(timeout=5.0)
