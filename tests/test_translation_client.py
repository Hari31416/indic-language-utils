from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from indic_language_utils.cache import CacheKeyBuilder, MemoryCache
from indic_language_utils.config import CacheSettings, Settings
from indic_language_utils.errors import AuthenticationError, TransientProviderError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.models import OperationContext
from indic_language_utils.translation import (
    CatalogEntry,
    CatalogStatus,
    LocalizationCatalog,
    TextFormat,
    TranslationClient,
    TranslationOptions,
    TranslationProcessorPipeline,
    TranslationRequest,
    TranslationResult,
    get_translation_client,
)
from indic_language_utils.translation.processing import DefaultTranslationStructureProcessor

from .translation_support import FakeTranslationProvider, PrefixProcessor, router_for

EN = DEFAULT_LANGUAGE_REGISTRY.normalize("en")
HI = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")


@pytest.mark.asyncio
async def test_translate_and_batch_preserve_order() -> None:
    provider = FakeTranslationProvider(transform=str.upper)
    client = TranslationClient(router_for(provider))
    requests = tuple(TranslationRequest(text, EN, HI) for text in ("one", "two", "three"))
    results = await client.translate_batch(requests)
    assert tuple(result.text for result in results) == ("ONE", "TWO", "THREE")


@pytest.mark.asyncio
async def test_malformed_batch_retries_individual_segments() -> None:
    provider = FakeTranslationProvider(transform=str.upper, malformed_batch_once=True)
    client = TranslationClient(router_for(provider))
    request = TranslationRequest(
        "First sentence. Second sentence.",
        EN,
        HI,
        TranslationOptions(max_segment_characters=16),
    )
    result = await client.translate(request)
    assert result.text == request.text.upper()
    assert len(provider.calls) == 3
    assert all(len(call) == 1 for call in provider.calls[1:])


@pytest.mark.asyncio
async def test_dropped_placeholder_is_preserved_by_translating_around_it() -> None:
    def drop_placeholder(text: str) -> str:
        return text.replace("[[ILU-P-000000]]", "").upper()

    provider = FakeTranslationProvider(transform=drop_placeholder)
    source = "Read `a value with spaces` and visit https://example.gov/path today."
    request = TranslationRequest(
        source, EN, HI, TranslationOptions(text_format=TextFormat.MARKDOWN)
    )
    result = await TranslationClient(router_for(provider)).translate(request)
    assert result.text == "READ `a value with spaces` AND VISIT https://example.gov/path TODAY."
    assert len(provider.calls) > 2
    assert all("[[ILU-P-" not in call[0] for call in provider.calls[2:])


@pytest.mark.asyncio
async def test_literal_bracketed_numbers_do_not_collide_with_protected_content() -> None:
    provider = FakeTranslationProvider(transform=lambda text: text)
    client = TranslationClient(router_for(provider))
    for source in (
        "Reference [123456] is valid.",
        "Reference [000000] uses https://example.gov.",
        "Literal [[ILU-P-000000]] uses https://example.gov.",
    ):
        result = await client.translate(TranslationRequest(source, EN, HI))
        assert result.text == source


@pytest.mark.asyncio
async def test_provider_fallback_is_reported() -> None:
    failing = FakeTranslationProvider(
        "first", fail_with=TransientProviderError("temporary", provider="first")
    )
    working = FakeTranslationProvider("second", transform=str.upper)
    result = await TranslationClient(router_for(failing, working)).translate(
        TranslationRequest("hello", EN, HI)
    )
    assert result.text == "HELLO"
    assert result.provider.provider == "second"
    assert result.fallback_count == 1


@pytest.mark.asyncio
async def test_authentication_failure_is_not_silently_replaced() -> None:
    failing = FakeTranslationProvider(
        fail_with=AuthenticationError("bad credential", provider="fake")
    )
    with pytest.raises(AuthenticationError):
        await TranslationClient(router_for(failing)).translate(TranslationRequest("hello", EN, HI))


@pytest.mark.asyncio
async def test_reviewed_catalog_exact_match_bypasses_provider() -> None:
    entry = CatalogEntry(
        "welcome",
        "Welcome",
        "स्वागत",
        EN,
        HI,
        "2026-01",
        "reviewed fixture",
        CatalogStatus.REVIEWED,
        "reviewer",
    )
    provider = FakeTranslationProvider()
    catalog = LocalizationCatalog((entry,), version="catalog-v1")
    client = TranslationClient(router_for(provider), catalog=catalog)
    result = await client.translate(TranslationRequest("Welcome", EN, HI, message_id="welcome"))
    assert result.text == "स्वागत"
    assert result.provider.provider == "catalog"
    assert not provider.calls

    changed = await client.translate(
        TranslationRequest("Welcome back", EN, HI, message_id="welcome")
    )
    assert changed.text.startswith("translated:")


@pytest.mark.asyncio
async def test_runtime_cache_and_identity_include_options() -> None:
    provider = FakeTranslationProvider(transform=str.upper)
    cache: MemoryCache[TranslationResult] = MemoryCache()
    client = TranslationClient(
        router_for(provider), cache=cache, cache_keys=CacheKeyBuilder("test", tenant="one")
    )
    request = TranslationRequest("hello", EN, HI)
    first = await client.translate(request)
    second = await client.translate(request)
    assert not first.cache.hit
    assert second.cache.hit
    assert len(provider.calls) == 1
    another_context = replace(request, context=OperationContext(request_id="new-request"))
    cached_for_new_request = await client.translate(another_context)
    assert cached_for_new_request.request_id == "new-request"

    markdown = replace(request, options=TranslationOptions(text_format=TextFormat.MARKDOWN))
    await client.translate(markdown)
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_same_language_is_explicit_identity_result() -> None:
    provider = FakeTranslationProvider()
    result = await TranslationClient(router_for(provider)).translate(
        TranslationRequest("unchanged", EN, EN)
    )
    assert result.text == "unchanged"
    assert result.provider.provider == "identity"
    assert not provider.calls


@pytest.mark.asyncio
async def test_markdown_with_only_structure_is_preserved_without_provider_call() -> None:
    provider = FakeTranslationProvider()
    result = await TranslationClient(router_for(provider)).translate(
        TranslationRequest(
            "\n```py\nvalue = 1\n```\n",
            EN,
            HI,
            TranslationOptions(text_format=TextFormat.MARKDOWN),
        )
    )
    assert result.text == "\n```py\nvalue = 1\n```\n"
    assert result.provider.provider == "structure"
    assert not provider.calls


@pytest.mark.asyncio
async def test_processor_identity_participates_in_cache_keys() -> None:
    provider = FakeTranslationProvider(transform=lambda text: text)
    cache: MemoryCache[TranslationResult] = MemoryCache()
    keys = CacheKeyBuilder("processor-test")
    request = TranslationRequest("hello", EN, HI)
    default_client = TranslationClient(router_for(provider), cache=cache, cache_keys=keys)
    await default_client.translate(request)

    custom = TranslationProcessorPipeline(
        DefaultTranslationStructureProcessor(), (PrefixProcessor(),)
    )
    custom_client = TranslationClient(
        router_for(provider), cache=cache, cache_keys=keys, processors=custom
    )
    result = await custom_client.translate(request)
    assert result.text == "hello"
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_best_effort_returns_source_text_with_warning_on_failure() -> None:
    failing = FakeTranslationProvider(
        fail_with=TransientProviderError("server down", provider="fake")
    )
    request = TranslationRequest("hello", EN, HI, options=TranslationOptions(best_effort=True))
    result = await TranslationClient(router_for(failing)).translate(request)
    assert result.text == "hello"
    assert result.provider.provider == "fallback-source"
    assert any(w.code == "translation_fallback" for w in result.warnings)


@pytest.mark.asyncio
async def test_markdown_reuses_unchanged_segments_and_whole_result() -> None:
    provider = FakeTranslationProvider(transform=str.upper)
    settings = Settings(cache=CacheSettings(enabled=True, backend="memory"))
    client = get_translation_client(settings, providers=[provider])
    options = TranslationOptions(text_format=TextFormat.MARKDOWN)
    original = "# Heading\nFirst line.\nSecond line.\n"
    changed = "# Heading\nFirst line.\nChanged line.\n"

    first = await client.translate(original, EN, HI, options=options)
    second = await client.translate(changed, EN, HI, options=options)
    repeated = await client.translate(changed, EN, HI, options=options)
    structural_change = await client.translate(
        changed + "\n```py\nvalue = 1\n```\n", EN, HI, options=options
    )

    assert first.text == original.upper()
    assert second.text == changed.upper()
    assert not second.cache.hit
    assert repeated.cache.hit
    assert structural_change.cache.hit
    assert provider.calls == [
        ("Heading", "First line.", "Second line."),
        ("Changed line.",),
    ]


@pytest.mark.asyncio
async def test_segment_cache_keeps_provider_fallback_consistent() -> None:
    first = FakeTranslationProvider("first", transform=lambda text: f"A:{text}")
    second = FakeTranslationProvider("second", transform=lambda text: f"B:{text}")
    client = TranslationClient(
        router_for(first, second),
        cache=MemoryCache(),
        segment_cache=MemoryCache(),
    )
    options = TranslationOptions(text_format=TextFormat.MARKDOWN)
    await client.translate("Keep\nOld\n", EN, HI, options=options)
    first.fail_with = TransientProviderError("temporary", provider="first")

    result = await client.translate("Keep\nNew\n", EN, HI, options=options)

    assert result.text == "B:Keep\nB:New\n"
    assert result.provider.provider == "second"
    assert result.fallback_count == 1
    assert first.calls[-1] == ("New",)
    assert second.calls == [("Keep", "New")]


@pytest.mark.asyncio
async def test_model_change_invalidates_document_and_segment_cache() -> None:
    class ModelAwareProvider(FakeTranslationProvider):
        config: SimpleNamespace

    provider = ModelAwareProvider()
    model = SimpleNamespace(model="model-a")
    provider.config = model
    provider.transform = lambda text: f"{model.model}:{text}"
    client = TranslationClient(
        router_for(provider),
        cache=MemoryCache(),
        segment_cache=MemoryCache(),
    )
    options = TranslationOptions(text_format=TextFormat.MARKDOWN)

    first = await client.translate("Same line\n", EN, HI, options=options)
    model.model = "model-b"
    second = await client.translate("Same line\n", EN, HI, options=options)

    assert first.text == "model-a:Same line\n"
    assert second.text == "model-b:Same line\n"
    assert not second.cache.hit
    assert provider.calls == [("Same line",), ("Same line",)]


@pytest.mark.asyncio
async def test_protected_content_is_part_of_segment_identity() -> None:
    provider = FakeTranslationProvider(transform=lambda text: text)
    client = TranslationClient(
        router_for(provider), cache=MemoryCache(), segment_cache=MemoryCache()
    )
    options = TranslationOptions(text_format=TextFormat.MARKDOWN)

    first = await client.translate("Visit https://one.example/path\n", EN, HI, options=options)
    second = await client.translate("Visit https://two.example/path\n", EN, HI, options=options)

    assert first.text == "Visit https://one.example/path\n"
    assert second.text == "Visit https://two.example/path\n"
    assert not second.cache.hit
    assert provider.calls == [
        ("Visit [[ILU-P-000000]]",),
        ("Visit [[ILU-P-000000]]",),
    ]
