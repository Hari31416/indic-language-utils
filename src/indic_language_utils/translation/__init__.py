"""Public translation API."""

from .cache import TranslationResultCodec, create_translation_cache
from .catalog import CatalogEntry, CatalogStatus, LocalizationCatalog
from .client import TranslationClient
from .models import (
    ProviderTranslationResult,
    TextFormat,
    TranslationOptions,
    TranslationProviderMetadata,
    TranslationRequest,
    TranslationResult,
)
from .processing import (
    DEFAULT_TRANSLATION_PROCESSORS,
    DefaultTranslationStructureProcessor,
    PreparedText,
    ProtectedContentProcessor,
    Segment,
    TranslationProcessorPipeline,
    TranslationSegmentProcessor,
    TranslationStructureProcessor,
    UnicodeNormalizationProcessor,
)
from .protocols import TranslationProvider
from .sync import SyncTranslationClient

__all__ = [
    "DEFAULT_TRANSLATION_PROCESSORS",
    "CatalogEntry",
    "CatalogStatus",
    "DefaultTranslationStructureProcessor",
    "LocalizationCatalog",
    "PreparedText",
    "ProtectedContentProcessor",
    "ProviderTranslationResult",
    "Segment",
    "SyncTranslationClient",
    "TextFormat",
    "TranslationClient",
    "TranslationOptions",
    "TranslationProcessorPipeline",
    "TranslationProvider",
    "TranslationProviderMetadata",
    "TranslationRequest",
    "TranslationResult",
    "TranslationResultCodec",
    "TranslationSegmentProcessor",
    "TranslationStructureProcessor",
    "UnicodeNormalizationProcessor",
    "create_translation_cache",
]
