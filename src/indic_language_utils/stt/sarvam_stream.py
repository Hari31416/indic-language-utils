"""Sarvam Realtime ASR wire protocol mapped to the public stream events."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlencode

from ..errors import InvalidInputError, MalformedProviderResponseError, TransientProviderError
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..providers import CapabilityId, sarvam_socket
from ..providers.sarvam import SarvamConfig, sarvam_language_code
from .streaming import STTStreamEvent


class SarvamSTTStream:
    def __init__(
        self,
        socket: sarvam_socket.Socket,
        *,
        language: LanguageTag | None,
        model_id: str,
        request_id: str,
    ) -> None:
        self._socket = socket
        self.language = language
        self.model_id = model_id
        self.request_id = request_id
        self._finished = False

    async def send_audio(self, pcm: bytes) -> None:
        if self._finished:
            raise InvalidInputError("ASR stream has ended", provider="sarvam")
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2:
            raise InvalidInputError("Audio must be non-empty 16-bit PCM bytes", provider="sarvam")
        await self._socket.send(
            json.dumps({"event": "audio_input", "audio": base64.b64encode(pcm).decode("ascii")})
        )

    async def finish(self) -> None:
        if not self._finished:
            self._finished = True
            await self._socket.send('{"event":"end"}')

    async def events(self) -> AsyncIterator[STTStreamEvent]:
        ended = False
        async for raw in self._socket:
            try:
                data = json.loads(raw)
                if not isinstance(data, Mapping):
                    raise ValueError
                event = data.get("event")
                if event == "session.end":
                    ended = True
                    break
                if event == "error":
                    raise TransientProviderError(
                        str(data.get("message", "Sarvam ASR stream failed")),
                        provider="sarvam",
                        capability=CapabilityId.SPEECH_TO_TEXT.value,
                        request_id=self.request_id,
                    )
                kinds: dict[str, Literal["speech_start", "speech_end", "partial", "final"]] = {
                    "vad.speech_start": "speech_start",
                    "vad.speech_end": "speech_end",
                    "transcript.partial": "partial",
                    "transcript.final": "final",
                }
                if event not in kinds:
                    continue
                text = (
                    data.get("text")
                    if event in {"transcript.partial", "transcript.final"}
                    else None
                )
                if event in {"transcript.partial", "transcript.final"} and not isinstance(
                    text, str
                ):
                    raise ValueError
                raw_language = data.get("language")
                language = (
                    DEFAULT_LANGUAGE_REGISTRY.normalize(raw_language)
                    if isinstance(raw_language, str) and raw_language != "auto"
                    else self.language
                )
                yield STTStreamEvent(
                    kinds[event], text, language, "sarvam", self.model_id, self.request_id
                )
            except (TypeError, ValueError, KeyError) as exc:
                raise MalformedProviderResponseError(
                    "Sarvam returned a malformed ASR stream event",
                    provider="sarvam",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                    request_id=self.request_id,
                ) from exc
        if not ended:
            raise TransientProviderError(
                "Sarvam ASR stream closed before session.end",
                provider="sarvam",
                capability=CapabilityId.SPEECH_TO_TEXT.value,
                request_id=self.request_id,
            )


@asynccontextmanager
async def open_sarvam_stt_stream(
    config: SarvamConfig,
    *,
    language: LanguageTag | None,
    sampling_rate: int,
    model_id: str,
    request_id: str,
) -> AsyncIterator[SarvamSTTStream]:
    if sampling_rate not in {8000, 16000}:
        raise InvalidInputError("Sarvam Realtime ASR requires 8000 or 16000 Hz PCM")
    if model_id not in {"saaras:v3-realtime", "saaras:v4"}:
        raise InvalidInputError("Sarvam Realtime ASR requires saaras:v3-realtime or saaras:v4")
    query = urlencode(
        {
            "language_code": (
                "or-IN"
                if language is not None and language.language == "or"
                else sarvam_language_code(language)
                if language
                else "auto"
            ),
            "model": model_id,
            "sample_rate": sampling_rate,
            "encoding": "linear16",
            "mode": "transcribe",
            "endpointing": "vad",
        }
    )
    async with sarvam_socket.connect(config, f"/speech-to-text-realtime/ws?{query}") as socket:
        yield SarvamSTTStream(socket, language=language, model_id=model_id, request_id=request_id)
