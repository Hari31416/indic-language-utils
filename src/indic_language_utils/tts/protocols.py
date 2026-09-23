"""Provider contract for text to speech."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..languages import LanguageTag
from ..providers import Provider
from .models import ProviderTTSResult, TTSOptions


@runtime_checkable
class TTSProvider(Provider, Protocol):
    async def synthesize_batch(
        self,
        texts: tuple[str, ...],
        *,
        language: LanguageTag | None,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]: ...
