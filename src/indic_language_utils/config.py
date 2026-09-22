"""Validated settings with environment loading and redacted secrets."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from .errors import ConfigurationError


class Secret:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not value:
            raise ValueError("Secret cannot be empty")
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret('**********')"

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class RetrySettings:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0


@dataclass(frozen=True, slots=True)
class CacheSettings:
    enabled: bool = False
    backend: str = "null"
    namespace: str = "indic-language-utils"
    max_entries: int = 1024
    ttl_seconds: float = 300.0
    path: str = ".cache/indic-language-utils.sqlite3"


@dataclass(frozen=True, slots=True)
class TelemetrySettings:
    logging_enabled: bool = True
    metrics_enabled: bool = True
    traces_enabled: bool = True
    include_content: bool = False


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    timeout_seconds: float = 20.0
    max_concurrency: int = 8
    credential: Secret | None = None


@dataclass(frozen=True, slots=True)
class Settings:
    providers: Mapping[str, ProviderSettings] = field(default_factory=dict)
    routes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    retry: RetrySettings = field(default_factory=RetrySettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    telemetry: TelemetrySettings = field(default_factory=TelemetrySettings)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, prefix: str = "ILU_") -> Settings:
        values = os.environ if env is None else env

        def value(name: str, default: str) -> str:
            return values.get(prefix + name, default)

        try:
            cache = CacheSettings(
                enabled=_bool(value("CACHE_ENABLED", "false")),
                backend=value("CACHE_BACKEND", "null"),
                namespace=value("CACHE_NAMESPACE", "indic-language-utils"),
                max_entries=int(value("CACHE_MAX_ENTRIES", "1024")),
                ttl_seconds=float(value("CACHE_TTL_SECONDS", "300")),
                path=value("CACHE_PATH", ".cache/indic-language-utils.sqlite3"),
            )
            retry_settings = RetrySettings(
                max_attempts=int(value("RETRY_MAX_ATTEMPTS", "3")),
                base_delay_seconds=float(value("RETRY_BASE_DELAY_SECONDS", "0.25")),
                max_delay_seconds=float(value("RETRY_MAX_DELAY_SECONDS", "5")),
            )
            telemetry = TelemetrySettings(
                logging_enabled=_bool(value("LOGGING_ENABLED", "true")),
                metrics_enabled=_bool(value("METRICS_ENABLED", "true")),
                traces_enabled=_bool(value("TRACES_ENABLED", "true")),
                include_content=_bool(value("TELEMETRY_INCLUDE_CONTENT", "false")),
            )
        except ValueError as exc:
            raise ConfigurationError("Environment settings are invalid") from exc
        settings = cls(retry=retry_settings, cache=cache, telemetry=telemetry)
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.retry.max_attempts < 1:
            raise ConfigurationError("retry.max_attempts must be positive")
        if self.cache.max_entries < 1 or self.cache.ttl_seconds < 0:
            raise ConfigurationError("Cache size must be positive and TTL cannot be negative")
        if self.cache.backend not in {"null", "memory", "sqlite"}:
            raise ConfigurationError("Cache backend must be null, memory, or sqlite")
        if self.cache.backend == "sqlite" and not self.cache.path:
            raise ConfigurationError("SQLite cache path cannot be empty")
        for name, provider in self.providers.items():
            if not name or provider.timeout_seconds <= 0 or provider.max_concurrency < 1:
                raise ConfigurationError("Provider settings are invalid", provider=name or None)


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Not a boolean: {value}")
