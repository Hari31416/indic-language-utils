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

_FRAME_BYTES = 1024
_FINAL_TRANSCRIPT_TIMEOUT_SECONDS = 5.0


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
        self._finish_event = asyncio.Event()
        self._finish_deadline: float | None = None
        self._pending_audio = bytearray()
        self._next_frame_at: float | None = None

    async def _send_frames(self) -> None:
        loop = asyncio.get_running_loop()
        frame_seconds = (_FRAME_BYTES / 2) / self.sampling_rate
        while len(self._pending_audio) >= _FRAME_BYTES:
            if self._next_frame_at is not None:
                await asyncio.sleep(max(0, self._next_frame_at - loop.time()))
            frame = bytes(self._pending_audio[:_FRAME_BYTES])
            del self._pending_audio[:_FRAME_BYTES]
            await self._socket.send(frame)  # type: ignore[attr-defined]
            self._next_frame_at = max(loop.time(), self._next_frame_at or 0) + frame_seconds

    async def send_audio(self, pcm: bytes) -> None:
        if self._finished:
            raise InvalidInputError("ASR stream has ended", provider="gnani")
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2:
            raise InvalidInputError("Audio must be non-empty 16-bit PCM bytes", provider="gnani")
        self._pending_audio.extend(pcm)
        await self._send_frames()

    async def finish(self) -> None:
        if not self._finished:
            self._finished = True
            # Send 500 ms of silence for VAD, then pad the last frame.
            self._pending_audio.extend(bytes(self.sampling_rate))
            self._pending_audio.extend(bytes(-len(self._pending_audio) % _FRAME_BYTES))
            await self._send_frames()
            self._finish_deadline = (
                asyncio.get_running_loop().time() + _FINAL_TRANSCRIPT_TIMEOUT_SECONDS
            )
            self._finish_event.set()

    async def _receive_event(self, iterator: AsyncIterator[str | bytes]) -> str | bytes:
        async def read_next() -> str | bytes:
            return await iterator.__anext__()

        if self._finish_event.is_set():
            assert self._finish_deadline is not None
            remaining = max(0, self._finish_deadline - asyncio.get_running_loop().time())
            return await asyncio.wait_for(read_next(), timeout=remaining)

        receive_task = asyncio.create_task(read_next())
        finish_task = asyncio.create_task(self._finish_event.wait())
        try:
            done, _ = await asyncio.wait(
                {receive_task, finish_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if finish_task in done and receive_task not in done:
                assert self._finish_deadline is not None
                remaining = max(0, self._finish_deadline - asyncio.get_running_loop().time())
                return await asyncio.wait_for(receive_task, timeout=remaining)
            return receive_task.result()
        finally:
            for task in (receive_task, finish_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(receive_task, finish_task, return_exceptions=True)

    async def events(self) -> AsyncIterator[STTStreamEvent]:
        iterator: AsyncIterator[str | bytes] = self._socket.__aiter__()  # type: ignore[attr-defined]
        while True:
            try:
                raw = await self._receive_event(iterator)
            except (StopAsyncIteration, TimeoutError):
                break
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
                    if self._finish_event.is_set():
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
