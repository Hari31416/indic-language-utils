"""Browser WebSocket protocol checks with in-memory provider sessions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.server.app import create_app
from indic_language_utils.stt import STTStreamEvent
from indic_language_utils.stt.sarvam import SarvamSTTProvider
from indic_language_utils.tts import TTSStreamEvent
from indic_language_utils.tts.sarvam import SarvamTTSProvider


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from indic_language_utils.server import streaming

    monkeypatch.setattr(streaming, "_get_env_overrides", lambda: {})
    return TestClient(create_app())


def test_stt_websocket_forwards_pcm_and_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chunks: list[bytes] = []

    class FakeSession:
        def __init__(self) -> None:
            self.finished = asyncio.Event()

        async def send_audio(self, pcm: bytes) -> None:
            chunks.append(pcm)

        async def finish(self) -> None:
            self.finished.set()

        async def events(self) -> AsyncIterator[STTStreamEvent]:
            await self.finished.wait()
            yield STTStreamEvent("final", "नमस्ते", None, "sarvam", "saaras:v4", "request-1")

    @asynccontextmanager
    async def fake_open(self: SarvamSTTProvider, **_: object) -> AsyncIterator[FakeSession]:
        yield FakeSession()

    monkeypatch.setattr(SarvamSTTProvider, "open_stream", fake_open)
    with client.websocket_connect("/api/stt/stream") as websocket:
        websocket.send_json(
            {
                "type": "start",
                "provider": "sarvam",
                "language": "hi",
                "sampling_rate": 16000,
                "api_key": "test-key",
            }
        )
        assert websocket.receive_json() == {"type": "ready"}
        websocket.send_bytes(b"\0\1")
        websocket.send_text('{"type":"finish"}')
        event = websocket.receive_json()
        assert event["kind"] == "final"
        assert event["text"] == "नमस्ते"
        assert event["request_id"] == "request-1"
        assert websocket.receive_json() == {"type": "done"}
    assert chunks == [b"\0\1"]


def test_tts_websocket_forwards_text_and_audio(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    texts: list[str] = []

    class FakeSession:
        def __init__(self) -> None:
            self.flushed = asyncio.Event()

        async def send_text(self, text: str) -> None:
            texts.append(text)

        async def flush(self) -> None:
            self.flushed.set()

        async def events(self) -> AsyncIterator[TTSStreamEvent]:
            await self.flushed.wait()
            language = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
            yield TTSStreamEvent(
                "audio", b"\0\1", "linear16", language, "sarvam", "bulbul:v3", "request-2"
            )
            yield TTSStreamEvent(
                "done", None, "linear16", language, "sarvam", "bulbul:v3", "request-2"
            )

    @asynccontextmanager
    async def fake_open(self: SarvamTTSProvider, **_: object) -> AsyncIterator[FakeSession]:
        yield FakeSession()

    monkeypatch.setattr(SarvamTTSProvider, "open_stream", fake_open)
    with client.websocket_connect("/api/tts/stream") as websocket:
        websocket.send_json(
            {
                "type": "start",
                "provider": "sarvam",
                "language": "hi",
                "parameters": {"audio_format": "linear16"},
                "api_key": "test-key",
            }
        )
        assert websocket.receive_json() == {"type": "ready"}
        websocket.send_json({"type": "text", "text": "नमस्ते"})
        websocket.send_json({"type": "flush"})
        audio = websocket.receive_json()
        assert audio["kind"] == "audio"
        assert audio["audio_base64"] == "AAE="
        assert websocket.receive_json()["kind"] == "done"
        assert websocket.receive_json() == {"type": "done"}
    assert texts == ["नमस्ते"]
