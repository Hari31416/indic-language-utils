"""Sarvam AI provider transport, configuration, and API helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

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
from .bhashini import JsonResponse, _retry_after


@dataclass(frozen=True, slots=True)
class SarvamConfig:
    api_key: Secret
    endpoint: str = "https://api.sarvam.ai"
    model: str = "sarvam-translate:v1"
    timeout_seconds: float = 20.0
    max_concurrency: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if not self.endpoint.startswith(("https://", "http://")):
            raise ConfigurationError("Sarvam endpoint must be an HTTP or HTTPS URL")
        if not self.model or not self.model.strip():
            raise ConfigurationError("Sarvam model cannot be empty")
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Sarvam timeout and concurrency must be positive")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SarvamConfig:
        values = os.environ if env is None else env
        try:
            api_key = Secret(values["SARVAM_API_KEY"])
            endpoint = values.get("SARVAM_ENDPOINT_URL", "https://api.sarvam.ai")
            model = values.get("SARVAM_MODEL", "sarvam-translate:v1")
            timeout = float(values.get("SARVAM_TIMEOUT_SECONDS", "20"))
            concurrency = int(values.get("SARVAM_MAX_CONCURRENCY", "8"))
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("Sarvam environment configuration is invalid") from exc
        return cls(
            api_key,
            endpoint=endpoint,
            model=model,
            timeout_seconds=timeout,
            max_concurrency=concurrency,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        provider_name: str = "sarvam",
    ) -> SarvamConfig:
        values = os.environ if env is None else env
        provider = settings.providers.get(provider_name)
        try:
            api_key_raw = values.get("SARVAM_API_KEY")
            if not api_key_raw:
                raise KeyError("SARVAM_API_KEY")
            api_key = Secret(api_key_raw)
            endpoint = values.get("SARVAM_ENDPOINT_URL") or (
                provider.endpoint if provider and provider.endpoint else "https://api.sarvam.ai"
            )
            model = values.get("SARVAM_MODEL") or (
                provider.model if provider and provider.model else "sarvam-translate:v1"
            )
            timeout = float(
                values.get(
                    "SARVAM_TIMEOUT_SECONDS",
                    str(provider.timeout_seconds if provider else 20.0),
                )
            )
            concurrency = int(
                values.get(
                    "SARVAM_MAX_CONCURRENCY",
                    str(provider.max_concurrency if provider else 8),
                )
            )
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("Sarvam configuration is incomplete or invalid") from exc
        retry_policy = RetryPolicy(
            settings.retry.max_attempts,
            settings.retry.base_delay_seconds,
            settings.retry.max_delay_seconds,
        )
        return cls(
            api_key,
            endpoint=endpoint,
            model=model,
            timeout_seconds=timeout,
            max_concurrency=concurrency,
            retry_policy=retry_policy,
        )


class SarvamJsonTransport:
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
            raise ProviderTimeoutError("Sarvam request timed out", provider="sarvam") from exc
        except httpx.TransportError as exc:
            raise TransientProviderError("Sarvam transport failed", provider="sarvam") from exc
        try:
            data: object = response.json()
        except ValueError:
            data = None
        return JsonResponse(response.status_code, data, response.headers)

    async def close(self) -> None:
        await self._client.aclose()


def _raise_sarvam_status(
    provider: str,
    capability: CapabilityId,
    response: JsonResponse,
    request_id: str,
) -> None:
    if response.status_code < 400:
        return
    message = "Sarvam request failed"
    if isinstance(response.data, Mapping):
        err = response.data.get("error")
        if isinstance(err, Mapping) and "message" in err:
            message = str(err["message"])
        elif "message" in response.data:
            message = str(response.data["message"])
        elif "detail" in response.data:
            message = str(response.data["detail"])

    if response.status_code == 401:
        raise AuthenticationError(
            message if message != "Sarvam request failed" else "Sarvam authentication failed",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
        )
    if response.status_code == 403:
        raise PermissionDeniedError(
            message if message != "Sarvam request failed" else "Sarvam denied the request",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
        )
    if response.status_code == 429:
        raise RateLimitError(
            message if message != "Sarvam request failed" else "Sarvam rate limit exceeded",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
            retry_after=_retry_after(response.headers),
        )
    if response.status_code in {408, 504}:
        raise ProviderTimeoutError(
            message if message != "Sarvam request failed" else "Sarvam request timed out",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
        )
    if response.status_code >= 500:
        raise TransientProviderError(
            message if message != "Sarvam request failed" else "Sarvam service failed",
            provider=provider,
            capability=capability.value,
            request_id=request_id,
        )
    raise InvalidInputError(
        message if message != "Sarvam request failed" else "Sarvam rejected the request",
        provider=provider,
        capability=capability.value,
        request_id=request_id,
    )


def sarvam_language_code(tag: LanguageTag) -> str:
    normalized = DEFAULT_LANGUAGE_REGISTRY.normalize(tag)
    if normalized.language == "or":
        return "od-IN"
    return f"{normalized.language}-IN"
