"""Navana Bodhi WebSocket text-to-speech protocol."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Protocol

from ..errors import (
    InvalidInputError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
    TransientProviderError,
)
from ..languages import LanguageTag
from ..providers import CapabilityId
from ..providers.navana import NavanaConfig
from .models import TTSOptions
from .streaming import TTSStreamEvent

_RESERVED = {"auth_token", "lang", "type"}
_ALLOWED_OPTIONS = {"voice", "output_format", "num_step"}


class _Socket(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...

    def __aiter__(self) -> AsyncIterator[str | bytes]: ...


class NavanaTTSStream:
    def __init__(
        self,
        socket: _Socket,
        *,
        language: LanguageTag,
        output_format: str,
        request_id: str,
        session_id: str | None,
    ) -> None:
        self._socket = socket
        self.language = language
        self.audio_format = output_format
        self.request_id = request_id
        self.session_id = session_id or "navana-stream"
        self.model_id = "navana-tts"
        self._flushed = False
        self._sequence = 0
        self._max_text_len = 10000

    async def send_text(self, text: str) -> None:
        if self._flushed:
            raise InvalidInputError("TTS stream has been flushed", provider="navana")
        if not isinstance(text, str) or not text.strip():
            raise InvalidInputError("TTS text must be non-empty", provider="navana")
        if len(text) > self._max_text_len:
            raise InvalidInputError(
                "Navana TTS text exceeds the session character limit", provider="navana"
            )
        await self._socket.send(
            json.dumps({"type": "text", "seq": self._sequence, "target_text": text})
        )
        self._sequence += 1

    async def flush(self) -> None:
        if not self._flushed:
            self._flushed = True
            await self._socket.send('{"type":"end"}')

    async def events(self) -> AsyncIterator[TTSStreamEvent]:
        completed = False
        try:
            async for raw in self._socket:
                if isinstance(raw, (bytes, bytearray)):
                    if not raw:
                        raise ValueError("Empty audio frame")
                    yield TTSStreamEvent(
                        "audio",
                        bytes(raw),
                        self.audio_format,
                        self.language,
                        "navana",
                        self.model_id,
                        self.request_id,
                    )
                    continue
                frame = json.loads(raw)
                if not isinstance(frame, Mapping):
                    raise ValueError("Expected a JSON object")
                kind = frame.get("type")
                if kind == "error":
                    raise TransientProviderError(
                        str(frame.get("message") or "Navana TTS stream failed"),
                        provider="navana",
                        capability=CapabilityId.TEXT_TO_SPEECH.value,
                        request_id=self.request_id,
                    )
                if kind == "done":
                    completed = True
                    yield TTSStreamEvent(
                        "done",
                        None,
                        self.audio_format,
                        self.language,
                        "navana",
                        self.model_id,
                        self.request_id,
                    )
                    break
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise MalformedProviderResponseError(
                "Navana returned a malformed TTS stream event",
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=self.request_id,
            ) from exc
        if not completed:
            raise TransientProviderError(
                "Navana TTS stream closed before completion",
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=self.request_id,
            )


@asynccontextmanager
async def open_navana_tts_stream(
    config: NavanaConfig,
    *,
    language: LanguageTag,
    options: TTSOptions,
    request_id: str,
) -> AsyncIterator[NavanaTTSStream]:
    if _RESERVED.intersection(options.parameters) or set(options.parameters) - _ALLOWED_OPTIONS:
        raise InvalidInputError("TTS stream options contain a reserved field", provider="navana")
    voice = options.parameters.get("voice", "default_female")
    output_format = options.parameters.get("output_format", "24000:pcm16")
    num_step = options.parameters.get("num_step")
    if not isinstance(voice, str) or not voice:
        raise InvalidInputError("Navana voice must be a non-empty string", provider="navana")
    if not isinstance(output_format, str) or output_format not in {
        f"{rate}:{encoding}" for rate in (8000, 16000, 24000) for encoding in ("pcm16", "float32")
    }:
        raise InvalidInputError("Unsupported Navana output format", provider="navana")
    hello: dict[str, object] = {
        "type": "hello",
        "lang": language.language,
        "voice": voice,
        "output_format": output_format,
        "auth_token": config.api_key.reveal(),
    }
    if num_step is not None:
        if not isinstance(num_step, int) or isinstance(num_step, bool) or not 1 <= num_step <= 100:
            raise InvalidInputError("Navana num_step must be between 1 and 100", provider="navana")
        hello["num_step"] = num_step
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "Install indic-language-utils[streaming] for Navana TTS streams",
            provider="navana",
        ) from exc
    endpoint = (
        config.endpoint.rstrip("/").replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    )
    async with connect(
        f"{endpoint}/v1",
        open_timeout=config.timeout_seconds,
        additional_headers={"X-API-Key": config.api_key.reveal()},
    ) as socket:
        await socket.send(json.dumps(hello))
        try:
            ready = json.loads(await socket.recv())
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MalformedProviderResponseError(
                "Navana returned a malformed TTS ready frame",
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            ) from exc
        if not isinstance(ready, Mapping) or ready.get("type") != "ready":
            message = ready.get("message") if isinstance(ready, Mapping) else None
            raise TransientProviderError(
                str(message or "Navana TTS stream did not become ready"),
                provider="navana",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            )
        session_id = ready.get("session_id")
        stream = NavanaTTSStream(
            socket,
            language=language,
            output_format=output_format,
            request_id=request_id,
            session_id=session_id if isinstance(session_id, str) else None,
        )
        max_text_len = ready.get("max_text_len")
        if isinstance(max_text_len, int) and max_text_len > 0:
            stream._max_text_len = max_text_len
        sample_rate = ready.get("sample_rate")
        encoding = ready.get("encoding")
        if isinstance(sample_rate, int) and isinstance(encoding, str):
            if sample_rate not in {8000, 16000, 24000} or encoding not in {"pcm16", "float32"}:
                raise MalformedProviderResponseError(
                    "Navana selected an unsupported TTS stream format",
                    provider="navana",
                    capability=CapabilityId.TEXT_TO_SPEECH.value,
                    request_id=request_id,
                )
            stream.audio_format = f"{sample_rate}:{encoding}"
        yield stream
