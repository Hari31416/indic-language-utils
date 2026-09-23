"""Text to speech requests and results."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import OperationContext

_RESERVED_PARAMETERS = {"serviceId", "language"}


@dataclass(frozen=True, slots=True)
class TTSOptions:
    """Model-specific Bhashini task config, such as gender, voice, or tone."""

    parameters: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(isinstance(key, str) and key for key in self.parameters):
            raise ValueError("TTS parameter names must be non-empty strings")
        if _RESERVED_PARAMETERS.intersection(self.parameters):
            raise ValueError("TTS parameters cannot override serviceId or language")
        try:
            encoded = json.dumps(dict(self.parameters), allow_nan=False)
            copied = json.loads(encoded)
        except (TypeError, ValueError) as exc:
            raise ValueError("TTS parameters must contain JSON values") from exc
        if not isinstance(copied, dict):
            raise ValueError("TTS parameters must be a JSON object")
        object.__setattr__(self, "parameters", MappingProxyType(copied))


@dataclass(frozen=True, slots=True)
class TTSRequest:
    text: str
    language: LanguageTag | None = None
    options: TTSOptions = field(default_factory=TTSOptions)
    context: OperationContext = field(default_factory=OperationContext)

    def __init__(
        self,
        text: str,
        language: LanguageTag | str | None = None,
        options: TTSOptions | None = None,
        context: OperationContext | None = None,
    ) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("TTS text cannot be empty")
        object.__setattr__(self, "text", text)
        object.__setattr__(
            self, "language", DEFAULT_LANGUAGE_REGISTRY.normalize(language) if language else None
        )
        object.__setattr__(self, "options", options or TTSOptions())
        object.__setattr__(self, "context", context or OperationContext())


@dataclass(frozen=True, slots=True)
class ProviderTTSResult:
    audio: bytes
    audio_format: str | None = None
    model_id: str | None = None
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class TTSResult:
    audio: bytes
    audio_format: str | None
    language: LanguageTag | None
    provider: str
    model_id: str | None
    request_id: str
    provider_request_id: str | None = None
    fallback_count: int = 0
