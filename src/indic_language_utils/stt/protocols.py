"""Provider contract for batch audio transcription."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol, runtime_checkable

from ..languages import LanguageTag
from ..providers import Provider
from .models import ProviderSTTResult
from .streaming import STTStream


@runtime_checkable
class STTProvider(Provider, Protocol):
    async def transcribe_batch(
        self,
        audio: tuple[bytes, ...],
        *,
        language: LanguageTag | None,
        audio_format: str,
        sampling_rate: int,
        request_id: str,
    ) -> tuple[ProviderSTTResult, ...]: ...


@runtime_checkable
class StreamingSTTProvider(Provider, Protocol):
    def open_stream(
        self,
        *,
        language: LanguageTag | None,
        sampling_rate: int,
        request_id: str,
        model_id: str | None = None,
    ) -> AbstractAsyncContextManager[STTStream]: ...
