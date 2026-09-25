import asyncio
from pathlib import Path

import pytest

from indic_language_utils import (
    CacheSettings,
    CapabilityDeclaration,
    CapabilityId,
    ProviderIdentity,
    Settings,
    get_translation_client,
)
from indic_language_utils.errors import UnsupportedLanguageError
from indic_language_utils.languages import (
    DEFAULT_LANGUAGE_REGISTRY,
    LanguageDefinition,
    LanguageRegistry,
    LanguageTag,
)
from indic_language_utils.translation import ProviderTranslationResult, TranslationOptions


def test_custom_language_registry_survives_sqlite_cache(tmp_path: Path) -> None:
    class CustomProvider:
        identity = ProviderIdentity("custom")
        capabilities: tuple[CapabilityDeclaration, ...] = (
            CapabilityDeclaration(CapabilityId.TRANSLATION),
        )
        calls = 0

        async def translate_batch(
            self,
            texts: tuple[str, ...],
            *,
            source: LanguageTag,
            target: LanguageTag,
            options: TranslationOptions,
            request_id: str,
        ) -> ProviderTranslationResult:
            self.calls += 1
            return ProviderTranslationResult(tuple(f"{target}:{text}" for text in texts))

    registry = LanguageRegistry(
        (
            *DEFAULT_LANGUAGE_REGISTRY.definitions(),
            LanguageDefinition(LanguageTag("fr", region="FR"), "French"),
        )
    )
    provider = CustomProvider()
    settings = Settings(
        cache=CacheSettings(enabled=True, backend="sqlite", path=str(tmp_path / "cache.db"))
    )

    async def run() -> None:
        async with get_translation_client(
            settings, providers=[provider], language_registry=registry
        ) as client:
            first = await client.translate("bonjour", "fr", "hi")
            second = await client.translate("bonjour", "fr", "hi")
        assert str(first.source) == "fr-FR"
        assert second.cache.hit
        assert provider.calls == 1

    asyncio.run(run())


def test_registry_has_english_and_all_scheduled_languages() -> None:
    assert len(DEFAULT_LANGUAGE_REGISTRY.definitions()) == 23


@pytest.mark.parametrize(
    ("value", "expected"),
    [("HI_in", "hi-IN"), ("hin", "hi-IN"), ("od-IN", "or-IN"), ("ori_Orya", "or-IN")],
)
def test_registry_normalizes_aliases(value: str, expected: str) -> None:
    assert str(DEFAULT_LANGUAGE_REGISTRY.normalize(value)) == expected


def test_registry_retains_explicit_script() -> None:
    assert DEFAULT_LANGUAGE_REGISTRY.normalize("ks-Arab-IN") == LanguageTag("ks", "Arab", "IN")


def test_registry_rejects_unknown_language() -> None:
    with pytest.raises(UnsupportedLanguageError):
        DEFAULT_LANGUAGE_REGISTRY.normalize("zz-IN")
