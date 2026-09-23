"""Audio transcription requests and results."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import OperationContext


@dataclass(frozen=True, slots=True)
class STTRequest:
    audio: bytes
    language: LanguageTag | None
    audio_format: str = "wav"
    sampling_rate: int = 16000
    context: OperationContext = field(default_factory=OperationContext)

    def __init__(
        self,
        audio: bytes,
        language: LanguageTag | str | None = None,
        audio_format: str = "wav",
        sampling_rate: int = 16000,
        context: OperationContext | None = None,
    ) -> None:
        if not isinstance(audio, bytes) or not audio:
            raise ValueError("Audio must be non-empty bytes")
        if not audio_format or not audio_format.isascii() or not audio_format.isalnum():
            raise ValueError("Audio format must be a simple format name such as wav or flac")
        if sampling_rate <= 0:
            raise ValueError("Sampling rate must be positive")
        object.__setattr__(self, "audio", audio)
        object.__setattr__(
            self, "language", DEFAULT_LANGUAGE_REGISTRY.normalize(language) if language else None
        )
        object.__setattr__(self, "audio_format", audio_format)
        object.__setattr__(self, "sampling_rate", sampling_rate)
        object.__setattr__(self, "context", context or OperationContext())


@dataclass(frozen=True, slots=True)
class ProviderSTTResult:
    text: str
    model_id: str | None = None
    request_id: str | None = None
    detected_language: LanguageTag | None = None


@dataclass(frozen=True, slots=True)
class STTResult:
    text: str
    language: LanguageTag | None
    provider: str
    model_id: str | None
    request_id: str
    provider_request_id: str | None = None
    fallback_count: int = 0
