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
from .processors import ProcessorIdentity, VersionedProcessor
from .providers import CapabilityDeclaration, CapabilityId, ProviderRegistry
from .translation import (
    DEFAULT_TRANSLATION_PROCESSORS,
    CatalogEntry,
    CatalogStatus,
    DefaultTranslationStructureProcessor,
    LocalizationCatalog,
    PreparedText,
    ProtectedContentProcessor,
    Segment,
    SyncTranslationClient,
    TextFormat,
    TranslationClient,
    TranslationOptions,
    TranslationProcessorPipeline,
    TranslationRequest,
    TranslationResult,
    TranslationResultCodec,
    TranslationSegmentProcessor,
    TranslationStructureProcessor,
    UnicodeNormalizationProcessor,
    create_translation_cache,
    get_sync_translation_client,
    get_translation_client,
    translate,
    translate_batch,
    translate_batch_sync,
    translate_sync,
)

__all__ = [
    "DEFAULT_LANGUAGE_REGISTRY",
    "DEFAULT_TRANSLATION_PROCESSORS",
    "BhashiniConfig",
    "BhashiniTranslationProvider",
    "CacheKeyBuilder",
    "CacheMetadata",
    "CacheSettings",
    "CapabilityDeclaration",
    "CapabilityId",
    "CatalogEntry",
    "CatalogStatus",
    "DefaultTranslationStructureProcessor",
    "ExecutionTiming",
    "LanguageRegistry",
    "LanguageTag",
    "LanguageUtilsError",
    "LocalizationCatalog",
    "MemoryCache",
    "ModelIdentity",
    "NullCache",
    "OperationContext",
    "PreparedText",
    "ProcessorIdentity",
    "ProtectedContentProcessor",
    "ProviderIdentity",
    "ProviderRegistry",
    "ProviderSettings",
    "RetrySettings",
    "SQLiteCache",
    "Segment",
    "Settings",
    "SingleFlight",
    "SyncTranslationClient",
    "TelemetrySettings",
    "TextFormat",
    "TranslationClient",
    "TranslationOptions",
    "TranslationProcessorPipeline",
    "TranslationRequest",
    "TranslationResult",
    "TranslationResultCodec",
    "TranslationSegmentProcessor",
    "TranslationStructureProcessor",
    "UnicodeNormalizationProcessor",
    "VersionedProcessor",
    "WarningInfo",
    "__version__",
    "create_translation_cache",
    "get_sync_translation_client",
    "get_translation_client",
    "translate",
    "translate_batch",
    "translate_batch_sync",
    "translate_sync",
]
