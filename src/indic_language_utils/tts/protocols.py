"""Provider contract for text to speech."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol, runtime_checkable

from ..languages import LanguageTag
from ..providers import Provider
from .models import ProviderTTSResult, TTSOptions
from .streaming import TTSStream


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


@runtime_checkable
class StreamingTTSProvider(Provider, Protocol):
    def open_stream(
        self,
        *,
        language: LanguageTag,
        options: TTSOptions,
        request_id: str,
        model_id: str | None = None,
    ) -> AbstractAsyncContextManager[TTSStream]: ...
