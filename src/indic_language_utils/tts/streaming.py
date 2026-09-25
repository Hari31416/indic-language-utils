"""Provider-neutral live speech synthesis events and session contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from ..languages import LanguageTag


@dataclass(frozen=True, slots=True)
class TTSStreamEvent:
    kind: Literal["audio", "done"]
    audio: bytes | None
    audio_format: str
    language: LanguageTag
    provider: str
    model_id: str
    request_id: str


class TTSStream(Protocol):
    async def send_text(self, text: str) -> None: ...

    async def flush(self) -> None: ...

    def events(self) -> AsyncIterator[TTSStreamEvent]: ...
