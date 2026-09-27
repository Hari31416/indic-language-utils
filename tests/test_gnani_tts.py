from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from indic_language_utils.cache import NullCache
from indic_language_utils.config import Secret
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers.gnani import GnaniConfig
from indic_language_utils.tts import get_tts_client
from indic_language_utils.tts.gnani import GnaniTTSProvider
from indic_language_utils.tts.models import TTSOptions
from indic_language_utils.tts.streaming import TTSStreamEvent


@pytest.mark.asyncio
async def test_gnani_tts_inference_posts_json_and_returns_binary_audio() -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"audio-data")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = GnaniTTSProvider(GnaniConfig(Secret("secret")), client=client)
        result = await provider.synthesize_batch(
            ("नमस्ते",),
            language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TTSOptions(
                {"voice": "voice-1", "speed": 1.1, "audio_config": {"container": "wav"}}
            ),
            request_id="req-1",
        )

    request = seen[0]
    assert str(request.url) == "https://api.vachana.ai/api/v1/tts/inference"
    assert request.headers["X-API-Key-ID"] == "secret"
    assert json.loads(request.content) == {
        "text": "नमस्ते",
        "voice": "voice-1",
        "model": "timbre-v2.5",
        "language": "hi-IN",
        "speed": 1.1,
        "audio_config": {"container": "wav"},
    }
    assert result[0].audio == b"audio-data"
    assert result[0].audio_format == "wav"


@pytest.mark.asyncio
async def test_gnani_tts_routes_hinglish_and_sends_documented_code() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"audio-data")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        provider = GnaniTTSProvider(GnaniConfig(Secret("secret")), client=http)
        async with get_tts_client(providers=[provider], cache=NullCache()) as client:
            result = await client.synthesize(
                "Namaste, how are you?",
                language="hi-en",
                options=TTSOptions({"voice": "Poorvi"}),
            )

    assert result.provider == "gnani"
    assert json.loads(requests[0].content)["language"] == "hi-en"


@pytest.mark.asyncio
async def test_gnani_stream_sse_decodes_chunks_and_hides_transport_option() -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                b"event: start\ndata: {}\n\n"
                b'event: chunk\ndata: {"audio":"Y2h1bms="}\n\n'
                b"event: complete\ndata: {}\n\n"
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = GnaniTTSProvider(GnaniConfig(Secret("secret")), client=client)
        async with provider.open_stream(
            language=DEFAULT_LANGUAGE_REGISTRY.normalize("en"),
            options=TTSOptions({"voice": "voice-1", "streaming_transport": "sse"}),
            request_id="req-1",
        ) as stream:
            await stream.send_text("hello")
            await stream.flush()
            events = [event async for event in stream.events()]

    assert [event.kind for event in events] == ["audio", "done"]
    assert events[0].audio == b"chunk"
    assert json.loads(seen[0].content) == {
        "text": "hello",
        "voice": "voice-1",
        "model": "timbre-v2.5",
        "language": "en-IN",
    }


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, payload: str) -> None:
        self.sent.append(payload)

    def __aiter__(self) -> AsyncIterator[str]:
        async def events() -> AsyncIterator[str]:
            yield json.dumps({"type": "start"})
            yield json.dumps({"type": "audio", "data": {"audio": "Y2h1bms=", "is_final": False}})
            yield json.dumps({"type": "complete", "data": {"audio": "", "is_final": True}})

        return events()


@pytest.mark.asyncio
async def test_gnani_stream_websocket_maps_nested_audio_while_events_are_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = FakeWebSocket()
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def connect(url: str, **kwargs: object) -> AsyncIterator[FakeWebSocket]:
        captured.update(url=url, **kwargs)
        yield socket

    monkeypatch.setattr("websockets.asyncio.client.connect", connect)
    provider = GnaniTTSProvider(GnaniConfig(Secret("secret")))
    async with provider.open_stream(
        language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        options=TTSOptions({"voice": "Nalini"}),
        request_id="req-1",
    ) as stream:
        await stream.send_text("नमस्ते")
        event_task = asyncio.create_task(_collect_events(stream.events()))
        await stream.flush()
        events = await event_task

    assert captured["url"] == "wss://api.vachana.ai/api/v1/tts"
    assert captured["additional_headers"] == {
        "X-API-Key-ID": "secret",
        "Content-Type": "application/json",
    }
    assert json.loads(socket.sent[0])["voice"] == "Nalini"
    assert [event.kind for event in events] == ["audio", "done"]
    assert events[0].audio == b"chunk"


async def _collect_events(events: AsyncIterator[TTSStreamEvent]) -> list[TTSStreamEvent]:
    return [event async for event in events]
