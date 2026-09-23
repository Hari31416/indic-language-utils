"""Bhashini pipeline-compute text to speech adapter."""

from __future__ import annotations

import base64
import binascii

from ..concurrency import ConcurrencyLimiter
from ..errors import InvalidInputError, MalformedProviderResponseError, UnsupportedLanguageError
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..providers.bhashini import (
    BhashiniConfig,
    HttpxJsonTransport,
    JsonResponse,
    JsonTransport,
    _header,
    _list,
    _mapping,
    _raise_bhashini_status,
    bhashini_language_code,
)
from ..retry import retry
from .models import ProviderTTSResult, TTSOptions


class BhashiniTTSProvider:
    identity = ProviderIdentity("bhashini", "Bhashini")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(self, config: BhashiniConfig, *, transport: JsonTransport | None = None) -> None:
        self.config = config
        self._transport = transport
        self._owns_transport = transport is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = (
            frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
            if config.tts_model_id
            else frozenset(DEFAULT_LANGUAGE_REGISTRY.normalize(key) for key in config.tts_model_ids)
        )
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TEXT_TO_SPEECH, languages=languages),
        )

    async def start(self) -> None:
        if self._transport is None:
            self._transport = HttpxJsonTransport()

    async def close(self) -> None:
        if self._transport is not None and self._owns_transport:
            await self._transport.close()
            self._transport = None

    async def __aenter__(self) -> BhashiniTTSProvider:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def model_id_for(self, language: LanguageTag | None) -> str:
        tag = str(DEFAULT_LANGUAGE_REGISTRY.normalize(language)) if language else None
        model_id = (self.config.tts_model_ids.get(tag) if tag else None) or self.config.tts_model_id
        if model_id is None:
            raise UnsupportedLanguageError(
                "No Bhashini TTS model is configured for this language",
                provider="bhashini",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                details={"language": tag or "unspecified"},
            )
        return model_id

    async def synthesize_batch(
        self,
        texts: tuple[str, ...],
        *,
        language: LanguageTag | None,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]:
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise InvalidInputError(
                "Bhashini TTS text cannot be empty",
                provider="bhashini",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            )
        model_id = self.model_id_for(language)
        task_config: dict[str, object] = dict(options.parameters)
        task_config["serviceId"] = model_id
        if language is not None:
            task_config["language"] = {"sourceLanguage": bhashini_language_code(language)}
        payload: dict[str, object] = {
            "pipelineTasks": [{"taskType": "tts", "config": task_config}],
            "inputData": {"input": [{"source": text} for text in texts]},
        }
        transport = self._transport
        owns_call_transport = transport is None
        if transport is None:
            transport = HttpxJsonTransport()

        async def send() -> JsonResponse:
            async with self._limiter.slot("bhashini", CapabilityId.TEXT_TO_SPEECH):
                response = await transport.post(
                    self.config.endpoint,
                    headers={
                        "Authorization": self.config.api_key.reveal(),
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
            _raise_bhashini_status("bhashini", CapabilityId.TEXT_TO_SPEECH, response, request_id)
            return response

        try:
            response = await retry(send, self.config.retry_policy)
            return self._parse(response, len(texts), model_id, request_id)
        finally:
            if owns_call_transport:
                await transport.close()

    @staticmethod
    def _parse(
        response: JsonResponse, expected: int, selected_model: str, request_id: str
    ) -> tuple[ProviderTTSResult, ...]:
        try:
            task = _mapping(_list(_mapping(response.data)["pipelineResponse"])[0])
            if task.get("taskType") not in (None, "tts"):
                raise TypeError
            output = _list(task["audio"])
            if len(output) != expected:
                raise ValueError
            raw_config = task.get("config")
            config = _mapping(raw_config) if raw_config is not None else {}
            model_id = config.get("modelId") or selected_model
            if not isinstance(model_id, str):
                raise TypeError
            request_header = _header(response.headers, "x-request-id")
            results: list[ProviderTTSResult] = []
            for item in output:
                audio_data = _mapping(item)
                encoded = audio_data["audioContent"]
                if not isinstance(encoded, str):
                    raise TypeError
                raw = base64.b64decode(encoded, validate=True)
                if not raw:
                    raise ValueError
                audio_format = _audio_format(raw, audio_data.get("audioFormat"))
                results.append(ProviderTTSResult(raw, audio_format, model_id, request_header))
            return tuple(results)
        except (KeyError, IndexError, TypeError, ValueError, binascii.Error) as exc:
            raise MalformedProviderResponseError(
                "Bhashini returned a malformed TTS response",
                provider="bhashini",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                request_id=request_id,
            ) from exc


def _audio_format(audio: bytes, declared: object) -> str | None:
    if audio.startswith(b"RIFF") and audio[8:12] == b"WAVE":
        return "wav"
    if audio.startswith(b"fLaC"):
        return "flac"
    if audio.startswith(b"OggS"):
        return "ogg"
    if audio.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return "mp3"
    return declared.lower() if isinstance(declared, str) and declared else None
