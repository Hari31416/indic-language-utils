"""Immutable transliteration-specific request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import CacheMetadata, OperationContext, WarningInfo


@dataclass(frozen=True, slots=True)
class TransliterationOptions:
    max_segment_characters: int = 1_000
    max_batch_items: int = 16
    best_effort: bool = False

    def __post_init__(self) -> None:
        if self.max_segment_characters < 1 or self.max_batch_items < 1:
            raise ValueError("Transliteration limits must be positive")


@dataclass(frozen=True, slots=True)
class TransliterationRequest:
    text: str
    source: LanguageTag
    target: LanguageTag
    options: TransliterationOptions = field(default_factory=TransliterationOptions)
    context: OperationContext = field(default_factory=OperationContext)

    def __init__(
        self,
        text: str,
        source: LanguageTag | str,
        target: LanguageTag | str,
        options: TransliterationOptions | None = None,
        context: OperationContext | None = None,
    ) -> None:
        if not text:
            raise ValueError("Transliteration text cannot be empty")

        def _resolve_tag(val: LanguageTag | str) -> LanguageTag:
            if isinstance(val, LanguageTag):
                return val
            if val in DEFAULT_LANGUAGE_REGISTRY:
                return DEFAULT_LANGUAGE_REGISTRY.normalize(val)
            try:
                return LanguageTag.parse(val)
            except Exception:
                return LanguageTag(val.strip().lower())

        norm_source = _resolve_tag(source)
        norm_target = _resolve_tag(target)

        object.__setattr__(self, "text", text)
        object.__setattr__(self, "source", norm_source)
        object.__setattr__(self, "target", norm_target)
        object.__setattr__(
            self, "options", options if options is not None else TransliterationOptions()
        )
        object.__setattr__(self, "context", context if context is not None else OperationContext())


@dataclass(frozen=True, slots=True)
class TransliterationProviderMetadata:
    provider: str
    service_id: str | None = None
    model_id: str | None = None
    provider_request_id: str | None = None
    unofficial: bool = False


@dataclass(frozen=True, slots=True)
class ProviderTransliterationResult:
    transliterations: tuple[str, ...]
    service_id: str | None = None
    model_id: str | None = None
    request_id: str | None = None
    warnings: tuple[WarningInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class TransliterationResult:
    text: str
    source: LanguageTag
    target: LanguageTag
    provider: TransliterationProviderMetadata
    request_id: str
    elapsed_seconds: float
    cache: CacheMetadata
    fallback_count: int = 0
    warnings: tuple[WarningInfo, ...] = ()
    source_text: str = ""
