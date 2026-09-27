from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from indic_language_utils import GnaniConfig, GnaniSTTProvider, Secret, get_stt_client
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.retry import RetryPolicy
from indic_language_utils.stt.gnani_stream import GnaniSTTStream, open_gnani_stt_stream


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


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.asyncio
async def test_gnani_rest_retries_transient_responses(status: int) -> None:
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(status)
        return httpx.Response(200, json={"transcript": "नमस्ते"})

    retry_policy = RetryPolicy(max_attempts=2, base_delay=0, max_delay=0)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        provider = GnaniSTTProvider(
            GnaniConfig(Secret("test-key"), retry_policy=retry_policy), client=http
        )
        result = await provider.transcribe_batch(
            (b"wav-data",),
            language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            audio_format="wav",
            sampling_rate=16000,
            request_id="req",
        )

    assert attempts == 2
    assert result[0].text == "नमस्ते"


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.sent_at: list[float] = []

    async def send(self, payload: bytes) -> None:
        self.sent.append(payload)
        self.sent_at.append(asyncio.get_running_loop().time())

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
        await stream.send_audio(b"\x00\x01" * 1600)
        await stream.finish()
        events = [event async for event in stream.events()]

    assert captured["url"] == "wss://example.test/stt/v3/stream"
    assert captured["additional_headers"] == {
        "x-api-key-id": "test-key",
        "lang_code": "hi-IN",
        "x-sample-rate": "16000",
    }
    sent = b"".join(socket.sent)
    assert sent.startswith(b"\x00\x01" * 1600)
    assert sent[3200:] == bytes(len(sent) - 3200)
    assert len(sent) - 3200 >= 16000
    assert all(len(chunk) == 1024 for chunk in socket.sent)
    assert all(
        later - earlier >= 0.025
        for earlier, later in zip(socket.sent_at, socket.sent_at[1:], strict=False)
    )
    assert [(event.kind, event.text) for event in events] == [("final", "hello")]


@pytest.mark.parametrize("prior_transcript", [False, True])
@pytest.mark.asyncio
async def test_gnani_stream_finish_without_new_transcript_ends(
    monkeypatch: pytest.MonkeyPatch,
    prior_transcript: bool,
) -> None:
    monkeypatch.setattr(
        "indic_language_utils.stt.gnani_stream._FINAL_TRANSCRIPT_TIMEOUT_SECONDS", 0.01
    )
    waiting = asyncio.Event()

    class QuietSocket(FakeSocket):
        def __aiter__(self) -> AsyncIterator[str]:
            async def messages() -> AsyncIterator[str]:
                if prior_transcript:
                    yield json.dumps({"type": "transcript", "text": "already received"})
                await waiting.wait()

            return messages()

    stream = GnaniSTTStream(
        QuietSocket(),
        language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        sampling_rate=16000,
        request_id="req",
    )
    events = stream.events()
    if prior_transcript:
        first = await anext(events)
        assert first.text == "already received"
    else:
        pending = asyncio.create_task(anext(events, None))
        await asyncio.sleep(0)
    await stream.finish()
    if prior_transcript:
        assert await asyncio.wait_for(anext(events, None), timeout=0.1) is None
    else:
        assert await asyncio.wait_for(pending, timeout=0.1) is None
