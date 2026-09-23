"""Shared Bhashini provider transport, configuration, and API helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol

import httpx

from ..config import Secret, Settings
from ..errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidInputError,
    PermissionDeniedError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..retry import RetryPolicy
from .base import CapabilityId


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
    translation_service_id: str | None = None
    translation_service_ids: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 20.0
    max_concurrency: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    detection_service_id: str | None = None
    transliteration_service_id: str | None = None
    transliteration_service_ids: Mapping[str, str] = field(default_factory=dict)
    stt_model_id: str | None = None
    stt_model_ids: Mapping[str, str] = field(default_factory=dict)
    tts_model_id: str | None = None
    tts_model_ids: Mapping[str, str] = field(default_factory=dict)

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

        translit_normalized: dict[str, str] = {}
        for selector, service_id in self.transliteration_service_ids.items():
            if not service_id:
                raise ConfigurationError("Bhashini transliteration service IDs cannot be empty")
            normalized_selector = _normalize_service_selector(selector)
            if normalized_selector in translit_normalized:
                raise ConfigurationError("Bhashini transliteration service selector is duplicated")
            translit_normalized[normalized_selector] = service_id
        object.__setattr__(
            self, "transliteration_service_ids", MappingProxyType(translit_normalized)
        )

        for field_name in ("stt_model_ids", "tts_model_ids"):
            selected: dict[str, str] = {}
            for language, model_id in getattr(self, field_name).items():
                if not model_id or not model_id.strip():
                    raise ConfigurationError(f"Bhashini {field_name} values cannot be empty")
                tag = str(DEFAULT_LANGUAGE_REGISTRY.normalize(language))
                if tag in selected:
                    raise ConfigurationError(f"Bhashini {field_name} contains duplicate languages")
                selected[tag] = model_id
            object.__setattr__(self, field_name, MappingProxyType(selected))

        for field_name in ("stt_model_id", "tts_model_id"):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ConfigurationError(f"Bhashini {field_name} cannot be empty")

        if (
            not self.translation_service_id
            and not normalized
            and not self.detection_service_id
            and not self.transliteration_service_id
            and not translit_normalized
            and not self.stt_model_id
            and not self.stt_model_ids
            and not self.tts_model_id
            and not self.tts_model_ids
        ):
            raise ConfigurationError(
                "A default or language-specific Bhashini service ID is required"
            )
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Bhashini timeout and concurrency must be positive")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> BhashiniConfig:
        values = os.environ if env is None else env
        try:
            endpoint = values["BHASHINI_ENDPOINT_URL"]
            api_key = Secret(values["BHASHINI_API_KEY"])
            translation_service_id = values.get("BHASHINI_TRANSLATION_SERVICE_ID")
            detection_service_id = values.get("BHASHINI_DETECTION_SERVICE_ID") or values.get(
                "BHASHINI_TLD_SERVICE_ID"
            )
            transliteration_service_id = values.get("BHASHINI_TRANSLITERATION_SERVICE_ID")
            stt_model_id = values.get("BHASHINI_STT_MODEL_ID")
            tts_model_id = values.get("BHASHINI_TTS_MODEL_ID")
            if (
                translation_service_id is None
                and detection_service_id is None
                and transliteration_service_id is None
                and stt_model_id is None
                and tts_model_id is None
            ):
                raise KeyError("BHASHINI_TRANSLATION_SERVICE_ID")
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
            detection_service_id=detection_service_id,
            transliteration_service_id=transliteration_service_id,
            stt_model_id=stt_model_id,
            tts_model_id=tts_model_id,
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
            detection_service_id = (
                values.get("BHASHINI_DETECTION_SERVICE_ID")
                or values.get("BHASHINI_TLD_SERVICE_ID")
                or (provider.detection_service_id if provider else None)
            )
            transliteration_service_id = values.get("BHASHINI_TRANSLITERATION_SERVICE_ID") or (
                provider.transliteration_service_id if provider else None
            )
            stt_model_id = values.get("BHASHINI_STT_MODEL_ID") or (
                provider.stt_model_id if provider else None
            )
            tts_model_id = values.get("BHASHINI_TTS_MODEL_ID") or (
                provider.tts_model_id if provider else None
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
            transliteration_service_ids = provider.transliteration_service_ids if provider else {}
            stt_model_ids = provider.stt_model_ids if provider else {}
            tts_model_ids = provider.tts_model_ids if provider else {}
            if endpoint is None or (
                translation_service_id is None
                and not translation_service_ids
                and detection_service_id is None
                and transliteration_service_id is None
                and not transliteration_service_ids
                and stt_model_id is None
                and not stt_model_ids
                and tts_model_id is None
                and not tts_model_ids
            ):
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
            detection_service_id=detection_service_id,
            transliteration_service_id=transliteration_service_id,
            transliteration_service_ids=transliteration_service_ids,
            stt_model_id=stt_model_id,
            stt_model_ids=stt_model_ids,
            tts_model_id=tts_model_id,
            tts_model_ids=tts_model_ids,
        )


def _raise_bhashini_status(
    provider: str,
    capability: CapabilityId,
    response: JsonResponse,
    request_id: str,
) -> None:
    if response.status_code < 400:
        return
    if response.status_code == 401:
        raise AuthenticationError(
            "Bhashini authentication failed",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
        )
    if response.status_code == 403:
        raise PermissionDeniedError(
            "Bhashini denied the request",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
        )
    if response.status_code == 429:
        raise RateLimitError(
            "Bhashini rate limit exceeded",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
            retry_after=_retry_after(response.headers),
        )
    if response.status_code in {408, 504}:
        raise ProviderTimeoutError(
            "Bhashini request timed out",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
        )
    if response.status_code >= 500:
        raise TransientProviderError(
            "Bhashini service failed",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
        )
    raise InvalidInputError(
        "Bhashini rejected the request",
        provider=provider,
        capability=capability.value,
        request_id=request_id,
    )


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


def _string(value: object) -> str:
    if not isinstance(value, str):
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
