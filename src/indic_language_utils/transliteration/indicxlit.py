"""AI4Bharat IndicXlit local transliteration adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
    UnsupportedLanguagePairError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from .models import ProviderTransliterationResult, TransliterationOptions

try:
    import ai4bharat.transliteration

    HAVE_INDICXLIT = True
except ImportError:  # pragma: no cover
    HAVE_INDICXLIT = False
    ai4bharat = None


@runtime_checkable
class IndicXlitEngineProtocol(Protocol):
    def translit_sentence(self, text: str, lang_code: str) -> str: ...


@dataclass(frozen=True, slots=True)
class IndicXlitConfig:
    beam_width: int = 4
    rescore: bool = True
    max_concurrency: int = 4

    def __post_init__(self) -> None:
        if self.beam_width < 1 or self.max_concurrency < 1:
            raise ConfigurationError("IndicXlit beam_width and max_concurrency must be positive")


class IndicXlitTransliterationProvider:
    identity = ProviderIdentity("indicxlit", "AI4Bharat IndicXlit")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: IndicXlitConfig | None = None,
        *,
        engine: IndicXlitEngineProtocol | Any = None,
    ) -> None:
        if not HAVE_INDICXLIT and engine is None:
            raise MissingOptionalDependencyError(
                "The 'ai4bharat-transliteration' package is required for IndicXlit local "
                "transliteration. Install it with: "
                "pip install 'indic-language-utils[local-transliteration]'"
            )
        self.config = config or IndicXlitConfig()
        self._engine = engine
        self._limiter = ConcurrencyLimiter(self.config.max_concurrency)
        supported_tags = frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TRANSLITERATION, languages=supported_tags),
        )

    def _get_engine(self, src_script_type: str = "roman") -> Any:
        if self._engine is not None:
            return self._engine
        if not HAVE_INDICXLIT:
            raise MissingOptionalDependencyError(
                "The 'ai4bharat-transliteration' package is required for IndicXlit local "
                "transliteration. Install it with: "
                "pip install 'indic-language-utils[local-transliteration]'"
            )
        from ai4bharat.transliteration import XlitEngine

        return XlitEngine(
            src_script_type=src_script_type,
            beam_width=self.config.beam_width,
            rescore=self.config.rescore,
        )

    async def transliterate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TransliterationOptions,
        request_id: str,
    ) -> ProviderTransliterationResult:
        if not texts or any(not text or not text.strip() for text in texts):
            raise InvalidInputError(
                "IndicXlit transliteration inputs cannot be empty",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLITERATION.value,
                request_id=request_id,
            )

        src_lang = source.language.lower()
        tgt_lang = target.language.lower()

        # Determine mode: roman-to-indic or indic-to-roman
        if src_lang == "en" or source.script == "Latn":
            mode = "roman"
            lang_code = tgt_lang
        elif tgt_lang == "en" or target.script == "Latn":
            mode = "indic"
            lang_code = src_lang
        else:
            # Indic to Indic: not directly a single XlitEngine step unless piped
            raise UnsupportedLanguagePairError(
                f"IndicXlit does not directly support direct {src_lang} to {tgt_lang} "
                "script conversion",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLITERATION.value,
                details={"source": str(source), "target": str(target)},
            )

        engine = self._get_engine(src_script_type=mode)

        async with self._limiter.slot(self.identity.provider, CapabilityId.TRANSLITERATION):
            try:
                results = await asyncio.to_thread(
                    self._run_transliteration, engine, texts, lang_code
                )
            except Exception as exc:
                if isinstance(exc, (InvalidInputError, UnsupportedLanguagePairError)):
                    raise
                raise MalformedProviderResponseError(
                    f"IndicXlit transliteration failed: {exc}",
                    provider=self.identity.provider,
                    capability=CapabilityId.TRANSLITERATION.value,
                    request_id=request_id,
                ) from exc

        return ProviderTransliterationResult(
            transliterations=tuple(results),
            model_id="ai4bharat/indicxlit",
            request_id=request_id,
        )

    def _run_transliteration(
        self, engine: Any, texts: tuple[str, ...], lang_code: str
    ) -> list[str]:
        results: list[str] = []
        for text in texts:
            if hasattr(engine, "translit_sentence"):
                out = engine.translit_sentence(text, lang_code=lang_code)
            elif hasattr(engine, "transliterate_sentence"):
                out = engine.transliterate_sentence(text, lang_code=lang_code)
            elif callable(engine):
                out = engine(text, lang_code=lang_code)
            else:
                raise TypeError(f"Unrecognized engine interface: {type(engine)}")
            if isinstance(out, Mapping) and "target" in out:
                out = out["target"]
            results.append(str(out))
        return results
