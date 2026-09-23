"""The capability protocol implemented by transliteration adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..languages import LanguageTag
from ..providers import Provider
from .models import ProviderTransliterationResult, TransliterationOptions


@runtime_checkable
class TransliterationProvider(Provider, Protocol):
    async def transliterate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TransliterationOptions,
        request_id: str,
    ) -> ProviderTransliterationResult: ...
