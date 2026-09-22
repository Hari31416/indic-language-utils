"""FastText text language detection adapter."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from .models import DetectionOptions, LanguageCandidate, ProviderDetectionResult

try:
    import ftlangdetect

    HAVE_FASTTEXT = True
except ImportError:  # pragma: no cover
    HAVE_FASTTEXT = False
    ftlangdetect = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_SCRIPT_RANGES: tuple[tuple[int, int, str], ...] = (
    (0x0900, 0x097F, "Deva"),
    (0xA8E0, 0xA8FF, "Deva"),
    (0x0980, 0x09FF, "Beng"),
    (0x0A00, 0x0A7F, "Guru"),
    (0x0A80, 0x0AFF, "Gujr"),
    (0x0B00, 0x0B7F, "Orya"),
    (0x0B80, 0x0BFF, "Taml"),
    (0x0C00, 0x0C7F, "Telu"),
    (0x0C80, 0x0CFF, "Knda"),
    (0x0D00, 0x0D7F, "Mlym"),
    (0x1C50, 0x1C7F, "Olck"),
    (0xABC0, 0xABFF, "Mtei"),
    (0xAAE0, 0xAAFF, "Mtei"),
    (0x0600, 0x06FF, "Arab"),
    (0x0750, 0x077F, "Arab"),
    (0x08A0, 0x08FF, "Arab"),
    (0x0041, 0x005A, "Latn"),
    (0x0061, 0x007A, "Latn"),
)


def detect_script(text: str) -> str | None:
    counts: dict[str, int] = {}
    for char in text:
        cp = ord(char)
        for start, end, script in _SCRIPT_RANGES:
            if start <= cp <= end:
                counts[script] = counts.get(script, 0) + 1
                break
    if not counts:
        return None
    return max(counts, key=counts.__getitem__)


@runtime_checkable
class FastTextDetectorProtocol(Protocol):
    def __call__(
        self,
        text: str,
        low_memory: bool = False,
        k: int = 1,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class FastTextDetectionConfig:
    low_memory: bool = False
    max_concurrency: int = 8

    def __post_init__(self) -> None:
        if self.max_concurrency < 1:
            raise ConfigurationError("FastText max_concurrency must be positive")


class FastTextDetectionProvider:
    identity = ProviderIdentity("fasttext", "FastText Language Detector")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: FastTextDetectionConfig | None = None,
        *,
        detector: FastTextDetectorProtocol | Callable[..., Any] | None = None,
    ) -> None:
        if not HAVE_FASTTEXT and detector is None:
            raise MissingOptionalDependencyError(
                "The 'fasttext-langdetect' package is required for FastText language detection. "
                "Install it with: pip install 'indic-language-utils[local-tld]'"
            )
        self.config = config or FastTextDetectionConfig()
        self._detector = detector or (ftlangdetect.detect if ftlangdetect is not None else None)
        self._limiter = ConcurrencyLimiter(self.config.max_concurrency)
        supported_tags = frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TEXT_LANGUAGE_DETECTION, languages=supported_tags),
        )

    async def detect_batch(
        self,
        texts: tuple[str, ...],
        *,
        options: DetectionOptions,
        request_id: str,
    ) -> tuple[ProviderDetectionResult, ...]:
        if not texts or any(not text or not text.strip() for text in texts):
            raise InvalidInputError(
                "FastText language detection inputs cannot be empty",
                provider=self.identity.provider,
                capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                request_id=request_id,
            )

        if self._detector is None:
            raise MissingOptionalDependencyError(
                "The 'fasttext-langdetect' package is required for FastText language detection. "
                "Install it with: pip install 'indic-language-utils[local-tld]'"
            )

        results: list[ProviderDetectionResult] = []
        for text in texts:
            result = await self._detect_single(text, options, request_id)
            results.append(result)
        return tuple(results)

    async def _detect_single(
        self,
        text: str,
        options: DetectionOptions,
        request_id: str,
    ) -> ProviderDetectionResult:
        cleaned = text.replace("\n", " ").replace("\r", " ").strip()
        script = detect_script(cleaned)
        k = max(1, options.max_candidates)

        async with self._limiter.slot(self.identity.provider, CapabilityId.TEXT_LANGUAGE_DETECTION):
            assert self._detector is not None
            try:
                raw = await asyncio.to_thread(
                    self._detector,
                    cleaned,
                    low_memory=self.config.low_memory,
                    k=k,
                )
            except Exception as exc:
                raise MalformedProviderResponseError(
                    f"FastText detection failed: {exc}",
                    provider=self.identity.provider,
                    capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                    request_id=request_id,
                ) from exc

        candidates: list[LanguageCandidate] = []
        raw_items = [raw] if isinstance(raw, Mapping) else raw
        if not isinstance(raw_items, (list, tuple)):
            raise MalformedProviderResponseError(
                f"FastText returned unexpected output type: {type(raw)}",
                provider=self.identity.provider,
                capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                request_id=request_id,
            )

        for item in raw_items:
            if not isinstance(item, Mapping) or "lang" not in item or "score" not in item:
                raise MalformedProviderResponseError(
                    f"FastText candidate malformed: {item}",
                    provider=self.identity.provider,
                    capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                    request_id=request_id,
                )
            lang_code = str(item["lang"]).lower()
            confidence = max(0.0, min(1.0, float(item["score"])))
            if lang_code in DEFAULT_LANGUAGE_REGISTRY:
                tag = DEFAULT_LANGUAGE_REGISTRY.normalize(lang_code)
            else:
                try:
                    tag = LanguageTag.parse(lang_code)
                except Exception:
                    tag = LanguageTag(lang_code)
            candidates.append(LanguageCandidate(tag, confidence, script=script))

        return ProviderDetectionResult(
            candidates=tuple(candidates),
            model_id="lid.176.ftz",
            request_id=request_id,
        )
