"""Gnani inference and server-sent-event text to speech adapter."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    AuthenticationError,
    InvalidInputError,
    MalformedProviderResponseError,
    PermissionDeniedError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..providers.gnani import GnaniConfig
from .models import ProviderTTSResult, TTSOptions
from .streaming import TTSStreamEvent

_LANGUAGES = ("bn", "en", "gu", "hi", "kn", "ml", "mr", "pa", "ta", "te")


def _audio_format(payload: Mapping[str, object]) -> str:
    config = payload.get("audio_config")
    if isinstance(config, Mapping) and isinstance(config.get("container"), str):
        return str(config["container"])
    return "wav"


def _payload(
    text: str, language: LanguageTag, options: TTSOptions, model_id: str | None
) -> dict[str, object]:
    values = dict(options.parameters)
    values.pop("streaming_transport", None)
    voice = values.pop("voice", None)
    if not isinstance(voice, str) or not voice.strip():
        raise InvalidInputError("Gnani TTS requires a voice", provider="gnani")
    audio_config = values.pop("audio_config", None)
    option_model = values.pop("model", "timbre-v2.5")
    result: dict[str, object] = {
        "text": text,
        "voice": voice,
        "model": model_id or str(option_model),
        "language": str(language),
    }
    if "speed" in values:
        result["speed"] = values.pop("speed")
    if audio_config is not None:
        if not isinstance(audio_config, Mapping):
            raise InvalidInputError("Gnani audio_config must be an object", provider="gnani")
        result["audio_config"] = dict(audio_config)
    result.update(values)
    return result


class GnaniTTSProvider:
    identity = ProviderIdentity("gnani", "Gnani AI")
    supports_unspecified_language = False
    capabilities: tuple[CapabilityDeclaration, ...] = (
        CapabilityDeclaration(
            CapabilityId.TEXT_TO_SPEECH,
            languages=frozenset(DEFAULT_LANGUAGE_REGISTRY.normalize(code) for code in _LANGUAGES),
        ),
    )

    def __init__(self, config: GnaniConfig, *, client: httpx.AsyncClient | None = None) -> None:
        self.config = config
        self._client = client
        self._owns_client = client is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient()

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def model_id_for(self, language: LanguageTag | None) -> str:
        if language is None:
            raise InvalidInputError("Gnani TTS requires a language", provider="gnani")
        return "timbre-v2.5"

    async def synthesize_batch(
        self,
        texts: tuple[str, ...],
        *,
        language: LanguageTag | None,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]:
        if language is None:
            raise InvalidInputError(
                "Gnani TTS requires a BCP 47 language", provider="gnani", request_id=request_id
            )
        results = []
        for text in texts:
            body = _payload(text, language, options, None)
            client, owned = self._get_client()
            try:
                async with self._limiter.slot("gnani", CapabilityId.TEXT_TO_SPEECH):
                    response = await client.post(
                        f"{self.config.endpoint.rstrip('/')}/api/v1/tts/inference",
                        headers={"X-API-Key-ID": self.config.api_key.reveal()},
                        json=body,
                        timeout=self.config.timeout_seconds,
                    )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(
                    "Gnani TTS timed out", provider="gnani", request_id=request_id
                ) from exc
            except httpx.TransportError as exc:
                raise TransientProviderError(
                    "Gnani TTS transport failed", provider="gnani", request_id=request_id
                ) from exc
            finally:
                if owned:
                    await client.aclose()
            if response.status_code >= 400:
                if response.status_code == 401:
                    raise AuthenticationError(
                        "Gnani authentication failed", provider="gnani", request_id=request_id
                    )
                if response.status_code == 403:
                    raise PermissionDeniedError(
                        "Gnani denied access to TTS", provider="gnani", request_id=request_id
                    )
                if response.status_code == 429:
                    raise RateLimitError(
                        "Gnani TTS rate limit exceeded", provider="gnani", request_id=request_id
                    )
                error = TransientProviderError if response.status_code >= 500 else InvalidInputError
                raise error(
                    "Gnani rejected the TTS request", provider="gnani", request_id=request_id
                )
            if not response.content:
                raise MalformedProviderResponseError(
                    "Gnani returned empty TTS audio", provider="gnani", request_id=request_id
                )
            results.append(
                ProviderTTSResult(response.content, _audio_format(body), str(body["model"]))
            )
        return tuple(results)

    def _get_client(self) -> tuple[httpx.AsyncClient, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.AsyncClient(), True

    @asynccontextmanager
    async def open_stream(
        self,
        *,
        language: LanguageTag,
        options: TTSOptions,
        request_id: str,
        model_id: str | None = None,
    ) -> AsyncIterator[GnaniTTSStream]:
        stream = GnaniTTSStream(self, language, options, request_id, model_id)
        async with self._limiter.slot("gnani", CapabilityId.TEXT_TO_SPEECH):
            yield stream


class GnaniTTSStream:
    """Buffered text-input stream; synthesizes once when flush is called."""

    def __init__(
        self,
        provider: GnaniTTSProvider,
        language: LanguageTag,
        options: TTSOptions,
        request_id: str,
        model_id: str | None,
    ) -> None:
        self.provider, self.language, self.options = provider, language, options
        self.request_id, self.model_id = request_id, model_id or "timbre-v2.5"
        self._texts: list[str] = []
        self._event_queue: asyncio.Queue[TTSStreamEvent | None] = asyncio.Queue()
        self._audio_count = 0
        self._audio_format = "wav"
        self._flushed = False

    async def send_text(self, text: str) -> None:
        if self._flushed or not isinstance(text, str) or not text.strip():
            raise InvalidInputError(
                "Gnani TTS stream expects non-empty text before flush", provider="gnani"
            )
        self._texts.append(text)

    async def flush(self) -> None:
        if self._flushed:
            return
        if not self._texts:
            raise InvalidInputError("Cannot flush an empty Gnani TTS stream", provider="gnani")
        self._flushed = True
        transport = self.options.parameters.get("streaming_transport", "websocket")
        try:
            if transport == "sse":
                await self._flush_sse()
            elif transport == "websocket":
                await self._flush_ws()
            else:
                raise InvalidInputError(
                    "streaming_transport must be 'websocket' or 'sse'", provider="gnani"
                )
            self._event_queue.put_nowait(
                TTSStreamEvent(
                    "done",
                    None,
                    self._audio_format,
                    self.language,
                    "gnani",
                    self.model_id,
                    self.request_id,
                )
            )
        except BaseException:
            self._event_queue.put_nowait(None)
            raise
        self._event_queue.put_nowait(None)

    def _add_audio(self, audio: bytes) -> None:
        if not audio:
            raise MalformedProviderResponseError(
                "Gnani returned an empty audio chunk", provider="gnani", request_id=self.request_id
            )
        self._audio_count += 1
        self._event_queue.put_nowait(
            TTSStreamEvent(
                "audio",
                audio,
                self._audio_format,
                self.language,
                "gnani",
                self.model_id,
                self.request_id,
            )
        )

    async def _flush_sse(self) -> None:
        payload = _payload(" ".join(self._texts), self.language, self.options, self.model_id)
        self._audio_format = _audio_format(payload)
        client, owned = self.provider._get_client()
        try:
            async with client.stream(
                "POST",
                f"{self.provider.config.endpoint.rstrip('/')}/api/v1/tts/sse",
                headers={
                    "X-API-Key-ID": self.provider.config.api_key.reveal(),
                    "Accept": "text/event-stream",
                },
                json=payload,
                timeout=self.provider.config.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    if response.status_code == 401:
                        raise AuthenticationError(
                            "Gnani authentication failed",
                            provider="gnani",
                            request_id=self.request_id,
                        )
                    if response.status_code == 403:
                        raise PermissionDeniedError(
                            "Gnani denied access to TTS",
                            provider="gnani",
                            request_id=self.request_id,
                        )
                    if response.status_code == 429:
                        raise RateLimitError(
                            "Gnani TTS rate limit exceeded",
                            provider="gnani",
                            request_id=self.request_id,
                        )
                    raise TransientProviderError(
                        "Gnani SSE TTS request failed", provider="gnani", request_id=self.request_id
                    )
                event = "message"
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                        if event == "error":
                            raise TransientProviderError(
                                "Gnani SSE synthesis failed",
                                provider="gnani",
                                request_id=self.request_id,
                            )
                        if event == "chunk":
                            try:
                                obj = json.loads(data)
                                encoded = obj.get("audio") or obj.get("audio_base64")
                                self._add_audio(base64.b64decode(encoded, validate=True))
                            except (ValueError, TypeError, binascii.Error, AttributeError) as exc:
                                raise MalformedProviderResponseError(
                                    "Malformed Gnani SSE audio chunk",
                                    provider="gnani",
                                    request_id=self.request_id,
                                ) from exc
                        elif event == "complete":
                            break
                        event = "message"
            if self._audio_count == 0:
                raise MalformedProviderResponseError(
                    "Gnani SSE returned no audio", provider="gnani", request_id=self.request_id
                )
        finally:
            if owned:
                await client.aclose()

    async def _flush_ws(self) -> None:
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:
            from ..errors import MissingOptionalDependencyError

            raise MissingOptionalDependencyError(
                "Install indic-language-utils[streaming] for Gnani TTS streams", provider="gnani"
            ) from exc
        endpoint = (
            self.provider.config.endpoint.rstrip("/")
            .replace("https://", "wss://", 1)
            .replace("http://", "ws://", 1)
        )
        payload = _payload(" ".join(self._texts), self.language, self.options, self.model_id)
        self._audio_format = _audio_format(payload)
        async with connect(
            endpoint + "/api/v1/tts",
            additional_headers={
                "X-API-Key-ID": self.provider.config.api_key.reveal(),
                "Content-Type": "application/json",
            },
            open_timeout=self.provider.config.timeout_seconds,
        ) as socket:
            await socket.send(json.dumps(payload))
            async for raw in socket:
                if isinstance(raw, bytes):
                    self._add_audio(raw)
                    continue
                try:
                    data = json.loads(raw)
                    kind = str(data.get("type", data.get("event", ""))).lower()
                    if kind in {"done", "complete", "completed", "final"}:
                        break
                    if kind == "error":
                        raise TransientProviderError(
                            "Gnani WebSocket synthesis failed",
                            provider="gnani",
                            request_id=self.request_id,
                        )
                    event_data = data.get("data")
                    if not isinstance(event_data, Mapping):
                        event_data = data
                    encoded = (
                        event_data.get("audio")
                        or event_data.get("audio_base64")
                        or event_data.get("chunk")
                    )
                    if encoded:
                        self._add_audio(base64.b64decode(encoded, validate=True))
                    if event_data.get("is_final") is True:
                        break
                except (ValueError, TypeError, binascii.Error, AttributeError) as exc:
                    raise MalformedProviderResponseError(
                        "Malformed Gnani WebSocket event",
                        provider="gnani",
                        request_id=self.request_id,
                    ) from exc
        if self._audio_count == 0:
            raise MalformedProviderResponseError(
                "Gnani WebSocket returned no audio", provider="gnani", request_id=self.request_id
            )

    async def events(self) -> AsyncIterator[TTSStreamEvent]:
        while True:
            event = await self._event_queue.get()
            if event is None:
                break
            yield event
