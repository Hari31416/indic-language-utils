"""Gnani provider configuration shared by its speech adapters."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from ..config import Secret, Settings
from ..errors import ConfigurationError
from ..retry import RetryPolicy


@dataclass(frozen=True, slots=True)
class GnaniConfig:
    """Credentials and shared runtime settings for Gnani STT and TTS."""

    api_key: Secret
    endpoint: str = "https://api.vachana.ai"
    timeout_seconds: float = 120.0
    max_concurrency: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if self.endpoint and not self.endpoint.startswith(("https://", "http://")):
            raise ConfigurationError("Gnani endpoint must be an HTTP or HTTPS URL")
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Gnani timeout and concurrency must be positive")

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        provider_name: str = "gnani",
    ) -> GnaniConfig:
        values = os.environ if env is None else env
        provider = settings.providers.get(provider_name)
        try:
            api_key = Secret(values["GNANI_API_KEY"])
            endpoint = values.get("GNANI_ENDPOINT_URL") or (
                provider.endpoint if provider and provider.endpoint else "https://api.vachana.ai"
            )
            timeout = float(
                values.get(
                    "GNANI_TIMEOUT_SECONDS",
                    str(provider.timeout_seconds if provider else 120.0),
                )
            )
            concurrency = int(
                values.get(
                    "GNANI_MAX_CONCURRENCY",
                    str(provider.max_concurrency if provider else 8),
                )
            )
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("Gnani configuration is incomplete or invalid") from exc
        return cls(
            api_key,
            endpoint=endpoint,
            timeout_seconds=timeout,
            max_concurrency=concurrency,
            retry_policy=RetryPolicy(
                settings.retry.max_attempts,
                settings.retry.base_delay_seconds,
                settings.retry.max_delay_seconds,
            ),
        )
