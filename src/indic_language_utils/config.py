"""Validated settings with environment loading and redacted secrets."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    endpoint: str | None = None
    translation_service_id: str | None = None
    translation_service_ids: Mapping[str, str] = field(default_factory=dict)
    detection_service_id: str | None = None
    transliteration_service_id: str | None = None
    transliteration_service_ids: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 20.0
    max_concurrency: int = 8
    credential: Secret | None = None
    model: str | None = None
    stt_model_id: str | None = None
    stt_model_ids: Mapping[str, str] = field(default_factory=dict)
    tts_model_id: str | None = None
    tts_model_ids: Mapping[str, str] = field(default_factory=dict)
    options: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Settings:
    providers: Mapping[str, ProviderSettings] = field(default_factory=dict)
    routes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    retry: RetrySettings = field(default_factory=RetrySettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    telemetry: TelemetrySettings = field(default_factory=TelemetrySettings)

    @classmethod
    def load(
        cls,
        path: str | Path | None = None,
        *,
        env: Mapping[str, str] | None = None,
        overrides: Mapping[str, object] | None = None,
        start_dir: str | Path | None = None,
        prefix: str = "ILU_",
    ) -> Settings:
        """Load defaults, discovered TOML files, environment, and explicit overrides."""
        values = os.environ if env is None else env
        data: dict[str, Any] = {}
        for config_path in discover_config_files(values, start_dir=start_dir):
            _deep_merge(data, _load_toml(config_path))

        selected_path = path or values.get(prefix + "CONFIG_FILE")
        if selected_path is not None:
            explicit_path = Path(selected_path).expanduser().resolve()
            if not explicit_path.is_file():
                raise ConfigurationError("Explicit configuration file does not exist")
            discovered = set(discover_config_files(values, start_dir=start_dir))
            if explicit_path not in discovered:
                _deep_merge(data, _load_toml(explicit_path))

        try:
            _deep_merge(data, _environment_data(values, prefix))
        except ValueError as exc:
            raise ConfigurationError("Environment settings are invalid") from exc
        if overrides:
            _deep_merge(data, overrides)
        return cls._from_mapping(data)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, prefix: str = "ILU_") -> Settings:
        values = os.environ if env is None else env
        try:
            return cls._from_mapping(_environment_data(values, prefix))
        except ValueError as exc:
            raise ConfigurationError("Environment settings are invalid") from exc

    @classmethod
    def _from_mapping(cls, data: Mapping[str, object]) -> Settings:
        _reject_unknown(data, {"providers", "routes", "retry", "cache", "telemetry"}, "root")
        retry_data = _section(data, "retry")
        cache_data = _section(data, "cache")
        telemetry_data = _section(data, "telemetry")
        _reject_unknown(
            retry_data,
            {"max_attempts", "base_delay_seconds", "max_delay_seconds"},
            "retry",
        )
        _reject_unknown(
            cache_data,
            {"enabled", "backend", "namespace", "max_entries", "ttl_seconds", "path"},
            "cache",
        )
        _reject_unknown(
            telemetry_data,
            {"logging_enabled", "metrics_enabled", "traces_enabled", "include_content"},
            "telemetry",
        )
        defaults = cls()
        retry_settings = RetrySettings(
            max_attempts=_integer(retry_data.get("max_attempts", defaults.retry.max_attempts)),
            base_delay_seconds=_number(
                retry_data.get("base_delay_seconds", defaults.retry.base_delay_seconds)
            ),
            max_delay_seconds=_number(
                retry_data.get("max_delay_seconds", defaults.retry.max_delay_seconds)
            ),
        )
        cache = CacheSettings(
            enabled=_boolean(cache_data.get("enabled", defaults.cache.enabled)),
            backend=_string(cache_data.get("backend", defaults.cache.backend)),
            namespace=_string(cache_data.get("namespace", defaults.cache.namespace)),
            max_entries=_integer(cache_data.get("max_entries", defaults.cache.max_entries)),
            ttl_seconds=_number(cache_data.get("ttl_seconds", defaults.cache.ttl_seconds)),
            path=_string(cache_data.get("path", defaults.cache.path)),
        )
        telemetry = TelemetrySettings(
            logging_enabled=_boolean(
                telemetry_data.get("logging_enabled", defaults.telemetry.logging_enabled)
            ),
            metrics_enabled=_boolean(
                telemetry_data.get("metrics_enabled", defaults.telemetry.metrics_enabled)
            ),
            traces_enabled=_boolean(
                telemetry_data.get("traces_enabled", defaults.telemetry.traces_enabled)
            ),
            include_content=_boolean(
                telemetry_data.get("include_content", defaults.telemetry.include_content)
            ),
        )
        providers = _providers(_section(data, "providers"))
        routes = _routes(_section(data, "routes"))
        settings = cls(
            providers=providers,
            routes=routes,
            retry=retry_settings,
            cache=cache,
            telemetry=telemetry,
        )
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


def discover_config_files(
    env: Mapping[str, str] | None = None, *, start_dir: str | Path | None = None
) -> tuple[Path, ...]:
    """Return existing user and nearest-project config files in precedence order."""
    values = os.environ if env is None else env
    xdg_root = values.get("XDG_CONFIG_HOME")
    if xdg_root:
        user_root = Path(xdg_root).expanduser()
    elif values.get("HOME"):
        user_root = Path(values["HOME"]).expanduser() / ".config"
    else:
        user_root = Path.home() / ".config"
    user_config = (user_root / "indic-language-utils" / "config.toml").resolve()

    current = Path.cwd() if start_dir is None else Path(start_dir)
    current = current.expanduser().resolve()
    if current.is_file():
        current = current.parent
    project_config: Path | None = None
    for directory in (current, *current.parents):
        candidate = directory / ".indic-language-utils.toml"
        if candidate.is_file():
            project_config = candidate.resolve()
            break
    return tuple(
        item for item in (user_config if user_config.is_file() else None, project_config) if item
    )


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError("Configuration file could not be read or parsed") from exc
    _reject_secrets(data)
    return data


def _reject_secrets(data: Mapping[str, object], prefix: str = "") -> None:
    sensitive = {"api_key", "credential", "password", "secret", "token", "authorization"}
    for key, value in data.items():
        normalized = key.lower().replace("-", "_")
        if normalized in sensitive or any(normalized.endswith(f"_{item}") for item in sensitive):
            raise ConfigurationError("Secrets are not allowed in TOML configuration")
        if isinstance(value, Mapping):
            _reject_secrets(value, f"{prefix}.{key}" if prefix else key)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, Mapping):
                    _reject_secrets(item, f"{prefix}.{key}" if prefix else key)


def _deep_merge(target: dict[str, Any], source: Mapping[str, object]) -> None:
    for key, value in source.items():
        existing = target.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            _deep_merge(existing, value)
        elif isinstance(value, Mapping):
            nested: dict[str, Any] = {}
            _deep_merge(nested, value)
            target[key] = nested
        else:
            target[key] = value


def _environment_data(values: Mapping[str, str], prefix: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    mappings: dict[str, tuple[str, str, Callable[[str], object]]] = {
        "CACHE_ENABLED": ("cache", "enabled", _bool),
        "CACHE_BACKEND": ("cache", "backend", str),
        "CACHE_NAMESPACE": ("cache", "namespace", str),
        "CACHE_MAX_ENTRIES": ("cache", "max_entries", int),
        "CACHE_TTL_SECONDS": ("cache", "ttl_seconds", float),
        "CACHE_PATH": ("cache", "path", str),
        "RETRY_MAX_ATTEMPTS": ("retry", "max_attempts", int),
        "RETRY_BASE_DELAY_SECONDS": ("retry", "base_delay_seconds", float),
        "RETRY_MAX_DELAY_SECONDS": ("retry", "max_delay_seconds", float),
        "LOGGING_ENABLED": ("telemetry", "logging_enabled", _bool),
        "METRICS_ENABLED": ("telemetry", "metrics_enabled", _bool),
        "TRACES_ENABLED": ("telemetry", "traces_enabled", _bool),
        "TELEMETRY_INCLUDE_CONTENT": ("telemetry", "include_content", _bool),
    }
    for env_name, (section, key, converter) in mappings.items():
        raw = values.get(prefix + env_name)
        if raw is not None:
            data.setdefault(section, {})[key] = converter(raw)
    route_prefix = prefix + "ROUTE_"
    for key, raw in values.items():
        if key.startswith(route_prefix):
            capability = key[len(route_prefix) :].lower()
            data.setdefault("routes", {})[capability] = [
                item.strip() for item in raw.split(",") if item.strip()
            ]
    return data


def _providers(data: Mapping[str, object]) -> dict[str, ProviderSettings]:
    result: dict[str, ProviderSettings] = {}
    allowed = {
        "endpoint",
        "translation_service_id",
        "translation_service_ids",
        "detection_service_id",
        "tld_service_id",
        "transliteration_service_id",
        "transliteration_service_ids",
        "timeout_seconds",
        "max_concurrency",
        "model",
        "stt_model_id",
        "stt_model_ids",
        "tts_model_id",
        "tts_model_ids",
        "options",
    }
    for name, raw in data.items():
        values = _mapping(raw, f"providers.{name}")
        _reject_unknown(values, allowed, f"providers.{name}")
        result[name] = ProviderSettings(
            endpoint=_optional_string(values.get("endpoint")),
            translation_service_id=_optional_string(values.get("translation_service_id")),
            translation_service_ids=_string_mapping(
                values.get("translation_service_ids", {}),
                f"providers.{name}.translation_service_ids",
            ),
            detection_service_id=_optional_string(
                values.get("detection_service_id") or values.get("tld_service_id")
            ),
            transliteration_service_id=_optional_string(values.get("transliteration_service_id")),
            transliteration_service_ids=_string_mapping(
                values.get("transliteration_service_ids", {}),
                f"providers.{name}.transliteration_service_ids",
            ),
            timeout_seconds=_number(values.get("timeout_seconds", 20.0)),
            max_concurrency=_integer(values.get("max_concurrency", 8)),
            model=_optional_string(values.get("model")),
            stt_model_id=_optional_string(values.get("stt_model_id")),
            stt_model_ids=_string_mapping(
                values.get("stt_model_ids", {}), f"providers.{name}.stt_model_ids"
            ),
            tts_model_id=_optional_string(values.get("tts_model_id")),
            tts_model_ids=_string_mapping(
                values.get("tts_model_ids", {}), f"providers.{name}.tts_model_ids"
            ),
            options=_provider_options(values.get("options", {}), name),
        )
    return result


def _provider_options(value: object, provider: str) -> dict[str, object]:
    options = _mapping(value, f"providers.{provider}.options")
    if not all(isinstance(key, str) and key for key in options):
        raise ConfigurationError(f"Provider options must have non-empty string keys: {provider}")
    _reject_secrets(options)
    return {key: _provider_option(item, provider) for key, item in options.items()}


def _provider_option(value: object, provider: str) -> object:
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_provider_option(item, provider) for item in value]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) and key for key in value):
            raise ConfigurationError(
                f"Provider options must have non-empty string keys: {provider}"
            )
        _reject_secrets(value)
        return {key: _provider_option(item, provider) for key, item in value.items()}
    raise ConfigurationError(f"Provider options must contain TOML-compatible values: {provider}")


def _routes(data: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for capability, raw in data.items():
        if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
            raise ConfigurationError("Route values must be non-empty provider name arrays")
        result[capability] = tuple(raw)
    return result


def _string_mapping(value: object, name: str) -> dict[str, str]:
    values = _mapping(value, name)
    result: dict[str, str] = {}
    for key, item in values.items():
        if not key or not isinstance(item, str) or not item:
            raise ConfigurationError(f"Configuration mapping must contain strings: {name}")
        result[key] = item
    return result


def _section(data: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = data.get(name, {})
    return _mapping(value, name)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"Configuration section must be a table: {name}")
    return value


def _reject_unknown(data: Mapping[str, object], allowed: set[str], section: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ConfigurationError(f"Unknown configuration field in {section}: {sorted(unknown)[0]}")


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("Configuration value must be a string")
    return value


def _optional_string(value: object) -> str | None:
    return None if value is None else _string(value)


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError("Configuration value must be a boolean")
    return value


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError("Configuration value must be an integer")
    return value


def _number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigurationError("Configuration value must be a number")
    return float(value)


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Not a boolean: {value}")
