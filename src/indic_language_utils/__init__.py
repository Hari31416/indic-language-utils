"""Shared foundations for provider-neutral Indian language operations."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("indic-language-utils")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

from .bhashini import BhashiniConfig, BhashiniTranslationProvider
from .cache import CacheKeyBuilder, MemoryCache, NullCache, SingleFlight, SQLiteCache
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
    TranslationResultCodec,
    create_translation_cache,
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
    "SQLiteCache",
    "Settings",
    "SingleFlight",
    "SyncTranslationClient",
    "TelemetrySettings",
    "TextFormat",
    "TranslationClient",
    "TranslationOptions",
    "TranslationRequest",
    "TranslationResult",
    "TranslationResultCodec",
    "WarningInfo",
    "__version__",
    "create_translation_cache",
]
