from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx
import pytest
from fastapi.testclient import TestClient

from indic_language_utils import (
    SarvamConfig,
    Secret,
    Settings,
    STTRequest,
    TTSOptions,
    TTSRequest,
    get_stt_client,
    get_tts_client,
)
from indic_language_utils.errors import InvalidInputError, MalformedProviderResponseError
from indic_language_utils.providers.bhashini import JsonResponse
from indic_language_utils.server import routes
from indic_language_utils.server.app import create_app
from indic_language_utils.stt.models import ProviderSTTResult
from indic_language_utils.stt.sarvam import SarvamSTTProvider
from indic_language_utils.tts.models import ProviderTTSResult
from indic_language_utils.tts.sarvam import SarvamTTSProvider

WAV = b"RIFF\x04\x00\x00\x00WAVE" + b"audio"


def config() -> SarvamConfig:
    return SarvamConfig(
        Secret("key"),
        endpoint="https://example.test",
        stt_model_id="saaras:v4",
        stt_model_ids={"hi-IN": "saaras:v3"},
        tts_model_id="bulbul:v3",
        tts_model_ids={"hi-IN": "bulbul:v2"},
    )


@pytest.mark.asyncio
async def test_sarvam_stt_multipart_language_and_model() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"transcript": "नमस्ते", "request_id": "provider-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        provider = SarvamSTTProvider(config(), client=http_client)
        result = await provider.transcribe_batch(
            (WAV,),
            language=STTRequest(WAV, "hi").language,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req",
        )
    assert result[0].text == "नमस्ते"
    assert result[0].model_id == "saaras:v3"
    assert result[0].request_id == "provider-1"
    request = requests[0]
    assert request.url.path == "/speech-to-text"
    assert request.headers["api-subscription-key"] == "key"
    assert "multipart/form-data" in request.headers["content-type"]
    assert b'name="model"' in request.content and b"saaras:v3" in request.content
    assert b'name="language_code"' in request.content and b"hi-IN" in request.content
    assert b'name="file"; filename="audio.wav"' in request.content
    assert WAV in request.content


@pytest.mark.asyncio
async def test_sarvam_stt_omits_language_when_unspecified() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"transcript": "hello", "language_code": "en-IN"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        provider = SarvamSTTProvider(config(), client=http_client)
        result = await provider.transcribe_batch(
            (WAV,), language=None, audio_format="wav", sampling_rate=16000, request_id="req"
        )
    assert result[0].model_id == "saaras:v4"
    assert str(result[0].detected_language) == "en-IN"
    assert b'name="language_code"' not in requests[0].content


@dataclass
class FakeJsonTransport:
    responses: list[JsonResponse]
    requests: list[Mapping[str, object]] = field(default_factory=list)

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        assert url == "https://example.test/text-to-speech"
        assert headers["api-subscription-key"] == "key"
        self.requests.append(json)
        return self.responses.pop(0)

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_sarvam_tts_options_and_audio() -> None:
    transport = FakeJsonTransport(
        [
            JsonResponse(
                200, {"audios": [base64.b64encode(WAV).decode()], "request_id": "provider-2"}, {}
            )
        ]
    )
    provider = SarvamTTSProvider(config(), transport=transport)
    result = await provider.synthesize_batch(
        ("नमस्ते",),
        language=TTSRequest("x", "hi").language,
        options=TTSOptions({"speaker": "shubh", "pace": 1.2}),
        request_id="req",
    )
    assert result[0].audio == WAV
    assert result[0].audio_format == "wav"
    assert result[0].model_id == "bulbul:v2"
    assert result[0].request_id == "provider-2"
    assert transport.requests[0] == {
        "text": "नमस्ते",
        "language_code": "hi-IN",
        "model": "bulbul:v2",
        "speaker": "shubh",
        "pace": 1.2,
    }


@pytest.mark.asyncio
async def test_sarvam_tts_requires_language_and_valid_audio() -> None:
    provider = SarvamTTSProvider(config(), transport=FakeJsonTransport([]))
    with pytest.raises(InvalidInputError, match="requires a language"):
        await provider.synthesize_batch(
            ("Hello",), language=None, options=TTSOptions(), request_id="req"
        )
    with pytest.raises(InvalidInputError, match="cannot override"):
        await provider.synthesize_batch(
            ("Hello",),
            language=TTSRequest("x", "en").language,
            options=TTSOptions({"model": "other"}),
            request_id="req",
        )
    bad = SarvamTTSProvider(
        config(), transport=FakeJsonTransport([JsonResponse(200, {"audios": ["not-base64"]}, {})])
    )
    with pytest.raises(MalformedProviderResponseError):
        await bad.synthesize_batch(
            ("Hello",),
            language=TTSRequest("x", "en").language,
            options=TTSOptions(),
            request_id="req",
        )


def test_sarvam_only_configuration_registers_speech_providers() -> None:
    settings = Settings._from_mapping(
        {
            "providers": {
                "sarvam": {
                    "stt_model_id": "saaras:v4",
                    "tts_model_id": "bulbul:v3",
                    "stt_model_ids": {"hi": "saaras:v3"},
                    "tts_model_ids": {"hi": "bulbul:v2"},
                }
            },
            "routes": {"speech_to_text": ["sarvam"], "text_to_speech": ["sarvam"]},
        }
    )
    env = {"SARVAM_API_KEY": "key"}
    stt = get_stt_client(settings, env=env)
    tts = get_tts_client(settings, env=env)
    assert stt.router.registry.get("sarvam").identity.provider == "sarvam"
    assert tts.router.registry.get("sarvam").identity.provider == "sarvam"
    sarvam = SarvamConfig.from_settings(settings, env=env)
    assert sarvam.stt_model_ids["hi-IN"] == "saaras:v3"
    assert sarvam.tts_model_ids["hi-IN"] == "bulbul:v2"


def test_sarvam_fastapi_speech_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "_get_env_overrides", lambda: {"SARVAM_API_KEY": "key"})

    async def transcribe(
        self: SarvamSTTProvider,
        audio: tuple[bytes, ...],
        *,
        language: object,
        audio_format: str,
        sampling_rate: int,
        request_id: str,
    ) -> tuple[ProviderSTTResult, ...]:
        assert audio == (WAV,)
        assert str(language) == "hi-IN"
        return (ProviderSTTResult("नमस्ते", "saaras:v4", "sarvam-stt"),)

    async def synthesize(
        self: SarvamTTSProvider,
        texts: tuple[str, ...],
        *,
        language: object,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]:
        assert texts == ("नमस्ते",)
        assert str(language) == "hi-IN"
        assert options.parameters == {"speaker": "shubh"}
        return (ProviderTTSResult(WAV, "wav", "bulbul:v3", "sarvam-tts"),)

    monkeypatch.setattr(SarvamSTTProvider, "transcribe_batch", transcribe)
    monkeypatch.setattr(SarvamTTSProvider, "synthesize_batch", synthesize)
    client = TestClient(create_app())
    providers = client.get("/api/providers").json()
    assert any(p["id"] == "sarvam" and p["available"] for p in providers["speech_to_text"])
    assert any(p["id"] == "sarvam" and p["available"] for p in providers["text_to_speech"])
    stt = client.post(
        "/api/stt",
        json={
            "audio_base64": base64.b64encode(WAV).decode(),
            "language": "hi",
            "provider": "sarvam",
        },
    )
    assert stt.status_code == 200
    assert stt.json()["text"] == "नमस्ते"
    assert stt.json()["model_id"] == "saaras:v4"
    tts = client.post(
        "/api/tts",
        json={
            "text": "नमस्ते",
            "language": "hi",
            "provider": "sarvam",
            "parameters": {"speaker": "shubh"},
        },
    )
    assert tts.status_code == 200
    assert base64.b64decode(tts.json()["audio_base64"]) == WAV
    assert tts.json()["model_id"] == "bulbul:v3"
