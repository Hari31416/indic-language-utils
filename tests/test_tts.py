from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils import BhashiniConfig, Secret, TTSOptions, TTSRequest, get_tts_client
from indic_language_utils.config import CacheSettings, Settings
from indic_language_utils.errors import (
    ConfigurationError,
    MalformedProviderResponseError,
    TransientProviderError,
    UnsupportedLanguageError,
)
from indic_language_utils.languages import LanguageTag
from indic_language_utils.models import ProviderIdentity
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId
from indic_language_utils.providers.bhashini import JsonResponse
from indic_language_utils.providers.sarvam import SarvamConfig
from indic_language_utils.tts.bhashini import BhashiniTTSProvider
from indic_language_utils.tts.models import ProviderTTSResult
from indic_language_utils.tts.sarvam import SarvamTTSProvider

WAV = b"RIFF\x04\x00\x00\x00WAVE" + b"test-audio"


@dataclass
class FakeTransport:
    responses: list[JsonResponse]
    payloads: list[Mapping[str, object]] = field(default_factory=list)

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        self.payloads.append(json)
        return self.responses.pop(0)

    async def close(self) -> None:
        pass


def response(audio: bytes = WAV) -> JsonResponse:
    return JsonResponse(
        200,
        {
            "pipelineResponse": [
                {"taskType": "tts", "audio": [{"audioContent": base64.b64encode(audio).decode()}]}
            ]
        },
        {"x-request-id": "tts-provider-123"},
    )


def config() -> BhashiniConfig:
    return BhashiniConfig(
        "https://example.test/inference",
        Secret("key"),
        tts_model_id="default-voice",
        tts_model_ids={"hi": "hindi-voice"},
    )


@pytest.mark.asyncio
async def test_bhashini_tts_with_language_and_model_options() -> None:
    transport = FakeTransport([response()])
    provider = BhashiniTTSProvider(config(), transport=transport)
    options = TTSOptions(
        {"gender": "female", "samplingRate": 16000, "voiceId": "speaker-2", "tone": "calm"}
    )
    result = await provider.synthesize_batch(
        ("नमस्ते",), language=TTSRequest("x", "hi").language, options=options, request_id="req"
    )
    assert result[0].audio == WAV
    assert result[0].audio_format == "wav"
    assert result[0].model_id == "hindi-voice"
    task = transport.payloads[0]["pipelineTasks"][0]  # type: ignore[index]
    assert task["taskType"] == "tts"
    assert task["config"] == {
        "gender": "female",
        "samplingRate": 16000,
        "voiceId": "speaker-2",
        "tone": "calm",
        "serviceId": "hindi-voice",
        "language": {"sourceLanguage": "hi"},
    }
    assert transport.payloads[0]["inputData"] == {"input": [{"source": "नमस्ते"}]}


@pytest.mark.asyncio
async def test_tts_without_language_uses_default_model() -> None:
    transport = FakeTransport([response()])
    provider = BhashiniTTSProvider(config(), transport=transport)
    client = get_tts_client(Settings(cache=CacheSettings()), providers=[provider])
    result = await client.synthesize("Hello", options=TTSOptions({"gender": "male"}))
    assert result.audio == WAV
    assert result.language is None
    assert result.model_id == "default-voice"
    task = transport.payloads[0]["pipelineTasks"][0]  # type: ignore[index]
    assert "language" not in task["config"]


def test_tts_options_reject_reserved_or_invalid_values() -> None:
    with pytest.raises(ValueError, match="override"):
        TTSOptions({"serviceId": "other"})
    with pytest.raises(ValueError, match="JSON"):
        TTSOptions({"tone": object()})
    with pytest.raises(ValueError, match="override"):
        TTSOptions(provider_parameters={"bhashini": {"serviceId": "other"}})


@pytest.mark.asyncio
async def test_tts_skips_provider_requiring_language() -> None:
    sarvam = SarvamTTSProvider(SarvamConfig(Secret("key"), tts_model_id="bulbul:v3"))
    transport = FakeTransport([response()])
    bhashini = BhashiniTTSProvider(config(), transport=transport)
    client = get_tts_client(providers=[sarvam, bhashini])
    result = await client.synthesize("Hello")
    assert result.provider == "bhashini"
    assert result.fallback_count == 0


@pytest.mark.asyncio
async def test_tts_fallback_uses_only_target_provider_options() -> None:
    class FailingProvider:
        identity = ProviderIdentity("first", "First")
        capabilities: tuple[CapabilityDeclaration, ...] = (
            CapabilityDeclaration(CapabilityId.TEXT_TO_SPEECH),
        )

        async def synthesize_batch(
            self,
            texts: tuple[str, ...],
            *,
            language: LanguageTag | None,
            options: TTSOptions,
            request_id: str,
        ) -> tuple[ProviderTTSResult, ...]:
            assert options.parameters == {"speaker": "first-speaker"}
            raise TransientProviderError("temporary failure")

    class SuccessProvider:
        identity = ProviderIdentity("second", "Second")
        capabilities: tuple[CapabilityDeclaration, ...] = (
            CapabilityDeclaration(CapabilityId.TEXT_TO_SPEECH),
        )

        async def synthesize_batch(
            self,
            texts: tuple[str, ...],
            *,
            language: LanguageTag | None,
            options: TTSOptions,
            request_id: str,
        ) -> tuple[ProviderTTSResult, ...]:
            assert options.parameters == {"voice": "second-voice"}
            return (ProviderTTSResult(WAV, "wav"),)

    client = get_tts_client(providers=[FailingProvider(), SuccessProvider()])
    result = await client.synthesize(
        "Hello",
        options=TTSOptions(
            {"speaker": "first-speaker"},
            {"second": {"voice": "second-voice"}},
        ),
    )
    assert result.provider == "second"
    assert result.fallback_count == 1


def test_invalid_edge_tts_configuration_is_reported() -> None:
    with pytest.raises(ConfigurationError, match="Edge TTS timeout and concurrency"):
        get_tts_client(env={"EDGE_TTS_TIMEOUT_SECONDS": "0"})


@pytest.mark.asyncio
async def test_tts_rejects_malformed_audio_and_missing_model() -> None:
    provider = BhashiniTTSProvider(config(), transport=FakeTransport([response(b"")]))
    with pytest.raises(MalformedProviderResponseError):
        await provider.synthesize_batch(
            ("Hello",), language=None, options=TTSOptions(), request_id="req"
        )
    mapping_only = BhashiniConfig(
        "https://example.test/inference", Secret("key"), tts_model_ids={"hi": "hindi-voice"}
    )
    with pytest.raises(UnsupportedLanguageError):
        BhashiniTTSProvider(mapping_only).model_id_for(None)
