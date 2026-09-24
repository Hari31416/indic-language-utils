from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils.config import Secret, Settings
from indic_language_utils.errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    UnsupportedLanguagePairError,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers.base import CapabilityId
from indic_language_utils.providers.bhashini import (
    BhashiniConfig,
    JsonResponse,
    _raise_bhashini_status,
    bhashini_language_code,
)
from indic_language_utils.retry import RetryPolicy
from indic_language_utils.translation import TranslationOptions
from indic_language_utils.translation.bhashini_translate import (
    BhashiniTranslationProvider,
)


@dataclass
class FakeTransport:
    responses: list[JsonResponse]
    requests: list[tuple[str, Mapping[str, str], Mapping[str, object], float]] = field(
        default_factory=list
    )
    closed: bool = False

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        self.requests.append((url, headers, json, timeout_seconds))
        return self.responses.pop(0)

    async def close(self) -> None:
        self.closed = True


def response(*translations: str, status: int = 200) -> JsonResponse:
    return JsonResponse(
        status,
        {
            "pipelineResponse": [
                {
                    "taskType": "translation",
                    "config": {"modelId": "model-1"},
                    "output": [{"target": value} for value in translations],
                }
            ]
        },
        {"X-Request-ID": "provider-request"},
    )


def config() -> BhashiniConfig:
    return BhashiniConfig(
        "https://example.test/inference",
        Secret("credential"),
        "configured-service",
        retry_policy=RetryPolicy(max_attempts=2, base_delay=0, max_delay=0, jitter=0),
    )


def test_bhashini_error_log_omits_provider_response(caplog: pytest.LogCaptureFixture) -> None:
    response = JsonResponse(400, {"message": "invalid service", "input": "private source text"})
    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(InvalidInputError, match="invalid service"),
    ):
        _raise_bhashini_status("bhashini", CapabilityId.TRANSLATION, response, "request")
    assert "private source text" not in caplog.text


@pytest.mark.asyncio
async def test_payload_language_mapping_and_response_metadata() -> None:
    transport = FakeTransport([response("नमस्ते", "दुनिया")])
    provider = BhashiniTranslationProvider(config(), transport=transport)
    await provider.start()
    result = await provider.translate_batch(
        ("hello", "world"),
        source=DEFAULT_LANGUAGE_REGISTRY.normalize("en-IN"),
        target=DEFAULT_LANGUAGE_REGISTRY.normalize("hin"),
        options=TranslationOptions(),
        request_id="library-request",
    )
    assert result.translations == ("नमस्ते", "दुनिया")
    assert result.service_id == "configured-service"
    assert result.model_id == "model-1"
    assert result.request_id == "provider-request"

    _, headers, payload, timeout = transport.requests[0]
    assert headers["Authorization"] == "credential"
    assert timeout == 20
    task = payload["pipelineTasks"][0]  # type: ignore[index]
    assert task["config"]["language"] == {
        "sourceLanguage": "en",
        "targetLanguage": "hi",
    }
    assert payload["inputData"] == {"input": [{"source": "hello"}, {"source": "world"}]}


@pytest.mark.asyncio
async def test_rate_limit_is_retried() -> None:
    transport = FakeTransport([JsonResponse(429, {}, {"Retry-After": "0"}), response("ok")])
    provider = BhashiniTranslationProvider(config(), transport=transport)
    await provider.start()
    result = await provider.translate_batch(
        ("hello",),
        source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
        target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        options=TranslationOptions(),
        request_id="request",
    )
    assert result.translations == ("ok",)
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_authentication_and_malformed_responses_are_strict() -> None:
    auth = BhashiniTranslationProvider(config(), transport=FakeTransport([JsonResponse(401, {})]))
    await auth.start()
    with pytest.raises(AuthenticationError):
        await auth.translate_batch(
            ("hello",),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="request",
        )


@pytest.mark.asyncio
async def test_mismatched_batch_is_returned_for_client_level_recovery() -> None:
    provider = BhashiniTranslationProvider(config(), transport=FakeTransport([response("one")]))
    await provider.start()
    result = await provider.translate_batch(
        ("one", "two"),
        source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
        target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        options=TranslationOptions(),
        request_id="request",
    )
    assert result.translations == ("one",)

    malformed = BhashiniTranslationProvider(
        config(), transport=FakeTransport([JsonResponse(200, {})])
    )
    await malformed.start()
    with pytest.raises(MalformedProviderResponseError):
        await malformed.translate_batch(
            ("hello",),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="request",
        )


def test_translation_service_id_is_required_and_odia_alias_maps_inside_adapter() -> None:
    with pytest.raises(ConfigurationError):
        BhashiniConfig("https://example.test", Secret("key"), "")
    assert bhashini_language_code(DEFAULT_LANGUAGE_REGISTRY.normalize("ori_Orya")) == "or"


def test_environment_configuration() -> None:
    loaded = BhashiniConfig.from_env(
        {
            "BHASHINI_ENDPOINT_URL": "https://example.test/inference",
            "BHASHINI_API_KEY": "key",
            "BHASHINI_TRANSLATION_SERVICE_ID": "service",
            "BHASHINI_MAX_CONCURRENCY": "3",
        }
    )
    assert loaded.translation_service_id == "service"
    assert loaded.max_concurrency == 3
    with pytest.raises(ConfigurationError):
        BhashiniConfig.from_env({})


def test_language_specific_translation_service_resolution() -> None:
    configured = BhashiniConfig(
        "https://example.test/inference",
        Secret("key"),
        "default-service",
        {
            "hi": "target-hindi-service",
            "en>hi": "english-hindi-service",
        },
    )
    provider = BhashiniTranslationProvider(configured, transport=FakeTransport([]))
    en = DEFAULT_LANGUAGE_REGISTRY.normalize("en")
    hi = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    ta = DEFAULT_LANGUAGE_REGISTRY.normalize("ta")
    assert provider.service_id_for(en, hi) == "english-hindi-service"
    assert provider.service_id_for(ta, hi) == "target-hindi-service"
    assert provider.service_id_for(en, ta) == "default-service"


def test_mapping_only_config_rejects_unconfigured_pair() -> None:
    configured = BhashiniConfig(
        "https://example.test/inference",
        Secret("key"),
        None,
        {"hi-IN": "hindi-service"},
    )
    provider = BhashiniTranslationProvider(configured, transport=FakeTransport([]))
    with pytest.raises(UnsupportedLanguagePairError):
        provider.service_id_for(
            DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            DEFAULT_LANGUAGE_REGISTRY.normalize("ta"),
        )


def _live_bhashini_config() -> BhashiniConfig | None:
    if not os.environ.get("RUN_LIVE_TESTS") or not os.environ.get("BHASHINI_API_KEY"):
        return None
    try:
        return BhashiniConfig.from_settings(Settings.load())
    except Exception:
        return None


@pytest.mark.live_bhashini
@pytest.mark.skipif(
    _live_bhashini_config() is None,
    reason="live Bhashini credentials or settings are not configured",
)
@pytest.mark.asyncio
async def test_live_bhashini_translation() -> None:
    config = _live_bhashini_config()
    assert config is not None
    provider = BhashiniTranslationProvider(config)
    async with provider:
        result = await provider.translate_batch(
            ("Hello",),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="live-test",
        )
    assert result.translations[0].strip()
