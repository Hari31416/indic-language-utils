from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils import BhashiniConfig, Secret, TTSOptions, TTSRequest, get_tts_client
from indic_language_utils.errors import MalformedProviderResponseError, UnsupportedLanguageError
from indic_language_utils.providers.bhashini import JsonResponse
from indic_language_utils.tts.bhashini import BhashiniTTSProvider

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
    client = get_tts_client(providers=[provider])
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
