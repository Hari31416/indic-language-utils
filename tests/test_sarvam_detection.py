from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils.config import Secret
from indic_language_utils.detection.client import DetectionClient
from indic_language_utils.detection.models import DetectionOptions
from indic_language_utils.detection.sarvam_detect import SarvamDetectionProvider
from indic_language_utils.errors import (
    AuthenticationError,
    InvalidInputError,
    MalformedProviderResponseError,
    RateLimitError,
)
from indic_language_utils.languages import LanguageTag
from indic_language_utils.providers import CapabilityId, ProviderRegistry
from indic_language_utils.providers.bhashini import JsonResponse
from indic_language_utils.providers.sarvam import SarvamConfig
from indic_language_utils.retry import RetryPolicy
from indic_language_utils.routing import OrderedRouter
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


def lid_response(
    lang_code: str,
    script_code: str = "Deva",
    status: int = 200,
    request_id: str = "lid-req-123",
) -> JsonResponse:
    return JsonResponse(
        status,
        {
            "request_id": request_id,
            "language_code": lang_code,
            "script_code": script_code,
        },
        {"X-Request-ID": request_id},
    )


def sample_config() -> SarvamConfig:
    return SarvamConfig(
        Secret("test-api-key"),
        endpoint="https://api.sarvam.ai",
        model="sarvam-translate:v1",
        timeout_seconds=10.0,
        max_concurrency=4,
        retry_policy=RetryPolicy(max_attempts=2, base_delay=0, max_delay=0, jitter=0),
    )


@pytest.mark.asyncio
async def test_sarvam_detection_batch_success() -> None:
    transport = FakeTransport(
        [
            lid_response("hi-IN", script_code="Deva", request_id="req-hi"),
            lid_response("od-IN", script_code="Orya", request_id="req-od"),
        ]
    )
    provider = SarvamDetectionProvider(sample_config(), transport=transport)
    await provider.start()

    results = await provider.detect_batch(
        ("नमस्ते दुनिया", "ନମସ୍କାର"),
        options=DetectionOptions(),
        request_id="test-detect-req",
    )

    assert len(results) == 2
    assert results[0].candidates[0].language == LanguageTag("hi", region="IN")
    assert results[0].candidates[0].script == "Deva"
    assert results[0].candidates[0].confidence == 1.0
    assert results[0].request_id == "req-hi"

    # Verify Odia normalization from od-IN to or-IN
    assert results[1].candidates[0].language == LanguageTag("or", region="IN")
    assert results[1].candidates[0].script == "Orya"
    assert results[1].candidates[0].confidence == 1.0
    assert results[1].request_id == "req-od"

    assert len(transport.requests) == 2
    url, headers, payload, timeout = transport.requests[0]
    assert url == "https://api.sarvam.ai/text-lid"
    assert headers["api-subscription-key"] == "test-api-key"
    assert headers["Content-Type"] == "application/json"
    assert payload == {"input": "नमस्ते दुनिया"}
    assert timeout == 10.0

    await provider.close()


@pytest.mark.asyncio
async def test_sarvam_detection_empty_input_raises() -> None:
    provider = SarvamDetectionProvider(sample_config(), transport=FakeTransport([]))
    with pytest.raises(InvalidInputError):
        await provider.detect_batch(
            (),
            options=DetectionOptions(),
            request_id="req",
        )
    with pytest.raises(InvalidInputError):
        await provider.detect_batch(
            ("hello", "   "),
            options=DetectionOptions(),
            request_id="req",
        )


@pytest.mark.asyncio
async def test_sarvam_detection_errors() -> None:
    auth_transport = FakeTransport([JsonResponse(401, {"message": "Invalid key"})])
    auth_provider = SarvamDetectionProvider(sample_config(), transport=auth_transport)
    with pytest.raises(AuthenticationError):
        await auth_provider.detect_batch(
            ("text",),
            options=DetectionOptions(),
            request_id="req",
        )

    rate_transport = FakeTransport([JsonResponse(429, {})])
    rate_provider = SarvamDetectionProvider(sample_config(), transport=rate_transport)
    # retry_policy max_attempts=2 so 2 attempts then RateLimitError
    rate_transport.responses.append(JsonResponse(429, {}))
    with pytest.raises(RateLimitError):
        await rate_provider.detect_batch(
            ("text",),
            options=DetectionOptions(),
            request_id="req",
        )

    malformed_transport = FakeTransport([JsonResponse(200, {"not_lang": "val"})])
    malformed_provider = SarvamDetectionProvider(sample_config(), transport=malformed_transport)
    with pytest.raises(MalformedProviderResponseError):
        await malformed_provider.detect_batch(
            ("text",),
            options=DetectionOptions(),
            request_id="req",
        )


@pytest.mark.asyncio
async def test_sarvam_translation_provider_detect_batch_delegation() -> None:
    transport = FakeTransport([lid_response("ta-IN", script_code="Taml", request_id="ta-req")])
    trans_provider = SarvamTranslationProvider(sample_config(), transport=transport)

    results = await trans_provider.detect_batch(
        ("வணக்கம்",),
        options=DetectionOptions(),
        request_id="delegated-req",
    )
    assert len(results) == 1
    assert results[0].candidates[0].language == LanguageTag("ta", region="IN")
    assert results[0].request_id == "ta-req"


@pytest.mark.asyncio
async def test_sarvam_detection_client_integration() -> None:
    transport = FakeTransport([lid_response("bn-IN", script_code="Beng")])
    provider = SarvamDetectionProvider(sample_config(), transport=transport)

    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(
        registry,
        {CapabilityId.TEXT_LANGUAGE_DETECTION: ("sarvam",)},
    )
    client = DetectionClient(router=router)

    result = await client.detect("নমস্কার")
    assert result.language == LanguageTag("bn", region="IN")
    assert result.provider.provider == "sarvam"
