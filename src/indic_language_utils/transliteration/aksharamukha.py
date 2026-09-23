"""Aksharamukha transliteration provider adapter.

Provides lightweight, pure-Python script-to-script and Roman-to-Indic
transliteration across all 22 Eighth Schedule Indian languages.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..errors import MissingOptionalDependencyError, UnsupportedLanguagePairError
from ..languages import LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from .models import ProviderTransliterationResult, TransliterationOptions
from .protocols import TransliterationProvider

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

try:
    from aksharamukha import transliterate as aksharamukha_engine

    HAVE_AKSHARAMUKHA = True
except ImportError:
    aksharamukha_engine = None
    HAVE_AKSHARAMUKHA = False

# Mapping from ISO 15924 script codes to Aksharamukha script names
SCRIPT_MAP: Mapping[str, str] = {
    "Deva": "Devanagari",
    "Taml": "Tamil",
    "Telu": "Telugu",
    "Knda": "Kannada",
    "Mlym": "Malayalam",
    "Beng": "Bengali",
    "Gujr": "Gujarati",
    "Guru": "Gurmukhi",
    "Orya": "Oriya",
    "Arab": "Urdu",
    "Olck": "Santali",
    "Mtei": "MeeteiMayek",
    "Latn": "ITRANS",
}

# Mapping from BCP-47 language codes to default Aksharamukha script names
LANGUAGE_SCRIPT_MAP: Mapping[str, str] = {
    "hi": "Devanagari",
    "mr": "Devanagari",
    "ne": "Devanagari",
    "sa": "Devanagari",
    "kok": "Devanagari",
    "mai": "Devanagari",
    "doi": "Devanagari",
    "bho": "Devanagari",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "as": "Assamese",
    "gu": "Gujarati",
    "pa": "Gurmukhi",
    "or": "Oriya",
    "ur": "Urdu",
    "ks": "Urdu",
    "sd": "Urdu",
    "sat": "Santali",
    "mni": "MeeteiMayek",
    "en": "ITRANS",
}


def _resolve_script(tag: LanguageTag, roman_scheme: str) -> str:
    """Resolve an Aksharamukha script identifier from a LanguageTag."""
    if tag.script:
        if tag.script.capitalize() in ("Latn", "Latin"):
            return roman_scheme
        mapped = SCRIPT_MAP.get(tag.script)
        if mapped:
            return mapped

    lang = tag.language.lower()
    if lang == "en":
        return roman_scheme

    mapped = LANGUAGE_SCRIPT_MAP.get(lang)
    if mapped:
        return mapped

    # Fallback to capitalize language as possible script name
    return lang.capitalize()


@dataclass(frozen=True, slots=True)
class AksharamukhaConfig:
    """Configuration options for the Aksharamukha transliteration adapter."""

    roman_scheme: str = "ITRANS"
    nativize: bool = True
    pre_options: tuple[str, ...] = field(default_factory=tuple)
    post_options: tuple[str, ...] = field(default_factory=tuple)


class AksharamukhaTransliterationProvider(TransliterationProvider):
    """Offline, pure-Python transliteration provider powered by Aksharamukha."""

    def __init__(
        self,
        config: AksharamukhaConfig | None = None,
        *,
        engine: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config or AksharamukhaConfig()
        if engine is not None:
            self._engine = engine
        elif HAVE_AKSHARAMUKHA:
            self._engine = aksharamukha_engine.process
        else:
            raise MissingOptionalDependencyError(
                "Aksharamukha is not installed. Install it with: "
                "uv sync --extra local-transliteration",
                provider="aksharamukha",
            )

        self.identity = ProviderIdentity(
            provider="aksharamukha",
            display_name="Aksharamukha",
            unofficial=False,
        )
        self.capabilities: tuple[CapabilityDeclaration, ...] = (
            CapabilityDeclaration(CapabilityId.TRANSLITERATION),
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
        """Transliterate a batch of texts synchronously within an async thread pool."""
        src_script = _resolve_script(source, self.config.roman_scheme)
        tgt_script = _resolve_script(target, self.config.roman_scheme)

        if src_script == tgt_script:
            return ProviderTransliterationResult(
                texts,
                model_id="aksharamukha",
                request_id=request_id,
            )

        def _run_batch() -> tuple[str, ...]:
            results: list[str] = []
            for text in texts:
                try:
                    converted = self._engine(
                        src_script,
                        tgt_script,
                        text,
                        nativize=self.config.nativize,
                        post_options=list(self.config.post_options),
                        pre_options=list(self.config.pre_options),
                    )
                    results.append(str(converted))
                except Exception as exc:
                    logger.error(
                        "Aksharamukha failed to transliterate %s -> %s: %s",
                        src_script,
                        tgt_script,
                        exc,
                        exc_info=True,
                    )
                    raise UnsupportedLanguagePairError(
                        f"Aksharamukha cannot transliterate from script '{src_script}' "
                        f"to '{tgt_script}': {exc}",
                        provider="aksharamukha",
                    ) from exc
            return tuple(results)

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, _run_batch)

        return ProviderTransliterationResult(
            results,
            model_id="aksharamukha",
            request_id=request_id,
        )
