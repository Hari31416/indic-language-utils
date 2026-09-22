"""Shared foundations for provider-neutral Indian language operations."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("indic-language-utils")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

from .cache import CacheKeyBuilder, MemoryCache, NullCache, SingleFlight
from .config import CacheSettings, ProviderSettings, RetrySettings, Settings, TelemetrySettings
from .errors import LanguageUtilsError
from .languages import DEFAULT_LANGUAGE_REGISTRY, LanguageRegistry, LanguageTag
from .models import (
    CacheMetadata,
    ExecutionTiming,
    ModelIdentity,
    OperationContext,
    ProviderIdentity,
    WarningInfo,
)
from .providers import CapabilityDeclaration, CapabilityId, ProviderRegistry

__all__ = [
    "DEFAULT_LANGUAGE_REGISTRY",
    "CacheKeyBuilder",
    "CacheMetadata",
    "CacheSettings",
    "CapabilityDeclaration",
    "CapabilityId",
    "ExecutionTiming",
    "LanguageRegistry",
    "LanguageTag",
    "LanguageUtilsError",
    "MemoryCache",
    "ModelIdentity",
    "NullCache",
    "OperationContext",
    "ProviderIdentity",
    "ProviderRegistry",
    "ProviderSettings",
    "RetrySettings",
    "Settings",
    "SingleFlight",
    "TelemetrySettings",
    "WarningInfo",
    "__version__",
]
