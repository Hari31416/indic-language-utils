"""Bhashini pipeline-compute batch ASR adapter."""

from __future__ import annotations

import base64

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
from .models import ProviderSTTResult


class BhashiniSTTProvider:
    identity = ProviderIdentity("bhashini", "Bhashini")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(self, config: BhashiniConfig, *, transport: JsonTransport | None = None) -> None:
        self.config = config
        self._transport = transport
        self._owns_transport = transport is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = (
            frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
            if config.stt_model_id
            else frozenset(DEFAULT_LANGUAGE_REGISTRY.normalize(key) for key in config.stt_model_ids)
        )
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.SPEECH_TO_TEXT, languages=languages),
        )

    async def start(self) -> None:
        if self._transport is None:
            self._transport = HttpxJsonTransport()

    async def close(self) -> None:
        if self._transport is not None and self._owns_transport:
            await self._transport.close()
            self._transport = None

    async def __aenter__(self) -> BhashiniSTTProvider:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def model_id_for(self, language: LanguageTag) -> str:
        tag = str(DEFAULT_LANGUAGE_REGISTRY.normalize(language))
        model_id = self.config.stt_model_ids.get(tag) or self.config.stt_model_id
        if model_id is None:
            raise UnsupportedLanguageError(
                "No Bhashini STT model is configured for this language",
                provider="bhashini",
                capability=CapabilityId.SPEECH_TO_TEXT.value,
                details={"language": tag},
            )
        return model_id

    async def transcribe_batch(
        self,
        audio: tuple[bytes, ...],
        *,
        language: LanguageTag,
        audio_format: str,
        sampling_rate: int,
        request_id: str,
    ) -> tuple[ProviderSTTResult, ...]:
        if not audio or any(not isinstance(item, bytes) or not item for item in audio):
            raise InvalidInputError(
                "Bhashini STT audio cannot be empty",
                provider="bhashini",
                capability=CapabilityId.SPEECH_TO_TEXT.value,
                request_id=request_id,
            )
        model_id = self.model_id_for(language)
        payload: dict[str, object] = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {"sourceLanguage": bhashini_language_code(language)},
                        "serviceId": model_id,
                        "audioFormat": audio_format,
                        "samplingRate": sampling_rate,
                    },
                }
            ],
            "inputData": {
                "audio": [
                    {"audioContent": base64.b64encode(item).decode("ascii")} for item in audio
                ]
            },
        }
        transport = self._transport
        owns_call_transport = transport is None
        if transport is None:
            transport = HttpxJsonTransport()

        async def send() -> JsonResponse:
            async with self._limiter.slot("bhashini", CapabilityId.SPEECH_TO_TEXT):
                response = await transport.post(
                    self.config.endpoint,
                    headers={
                        "Authorization": self.config.api_key.reveal(),
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
            _raise_bhashini_status("bhashini", CapabilityId.SPEECH_TO_TEXT, response, request_id)
            return response

        try:
            response = await retry(send, self.config.retry_policy)
            return self._parse(response, len(audio), model_id, request_id)
        finally:
            if owns_call_transport:
                await transport.close()

    @staticmethod
    def _parse(
        response: JsonResponse, expected: int, selected_model: str, request_id: str
    ) -> tuple[ProviderSTTResult, ...]:
        try:
            task = _mapping(_list(_mapping(response.data)["pipelineResponse"])[0])
            if task.get("taskType") not in (None, "asr"):
                raise TypeError
            output = _list(task["output"])
            if len(output) != expected:
                raise ValueError
            raw_config = task.get("config")
            config = _mapping(raw_config) if raw_config is not None else {}
            model_id = config.get("modelId") or selected_model
            if not isinstance(model_id, str):
                raise TypeError
            texts = tuple(_mapping(item)["source"] for item in output)
            if any(not isinstance(item, str) for item in texts):
                raise TypeError
            return tuple(
                ProviderSTTResult(text, model_id, _header(response.headers, "x-request-id"))
                for text in texts
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise MalformedProviderResponseError(
                "Bhashini returned a malformed STT response",
                provider="bhashini",
                capability=CapabilityId.SPEECH_TO_TEXT.value,
                request_id=request_id,
            ) from exc
