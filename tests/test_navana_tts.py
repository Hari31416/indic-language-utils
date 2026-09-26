from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest

from indic_language_utils.config import Secret
from indic_language_utils.errors import AuthenticationError, InvalidInputError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY
from indic_language_utils.providers.navana import NavanaConfig
from indic_language_utils.tts.models import TTSOptions
from indic_language_utils.tts.navana import NavanaTTSProvider
from indic_language_utils.tts.navana_stream import NavanaTTSStream


@pytest.mark.asyncio
async def test_navana_non_streaming_sends_key_and_wraps_pcm_as_wav() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            content=b"\x00\x00\x01\x00",
            headers={"X-Sample-Rate": "16000", "X-Encoding": "pcm16", "X-Request-ID": "provider-1"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = NavanaTTSProvider(NavanaConfig(Secret("test-secret")), client=client)
        result = await provider.synthesize_batch(
            ("नमस्ते",),
            language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TTSOptions({"voice": "achu", "output_format": "16000:pcm16"}),
            request_id="request-1",
        )

    request = requests[0]
    assert request.url == "https://tts.navana.ai/tts/bytes"
    assert request.headers["X-API-Key"] == "test-secret"
    assert json.loads(request.content) == {
        "text": "नमस्ते",
        "lang": "hi",
        "voice": "achu",
        "output_format": "16000:pcm16",
    }
    assert result[0].audio.startswith(b"RIFF")
    assert result[0].audio[20:22] == b"\x01\x00"
    assert result[0].audio[24:28] == b"\x80\x3e\x00\x00"
    assert result[0].audio[-4:] == b"\x00\x00\x01\x00"
    assert result[0].audio_format == "wav"
    assert result[0].request_id == "provider-1"


@pytest.mark.asyncio
async def test_navana_maps_authentication_errors() -> None:
    async def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "key rejected"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = NavanaTTSProvider(NavanaConfig(Secret("test-secret")), client=client)
        with pytest.raises(AuthenticationError, match="Navana authentication failed"):
            await provider.synthesize_batch(
                ("Hello",),
                language=None,
                options=TTSOptions(),
                request_id="request-1",
            )


@pytest.mark.asyncio
async def test_navana_stream_sends_sequence_and_translates_audio_frames() -> None:
    class Socket:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send(self, message: str) -> None:
            self.sent.append(message)

        async def recv(self) -> str:
            return ""

        def __aiter__(self) -> AsyncIterator[str | bytes]:
            async def messages() -> AsyncIterator[str | bytes]:
                yield b"\x00\x01"
                yield '{"type":"done","session_id":"session-1"}'

            return messages()

    socket = Socket()
    stream = NavanaTTSStream(
        socket,
        language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
        output_format="24000:pcm16",
        request_id="request-1",
        session_id="session-1",
    )
    await stream.send_text("नमस्ते।")
    await stream.send_text("फिर मिलेंगे।")
    await stream.flush()
    assert [json.loads(frame) for frame in socket.sent] == [
        {"type": "text", "seq": 0, "target_text": "नमस्ते।"},
        {"type": "text", "seq": 1, "target_text": "फिर मिलेंगे।"},
        {"type": "end"},
    ]
    events = [event async for event in stream.events()]
    assert [event.kind for event in events] == ["audio", "done"]
    assert events[0].audio == b"\x00\x01"
    assert events[0].provider == "navana"


@pytest.mark.asyncio
async def test_navana_stream_rejects_unsupported_options() -> None:
    provider = NavanaTTSProvider(NavanaConfig(Secret("test-secret")))
    with pytest.raises(InvalidInputError, match="reserved field"):
        async with provider.open_stream(
            language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi"),
            options=TTSOptions({"speed": 1.0}),
            request_id="request-1",
        ):
            pass
