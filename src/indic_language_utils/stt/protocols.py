"""Provider contract for batch audio transcription."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..languages import LanguageTag
from ..providers import Provider
from .models import ProviderSTTResult


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
