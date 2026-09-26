"""Browser WebSocket bridges for provider-neutral speech streams."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import replace

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from ..config import Settings
from ..errors import LanguageUtilsError
from ..providers import CapabilityId
from ..stt import get_stt_client
from ..tts import TTSOptions, get_tts_client
from .routes import _get_env_overrides

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
MAX_AUDIO_CHUNK_BYTES = 64 * 1024


class StreamStart(BaseModel):
    type: str
    provider: str | None = None
    language: str | None = None
    model_id: str | None = None
    api_key: str | None = None
    endpoint: str | None = None


class STTStreamStart(StreamStart):
    sampling_rate: int = Field(default=16000, ge=8000, le=16000)


class TTSStreamStart(StreamStart):
    parameters: dict[str, object] = Field(default_factory=dict)


async def _start_message(websocket: WebSocket, model: type[StreamStart]) -> StreamStart:
    data = await websocket.receive_json()
    start = model.model_validate(data)
    if start.type != "start":
        raise ValueError("First message must have type 'start'")
    return start


def _stream_env(start: StreamStart) -> dict[str, str]:
    env = _get_env_overrides()
    if start.api_key:
        if start.provider == "navana":
            env["NAVANA_API_KEY"] = start.api_key
        else:
            env["SARVAM_API_KEY"] = start.api_key
    if start.endpoint:
        if start.provider == "navana":
            env["NAVANA_ENDPOINT_URL"] = start.endpoint
        else:
            env["SARVAM_ENDPOINT_URL"] = start.endpoint
    return env


async def _send_error(websocket: WebSocket, exc: Exception) -> None:
    message = (
        str(exc)
        if isinstance(exc, (LanguageUtilsError, ValueError, ValidationError))
        else "Speech stream failed"
    )
    try:
        await websocket.send_json({"type": "error", "message": message})
    except (RuntimeError, WebSocketDisconnect):
        pass


@router.websocket("/stt/stream")
async def stream_stt(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        start = await _start_message(websocket, STTStreamStart)
        assert isinstance(start, STTStreamStart)
        client = get_stt_client(env=_stream_env(start))
        async with client:
            async with client.stream(
                language=start.language,
                sampling_rate=start.sampling_rate,
                provider=start.provider,
                model_id=start.model_id,
            ) as stream:
                await websocket.send_json({"type": "ready"})

                async def receive_audio() -> None:
                    while True:
                        message = await websocket.receive()
                        if message["type"] == "websocket.disconnect":
                            raise WebSocketDisconnect()
                        chunk = message.get("bytes")
                        if chunk is not None:
                            if not chunk or len(chunk) > MAX_AUDIO_CHUNK_BYTES:
                                raise ValueError("Audio chunk must contain 1 to 65536 bytes")
                            await stream.send_audio(chunk)
                            continue
                        text = message.get("text")
                        if text is not None:
                            try:
                                control = json.loads(text)
                            except json.JSONDecodeError as exc:
                                raise ValueError("Expected PCM audio or a finish message") from exc
                            if isinstance(control, dict) and control.get("type") == "finish":
                                await stream.finish()
                                return
                        raise ValueError("Expected PCM audio or a finish message")

                async def send_events() -> None:
                    async for event in stream.events():
                        await websocket.send_json(
                            {
                                "type": "event",
                                "kind": event.kind,
                                "text": event.text,
                                "language": str(event.language) if event.language else None,
                                "provider": event.provider,
                                "model_id": event.model_id,
                                "request_id": event.request_id,
                            }
                        )

                await _run_pair(receive_audio(), send_events())
                await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.warning("STT stream failed: %s", exc)
        await _send_error(websocket, exc)


@router.websocket("/tts/stream")
async def stream_tts(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        start = await _start_message(websocket, TTSStreamStart)
        assert isinstance(start, TTSStreamStart)
        if not start.language:
            raise ValueError("Live TTS requires a language")
        env = _stream_env(start)
        settings = Settings.load(env=env)
        if start.provider:
            if start.provider == "navana":
                env.pop("BHASHINI_API_KEY", None)
                env.pop("SARVAM_API_KEY", None)
            settings = replace(
                settings,
                routes={
                    **settings.routes,
                    CapabilityId.TEXT_TO_SPEECH.value: (start.provider,),
                },
            )
        client = get_tts_client(settings=settings, env=env)
        async with client:
            async with client.stream(
                language=start.language,
                options=TTSOptions(start.parameters),
                provider=start.provider,
                model_id=start.model_id,
            ) as stream:
                await websocket.send_json({"type": "ready"})

                async def receive_text() -> None:
                    while True:
                        data = await websocket.receive_json()
                        if data.get("type") == "text":
                            await stream.send_text(data.get("text"))
                        elif data.get("type") == "flush":
                            await stream.flush()
                            return
                        else:
                            raise ValueError("Expected text or flush message")

                async def send_events() -> None:
                    async for event in stream.events():
                        await websocket.send_json(
                            {
                                "type": "event",
                                "kind": event.kind,
                                "audio_base64": (
                                    base64.b64encode(event.audio).decode("ascii")
                                    if event.audio is not None
                                    else None
                                ),
                                "audio_format": event.audio_format,
                                "language": str(event.language),
                                "provider": event.provider,
                                "model_id": event.model_id,
                                "request_id": event.request_id,
                            }
                        )

                await _run_pair(receive_text(), send_events())
                await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.warning("TTS stream failed: %s", exc)
        await _send_error(websocket, exc)


async def _run_pair(receiver: object, sender: object) -> None:
    """Keep sending output after input flush, but stop input if output ends first."""
    assert asyncio.iscoroutine(receiver) and asyncio.iscoroutine(sender)
    receive_task = asyncio.create_task(receiver)
    send_task = asyncio.create_task(sender)
    try:
        done, _ = await asyncio.wait({receive_task, send_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        if receive_task in done:
            await send_task
        else:
            receive_task.cancel()
            await asyncio.gather(receive_task, return_exceptions=True)
    finally:
        for task in (receive_task, send_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(receive_task, send_task, return_exceptions=True)
