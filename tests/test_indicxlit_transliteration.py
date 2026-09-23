from __future__ import annotations

import pytest

from indic_language_utils.errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
    UnsupportedLanguagePairError,
)
from indic_language_utils.languages import LanguageTag
from indic_language_utils.transliteration.indicxlit import (
    HAVE_INDICXLIT,
    IndicXlitConfig,
    IndicXlitTransliterationProvider,
)
from indic_language_utils.transliteration.models import TransliterationOptions


def test_indicxlit_config_validation() -> None:
    with pytest.raises(ConfigurationError):
        IndicXlitConfig(beam_width=0)

    with pytest.raises(ConfigurationError):
        IndicXlitConfig(max_concurrency=0)

    config = IndicXlitConfig(beam_width=5, max_concurrency=2)
    assert config.beam_width == 5
    assert config.max_concurrency == 2


def test_indicxlit_missing_dependency() -> None:
    if not HAVE_INDICXLIT:
        with pytest.raises(MissingOptionalDependencyError) as exc_info:
            IndicXlitTransliterationProvider()
        assert "ai4bharat-transliteration" in str(exc_info.value)


@pytest.mark.asyncio
async def test_indicxlit_with_mock_engine() -> None:
    class MockEngine:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def translit_sentence(self, text: str, lang_code: str) -> str:
            self.calls.append((text, lang_code))
            if text == "namaste":
                return "नमस्ते"
            if text == "duniya":
                return "दुनिया"
            return "output"

    engine = MockEngine()
    provider = IndicXlitTransliterationProvider(engine=engine)

    result = await provider.transliterate_batch(
        ("namaste", "duniya"),
        source=LanguageTag("en"),
        target=LanguageTag("hi"),
        options=TransliterationOptions(),
        request_id="req-1",
    )

    assert result.transliterations == ("नमस्ते", "दुनिया")
    assert result.model_id == "ai4bharat/indicxlit"
    assert engine.calls == [("namaste", "hi"), ("duniya", "hi")]


@pytest.mark.asyncio
async def test_indicxlit_indic_to_roman() -> None:
    class MockEngine:
        def translit_sentence(self, text: str, lang_code: str) -> str:
            return "namaste"

    provider = IndicXlitTransliterationProvider(engine=MockEngine())
    result = await provider.transliterate_batch(
        ("नमस्ते",),
        source=LanguageTag("hi"),
        target=LanguageTag("en"),
        options=TransliterationOptions(),
        request_id="req-2",
    )
    assert result.transliterations == ("namaste",)


@pytest.mark.asyncio
async def test_indicxlit_empty_input_validation() -> None:
    provider = IndicXlitTransliterationProvider(engine=lambda t, lang_code: "x")
    with pytest.raises(InvalidInputError):
        await provider.transliterate_batch(
            (),
            source=LanguageTag("en"),
            target=LanguageTag("hi"),
            options=TransliterationOptions(),
            request_id="req-1",
        )

    with pytest.raises(InvalidInputError):
        await provider.transliterate_batch(
            ("   ",),
            source=LanguageTag("en"),
            target=LanguageTag("hi"),
            options=TransliterationOptions(),
            request_id="req-1",
        )


@pytest.mark.asyncio
async def test_indicxlit_unsupported_language_pair() -> None:
    provider = IndicXlitTransliterationProvider(engine=lambda t, lang_code: "x")
    with pytest.raises(UnsupportedLanguagePairError):
        await provider.transliterate_batch(
            ("नमस्ते",),
            source=LanguageTag("hi"),
            target=LanguageTag("ta"),
            options=TransliterationOptions(),
            request_id="req-1",
        )


@pytest.mark.asyncio
async def test_indicxlit_engine_failure() -> None:
    def broken_engine(text: str, lang_code: str) -> str:
        raise RuntimeError("Inference boom")

    provider = IndicXlitTransliterationProvider(engine=broken_engine)
    with pytest.raises(MalformedProviderResponseError):
        await provider.transliterate_batch(
            ("namaste",),
            source=LanguageTag("en"),
            target=LanguageTag("hi"),
            options=TransliterationOptions(),
            request_id="req-err",
        )
