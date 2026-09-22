"""Bhashini pipeline-compute translation adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    UnsupportedLanguagePairError,
)
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
from .models import ProviderTranslationResult, TranslationOptions

if TYPE_CHECKING:
    from ..detection.models import DetectionOptions, ProviderDetectionResult


class BhashiniTranslationProvider:
    identity = ProviderIdentity("bhashini", "Bhashini")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(self, config: BhashiniConfig, *, transport: JsonTransport | None = None) -> None:
        self.config = config
        self._transport = transport
        self._owns_transport = transport is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
        caps: list[CapabilityDeclaration] = [
            CapabilityDeclaration(CapabilityId.TRANSLATION, languages=languages)
        ]
        if config.detection_service_id:
            caps.append(
                CapabilityDeclaration(CapabilityId.TEXT_LANGUAGE_DETECTION, languages=languages)
            )
        self.capabilities = tuple(caps)

    async def start(self) -> None:
        if self._transport is None:
            self._transport = HttpxJsonTransport()

    async def close(self) -> None:
        if self._transport is not None and self._owns_transport:
            await self._transport.close()
            self._transport = None

    async def __aenter__(self) -> BhashiniTranslationProvider:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def translate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TranslationOptions,
        request_id: str,
    ) -> ProviderTranslationResult:
        if not texts or any(not text for text in texts):
            raise InvalidInputError(
                "Bhashini translation inputs cannot be empty",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            )
        payload = self._payload(texts, source, target)
        service_id = self.service_id_for(source, target)
        transport = self._transport
        owns_call_transport = False
        if transport is None:
            transport = HttpxJsonTransport()
            owns_call_transport = True

        async def send() -> JsonResponse:
            async with self._limiter.slot(self.identity.provider, CapabilityId.TRANSLATION):
                response = await transport.post(
                    self.config.endpoint,
                    headers={
                        "Authorization": self.config.api_key.reveal(),
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
            self._raise_for_status(response, request_id)
            return response

        try:
            response = await retry(send, self.config.retry_policy)
            translations, model_id = self._parse(response.data, len(texts), request_id)
            provider_request_id = _header(response.headers, "x-request-id")
            return ProviderTranslationResult(
                translations,
                service_id=service_id,
                model_id=model_id,
                request_id=provider_request_id,
            )
        finally:
            if owns_call_transport:
                await transport.close()

    def _payload(
        self, texts: tuple[str, ...], source: LanguageTag, target: LanguageTag
    ) -> dict[str, object]:
        service_id = self.service_id_for(source, target)
        return {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": bhashini_language_code(source),
                            "targetLanguage": bhashini_language_code(target),
                        },
                        "serviceId": service_id,
                    },
                }
            ],
            "inputData": {"input": [{"source": text} for text in texts]},
        }

    def service_id_for(self, source: LanguageTag, target: LanguageTag) -> str:
        source_tag = str(DEFAULT_LANGUAGE_REGISTRY.normalize(source))
        target_tag = str(DEFAULT_LANGUAGE_REGISTRY.normalize(target))
        selected = self.config.translation_service_ids.get(f"{source_tag}>{target_tag}")
        if selected is None:
            selected = self.config.translation_service_ids.get(target_tag)
        if selected is None:
            selected = self.config.translation_service_id
        if selected is None:
            raise UnsupportedLanguagePairError(
                "No Bhashini translation service is configured for the language pair",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                details={"source": source_tag, "target": target_tag},
            )
        return selected

    async def detect_batch(
        self,
        texts: tuple[str, ...],
        *,
        options: DetectionOptions,
        request_id: str,
    ) -> tuple[ProviderDetectionResult, ...]:
        if not self.config.detection_service_id:
            raise ConfigurationError(
                "A Bhashini detection service ID is required for language detection",
                provider=self.identity.provider,
                capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
            )
        from ..detection.bhashini_detect import BhashiniDetectionProvider

        delegate = BhashiniDetectionProvider(self.config, transport=self._transport)
        return await delegate.detect_batch(texts, options=options, request_id=request_id)

    def _raise_for_status(self, response: JsonResponse, request_id: str) -> None:
        _raise_bhashini_status(
            self.identity.provider, CapabilityId.TRANSLATION, response, request_id
        )

    def _parse(
        self, data: object, expected: int, request_id: str
    ) -> tuple[tuple[str, ...], str | None]:
        try:
            root = _mapping(data)
            pipeline = _list(root["pipelineResponse"])
            task = _mapping(pipeline[0])
            if task.get("taskType") not in {None, "translation"}:
                raise TypeError
            output = _list(task["output"])
            translations = tuple(str(_mapping(item)["target"]) for item in output)
            if not translations or any(not value.strip() for value in translations):
                raise TypeError
            raw_config = task.get("config")
            config = _mapping(raw_config) if raw_config is not None else {}
            model_id_value = config.get("modelId")
            model_id = str(model_id_value) if model_id_value else None
            return translations, model_id
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise MalformedProviderResponseError(
                "Bhashini returned a malformed translation response",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            ) from exc
