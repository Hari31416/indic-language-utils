from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from indic_language_utils.config import Settings
from indic_language_utils.errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
    UnsupportedLanguagePairError,
)
from indic_language_utils.google_translate import (
    GoogletransConfig,
    GoogleTranslateConfig,
    GoogleTranslateProvider,
    GoogletransTranslationProvider,
    google_translate_language_code,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers import CapabilityId, ProviderRegistry
from indic_language_utils.retry import RetryPolicy
from indic_language_utils.routing import OrderedRouter
from indic_language_utils.translation import (
    TranslationClient,
    TranslationOptions,
)

from .translation_support import FakeTranslationProvider


@dataclass
class FakeTranslated:
    text: str
    src: str = "en"
    dest: str = "hi"


class FakeTranslator:
    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses: list[Any] = responses or []
        self.calls: list[tuple[Any, str, str]] = []
        self.closed: bool = False

    async def translate(
        self,
        text: str | list[str],
        dest: str = "en",
        src: str = "auto",
        **kwargs: Any,
    ) -> Any:
        self.calls.append((text, dest, src))
        if self.responses:
            resp = self.responses.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return resp
        if isinstance(text, list):
            return [FakeTranslated(f"translated:{t}", src=src, dest=dest) for t in text]
        return FakeTranslated(f"translated:{text}", src=src, dest=dest)

    async def __aenter__(self) -> FakeTranslator:
        return self

    async def __aexit__(self, *args: object) -> None:
        self.closed = True


def test_google_translate_config_defaults() -> None:
    config = GoogleTranslateConfig()
    assert config.service_urls == ("translate.googleapis.com",)
    assert config.timeout_seconds == 20.0
    assert config.max_concurrency == 4
    assert config.user_agent is None


def test_google_translate_config_validation() -> None:
    with pytest.raises(ConfigurationError):
        GoogleTranslateConfig(timeout_seconds=0)

    with pytest.raises(ConfigurationError):
        GoogleTranslateConfig(max_concurrency=0)

    with pytest.raises(ConfigurationError):
        GoogleTranslateConfig(service_urls=())


def test_google_translate_config_from_env() -> None:
    env = {
        "GOOGLETRANS_TIMEOUT_SECONDS": "15.0",
        "GOOGLETRANS_MAX_CONCURRENCY": "2",
        "GOOGLETRANS_SERVICE_URLS": "translate.google.com, translate.google.co.in",
        "GOOGLETRANS_USER_AGENT": "CustomUserAgent/1.0",
    }
    config = GoogleTranslateConfig.from_env(env)
    assert config.timeout_seconds == 15.0
    assert config.max_concurrency == 2
    assert config.service_urls == ("translate.google.com", "translate.google.co.in")
    assert config.user_agent == "CustomUserAgent/1.0"


def test_google_translate_config_from_settings() -> None:
    settings = Settings.load(
        overrides={
            "providers": {
                "googletrans": {
                    "endpoint": "translate.google.org",
                    "timeout_seconds": 12.0,
                    "max_concurrency": 3,
                }
            }
        }
    )
    config = GoogleTranslateConfig.from_settings(settings)
    assert config.service_urls == ("translate.google.org",)
    assert config.timeout_seconds == 12.0
    assert config.max_concurrency == 3


def test_google_translate_aliases() -> None:
    assert GoogletransConfig is GoogleTranslateConfig
    assert GoogletransTranslationProvider is GoogleTranslateProvider


def test_google_translate_language_code_mapping() -> None:
    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    assert google_translate_language_code(hi_tag) == "hi"

    kok_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("kok")
    assert google_translate_language_code(kok_tag) == "gom"

    mni_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("mni")
    assert google_translate_language_code(mni_tag) == "mni-mtei"


@pytest.mark.asyncio
async def test_google_translate_provider_single_translation() -> None:
    translator = FakeTranslator()
    provider = GoogleTranslateProvider(
        GoogleTranslateConfig(retry_policy=RetryPolicy(max_attempts=1)),
        translator=translator,
    )
    assert provider.identity.unofficial is True
    assert provider.identity.provider == "googletrans"

    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("en")

    result = await provider.translate_batch(
        ("Hello world",),
        source=en_tag,
        target=hi_tag,
        options=TranslationOptions(),
        request_id="req-1",
    )

    assert result.translations == ("translated:Hello world",)
    assert result.service_id == "googletrans"
    assert len(translator.calls) == 1
    assert translator.calls[0] == ("Hello world", "hi", "en")


@pytest.mark.asyncio
async def test_google_translate_provider_batch_translation() -> None:
    translator = FakeTranslator()
    provider = GoogleTranslateProvider(
        GoogleTranslateConfig(retry_policy=RetryPolicy(max_attempts=1)),
        translator=translator,
    )

    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("en")

    result = await provider.translate_batch(
        ("Hello", "World"),
        source=en_tag,
        target=hi_tag,
        options=TranslationOptions(),
        request_id="req-2",
    )

    assert result.translations == ("translated:Hello", "translated:World")
    assert len(translator.calls) == 1
    assert translator.calls[0] == (["Hello", "World"], "hi", "en")


@pytest.mark.asyncio
async def test_google_translate_provider_empty_input() -> None:
    translator = FakeTranslator()
    provider = GoogleTranslateProvider(translator=translator)

    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("en")

    with pytest.raises(InvalidInputError):
        await provider.translate_batch(
            (),
            source=en_tag,
            target=hi_tag,
            options=TranslationOptions(),
            request_id="req-3",
        )

    with pytest.raises(InvalidInputError):
        await provider.translate_batch(
            ("Hello", ""),
            source=en_tag,
            target=hi_tag,
            options=TranslationOptions(),
            request_id="req-3",
        )


@pytest.mark.asyncio
async def test_google_translate_provider_timeout_error() -> None:
    translator = FakeTranslator(responses=[httpx.ReadTimeout("Timeout")])
    provider = GoogleTranslateProvider(
        GoogleTranslateConfig(retry_policy=RetryPolicy(max_attempts=1)),
        translator=translator,
    )

    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("en")

    with pytest.raises(ProviderTimeoutError):
        await provider.translate_batch(
            ("Hello world",),
            source=en_tag,
            target=hi_tag,
            options=TranslationOptions(),
            request_id="req-4",
        )


@pytest.mark.asyncio
async def test_google_translate_provider_transport_error() -> None:
    translator = FakeTranslator(responses=[httpx.NetworkError("Network failed")])
    provider = GoogleTranslateProvider(
        GoogleTranslateConfig(retry_policy=RetryPolicy(max_attempts=1)),
        translator=translator,
    )

    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("en")

    with pytest.raises(TransientProviderError):
        await provider.translate_batch(
            ("Hello world",),
            source=en_tag,
            target=hi_tag,
            options=TranslationOptions(),
            request_id="req-5",
        )


@pytest.mark.asyncio
async def test_google_translate_provider_rate_limit_error() -> None:
    translator = FakeTranslator(responses=[Exception("Unexpected status code 429")])
    provider = GoogleTranslateProvider(
        GoogleTranslateConfig(retry_policy=RetryPolicy(max_attempts=1)),
        translator=translator,
    )

    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("en")

    with pytest.raises(RateLimitError):
        await provider.translate_batch(
            ("Hello world",),
            source=en_tag,
            target=hi_tag,
            options=TranslationOptions(),
            request_id="req-6",
        )


@pytest.mark.asyncio
async def test_google_translate_provider_empty_or_short_output() -> None:
    translator = FakeTranslator(responses=[FakeTranslated("")])
    provider = GoogleTranslateProvider(
        GoogleTranslateConfig(retry_policy=RetryPolicy(max_attempts=1)),
        translator=translator,
    )

    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("en")

    with pytest.raises(MalformedProviderResponseError):
        await provider.translate_batch(
            ("This is a long sentence for testing",),
            source=en_tag,
            target=hi_tag,
            options=TranslationOptions(),
            request_id="req-7",
        )


@pytest.mark.asyncio
async def test_google_translate_provider_unsupported_language() -> None:
    translator = FakeTranslator(responses=[ValueError("invalid destination language")])
    provider = GoogleTranslateProvider(
        GoogleTranslateConfig(retry_policy=RetryPolicy(max_attempts=1)),
        translator=translator,
    )

    hi_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    en_tag = DEFAULT_LANGUAGE_REGISTRY.normalize("en")

    with pytest.raises(UnsupportedLanguagePairError):
        await provider.translate_batch(
            ("Hello world",),
            source=en_tag,
            target=hi_tag,
            options=TranslationOptions(),
            request_id="req-8",
        )


@pytest.mark.asyncio
async def test_google_translate_lifecycle() -> None:
    translator = FakeTranslator()
    provider = GoogleTranslateProvider(translator=translator, owns_translator=True)

    async with provider:
        pass
    assert translator.closed is True


@pytest.mark.asyncio
async def test_translation_client_fallback_to_google_translate() -> None:
    # Primary failing provider
    failing_primary = FakeTranslationProvider(
        "bhashini",
        fail_with=TransientProviderError("Bhashini down", provider="bhashini"),
    )
    # Secondary working Google Translate provider
    google_translator = FakeTranslator()
    google_provider = GoogleTranslateProvider(
        GoogleTranslateConfig(retry_policy=RetryPolicy(max_attempts=1)),
        translator=google_translator,
    )

    registry = ProviderRegistry()
    registry.register(failing_primary)
    registry.register(google_provider)

    router = OrderedRouter(
        registry,
        {CapabilityId.TRANSLATION: ("bhashini", "googletrans")},
    )
    client = TranslationClient(router=router)

    async with client:
        result = await client.translate("Hello world", "en", "hi")
        assert result.text == "translated:Hello world"
        assert result.provider.provider == "googletrans"
        assert result.provider.unofficial is True
        assert result.fallback_count == 1


def test_google_translate_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import indic_language_utils.google_translate as gt_mod
    from indic_language_utils.errors import MissingOptionalDependencyError

    monkeypatch.setattr(gt_mod, "HAVE_GOOGLETRANS", False)
    with pytest.raises(MissingOptionalDependencyError):
        gt_mod.GoogleTranslateProvider()
