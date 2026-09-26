from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from indic_language_utils import GnaniConfig, GnaniSTTProvider, Secret, get_stt_client
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.stt.gnani_stream import open_gnani_stt_stream


def config() -> GnaniConfig:
    return GnaniConfig(Secret("test-key"), endpoint="https://example.test")


@pytest.mark.asyncio
async def test_gnani_rest_posts_audio_and_maps_transcript() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, json={"success": True, "request_id": "abc", "transcript": "નમસ્તે"}
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        async with get_stt_client(providers=[GnaniSTTProvider(config(), client=http)]) as client:
            result = await client.transcribe(b"wav-data", language="gu", audio_format="wav")

    request = requests[0]
    body = request.read().decode("latin1")
    assert request.url.path == "/stt/v3"
    assert request.headers["x-api-key-id"] == "test-key"
    assert 'name="language_code"' in body and "gu-IN" in body
    assert 'name="format"' in body and "transcribe" in body
    assert 'name="audio_file"' in body and "wav-data" in body
    assert result.text == "નમસ્તે"
    assert result.provider_request_id == "abc"


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    async def send(self, payload: bytes) -> None:
        self.sent.append(payload)

    def __aiter__(self) -> AsyncIterator[str]:
        async def events() -> AsyncIterator[str]:
            for message in (
                {"type": "connected"},
                {"type": "processing"},
                {"type": "transcript", "text": "hello"},
            ):
                yield json.dumps(message)

        return events()


@pytest.mark.asyncio
async def test_gnani_stream_sends_raw_pcm_and_maps_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = FakeSocket()
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def connect(url: str, **kwargs: object) -> AsyncIterator[FakeSocket]:
        captured.update(url=url, **kwargs)
        yield socket

    monkeypatch.setattr("websockets.asyncio.client.connect", connect)
    async with open_gnani_stt_stream(
        config(),
        language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        sampling_rate=16000,
        request_id="req",
    ) as stream:
        await stream.send_audio(b"\x00\x01")
        await stream.finish()
        events = [event async for event in stream.events()]

    assert captured["url"] == "wss://example.test/stt/v3/stream"
    assert captured["additional_headers"] == {
        "x-api-key-id": "test-key",
        "lang_code": "hi-IN",
        "x-sample-rate": "16000",
    }
    assert socket.sent[0] == b"\x00\x01"
    assert b"".join(socket.sent[1:]) == bytes(16000)
    assert all(len(chunk) <= 1024 for chunk in socket.sent[1:])
    assert [(event.kind, event.text) for event in events] == [("final", "hello")]
