"""Text to speech requests and results."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageRegistry, LanguageTag
from ..models import CacheMetadata, OperationContext

_RESERVED_PARAMETERS = {"serviceId", "language"}


@dataclass(frozen=True, slots=True)
class TTSOptions:
    """Provider-specific JSON options for voice and audio output."""

    parameters: Mapping[str, object] = field(default_factory=dict)
    provider_parameters: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

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
        if not all(isinstance(name, str) and name for name in self.provider_parameters):
            raise ValueError("TTS provider names must be non-empty strings")
        providers: dict[str, Mapping[str, object]] = {}
        for name, values in self.provider_parameters.items():
            if not isinstance(values, Mapping):
                raise ValueError("TTS provider parameters must be JSON objects")
            providers[name] = TTSOptions(values).parameters
        object.__setattr__(self, "provider_parameters", MappingProxyType(providers))

    def for_provider(self, name: str, *, primary: bool) -> TTSOptions:
        """Use legacy parameters on the first route and named settings on every route."""
        parameters = dict(self.parameters) if primary else {}
        parameters.update(self.provider_parameters.get(name, {}))
        return TTSOptions(parameters)


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
        *,
        language_registry: LanguageRegistry | None = None,
    ) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("TTS text cannot be empty")
        object.__setattr__(self, "text", text)
        object.__setattr__(
            self,
            "language",
            (language_registry or DEFAULT_LANGUAGE_REGISTRY).normalize(language)
            if language
            else None,
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
    cache: CacheMetadata = field(default_factory=lambda: CacheMetadata(False, "none", 1))
