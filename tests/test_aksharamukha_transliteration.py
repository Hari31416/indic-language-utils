from __future__ import annotations

import pytest

from indic_language_utils.errors import (
    MissingOptionalDependencyError,
    UnsupportedLanguagePairError,
)
from indic_language_utils.languages import LanguageTag
from indic_language_utils.providers import CapabilityId, ProviderRegistry
from indic_language_utils.routing import OrderedRouter
from indic_language_utils.transliteration.aksharamukha import (
    HAVE_AKSHARAMUKHA,
    AksharamukhaConfig,
    AksharamukhaTransliterationProvider,
    _resolve_script,
)
from indic_language_utils.transliteration.client import TransliterationClient
from indic_language_utils.transliteration.helpers import (
    get_sync_transliteration_client,
    transliterate_sync,
)
from indic_language_utils.transliteration.models import TransliterationOptions


def test_aksharamukha_config_defaults() -> None:
    config = AksharamukhaConfig()
    assert config.roman_scheme == "ITRANS"
    assert config.nativize is True
    assert config.pre_options == ()
    assert config.post_options == ()


def test_resolve_script() -> None:
    assert _resolve_script(LanguageTag("hi"), "ITRANS") == "Devanagari"
    assert _resolve_script(LanguageTag("ta"), "ITRANS") == "Tamil"
    assert _resolve_script(LanguageTag("te"), "ITRANS") == "Telugu"
    assert _resolve_script(LanguageTag("bn"), "ITRANS") == "Bengali"
    assert _resolve_script(LanguageTag("en"), "ITRANS") == "ITRANS"
    assert _resolve_script(LanguageTag("hi", script="Latn"), "ISO") == "ISO"
    assert _resolve_script(LanguageTag("sa", script="Deva"), "ITRANS") == "Devanagari"


def test_aksharamukha_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import indic_language_utils.transliteration.aksharamukha as ak_module

    monkeypatch.setattr(ak_module, "HAVE_AKSHARAMUKHA", False)
    with pytest.raises(MissingOptionalDependencyError) as exc_info:
        AksharamukhaTransliterationProvider()
    assert "aksharamukha" in str(exc_info.value)


@pytest.mark.asyncio
async def test_aksharamukha_with_mock_engine() -> None:
    calls: list[tuple[str, str, str]] = []

    def mock_engine(
        src: str,
        tgt: str,
        txt: str,
        nativize: bool = True,
        post_options: list[str] | None = None,
        pre_options: list[str] | None = None,
    ) -> str:
        calls.append((src, tgt, txt))
        if txt == "namaste":
            return "नमस्ते"
        return "आउटपुट"

    provider = AksharamukhaTransliterationProvider(engine=mock_engine)
    result = await provider.transliterate_batch(
        ("namaste", "test"),
        source=LanguageTag("en"),
        target=LanguageTag("hi"),
        options=TransliterationOptions(),
        request_id="req-123",
    )

    assert result.transliterations == ("नमस्ते", "आउटपुट")
    assert result.model_id == "aksharamukha"
    assert result.request_id == "req-123"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_aksharamukha_same_script_bypass() -> None:
    provider = AksharamukhaTransliterationProvider(
        engine=lambda *args, **kwargs: "should not be called"
    )
    result = await provider.transliterate_batch(
        ("नमस्ते",),
        source=LanguageTag("hi"),
        target=LanguageTag("mr"),
        options=TransliterationOptions(),
        request_id="bypass-1",
    )
    assert result.transliterations == ("नमस्ते",)


@pytest.mark.asyncio
async def test_aksharamukha_engine_error() -> None:
    def broken_engine(*args: object, **kwargs: object) -> str:
        raise ValueError("Conversion crash")

    provider = AksharamukhaTransliterationProvider(engine=broken_engine)
    with pytest.raises(UnsupportedLanguagePairError) as exc_info:
        await provider.transliterate_batch(
            ("sample",),
            source=LanguageTag("en"),
            target=LanguageTag("hi"),
            options=TransliterationOptions(),
            request_id="err-1",
        )
    assert "Conversion crash" in str(exc_info.value)


@pytest.mark.skipif(not HAVE_AKSHARAMUKHA, reason="aksharamukha library is not installed")
@pytest.mark.asyncio
async def test_aksharamukha_live_script_conversions() -> None:
    provider = AksharamukhaTransliterationProvider()

    # 1. Roman to Devanagari
    res_en_hi = await provider.transliterate_batch(
        ("namaste",),
        source=LanguageTag("en"),
        target=LanguageTag("hi"),
        options=TransliterationOptions(),
        request_id="live-1",
    )
    assert "नमस्" in res_en_hi.transliterations[0]

    # 2. Devanagari to Tamil
    res_hi_ta = await provider.transliterate_batch(
        ("नमस्ते",),
        source=LanguageTag("hi"),
        target=LanguageTag("ta"),
        options=TransliterationOptions(),
        request_id="live-2",
    )
    assert res_hi_ta.transliterations[0] == "நமஸ்தே"

    # 3. Tamil to Devanagari
    res_ta_hi = await provider.transliterate_batch(
        ("வணக்கம்",),
        source=LanguageTag("ta"),
        target=LanguageTag("hi"),
        options=TransliterationOptions(),
        request_id="live-3",
    )
    assert res_ta_hi.transliterations[0] == "वणक्कम्"

    # 4. Devanagari to Roman (ITRANS)
    res_hi_en = await provider.transliterate_batch(
        ("नमस्ते",),
        source=LanguageTag("hi"),
        target=LanguageTag("en"),
        options=TransliterationOptions(),
        request_id="live-4",
    )
    assert "namaste" in res_hi_en.transliterations[0].lower()


@pytest.mark.skipif(not HAVE_AKSHARAMUKHA, reason="aksharamukha library is not installed")
@pytest.mark.asyncio
async def test_aksharamukha_client_routing() -> None:
    registry = ProviderRegistry()
    registry.register(AksharamukhaTransliterationProvider())
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("aksharamukha",)})

    client = TransliterationClient(router)
    async with client:
        res = await client.transliterate("வணக்கம்", source="ta", target="hi")
        assert res.text == "वणक्कम्"
        assert res.provider.provider == "aksharamukha"


@pytest.mark.skipif(not HAVE_AKSHARAMUKHA, reason="aksharamukha library is not installed")
def test_aksharamukha_helper_sync() -> None:
    client = get_sync_transliteration_client()
    res = client.transliterate("வணக்கம்", source="ta", target="hi")
    assert res.text == "वणक्कम्"
    assert res.provider.provider == "aksharamukha"

    # Quick one-liner
    direct = transliterate_sync("வணக்கம்", source="ta", target="hi")
    assert direct.text == "वणक्कम्"
