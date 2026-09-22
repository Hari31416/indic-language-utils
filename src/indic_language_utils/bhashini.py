"""Bhashini pipeline-compute translation adapter."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol

import httpx

from .concurrency import ConcurrencyLimiter
from .config import Secret, Settings
from .errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    PermissionDeniedError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
    UnsupportedLanguagePairError,
)
from .languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from .models import ProviderIdentity
from .providers import CapabilityDeclaration, CapabilityId
from .retry import RetryPolicy, retry
from .translation.models import ProviderTranslationResult, TranslationOptions


@dataclass(frozen=True, slots=True)
class JsonResponse:
    status_code: int
    data: object
    headers: Mapping[str, str] = field(default_factory=dict)


class JsonTransport(Protocol):
    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse: ...

    async def close(self) -> None: ...


class HttpxJsonTransport:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient()

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        try:
            response = await self._client.post(
                url, headers=headers, json=json, timeout=timeout_seconds
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("Bhashini request timed out", provider="bhashini") from exc
        except httpx.TransportError as exc:
            raise TransientProviderError("Bhashini transport failed", provider="bhashini") from exc
        try:
            data: object = response.json()
        except ValueError:
            data = None
        return JsonResponse(response.status_code, data, response.headers)

    async def close(self) -> None:
        await self._client.aclose()


@dataclass(frozen=True, slots=True)
class BhashiniConfig:
    endpoint: str
    api_key: Secret
    translation_service_id: str | None
    translation_service_ids: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 20.0
    max_concurrency: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if not self.endpoint.startswith(("https://", "http://")):
            raise ConfigurationError("Bhashini endpoint must be an HTTP or HTTPS URL")
        normalized: dict[str, str] = {}
        for selector, service_id in self.translation_service_ids.items():
            if not service_id:
                raise ConfigurationError("Bhashini translation service IDs cannot be empty")
            normalized_selector = _normalize_service_selector(selector)
            if normalized_selector in normalized:
                raise ConfigurationError("Bhashini translation service selector is duplicated")
            normalized[normalized_selector] = service_id
        object.__setattr__(self, "translation_service_ids", MappingProxyType(normalized))
        if not self.translation_service_id and not normalized:
            raise ConfigurationError(
                "A default or language-specific Bhashini translation service ID is required"
            )
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Bhashini timeout and concurrency must be positive")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> BhashiniConfig:
        values = os.environ if env is None else env
        try:
            endpoint = values["BHASHINI_ENDPOINT_URL"]
            api_key = Secret(values["BHASHINI_API_KEY"])
            translation_service_id = values["BHASHINI_TRANSLATION_SERVICE_ID"]
            timeout = float(values.get("BHASHINI_TIMEOUT_SECONDS", "20"))
            concurrency = int(values.get("BHASHINI_MAX_CONCURRENCY", "8"))
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("Bhashini environment configuration is invalid") from exc
        return cls(
            endpoint,
            api_key,
            translation_service_id,
            timeout_seconds=timeout,
            max_concurrency=concurrency,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        provider_name: str = "bhashini",
    ) -> BhashiniConfig:
        """Combine non-secret provider settings with environment-only credentials."""
        values = os.environ if env is None else env
        provider = settings.providers.get(provider_name)
        try:
            endpoint = values.get("BHASHINI_ENDPOINT_URL") or (
                provider.endpoint if provider else None
            )
            translation_service_id = values.get("BHASHINI_TRANSLATION_SERVICE_ID") or (
                provider.translation_service_id if provider else None
            )
            api_key = Secret(values["BHASHINI_API_KEY"])
            timeout = float(
                values.get(
                    "BHASHINI_TIMEOUT_SECONDS",
                    str(provider.timeout_seconds if provider else 20.0),
                )
            )
            concurrency = int(
                values.get(
                    "BHASHINI_MAX_CONCURRENCY",
                    str(provider.max_concurrency if provider else 8),
                )
            )
            translation_service_ids = provider.translation_service_ids if provider else {}
            if endpoint is None or (translation_service_id is None and not translation_service_ids):
                raise KeyError
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("Bhashini configuration is incomplete or invalid") from exc
        retry_policy = RetryPolicy(
            settings.retry.max_attempts,
            settings.retry.base_delay_seconds,
            settings.retry.max_delay_seconds,
        )
        return cls(
            endpoint,
            api_key,
            translation_service_id,
            translation_service_ids,
            timeout,
            concurrency,
            retry_policy,
        )


class BhashiniTranslationProvider:
    identity = ProviderIdentity("bhashini", "Bhashini")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(self, config: BhashiniConfig, *, transport: JsonTransport | None = None) -> None:
        self.config = config
        self._transport = transport
        self._owns_transport = transport is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
        self.capabilities = (CapabilityDeclaration(CapabilityId.TRANSLATION, languages=languages),)

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

    def _raise_for_status(self, response: JsonResponse, request_id: str) -> None:
        if response.status_code < 400:
            return
        if response.status_code == 401:
            raise AuthenticationError(
                "Bhashini authentication failed",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            )
        if response.status_code == 403:
            raise PermissionDeniedError(
                "Bhashini denied the request",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            )
        if response.status_code == 429:
            raise RateLimitError(
                "Bhashini rate limit exceeded",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
                retry_after=_retry_after(response.headers),
            )
        if response.status_code in {408, 504}:
            raise ProviderTimeoutError(
                "Bhashini request timed out",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            )
        if response.status_code >= 500:
            raise TransientProviderError(
                "Bhashini service failed",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            )
        raise InvalidInputError(
            "Bhashini rejected the request",
            provider=self.identity.provider,
            capability=CapabilityId.TRANSLATION.value,
            request_id=request_id,
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


def bhashini_language_code(tag: LanguageTag) -> str:
    normalized = DEFAULT_LANGUAGE_REGISTRY.normalize(tag)
    return normalized.language


def _normalize_service_selector(selector: str) -> str:
    parts = selector.split(">")
    if len(parts) == 1:
        return str(DEFAULT_LANGUAGE_REGISTRY.normalize(parts[0].strip()))
    if len(parts) == 2 and all(part.strip() for part in parts):
        source = DEFAULT_LANGUAGE_REGISTRY.normalize(parts[0].strip())
        target = DEFAULT_LANGUAGE_REGISTRY.normalize(parts[1].strip())
        return f"{source}>{target}"
    raise ConfigurationError("Translation service selector must be a target or source>target")


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError
    return value


def _list(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError
    return value


def _header(headers: Mapping[str, str], name: str) -> str | None:
    return next((value for key, value in headers.items() if key.lower() == name), None)


def _retry_after(headers: Mapping[str, str]) -> float | None:
    value = _header(headers, "retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
