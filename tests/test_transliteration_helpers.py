from __future__ import annotations

import concurrent.futures

import pytest

from indic_language_utils.config import ProviderSettings, Settings
from indic_language_utils.languages import LanguageTag
from indic_language_utils.models import ProviderIdentity
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId
from indic_language_utils.transliteration.helpers import (
    get_sync_transliteration_client,
    get_transliteration_client,
    transliterate,
    transliterate_batch,
    transliterate_batch_sync,
    transliterate_sync,
)
from indic_language_utils.transliteration.models import (
    ProviderTransliterationResult,
    TransliterationOptions,
)


class DummyTransliterationProvider:
    identity = ProviderIdentity("dummy", "Dummy Provider")
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
            transliterations=tuple(f"{t}-dummy" for t in texts),
            model_id="dummy-m",
            request_id=request_id,
        )


@pytest.mark.asyncio
async def test_get_transliteration_client_with_custom_provider() -> None:
    provider = DummyTransliterationProvider()
    client = get_transliteration_client(providers=[provider])
    async with client:
        result = await client.transliterate("hello", source="en", target="hi")
        assert result.text == "hello-dummy"
        assert result.provider.provider == "dummy"


@pytest.mark.asyncio
async def test_get_transliteration_client_with_bhashini_settings() -> None:
    settings = Settings(
        providers={
            "bhashini": ProviderSettings(
                endpoint="https://example.com/compute",
                transliteration_service_id="service-xlit-test",
            )
        }
    )
    env = {"BHASHINI_API_KEY": "test-key"}
    client = get_transliteration_client(settings=settings, env=env)
    assert "bhashini" in {p.identity.provider for p in client.router.registry.all()}


@pytest.mark.asyncio
async def test_convenience_transliterate_and_batch() -> None:
    provider = DummyTransliterationProvider()
    res = await transliterate("namaste", source="en", target="hi", providers=[provider])
    assert res.text == "namaste-dummy"

    batch_res = await transliterate_batch(
        ["namaste", "duniya"], source="en", target="hi", providers=[provider]
    )
    assert len(batch_res) == 2
    assert batch_res[0].text == "namaste-dummy"
    assert batch_res[1].text == "duniya-dummy"


def test_convenience_sync_functions() -> None:
    def worker() -> None:
        provider = DummyTransliterationProvider()
        res = transliterate_sync("namaste", source="en", target="hi", providers=[provider])
        assert res.text == "namaste-dummy"

        batch_res = transliterate_batch_sync(
            ["namaste", "duniya"], source="en", target="hi", providers=[provider]
        )
        assert len(batch_res) == 2
        assert batch_res[0].text == "namaste-dummy"
        assert batch_res[1].text == "duniya-dummy"

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(worker).result(timeout=5.0)


def test_get_sync_transliteration_client() -> None:
    provider = DummyTransliterationProvider()
    sync_client = get_sync_transliteration_client(providers=[provider])
    assert sync_client is not None
