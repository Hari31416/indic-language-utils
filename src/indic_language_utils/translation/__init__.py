"""Public translation API."""

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
from .protocols import TranslationProvider
from .sync import SyncTranslationClient

__all__ = [
    "CatalogEntry",
    "CatalogStatus",
    "LocalizationCatalog",
    "ProviderTranslationResult",
    "SyncTranslationClient",
    "TextFormat",
    "TranslationClient",
    "TranslationOptions",
    "TranslationProvider",
    "TranslationProviderMetadata",
    "TranslationRequest",
    "TranslationResult",
]
