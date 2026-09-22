"""Immutable translation-specific request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ..languages import LanguageTag
from ..models import CacheMetadata, OperationContext, WarningInfo


class TextFormat(StrEnum):
    PLAIN = "plain"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class TranslationOptions:
    text_format: TextFormat = TextFormat.PLAIN
    max_segment_characters: int = 1_000
    max_batch_items: int = 16
    allow_reordered_placeholders: bool = True
    best_effort: bool = False

    def __post_init__(self) -> None:
        if self.max_segment_characters < 1 or self.max_batch_items < 1:
            raise ValueError("Translation limits must be positive")


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    text: str
    source: LanguageTag
    target: LanguageTag
    options: TranslationOptions = field(default_factory=TranslationOptions)
    context: OperationContext = field(default_factory=OperationContext)
    message_id: str | None = None

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("Translation text cannot be empty")


@dataclass(frozen=True, slots=True)
class TranslationProviderMetadata:
    provider: str
    service_id: str | None = None
    model_id: str | None = None
    provider_request_id: str | None = None
    unofficial: bool = False


@dataclass(frozen=True, slots=True)
class ProviderTranslationResult:
    translations: tuple[str, ...]
    service_id: str | None = None
    model_id: str | None = None
    request_id: str | None = None
    warnings: tuple[WarningInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class TranslationResult:
    text: str
    source: LanguageTag
    target: LanguageTag
    provider: TranslationProviderMetadata
    request_id: str
    elapsed_seconds: float
    cache: CacheMetadata
    fallback_count: int = 0
    warnings: tuple[WarningInfo, ...] = ()
