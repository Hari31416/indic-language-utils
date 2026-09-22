"""The capability protocol implemented by text language detection adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..providers import Provider
from .models import DetectionOptions, ProviderDetectionResult


@runtime_checkable
class DetectionProvider(Provider, Protocol):
    async def detect_batch(
        self,
        texts: tuple[str, ...],
        *,
        options: DetectionOptions,
        request_id: str,
    ) -> tuple[ProviderDetectionResult, ...]: ...
