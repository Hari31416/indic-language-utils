from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils.config import ProviderSettings, Secret, Settings
from indic_language_utils.errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    PermissionDeniedError,
    ProviderTimeoutError,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers.bhashini import JsonResponse
from indic_language_utils.providers.sarvam import (
    SarvamConfig,
    sarvam_language_code,
)
from indic_language_utils.retry import RetryPolicy
from indic_language_utils.translation import TranslationOptions
from indic_language_utils.translation.sarvam_translate import (
    SarvamTranslationProvider,
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


def translate_response(
    text: str, status: int = 200, request_id: str = "sarvam-req-123"
) -> JsonResponse:
    return JsonResponse(
        status,
        {
            "request_id": request_id,
            "translated_text": text,
            "source_language_code": "en-IN",
        },
        {"X-Request-ID": request_id},
    )


def sample_config() -> SarvamConfig:
    return SarvamConfig(
        Secret("test-api-key"),
        endpoint="https://api.sarvam.ai",
        model="sarvam-translate:v1",
        timeout_seconds=15.0,
        max_concurrency=4,
        retry_policy=RetryPolicy(max_attempts=2, base_delay=0, max_delay=0, jitter=0),
    )


def test_sarvam_config_validation() -> None:
    with pytest.raises(ConfigurationError, match="HTTP or HTTPS"):
        SarvamConfig(Secret("key"), endpoint="ftp://invalid")
    with pytest.raises(ConfigurationError, match="model cannot be empty"):
        SarvamConfig(Secret("key"), model="")
    with pytest.raises(ConfigurationError, match="must be positive"):
        SarvamConfig(Secret("key"), timeout_seconds=0)
    with pytest.raises(ConfigurationError, match="must be positive"):
        SarvamConfig(Secret("key"), max_concurrency=0)


def test_sarvam_config_from_env() -> None:
    cfg = SarvamConfig.from_env(
        {
            "SARVAM_API_KEY": "env-key",
            "SARVAM_ENDPOINT_URL": "https://custom.sarvam.ai",
            "SARVAM_MODEL": "mayura:v1",
            "SARVAM_TIMEOUT_SECONDS": "25",
            "SARVAM_MAX_CONCURRENCY": "10",
        }
    )
    assert cfg.api_key.reveal() == "env-key"
    assert cfg.endpoint == "https://custom.sarvam.ai"
    assert cfg.model == "mayura:v1"
    assert cfg.timeout_seconds == 25.0
    assert cfg.max_concurrency == 10

    with pytest.raises(ConfigurationError):
        SarvamConfig.from_env({})


def test_sarvam_config_from_settings() -> None:
    settings = Settings(
        providers={
            "sarvam": ProviderSettings(
                endpoint="https://settings.sarvam.ai",
                model="mayura:v1",
                timeout_seconds=30.0,
                max_concurrency=6,
            )
        }
    )
    cfg = SarvamConfig.from_settings(settings, env={"SARVAM_API_KEY": "secret-key"})
    assert cfg.api_key.reveal() == "secret-key"
    assert cfg.endpoint == "https://settings.sarvam.ai"
    assert cfg.model == "mayura:v1"
    assert cfg.timeout_seconds == 30.0
    assert cfg.max_concurrency == 6

    with pytest.raises(ConfigurationError):
        SarvamConfig.from_settings(settings, env={})


def test_sarvam_language_code_mapping() -> None:
    assert sarvam_language_code(DEFAULT_LANGUAGE_REGISTRY.normalize("hi")) == "hi-IN"
    assert sarvam_language_code(DEFAULT_LANGUAGE_REGISTRY.normalize("en")) == "en-IN"
    assert sarvam_language_code(DEFAULT_LANGUAGE_REGISTRY.normalize("ta")) == "ta-IN"
    assert sarvam_language_code(DEFAULT_LANGUAGE_REGISTRY.normalize("bn")) == "bn-IN"
    assert sarvam_language_code(DEFAULT_LANGUAGE_REGISTRY.normalize("or")) == "od-IN"
    assert sarvam_language_code(DEFAULT_LANGUAGE_REGISTRY.normalize("ori_Orya")) == "od-IN"
    assert sarvam_language_code(DEFAULT_LANGUAGE_REGISTRY.normalize("od-IN")) == "od-IN"


@pytest.mark.asyncio
async def test_sarvam_translation_batch_success() -> None:
    transport = FakeTransport(
        [
            translate_response("नमस्ते", request_id="req-1"),
            translate_response("दुनिया", request_id="req-2"),
        ]
    )
    provider = SarvamTranslationProvider(sample_config(), transport=transport)
    await provider.start()

    result = await provider.translate_batch(
        ("hello", "world"),
        source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
        target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        options=TranslationOptions(),
        request_id="client-req",
    )
    assert result.translations == ("नमस्ते", "दुनिया")
    assert result.model_id == "sarvam-translate:v1"
    assert result.request_id == "req-1"
    assert len(transport.requests) == 2

    url, headers, payload, timeout = transport.requests[0]
    assert url == "https://api.sarvam.ai/translate"
    assert headers["api-subscription-key"] == "test-api-key"
    assert headers["Content-Type"] == "application/json"
    assert timeout == 15.0
    assert payload["source_language_code"] == "en-IN"
    assert payload["target_language_code"] == "hi-IN"
    assert payload["model"] == "sarvam-translate:v1"

    await provider.close()


@pytest.mark.asyncio
async def test_sarvam_translation_empty_inputs_raises() -> None:
    provider = SarvamTranslationProvider(sample_config(), transport=FakeTransport([]))
    with pytest.raises(InvalidInputError):
        await provider.translate_batch(
            (),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="req",
        )
    with pytest.raises(InvalidInputError):
        await provider.translate_batch(
            ("hello", ""),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="req",
        )


@pytest.mark.asyncio
async def test_sarvam_translation_rate_limit_retry() -> None:
    transport = FakeTransport(
        [
            JsonResponse(429, {"message": "Rate limit exceeded"}, {"Retry-After": "0"}),
            translate_response("नमस्ते"),
        ]
    )
    provider = SarvamTranslationProvider(sample_config(), transport=transport)
    result = await provider.translate_batch(
        ("hello",),
        source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
        target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        options=TranslationOptions(),
        request_id="req",
    )
    assert result.translations == ("नमस्ते",)
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_sarvam_translation_authentication_error() -> None:
    transport = FakeTransport([JsonResponse(401, {"error": {"message": "Invalid API key"}})])
    provider = SarvamTranslationProvider(sample_config(), transport=transport)
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        await provider.translate_batch(
            ("hello",),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="req",
        )


@pytest.mark.asyncio
async def test_sarvam_translation_permission_and_timeout_errors() -> None:
    forbidden = SarvamTranslationProvider(
        sample_config(), transport=FakeTransport([JsonResponse(403, {})])
    )
    with pytest.raises(PermissionDeniedError):
        await forbidden.translate_batch(
            ("hello",),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="req",
        )

    timeout = SarvamTranslationProvider(
        sample_config(),
        transport=FakeTransport([JsonResponse(504, {}), JsonResponse(504, {})]),
    )
    with pytest.raises(ProviderTimeoutError):
        await timeout.translate_batch(
            ("hello",),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="req",
        )


@pytest.mark.asyncio
async def test_sarvam_translation_malformed_response() -> None:
    transport = FakeTransport([JsonResponse(200, {"not_translated": "wrong_key"})])
    provider = SarvamTranslationProvider(sample_config(), transport=transport)
    with pytest.raises(MalformedProviderResponseError):
        await provider.translate_batch(
            ("hello",),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="req",
        )


@pytest.mark.asyncio
async def test_sarvam_translation_async_context_manager() -> None:
    transport = FakeTransport([translate_response("नमस्ते")])
    async with SarvamTranslationProvider(sample_config(), transport=transport) as provider:
        result = await provider.translate_batch(
            ("hello",),
            source=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TranslationOptions(),
            request_id="req",
        )
        assert result.translations == ("नमस्ते",)
