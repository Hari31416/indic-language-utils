"""Bhashini pipeline-compute translation adapter."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from .concurrency import ConcurrencyLimiter
from .config import Secret
from .errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    PermissionDeniedError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
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
    service_id: str
    timeout_seconds: float = 20.0
    max_concurrency: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if not self.endpoint.startswith(("https://", "http://")):
            raise ConfigurationError("Bhashini endpoint must be an HTTP or HTTPS URL")
        if not self.service_id:
            raise ConfigurationError(
                "Bhashini service_id is required; obtain it from pipeline configuration"
            )
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Bhashini timeout and concurrency must be positive")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> BhashiniConfig:
        values = os.environ if env is None else env
        try:
            endpoint = values["BHASHINI_ENDPOINT_URL"]
            api_key = Secret(values["BHASHINI_API_KEY"])
            service_id = values["BHASHINI_TRANSLATION_SERVICE_ID"]
            timeout = float(values.get("BHASHINI_TIMEOUT_SECONDS", "20"))
            concurrency = int(values.get("BHASHINI_MAX_CONCURRENCY", "8"))
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("Bhashini environment configuration is invalid") from exc
        return cls(endpoint, api_key, service_id, timeout, concurrency)


class BhashiniTranslationProvider:
    identity = ProviderIdentity("bhashini", "Bhashini")

    def __init__(self, config: BhashiniConfig, *, transport: JsonTransport | None = None) -> None:
        self.config = config
        self.service_id = config.service_id
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
        if self._transport is None:
            raise ConfigurationError("Bhashini provider must be started before use")
        payload = self._payload(texts, source, target)

        async def send() -> JsonResponse:
            assert self._transport is not None
            async with self._limiter.slot(self.identity.provider, CapabilityId.TRANSLATION):
                response = await self._transport.post(
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

        response = await retry(send, self.config.retry_policy)
        translations, model_id = self._parse(response.data, len(texts), request_id)
        provider_request_id = _header(response.headers, "x-request-id")
        return ProviderTranslationResult(
            translations,
            service_id=self.config.service_id,
            model_id=model_id,
            request_id=provider_request_id,
        )

    def _payload(
        self, texts: tuple[str, ...], source: LanguageTag, target: LanguageTag
    ) -> dict[str, object]:
        return {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": bhashini_language_code(source),
                            "targetLanguage": bhashini_language_code(target),
                        },
                        "serviceId": self.config.service_id,
                    },
                }
            ],
            "inputData": {"input": [{"source": text} for text in texts]},
        }

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
            config = _mapping(task.get("config", {}))
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
