"""Immutable text language detection request and result models."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import CacheMetadata, OperationContext, WarningInfo


@dataclass(frozen=True, slots=True)
class LanguageCandidate:
    language: LanguageTag
    confidence: float
    script: str | None = None

    def __init__(
        self,
        language: LanguageTag | str,
        confidence: float,
        script: str | None = None,
    ) -> None:
        if isinstance(language, str):
            if language in DEFAULT_LANGUAGE_REGISTRY:
                norm_language = DEFAULT_LANGUAGE_REGISTRY.normalize(language)
            else:
                try:
                    norm_language = LanguageTag.parse(language)
                except Exception:
                    norm_language = LanguageTag(language.strip().lower())
        else:
            norm_language = language
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "language", norm_language)
        object.__setattr__(self, "confidence", float(confidence))
        object.__setattr__(self, "script", script)


@dataclass(frozen=True, slots=True)
class DetectionOptions:
    threshold: float = 0.0
    max_candidates: int = 5
    best_effort: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be positive")


@dataclass(frozen=True, slots=True)
class DetectionRequest:
    text: str
    options: DetectionOptions = field(default_factory=DetectionOptions)
    context: OperationContext = field(default_factory=OperationContext)

    def __init__(
        self,
        text: str,
        options: DetectionOptions | None = None,
        context: OperationContext | None = None,
    ) -> None:
        if not text:
            raise ValueError("Detection text cannot be empty")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "options", options if options is not None else DetectionOptions())
        object.__setattr__(self, "context", context if context is not None else OperationContext())


@dataclass(frozen=True, slots=True)
class DetectionProviderMetadata:
    provider: str
    model_id: str | None = None
    request_id: str | None = None
    unofficial: bool = False


@dataclass(frozen=True, slots=True)
class ProviderDetectionResult:
    candidates: tuple[LanguageCandidate, ...]
    model_id: str | None = None
    request_id: str | None = None
    warnings: tuple[WarningInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class DetectionResult:
    language: LanguageTag | None
    candidates: tuple[LanguageCandidate, ...]
    script: str | None
    provider: DetectionProviderMetadata
    request_id: str
    elapsed_seconds: float
    cache: CacheMetadata
    fallback_count: int = 0
    warnings: tuple[WarningInfo, ...] = ()
    source_text: str = ""
