"""Sarvam Bulbul WebSocket wire protocol mapped to public audio events."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from urllib.parse import urlencode

from ..errors import InvalidInputError, MalformedProviderResponseError, TransientProviderError
from ..languages import LanguageTag
from ..providers import CapabilityId, sarvam_socket
from ..providers.sarvam import SarvamConfig, sarvam_language_code
from .models import TTSOptions
from .streaming import TTSStreamEvent

_RESERVED = {"language_code", "model", "text", "output_audio_codec"}


class SarvamTTSStream:
    def __init__(
        self,
        socket: sarvam_socket.Socket,
        *,
        language: LanguageTag,
        model_id: str,
        request_id: str,
        audio_format: str,
    ) -> None:
        self._socket = socket
        self.language = language
        self.model_id = model_id
        self.request_id = request_id
        self.audio_format = audio_format
        self._flushed = False

    async def send_text(self, text: str) -> None:
        if self._flushed:
            raise InvalidInputError("TTS stream has been flushed", provider="sarvam")
        if not isinstance(text, str) or not text.strip():
            raise InvalidInputError("TTS text must be non-empty", provider="sarvam")
        await self._socket.send(json.dumps({"type": "text", "data": {"text": text}}))

    async def flush(self) -> None:
        if not self._flushed:
            self._flushed = True
            await self._socket.send('{"type":"flush"}')

    async def events(self) -> AsyncIterator[TTSStreamEvent]:
        completed = False
        async for raw in self._socket:
            try:
                data = json.loads(raw)
                if not isinstance(data, Mapping):
                    raise ValueError
                message_type = data.get("type")
                payload = data.get("data")
                if message_type == "error":
                    message = payload.get("message") if isinstance(payload, Mapping) else None
                    raise TransientProviderError(
                        str(message or "Sarvam TTS stream failed"),
                        provider="sarvam",
                        capability=CapabilityId.TEXT_TO_SPEECH.value,
                        request_id=self.request_id,
                    )
                if message_type == "event":
                    if isinstance(payload, Mapping) and payload.get("event_type") == "final":
                        completed = True
                        yield TTSStreamEvent(
                            "done",
                            None,
                            self.audio_format,
                            self.language,
                            "sarvam",
                            self.model_id,
                            self.request_id,
                        )
                        break
                    continue
                if message_type != "audio":
                    continue
                if not isinstance(payload, Mapping) or not isinstance(payload.get("audio"), str):
                    raise ValueError
                audio = base64.b64decode(payload["audio"], validate=True)
                if not audio:
                    raise ValueError
                yield TTSStreamEvent(
                    "audio",
                    audio,
                    self.audio_format,
                    self.language,
                    "sarvam",
                    self.model_id,
                    self.request_id,
                )
            except (TypeError, ValueError, KeyError, binascii.Error) as exc:
                raise MalformedProviderResponseError(
                    "Sarvam returned a malformed TTS stream event",
                    provider="sarvam",
                    capability=CapabilityId.TEXT_TO_SPEECH.value,
                    request_id=self.request_id,
                ) from exc
        if not completed:
            raise TransientProviderError(
                "Sarvam TTS stream closed before completion",
                provider="sarvam",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=self.request_id,
            )


@asynccontextmanager
async def open_sarvam_tts_stream(
    config: SarvamConfig,
    *,
    language: LanguageTag,
    options: TTSOptions,
    model_id: str,
    request_id: str,
) -> AsyncIterator[SarvamTTSStream]:
    if model_id not in {"bulbul:v2", "bulbul:v3"}:
        raise InvalidInputError("Sarvam streaming TTS requires bulbul:v2 or bulbul:v3")
    if _RESERVED.intersection(options.parameters):
        raise InvalidInputError("TTS stream options contain a reserved field")
    audio_format = options.parameters.get("audio_format", "mp3")
    if audio_format not in {"mp3", "wav", "aac", "opus", "flac", "linear16", "mulaw", "alaw"}:
        raise InvalidInputError("Unsupported Sarvam streaming audio format")
    parameters = dict(options.parameters)
    parameters.pop("audio_format", None)
    parameters.update(
        {
            "language_code": sarvam_language_code(language),
            "output_audio_codec": audio_format,
        }
    )
    query = urlencode({"model": model_id, "send_completion_event": "true"})
    async with sarvam_socket.connect(config, f"/text-to-speech/ws?{query}") as socket:
        await socket.send(json.dumps({"type": "config", "data": parameters}))
        yield SarvamTTSStream(
            socket,
            language=language,
            model_id=model_id,
            request_id=request_id,
            audio_format=str(audio_format),
        )
