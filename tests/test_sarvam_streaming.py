"""Contract tests for Sarvam streams without live credentials."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from indic_language_utils import (
    BhashiniConfig,
    BhashiniSTTProvider,
    SarvamConfig,
    SarvamSTTProvider,
    SarvamTTSProvider,
    Secret,
    TTSOptions,
    get_stt_client,
    get_tts_client,
)
from indic_language_utils.errors import ConfigurationError, MalformedProviderResponseError
from indic_language_utils.providers import sarvam_socket


class FakeSocket:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self.messages = messages
        self.sent: list[dict[str, object]] = []

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def __aiter__(self) -> AsyncIterator[str]:
        for message in self.messages:
            yield json.dumps(message)


def config() -> SarvamConfig:
    return SarvamConfig(Secret("test-key"), stt_model_id="saaras:v4", tts_model_id="bulbul:v3")


@pytest.mark.asyncio
async def test_sarvam_asr_stream_maps_events_and_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = FakeSocket(
        [
            {"event": "session.begin"},
            {"event": "vad.speech_start"},
            {"event": "transcript.partial", "text": "नम"},
            {"event": "transcript.final", "text": "नमस्ते", "language": "hi-IN"},
            {"event": "vad.speech_end"},
            {"event": "session.end"},
        ]
    )
    paths: list[str] = []

    @asynccontextmanager
    async def fake_connect(_config: SarvamConfig, path: str) -> AsyncIterator[FakeSocket]:
        paths.append(path)
        yield socket

    monkeypatch.setattr(sarvam_socket, "connect", fake_connect)
    async with get_stt_client(providers=[SarvamSTTProvider(config())]) as client:
        async with client.stream(language="hi", provider="sarvam") as stream:
            await stream.send_audio(b"\x00\x01")
            await stream.finish()
            events = [event async for event in stream.events()]

    assert [event.kind for event in events] == ["speech_start", "partial", "final", "speech_end"]
    assert events[2].text == "नमस्ते"
    assert str(events[2].language) == "hi-IN"
    assert len({event.request_id for event in events}) == 1
    assert "model=saaras%3Av4" in paths[0]
    assert socket.sent == [
        {"event": "audio_input", "audio": base64.b64encode(b"\x00\x01").decode()},
        {"event": "end"},
    ]


@pytest.mark.asyncio
async def test_sarvam_tts_stream_maps_audio_and_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = FakeSocket(
        [
            {"type": "audio", "data": {"audio": base64.b64encode(b"mp3").decode()}},
            {"type": "event", "data": {"event_type": "final"}},
        ]
    )

    @asynccontextmanager
    async def fake_connect(_config: SarvamConfig, _path: str) -> AsyncIterator[FakeSocket]:
        yield socket

    monkeypatch.setattr(sarvam_socket, "connect", fake_connect)
    async with get_tts_client(providers=[SarvamTTSProvider(config())]) as client:
        async with client.stream(language="hi", options=TTSOptions({"speaker": "shubh"})) as stream:
            await stream.send_text("नमस्ते")
            await stream.flush()
            events = [event async for event in stream.events()]

    assert [(event.kind, event.audio) for event in events] == [("audio", b"mp3"), ("done", None)]
    assert events[0].audio_format == "mp3"
    assert socket.sent == [
        {
            "type": "config",
            "data": {"speaker": "shubh", "language_code": "hi-IN", "output_audio_codec": "mp3"},
        },
        {"type": "text", "data": {"text": "नमस्ते"}},
        {"type": "flush"},
    ]


@pytest.mark.asyncio
async def test_stream_rejects_batch_only_provider() -> None:
    bhashini = BhashiniSTTProvider(
        BhashiniConfig("https://example.test/inference", Secret("key"), stt_model_id="asr")
    )
    client = get_stt_client(providers=[bhashini])
    with pytest.raises(ConfigurationError, match="supports streaming"):
        async with client.stream(language="hi"):
            pass


@pytest.mark.asyncio
async def test_tts_stream_rejects_bad_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = FakeSocket([{"type": "audio", "data": {"audio": "not-base64"}}])

    @asynccontextmanager
    async def fake_connect(_config: SarvamConfig, _path: str) -> AsyncIterator[FakeSocket]:
        yield socket

    monkeypatch.setattr(sarvam_socket, "connect", fake_connect)
    client = get_tts_client(providers=[SarvamTTSProvider(config())])
    async with client.stream(language="hi") as stream:
        with pytest.raises(MalformedProviderResponseError):
            _ = [event async for event in stream.events()]
