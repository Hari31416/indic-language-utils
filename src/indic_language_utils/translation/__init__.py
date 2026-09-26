"""Public translation API."""

from .bhashini_translate import BhashiniTranslationProvider
from .cache import (
    SegmentTranslation,
    SegmentTranslationCodec,
    TranslationResultCodec,
    create_translation_cache,
    create_translation_segment_cache,
)
from .catalog import CatalogEntry, CatalogStatus, LocalizationCatalog
from .client import TranslationClient
from .google_translate import (
    GoogletransConfig,
    GoogleTranslateConfig,
    GoogleTranslateProvider,
    GoogletransTranslationProvider,
)
from .helpers import (
    get_sync_translation_client,
    get_translation_client,
    translate,
    translate_batch,
    translate_batch_sync,
    translate_sync,
)
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
from .sarvam_translate import SarvamTranslationProvider
from .sync import SyncTranslationClient

__all__ = [
    "DEFAULT_TRANSLATION_PROCESSORS",
    "BhashiniTranslationProvider",
    "CatalogEntry",
    "CatalogStatus",
    "DefaultTranslationStructureProcessor",
    "GoogleTranslateConfig",
    "GoogleTranslateProvider",
    "GoogletransConfig",
    "GoogletransTranslationProvider",
    "LocalizationCatalog",
    "PreparedText",
    "ProtectedContentProcessor",
    "ProviderTranslationResult",
    "SarvamTranslationProvider",
    "Segment",
    "SegmentTranslation",
    "SegmentTranslationCodec",
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
    "create_translation_segment_cache",
    "get_sync_translation_client",
    "get_translation_client",
    "translate",
    "translate_batch",
    "translate_batch_sync",
    "translate_sync",
]
