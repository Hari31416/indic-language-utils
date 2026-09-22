"""Immutable translation-specific request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
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

    def __init__(
        self,
        text: str,
        source: LanguageTag | str,
        target: LanguageTag | str,
        options: TranslationOptions | None = None,
        context: OperationContext | None = None,
        message_id: str | None = None,
    ) -> None:
        if not text:
            raise ValueError("Translation text cannot be empty")
        norm_source = (
            DEFAULT_LANGUAGE_REGISTRY.normalize(source) if isinstance(source, str) else source
        )
        norm_target = (
            DEFAULT_LANGUAGE_REGISTRY.normalize(target) if isinstance(target, str) else target
        )
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "source", norm_source)
        object.__setattr__(self, "target", norm_target)
        object.__setattr__(
            self, "options", options if options is not None else TranslationOptions()
        )
        object.__setattr__(self, "context", context if context is not None else OperationContext())
        object.__setattr__(self, "message_id", message_id)


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
