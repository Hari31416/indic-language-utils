"""Gnani realtime ASR WebSocket wire protocol."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from ..errors import (
    InvalidInputError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
    TransientProviderError,
)
from ..languages import LanguageTag
from ..providers import CapabilityId
from ..providers.gnani import GnaniConfig
from .streaming import STTStreamEvent


class GnaniSTTStream:
    def __init__(
        self, socket: object, *, language: LanguageTag | None, sampling_rate: int, request_id: str
    ) -> None:
        self._socket = socket
        self.language = language
        self.sampling_rate = sampling_rate
        self.model_id = "gnani-stt-stream"
        self.request_id = request_id
        self._finished = False

    async def send_audio(self, pcm: bytes) -> None:
        if self._finished:
            raise InvalidInputError("ASR stream has ended", provider="gnani")
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2:
            raise InvalidInputError("Audio must be non-empty 16-bit PCM bytes", provider="gnani")
        await self._socket.send(pcm)  # type: ignore[attr-defined]

    async def finish(self) -> None:
        if not self._finished:
            self._finished = True
            # Flush the final VAD segment with the API's 500 ms minimum silence.
            silence = bytes(self.sampling_rate)
            chunk_size = 1024
            for offset in range(0, len(silence), chunk_size):
                chunk = silence[offset : offset + chunk_size]
                await self._socket.send(chunk)  # type: ignore[attr-defined]
                await asyncio.sleep(len(chunk) / 2 / self.sampling_rate)

    async def events(self) -> AsyncIterator[STTStreamEvent]:
        async for raw in self._socket:  # type: ignore[attr-defined]
            try:
                data = json.loads(raw)
                if not isinstance(data, Mapping):
                    raise ValueError
                kind = str(data.get("type", data.get("event", data.get("status", "")))).lower()
                if kind in {"connected", "processing", ""}:
                    continue
                if kind == "error":
                    raise TransientProviderError(
                        str(data.get("message", "Gnani ASR stream failed")),
                        provider="gnani",
                        capability=CapabilityId.SPEECH_TO_TEXT.value,
                        request_id=self.request_id,
                    )
                transcript = data.get("text")
                if kind == "transcript":
                    if not isinstance(transcript, str):
                        raise ValueError
                    yield STTStreamEvent(
                        "final", transcript, self.language, "gnani", self.model_id, self.request_id
                    )
                    if self._finished:
                        break
            except (TypeError, ValueError, KeyError) as exc:
                raise MalformedProviderResponseError(
                    "Gnani returned a malformed ASR stream event",
                    provider="gnani",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                    request_id=self.request_id,
                ) from exc


@asynccontextmanager
async def open_gnani_stt_stream(
    config: GnaniConfig, *, language: LanguageTag | None, sampling_rate: int, request_id: str
) -> AsyncIterator[GnaniSTTStream]:
    if language is None:
        raise InvalidInputError("Gnani streaming STT requires a language", provider="gnani")
    if sampling_rate not in {8000, 16000, 44100, 48000}:
        raise InvalidInputError(
            "Gnani streaming STT requires 8000, 16000, 44100, or 48000 Hz", provider="gnani"
        )
    try:
        from websockets.asyncio.client import connect as ws_connect
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "Install indic-language-utils[streaming] for Gnani STT streams", provider="gnani"
        ) from exc
    endpoint = (
        config.endpoint.rstrip("/").replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    )
    async with ws_connect(
        endpoint + "/stt/v3/stream",
        additional_headers={
            "x-api-key-id": config.api_key.reveal(),
            "lang_code": str(language),
            "x-sample-rate": str(sampling_rate),
        },
        open_timeout=config.timeout_seconds,
    ) as socket:
        yield GnaniSTTStream(
            socket, language=language, sampling_rate=sampling_rate, request_id=request_id
        )
