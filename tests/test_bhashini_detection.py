from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils.bhashini import (
    BhashiniConfig,
    BhashiniDetectionProvider,
    BhashiniTranslationProvider,
    JsonResponse,
)
from indic_language_utils.config import ProviderSettings, Secret, Settings
from indic_language_utils.detection.client import DetectionClient
from indic_language_utils.detection.models import DetectionOptions
from indic_language_utils.errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    RateLimitError,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers import CapabilityId, ProviderRegistry
from indic_language_utils.retry import RetryPolicy
from indic_language_utils.routing import OrderedRouter


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


def detection_response(*predictions: list[dict[str, object]], status: int = 200) -> JsonResponse:
    output_items: list[dict[str, object]] = []
    for pred_list in predictions:
        output_items.append({"langPrediction": pred_list})
    return JsonResponse(
        status,
        {
            "pipelineResponse": [
                {
                    "taskType": "txt-lang-detection",
                    "config": {"modelId": "bhashini-lid-v1"},
                    "output": output_items,
                }
            ]
        },
        {"X-Request-ID": "bhashini-req-789"},
    )


def config(
    translation_service: str | None = None,
    detection_service: str | None = "bhashini-detect-svc",
) -> BhashiniConfig:
    return BhashiniConfig(
        "https://example.test/inference",
        Secret("credential"),
        translation_service,
        retry_policy=RetryPolicy(max_attempts=2, base_delay=0, max_delay=0, jitter=0),
        detection_service_id=detection_service,
    )


def test_bhashini_config_detection_only() -> None:
    cfg = config(translation_service=None, detection_service="lid-service")
    assert cfg.detection_service_id == "lid-service"
    assert cfg.translation_service_id is None


def test_bhashini_config_missing_all_services_raises() -> None:
    with pytest.raises(ConfigurationError, match="service ID is required"):
        BhashiniConfig(
            "https://example.test/inference",
            Secret("credential"),
            translation_service_id=None,
            detection_service_id=None,
        )


def test_bhashini_config_from_settings() -> None:
    settings = Settings(
        providers={
            "bhashini": ProviderSettings(
                endpoint="https://bhashini.ai/api",
                detection_service_id="svc-tld-1",
            )
        }
    )
    cfg = BhashiniConfig.from_settings(settings, env={"BHASHINI_API_KEY": "secret-key"})
    assert cfg.endpoint == "https://bhashini.ai/api"
    assert cfg.detection_service_id == "svc-tld-1"


@pytest.mark.asyncio
async def test_bhashini_detection_payload_and_parse() -> None:
    pred = [
        {"langCode": "hi", "langScore": 0.88},
        {"langCode": "mr", "langScore": 0.12},
    ]
    transport = FakeTransport([detection_response(pred)])
    provider = BhashiniDetectionProvider(config(), transport=transport)
    await provider.start()

    results = await provider.detect_batch(
        ("नमस्ते दुनिया",),
        options=DetectionOptions(max_candidates=2),
        request_id="req-test-1",
    )
    assert len(results) == 1
    candidates = results[0].candidates
    assert len(candidates) == 2
    assert candidates[0].language == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    assert pytest.approx(candidates[0].confidence) == 0.88
    assert candidates[1].language == DEFAULT_LANGUAGE_REGISTRY.normalize("mr")
    assert pytest.approx(candidates[1].confidence) == 0.12
    assert results[0].model_id == "bhashini-lid-v1"

    _, headers, payload, timeout = transport.requests[0]
    assert headers["Authorization"] == "credential"
    assert timeout == 20
    task = payload["pipelineTasks"][0]  # type: ignore[index]
    assert task["taskType"] == "txt-lang-detection"
    assert task["config"]["serviceId"] == "bhashini-detect-svc"
    assert payload["inputData"] == {"input": [{"source": "नमस्ते दुनिया"}]}


@pytest.mark.asyncio
async def test_bhashini_detection_empty_input() -> None:
    provider = BhashiniDetectionProvider(config())
    with pytest.raises(InvalidInputError):
        await provider.detect_batch((), options=DetectionOptions(), request_id="req-1")

    with pytest.raises(InvalidInputError):
        await provider.detect_batch(("",), options=DetectionOptions(), request_id="req-1")


@pytest.mark.asyncio
async def test_bhashini_detection_rate_limit() -> None:
    transport = FakeTransport(
        [
            JsonResponse(429, {}, {"Retry-After": "10"}),
            JsonResponse(429, {}, {"Retry-After": "10"}),
        ]
    )
    provider = BhashiniDetectionProvider(config(), transport=transport)
    with pytest.raises(RateLimitError):
        await provider.detect_batch(("text",), options=DetectionOptions(), request_id="req-1")


@pytest.mark.asyncio
async def test_bhashini_detection_auth_error() -> None:
    transport = FakeTransport([JsonResponse(401, {})])
    provider = BhashiniDetectionProvider(config(), transport=transport)
    with pytest.raises(AuthenticationError):
        await provider.detect_batch(("text",), options=DetectionOptions(), request_id="req-1")


@pytest.mark.asyncio
async def test_bhashini_detection_malformed_response() -> None:
    transport = FakeTransport([JsonResponse(200, {"pipelineResponse": []})])
    provider = BhashiniDetectionProvider(config(), transport=transport)
    with pytest.raises(MalformedProviderResponseError):
        await provider.detect_batch(("text",), options=DetectionOptions(), request_id="req-1")


@pytest.mark.asyncio
async def test_bhashini_dual_capability_translation_provider() -> None:
    # Dual capability when detection_service_id is configured
    cfg = config(translation_service="trans-svc", detection_service="detect-svc")
    transport = FakeTransport(
        [
            detection_response([{"langCode": "ta", "langScore": 0.99}]),
        ]
    )
    provider = BhashiniTranslationProvider(cfg, transport=transport)
    declared_caps = {c.capability for c in provider.capabilities}
    assert CapabilityId.TRANSLATION in declared_caps
    assert CapabilityId.TEXT_LANGUAGE_DETECTION in declared_caps

    results = await provider.detect_batch(
        ("வணக்கம்",),
        options=DetectionOptions(),
        request_id="req-dual",
    )
    assert len(results) == 1
    assert results[0].candidates[0].language == DEFAULT_LANGUAGE_REGISTRY.normalize("ta")


@pytest.mark.asyncio
async def test_detection_client_with_bhashini() -> None:
    transport = FakeTransport(
        [
            detection_response([{"langCode": "te", "langScore": 0.96}]),
        ]
    )
    bhashini = BhashiniDetectionProvider(config(), transport=transport)
    registry = ProviderRegistry()
    registry.register(bhashini)
    router = OrderedRouter(registry, {CapabilityId.TEXT_LANGUAGE_DETECTION: ("bhashini",)})
    client = DetectionClient(router)

    result = await client.detect("నమస్కారం")
    assert result.language == DEFAULT_LANGUAGE_REGISTRY.normalize("te")
    assert result.provider.provider == "bhashini"
    assert result.provider.model_id == "bhashini-lid-v1"
