"""The capability protocol implemented by translation adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..languages import LanguageTag
from ..providers import Provider
from .models import ProviderTranslationResult, TranslationOptions


@runtime_checkable
class TranslationProvider(Provider, Protocol):
    async def translate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TranslationOptions,
        request_id: str,
    ) -> ProviderTranslationResult: ...
