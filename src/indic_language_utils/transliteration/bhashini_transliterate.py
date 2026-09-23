"""Bhashini pipeline-compute transliteration adapter."""

from __future__ import annotations

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
from .models import ProviderTransliterationResult, TransliterationOptions


class BhashiniTransliterationProvider:
    identity = ProviderIdentity("bhashini", "Bhashini")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(self, config: BhashiniConfig, *, transport: JsonTransport | None = None) -> None:
        if not config.transliteration_service_id and not config.transliteration_service_ids:
            raise ConfigurationError(
                "A default or language-specific Bhashini transliteration service ID is required"
            )
        self.config = config
        self._transport = transport
        self._owns_transport = transport is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TRANSLITERATION, languages=languages),
        )

    async def start(self) -> None:
        if self._transport is None:
            self._transport = HttpxJsonTransport()

    async def close(self) -> None:
        if self._transport is not None and self._owns_transport:
            await self._transport.close()
            self._transport = None

    async def __aenter__(self) -> BhashiniTransliterationProvider:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def transliterate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TransliterationOptions,
        request_id: str,
    ) -> ProviderTransliterationResult:
        if not texts or any(not text or not text.strip() for text in texts):
            raise InvalidInputError(
                "Bhashini transliteration inputs cannot be empty",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLITERATION.value,
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
            async with self._limiter.slot(self.identity.provider, CapabilityId.TRANSLITERATION):
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
            transliterations, model_id = self._parse(response.data, len(texts), request_id)
            provider_request_id = _header(response.headers, "x-request-id")
            return ProviderTransliterationResult(
                transliterations,
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
        lang_config: dict[str, str] = {
            "sourceLanguage": bhashini_language_code(source),
            "targetLanguage": bhashini_language_code(target),
        }
        if source.script:
            lang_config["sourceScriptCode"] = source.script.lower()
        if target.script:
            lang_config["targetScriptCode"] = target.script.lower()

        return {
            "pipelineTasks": [
                {
                    "taskType": "transliteration",
                    "config": {
                        "language": lang_config,
                        "serviceId": service_id,
                    },
                }
            ],
            "inputData": {"input": [{"source": text} for text in texts]},
        }

    def service_id_for(self, source: LanguageTag, target: LanguageTag) -> str:
        source_tag = str(
            DEFAULT_LANGUAGE_REGISTRY.normalize(source)
            if source in DEFAULT_LANGUAGE_REGISTRY
            else source
        )
        target_tag = str(
            DEFAULT_LANGUAGE_REGISTRY.normalize(target)
            if target in DEFAULT_LANGUAGE_REGISTRY
            else target
        )
        selected = self.config.transliteration_service_ids.get(f"{source_tag}>{target_tag}")
        if selected is None:
            selected = self.config.transliteration_service_ids.get(target_tag)
        if selected is None:
            selected = self.config.transliteration_service_id
        if selected is None:
            raise UnsupportedLanguagePairError(
                "No Bhashini transliteration service is configured for the language pair",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLITERATION.value,
                details={"source": source_tag, "target": target_tag},
            )
        return selected

    def _raise_for_status(self, response: JsonResponse, request_id: str) -> None:
        _raise_bhashini_status(
            self.identity.provider, CapabilityId.TRANSLITERATION, response, request_id
        )

    def _parse(
        self, data: object, expected: int, request_id: str
    ) -> tuple[tuple[str, ...], str | None]:
        try:
            root = _mapping(data)
            pipeline = _list(root["pipelineResponse"])
            task = _mapping(pipeline[0])
            if task.get("taskType") not in {None, "transliteration"}:
                raise TypeError
            output = _list(task["output"])
            if len(output) != expected:
                raise TypeError(f"Expected {expected} outputs, got {len(output)}")
            transliterations: list[str] = []
            for item in output:
                item_map = _mapping(item)
                target_val = item_map.get("target")
                if isinstance(target_val, list):
                    if not target_val:
                        raise TypeError("Empty target suggestions list")
                    transliterations.append(str(target_val[0]))
                elif isinstance(target_val, str):
                    if not target_val.strip():
                        raise TypeError("Empty target transliteration")
                    transliterations.append(target_val)
                else:
                    raise TypeError("Invalid target transliteration format")
            raw_config = task.get("config")
            config = _mapping(raw_config) if raw_config is not None else {}
            model_id_value = config.get("modelId")
            model_id = str(model_id_value) if model_id_value else None
            return tuple(transliterations), model_id
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise MalformedProviderResponseError(
                "Bhashini returned a malformed transliteration response",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLITERATION.value,
                request_id=request_id,
            ) from exc
