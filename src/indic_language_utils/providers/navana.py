"""Navana Bodhi provider configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from ..config import Secret, Settings
from ..errors import ConfigurationError
from ..retry import RetryPolicy


@dataclass(frozen=True, slots=True)
class NavanaConfig:
    api_key: Secret
    endpoint: str = "https://tts.navana.ai"
    timeout_seconds: float = 120.0
    max_concurrency: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if not self.endpoint.startswith(("https://", "http://")):
            raise ConfigurationError("Navana endpoint must be an HTTP or HTTPS URL")
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Navana timeout and concurrency must be positive")

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        provider_name: str = "navana",
    ) -> NavanaConfig:
        values = os.environ if env is None else env
        provider = settings.providers.get(provider_name)
        try:
            api_key = Secret(values["NAVANA_API_KEY"])
            endpoint = values.get("NAVANA_ENDPOINT_URL") or (
                provider.endpoint if provider and provider.endpoint else "https://tts.navana.ai"
            )
            timeout = float(
                values.get(
                    "NAVANA_TIMEOUT_SECONDS",
                    str(provider.timeout_seconds if provider else 120.0),
                )
            )
            concurrency = int(
                values.get(
                    "NAVANA_MAX_CONCURRENCY",
                    str(provider.max_concurrency if provider else 8),
                )
            )
        except (KeyError, ValueError) as exc:
            raise ConfigurationError("Navana configuration is incomplete or invalid") from exc
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
