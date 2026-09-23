from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils import (
    BhashiniConfig,
    BhashiniSTTProvider,
    Secret,
    Settings,
    STTClient,
    STTRequest,
    get_stt_client,
)
from indic_language_utils.errors import MalformedProviderResponseError, UnsupportedLanguageError
from indic_language_utils.providers.bhashini import JsonResponse


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


def response(*texts: str) -> JsonResponse:
    return JsonResponse(
        200,
        {"pipelineResponse": [{"taskType": "asr", "output": [{"source": text} for text in texts]}]},
        {"x-request-id": "provider-123"},
    )


def config() -> BhashiniConfig:
    return BhashiniConfig(
        "https://example.test/inference",
        Secret("key"),
        stt_model_id="default",
        stt_model_ids={"hi": "hindi-model"},
        tts_model_ids={"hi": "hindi-voice"},
    )


@pytest.mark.asyncio
async def test_bhashini_stt_payload_and_language_model() -> None:
    transport = FakeTransport([response("नमस्ते")])
    provider = BhashiniSTTProvider(config(), transport=transport)
    result = await provider.transcribe_batch(
        (b"some audio",),
        language=STTRequest(b"x", "hi").language,
        audio_format="wav",
        sampling_rate=16000,
        request_id="request-123",
    )
    assert result[0].text == "नमस्ते"
    assert result[0].model_id == "hindi-model"
    assert result[0].request_id == "provider-123"
    payload = transport.payloads[0]
    task = payload["pipelineTasks"][0]  # type: ignore[index]
    assert task["config"]["serviceId"] == "hindi-model"
    assert task["config"]["language"] == {"sourceLanguage": "hi"}
    assert task["config"]["audioFormat"] == "wav"
    assert task["config"]["samplingRate"] == 16000
    assert payload["inputData"] == {
        "audio": [{"audioContent": base64.b64encode(b"some audio").decode()}]
    }


@pytest.mark.asyncio
async def test_stt_client_returns_transcript() -> None:
    transport = FakeTransport([response("hello")])
    provider = BhashiniSTTProvider(config(), transport=transport)
    client = get_stt_client(providers=[provider])
    assert isinstance(client, STTClient)
    result = await client.transcribe(b"audio", language="en")
    assert result.text == "hello"
    assert result.model_id == "default"
    assert result.provider == "bhashini"


@pytest.mark.asyncio
async def test_malformed_response_is_rejected() -> None:
    provider = BhashiniSTTProvider(config(), transport=FakeTransport([response()]))
    with pytest.raises(MalformedProviderResponseError):
        await provider.transcribe_batch(
            (b"x",),
            language=STTRequest(b"x", "hi").language,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req",
        )


def test_stt_model_mapping_from_settings() -> None:
    settings = Settings._from_mapping(
        {
            "providers": {
                "bhashini": {
                    "endpoint": "https://example.test/inference",
                    "stt_model_ids": {"hi": "model-hi", "ta-IN": "model-ta"},
                    "tts_model_ids": {"hi": "voice-hi"},
                }
            }
        }
    )
    cfg = BhashiniConfig.from_settings(settings, env={"BHASHINI_API_KEY": "key"})
    assert cfg.stt_model_ids["hi-IN"] == "model-hi"
    assert cfg.tts_model_ids["hi-IN"] == "voice-hi"
    assert BhashiniSTTProvider(cfg).model_id_for(STTRequest(b"x", "ta").language) == "model-ta"
    with pytest.raises(UnsupportedLanguageError):
        BhashiniSTTProvider(cfg).model_id_for(STTRequest(b"x", "en").language)
