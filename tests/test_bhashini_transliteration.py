from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils.config import Secret
from indic_language_utils.errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    RateLimitError,
    UnsupportedLanguagePairError,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from indic_language_utils.providers.bhashini import (
    BhashiniConfig,
    JsonResponse,
)
from indic_language_utils.retry import RetryPolicy
from indic_language_utils.transliteration.bhashini_transliterate import (
    BhashiniTransliterationProvider,
)
from indic_language_utils.transliteration.models import TransliterationOptions


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


def transliteration_response(
    *targets: str | list[str], status: int = 200, model_id: str = "ai4bharat/indicxlit"
) -> JsonResponse:
    output_items: list[dict[str, object]] = []
    for t in targets:
        output_items.append({"source": "src", "target": t})
    return JsonResponse(
        status,
        {
            "pipelineResponse": [
                {
                    "taskType": "transliteration",
                    "config": {"modelId": model_id},
                    "output": output_items,
                }
            ]
        },
    )


def test_bhashini_translit_config_validation() -> None:
    with pytest.raises(ConfigurationError):
        BhashiniConfig(
            endpoint="https://example.com",
            api_key=Secret("secret"),
        )

    config = BhashiniConfig(
        endpoint="https://example.com",
        api_key=Secret("secret"),
        transliteration_service_id="bhashini/translit-default",
    )
    assert config.transliteration_service_id == "bhashini/translit-default"


@pytest.mark.asyncio
async def test_bhashini_transliterate_single_and_batch() -> None:
    transport = FakeTransport(
        [
            transliteration_response("नमस्ते", "दुनिया"),
        ]
    )
    config = BhashiniConfig(
        endpoint="https://example.com/compute",
        api_key=Secret("test-key"),
        transliteration_service_id="service-xlit-1",
        retry_policy=RetryPolicy(max_attempts=1),
    )
    provider = BhashiniTransliterationProvider(config, transport=transport)

    source = DEFAULT_LANGUAGE_REGISTRY.normalize("en")
    target = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")

    result = await provider.transliterate_batch(
        ("namaste", "duniya"),
        source=source,
        target=target,
        options=TransliterationOptions(),
        request_id="req-123",
    )

    assert result.transliterations == ("नमस्ते", "दुनिया")
    assert result.service_id == "service-xlit-1"
    assert result.model_id == "ai4bharat/indicxlit"

    # Verify request payload
    url, headers, json_body, _timeout = transport.requests[0]
    assert url == "https://example.com/compute"
    assert headers["Authorization"] == "test-key"
    assert isinstance(json_body, dict)
    task = json_body["pipelineTasks"][0]
    assert task["taskType"] == "transliteration"
    assert task["config"]["serviceId"] == "service-xlit-1"
    assert task["config"]["language"]["sourceLanguage"] == "en"
    assert task["config"]["language"]["targetLanguage"] == "hi"
    assert json_body["inputData"]["input"] == [{"source": "namaste"}, {"source": "duniya"}]


@pytest.mark.asyncio
async def test_bhashini_transliterate_suggestion_list_target() -> None:
    transport = FakeTransport(
        [
            transliteration_response(["नमस्ते", "नमस्तें"]),
        ]
    )
    config = BhashiniConfig(
        endpoint="https://example.com/compute",
        api_key=Secret("test-key"),
        transliteration_service_id="service-xlit-1",
        retry_policy=RetryPolicy(max_attempts=1),
    )
    provider = BhashiniTransliterationProvider(config, transport=transport)

    result = await provider.transliterate_batch(
        ("namaste",),
        source=LanguageTag("en"),
        target=LanguageTag("hi"),
        options=TransliterationOptions(),
        request_id="req-456",
    )
    assert result.transliterations == ("नमस्ते",)


@pytest.mark.asyncio
async def test_bhashini_transliterate_empty_input_validation() -> None:
    config = BhashiniConfig(
        endpoint="https://example.com/compute",
        api_key=Secret("test-key"),
        transliteration_service_id="service-xlit-1",
    )
    provider = BhashiniTransliterationProvider(config, transport=FakeTransport([]))

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
            ("",),
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
async def test_bhashini_transliterate_service_id_routing() -> None:
    config = BhashiniConfig(
        endpoint="https://example.com/compute",
        api_key=Secret("test-key"),
        transliteration_service_ids={
            "hi": "hi-service",
            "en>ta": "en-ta-service",
        },
    )
    provider = BhashiniTransliterationProvider(config, transport=FakeTransport([]))

    assert provider.service_id_for(LanguageTag("en"), LanguageTag("hi")) == "hi-service"
    assert provider.service_id_for(LanguageTag("en"), LanguageTag("ta")) == "en-ta-service"

    with pytest.raises(UnsupportedLanguagePairError):
        provider.service_id_for(LanguageTag("en"), LanguageTag("bn"))


@pytest.mark.asyncio
async def test_bhashini_transliterate_status_errors() -> None:
    config = BhashiniConfig(
        endpoint="https://example.com/compute",
        api_key=Secret("test-key"),
        transliteration_service_id="service-1",
        retry_policy=RetryPolicy(max_attempts=1),
    )

    # 401 Authentication
    transport = FakeTransport([JsonResponse(401, {"error": "unauthorized"})])
    provider = BhashiniTransliterationProvider(config, transport=transport)
    with pytest.raises(AuthenticationError):
        await provider.transliterate_batch(
            ("namaste",),
            source=LanguageTag("en"),
            target=LanguageTag("hi"),
            options=TransliterationOptions(),
            request_id="req-err",
        )

    # 429 RateLimit
    transport = FakeTransport([JsonResponse(429, {"error": "rate limit"}, {"retry-after": "5"})])
    provider = BhashiniTransliterationProvider(config, transport=transport)
    with pytest.raises(RateLimitError) as exc_info:
        await provider.transliterate_batch(
            ("namaste",),
            source=LanguageTag("en"),
            target=LanguageTag("hi"),
            options=TransliterationOptions(),
            request_id="req-err",
        )
    assert exc_info.value.retry_after == 5.0


@pytest.mark.asyncio
async def test_bhashini_transliterate_malformed_response() -> None:
    config = BhashiniConfig(
        endpoint="https://example.com/compute",
        api_key=Secret("test-key"),
        transliteration_service_id="service-1",
        retry_policy=RetryPolicy(max_attempts=1),
    )
    transport = FakeTransport([JsonResponse(200, {"pipelineResponse": []})])
    provider = BhashiniTransliterationProvider(config, transport=transport)

    with pytest.raises(MalformedProviderResponseError):
        await provider.transliterate_batch(
            ("namaste",),
            source=LanguageTag("en"),
            target=LanguageTag("hi"),
            options=TransliterationOptions(),
            request_id="req-err",
        )
