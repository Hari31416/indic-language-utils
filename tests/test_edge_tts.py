from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from indic_language_utils.config import Settings
from indic_language_utils.errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
    ProviderTimeoutError,
    TransientProviderError,
    UnsupportedLanguageError,
)
from indic_language_utils.languages import LanguageTag
from indic_language_utils.server.app import create_app
from indic_language_utils.tts import (
    EdgeTTSConfig,
    EdgeTTSProvider,
    TTSOptions,
    get_tts_client,
)

FAKE_MP3 = b"\xff\xf3\x44\xc4fake-mp3-audio-bytes"


class MockCommunicate:
    def __init__(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
        *,
        chunks: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.text = text
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch
        self.chunks = chunks if chunks is not None else [{"type": "audio", "data": FAKE_MP3}]
        self.error = error
        self.delay_seconds = delay_seconds

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        for chunk in self.chunks:
            yield chunk


def test_edge_tts_config_defaults() -> None:
    config = EdgeTTSConfig()
    assert config.default_voice == "hi-IN-SwaraNeural"
    assert config.rate == "+0%"
    assert config.volume == "+0%"
    assert config.pitch == "+0Hz"
    assert config.timeout_seconds == 30.0
    assert config.max_concurrency == 4
    assert config.voices == {}


def test_edge_tts_config_validation() -> None:
    with pytest.raises(ConfigurationError, match="timeout and concurrency"):
        EdgeTTSConfig(timeout_seconds=0)
    with pytest.raises(ConfigurationError, match="timeout and concurrency"):
        EdgeTTSConfig(max_concurrency=0)
    with pytest.raises(ConfigurationError, match="default_voice cannot be empty"):
        EdgeTTSConfig(default_voice="")


def test_edge_tts_config_from_env_and_settings() -> None:
    env = {
        "EDGE_TTS_VOICE": "ta-IN-PallaviNeural",
        "EDGE_TTS_RATE": "+15%",
        "EDGE_TTS_VOLUME": "-10%",
        "EDGE_TTS_PITCH": "+5Hz",
        "EDGE_TTS_TIMEOUT_SECONDS": "25.0",
        "EDGE_TTS_MAX_CONCURRENCY": "6",
    }
    cfg = EdgeTTSConfig.from_env(env)
    assert cfg.default_voice == "ta-IN-PallaviNeural"
    assert cfg.rate == "+15%"
    assert cfg.volume == "-10%"
    assert cfg.pitch == "+5Hz"
    assert cfg.timeout_seconds == 25.0
    assert cfg.max_concurrency == 6

    # Test error in numeric env
    with pytest.raises(ConfigurationError, match="Invalid numeric setting"):
        EdgeTTSConfig.from_env({"EDGE_TTS_TIMEOUT_SECONDS": "invalid"})

    # Test from_settings
    settings = Settings._from_mapping(
        {
            "providers": {
                "edge_tts": {
                    "tts_model_id": "gu-IN-DhwaniNeural",
                    "tts_model_ids": {"hi": "hi-IN-MadhurNeural"},
                    "timeout_seconds": 18.0,
                    "max_concurrency": 2,
                }
            }
        }
    )
    from_sett = EdgeTTSConfig.from_settings(settings)
    assert from_sett.default_voice == "gu-IN-DhwaniNeural"
    assert from_sett.voices == {"hi": "hi-IN-MadhurNeural"}
    assert from_sett.timeout_seconds == 18.0
    assert from_sett.max_concurrency == 2


def test_edge_tts_voice_resolution() -> None:
    config = EdgeTTSConfig(
        default_voice="default-voice",
        voices={"ta": "custom-tamil-voice"},
    )
    provider = EdgeTTSProvider(
        config, communicate_factory=lambda **kwargs: MockCommunicate(**kwargs)
    )

    # Explicit voice parameter
    assert (
        provider.resolve_voice(LanguageTag("hi"), TTSOptions({"voice": "explicit-voice"}))
        == "explicit-voice"
    )
    assert (
        provider.resolve_voice(LanguageTag("hi"), TTSOptions({"voiceId": "explicit-voice-id"}))
        == "explicit-voice-id"
    )
    assert (
        provider.resolve_voice(LanguageTag("hi"), TTSOptions({"model": "explicit-model"}))
        == "explicit-model"
    )

    # Config voices override
    assert provider.resolve_voice(LanguageTag("ta"), TTSOptions()) == "custom-tamil-voice"

    # Built-in female / male defaults
    assert (
        provider.resolve_voice(LanguageTag("hi"), TTSOptions({"gender": "female"}))
        == "hi-IN-SwaraNeural"
    )
    assert (
        provider.resolve_voice(LanguageTag("hi"), TTSOptions({"gender": "male"}))
        == "hi-IN-MadhurNeural"
    )
    assert provider.resolve_voice(LanguageTag("mr"), TTSOptions()) == "mr-IN-AarohiNeural"
    assert (
        provider.resolve_voice(LanguageTag("mr"), TTSOptions({"gender": "male"}))
        == "mr-IN-ManoharNeural"
    )
    assert (
        provider.resolve_voice(LanguageTag("te"), TTSOptions({"gender": "male"}))
        == "te-IN-MohanNeural"
    )
    assert (
        provider.resolve_voice(LanguageTag("te"), TTSOptions({"gender": "female"}))
        == "te-IN-ShrutiNeural"
    )

    # None language falls back to default_voice
    assert provider.resolve_voice(None, TTSOptions()) == "default-voice"

    # Unsupported language
    with pytest.raises(UnsupportedLanguageError, match="does not support language 'kok'"):
        provider.resolve_voice(LanguageTag("kok"), TTSOptions())


@pytest.mark.asyncio
async def test_edge_tts_synthesize_batch() -> None:
    calls: list[dict[str, Any]] = []

    def fake_factory(**kwargs: Any) -> MockCommunicate:
        calls.append(kwargs)
        return MockCommunicate(**kwargs)

    provider = EdgeTTSProvider(communicate_factory=fake_factory)
    options = TTSOptions({"gender": "male", "rate": "+10%", "volume": "-5%", "pitch": "+2Hz"})
    results = await provider.synthesize_batch(
        ("नमस्ते", "शुभ प्रभात"),
        language=LanguageTag("hi"),
        options=options,
        request_id="test-req-1",
    )

    assert len(results) == 2
    assert results[0].audio == FAKE_MP3
    assert results[0].audio_format == "mp3"
    assert results[0].model_id == "hi-IN-MadhurNeural"
    assert results[0].request_id == "test-req-1"

    assert len(calls) == 2
    assert calls[0]["voice"] == "hi-IN-MadhurNeural"
    assert calls[0]["rate"] == "+10%"
    assert calls[0]["volume"] == "-5%"
    assert calls[0]["pitch"] == "+2Hz"
    assert calls[0]["text"] == "नमस्ते"
    assert calls[1]["text"] == "शुभ प्रभात"


@pytest.mark.asyncio
async def test_edge_tts_empty_text_error() -> None:
    provider = EdgeTTSProvider(communicate_factory=lambda **kw: MockCommunicate(**kw))
    with pytest.raises(InvalidInputError, match="text cannot be empty"):
        await provider.synthesize_batch(("",), language=None, options=TTSOptions(), request_id="r1")
    with pytest.raises(InvalidInputError, match="text cannot be empty"):
        await provider.synthesize_batch(
            ("   ",), language=None, options=TTSOptions(), request_id="r1"
        )


@pytest.mark.asyncio
async def test_edge_tts_empty_audio_response() -> None:
    def empty_factory(**kw: Any) -> MockCommunicate:
        return MockCommunicate(chunks=[], **kw)

    provider = EdgeTTSProvider(communicate_factory=empty_factory)
    with pytest.raises(MalformedProviderResponseError, match="empty audio response"):
        await provider.synthesize_batch(
            ("Hello",), language=None, options=TTSOptions(), request_id="r1"
        )


@pytest.mark.asyncio
async def test_edge_tts_no_audio_received_exception() -> None:
    import edge_tts.exceptions

    def err_factory(**kw: Any) -> MockCommunicate:
        return MockCommunicate(error=edge_tts.exceptions.NoAudioReceived("No audio"), **kw)

    provider = EdgeTTSProvider(communicate_factory=err_factory)
    with pytest.raises(MalformedProviderResponseError, match="returned no audio data"):
        await provider.synthesize_batch(
            ("Hello",), language=None, options=TTSOptions(), request_id="r1"
        )


@pytest.mark.asyncio
async def test_edge_tts_websocket_error() -> None:
    import edge_tts.exceptions

    def err_factory(**kw: Any) -> MockCommunicate:
        return MockCommunicate(error=edge_tts.exceptions.WebSocketError("Connection reset"), **kw)

    provider = EdgeTTSProvider(communicate_factory=err_factory)
    with pytest.raises(TransientProviderError, match="connection error"):
        await provider.synthesize_batch(
            ("Hello",), language=None, options=TTSOptions(), request_id="r1"
        )


@pytest.mark.asyncio
async def test_edge_tts_timeout_error() -> None:
    config = EdgeTTSConfig(timeout_seconds=0.05)

    def slow_factory(**kw: Any) -> MockCommunicate:
        return MockCommunicate(delay_seconds=0.2, **kw)

    provider = EdgeTTSProvider(config=config, communicate_factory=slow_factory)
    with pytest.raises(ProviderTimeoutError, match="timed out"):
        await provider.synthesize_batch(
            ("Hello",), language=None, options=TTSOptions(), request_id="r1"
        )


def test_edge_tts_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import indic_language_utils.tts.edge_tts as et_module

    monkeypatch.setattr(et_module, "HAVE_EDGE_TTS", False)
    with pytest.raises(MissingOptionalDependencyError, match="'edge-tts' package is required"):
        EdgeTTSProvider()


@pytest.mark.asyncio
async def test_get_tts_client_with_edge_tts() -> None:
    provider = EdgeTTSProvider(communicate_factory=lambda **kw: MockCommunicate(**kw))
    client = get_tts_client(providers=[provider])
    async with client:
        res = await client.synthesize("வணக்கம்", language="ta")
        assert res.audio == FAKE_MP3
        assert res.audio_format == "mp3"
        assert res.provider == "edge_tts"
        assert res.model_id == "ta-IN-PallaviNeural"


def test_get_tts_client_free_fallback_registration() -> None:
    # When no API keys exist, edge_tts is registered by default
    client = get_tts_client(env={})
    names = [p.identity.provider for p in client.router.registry.all()]
    assert "edge_tts" in names


def test_get_tts_client_route_alias() -> None:
    from indic_language_utils.providers import CapabilityId
    from indic_language_utils.routing import RouteRequirement

    settings = Settings._from_mapping(
        {
            "providers": {"edge_tts": {"tts_model_id": "test-voice"}},
            "routes": {"text_to_speech": ["edge"]},
        }
    )
    client = get_tts_client(settings=settings, env={})
    candidates = client.router.candidates(RouteRequirement(CapabilityId.TEXT_TO_SPEECH))
    assert [c.provider.identity.provider for c in candidates] == ["edge_tts"]


@pytest.mark.asyncio
async def test_server_routes_edge_tts_api(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    with TestClient(app) as test_client:
        # Check /api/providers
        resp = test_client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        tts_providers = data.get("text_to_speech", [])
        edge_info = next((p for p in tts_providers if p["id"] == "edge_tts"), None)
        assert edge_info is not None
        assert edge_info["name"] == "Microsoft Edge TTS"
        assert edge_info["available"] is True

        # Check /api/tts with explicit edge_tts provider (mocked via get_tts_client monkeypatch)
        provider = EdgeTTSProvider(communicate_factory=lambda **kw: MockCommunicate(**kw))
        custom_client = get_tts_client(providers=[provider])

        import indic_language_utils.server.routes as routes_mod

        monkeypatch.setattr(routes_mod, "get_tts_client", lambda *args, **kwargs: custom_client)
        tts_resp = test_client.post(
            "/api/tts",
            json={
                "text": "Hello world",
                "language": "hi",
                "parameters": {"gender": "female"},
                "provider": "edge_tts",
            },
        )
        assert tts_resp.status_code == 200
        res_data = tts_resp.json()
        assert res_data["audio_format"] == "mp3"
        assert res_data["provider"] == "edge_tts"
        assert res_data["model_id"] == "hi-IN-SwaraNeural"
