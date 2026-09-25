"""Provider-neutral live speech recognition events and session contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from ..languages import LanguageTag


@dataclass(frozen=True, slots=True)
class STTStreamEvent:
    kind: Literal["speech_start", "speech_end", "partial", "final"]
    text: str | None
    language: LanguageTag | None
    provider: str
    model_id: str
    request_id: str


class STTStream(Protocol):
    async def send_audio(self, pcm: bytes) -> None: ...

    async def finish(self) -> None: ...

    def events(self) -> AsyncIterator[STTStreamEvent]: ...
