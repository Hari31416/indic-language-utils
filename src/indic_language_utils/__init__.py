"""Shared foundations for provider-neutral Indian language operations."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("indic-language-utils")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

from .bhashini import BhashiniConfig, BhashiniTranslationProvider
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
from .translation import (
    CatalogEntry,
    CatalogStatus,
    LocalizationCatalog,
    SyncTranslationClient,
    TextFormat,
    TranslationClient,
    TranslationOptions,
    TranslationRequest,
    TranslationResult,
)

__all__ = [
    "DEFAULT_LANGUAGE_REGISTRY",
    "BhashiniConfig",
    "BhashiniTranslationProvider",
    "CacheKeyBuilder",
    "CacheMetadata",
    "CacheSettings",
    "CapabilityDeclaration",
    "CapabilityId",
    "CatalogEntry",
    "CatalogStatus",
    "ExecutionTiming",
    "LanguageRegistry",
    "LanguageTag",
    "LanguageUtilsError",
    "LocalizationCatalog",
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
    "SyncTranslationClient",
    "TelemetrySettings",
    "TextFormat",
    "TranslationClient",
    "TranslationOptions",
    "TranslationRequest",
    "TranslationResult",
    "WarningInfo",
    "__version__",
]
