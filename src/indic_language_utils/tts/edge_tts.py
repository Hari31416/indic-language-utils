"""Microsoft Edge TTS (free, keyless) text-to-speech adapter."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..concurrency import ConcurrencyLimiter
from ..config import Settings
from ..errors import (
    ConfigurationError,
    InvalidInputError,
    LanguageUtilsError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
    ProviderTimeoutError,
    TransientProviderError,
    UnsupportedLanguageError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..retry import RetryPolicy, retry
from .models import ProviderTTSResult, TTSOptions
from .protocols import TTSProvider

try:
    import edge_tts
    import edge_tts.exceptions

    HAVE_EDGE_TTS = True
except ImportError:  # pragma: no cover
    edge_tts = None  # type: ignore[assignment]
    HAVE_EDGE_TTS = False

logger = logging.getLogger(__name__)

# Built-in female and male neural voices for Indian languages supported by Edge TTS
_DEFAULT_VOICES: dict[str, dict[str, str]] = {
    "bn": {"female": "bn-IN-TanishaaNeural", "male": "bn-IN-BashkarNeural"},
    "en": {"female": "en-IN-NeerjaNeural", "male": "en-IN-PrabhatNeural"},
    "gu": {"female": "gu-IN-DhwaniNeural", "male": "gu-IN-NiranjanNeural"},
    "hi": {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"},
    "kn": {"female": "kn-IN-SapnaNeural", "male": "kn-IN-GaganNeural"},
    "ml": {"female": "ml-IN-SobhanaNeural", "male": "ml-IN-MidhunNeural"},
    "mr": {"female": "mr-IN-AarohiNeural", "male": "mr-IN-ManoharNeural"},
    "ne": {"female": "ne-NP-HemkalaNeural", "male": "ne-NP-SagarNeural"},
    "ta": {"female": "ta-IN-PallaviNeural", "male": "ta-IN-ValluvarNeural"},
    "te": {"female": "te-IN-ShrutiNeural", "male": "te-IN-MohanNeural"},
    "ur": {"female": "ur-IN-GulNeural", "male": "ur-IN-SalmanNeural"},
}


def _get_supported_tags() -> frozenset[LanguageTag]:
    tags: set[LanguageTag] = set()
    for definition in DEFAULT_LANGUAGE_REGISTRY.definitions():
        if definition.tag.language in _DEFAULT_VOICES:
            tags.add(definition.tag)
    return frozenset(tags)


@dataclass(frozen=True, slots=True)
class EdgeTTSConfig:
    """Configuration options for the Microsoft Edge TTS provider."""

    default_voice: str = "hi-IN-SwaraNeural"
    voices: Mapping[str, str] = field(default_factory=dict)
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"
    timeout_seconds: float = 30.0
    max_concurrency: int = 4
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Edge TTS timeout and concurrency must be positive")
        if not self.default_voice or not self.default_voice.strip():
            raise ConfigurationError("Edge TTS default_voice cannot be empty")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> EdgeTTSConfig:
        values = os.environ if env is None else env
        default_voice = (
            values.get("EDGE_TTS_VOICE")
            or values.get("EDGE_TTS_DEFAULT_VOICE")
            or "hi-IN-SwaraNeural"
        )
        rate = values.get("EDGE_TTS_RATE", "+0%")
        volume = values.get("EDGE_TTS_VOLUME", "+0%")
        pitch = values.get("EDGE_TTS_PITCH", "+0Hz")
        try:
            timeout_seconds = float(values.get("EDGE_TTS_TIMEOUT_SECONDS", "30.0"))
            max_concurrency = int(values.get("EDGE_TTS_MAX_CONCURRENCY", "4"))
        except ValueError as exc:
            raise ConfigurationError("Invalid numeric setting in Edge TTS environment") from exc
        return cls(
            default_voice=default_voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
            timeout_seconds=timeout_seconds,
            max_concurrency=max_concurrency,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        provider_name: str = "edge_tts",
    ) -> EdgeTTSConfig:
        values = os.environ if env is None else env
        provider = settings.providers.get(provider_name) or settings.providers.get("edge")
        try:
            default_voice = (
                values.get("EDGE_TTS_VOICE")
                or values.get("EDGE_TTS_DEFAULT_VOICE")
                or (provider.tts_model_id if provider and provider.tts_model_id else None)
                or (provider.model if provider and provider.model else None)
                or "hi-IN-SwaraNeural"
            )
            rate = values.get("EDGE_TTS_RATE", "+0%")
            volume = values.get("EDGE_TTS_VOLUME", "+0%")
            pitch = values.get("EDGE_TTS_PITCH", "+0Hz")
            timeout_seconds = float(
                values.get(
                    "EDGE_TTS_TIMEOUT_SECONDS",
                    str(provider.timeout_seconds if provider else 30.0),
                )
            )
            max_concurrency = int(
                values.get(
                    "EDGE_TTS_MAX_CONCURRENCY",
                    str(provider.max_concurrency if provider else 4),
                )
            )
            voices = dict(provider.tts_model_ids) if provider else {}
        except ValueError as exc:
            raise ConfigurationError("Invalid Edge TTS settings values") from exc
        return cls(
            default_voice=default_voice,
            voices=voices,
            rate=rate,
            volume=volume,
            pitch=pitch,
            timeout_seconds=timeout_seconds,
            max_concurrency=max_concurrency,
        )


class EdgeTTSProvider(TTSProvider):
    """Text-to-Speech provider backed by Microsoft Edge TTS."""

    identity = ProviderIdentity("edge_tts", "Microsoft Edge TTS", unofficial=True)
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: EdgeTTSConfig | None = None,
        *,
        communicate_factory: Any = None,
    ) -> None:
        if not HAVE_EDGE_TTS and communicate_factory is None:
            raise MissingOptionalDependencyError(
                "The 'edge-tts' package is required for Edge TTS. "
                "Install it with: pip install 'indic-language-utils[tts-edge]'",
                provider="edge_tts",
            )
        self.config = config or EdgeTTSConfig()
        self._communicate_factory = communicate_factory
        self._limiter = ConcurrencyLimiter(self.config.max_concurrency)
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TEXT_TO_SPEECH, languages=_get_supported_tags()),
        )

    def resolve_voice(
        self,
        language: LanguageTag | None,
        options: TTSOptions,
    ) -> str:
        params = options.parameters
        for key in ("voice", "voiceId", "model"):
            val = params.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        if language is not None:
            tag = DEFAULT_LANGUAGE_REGISTRY.normalize(language)
            lang_code = tag.language.lower()
            str_tag = str(tag)
            if str_tag in self.config.voices:
                return self.config.voices[str_tag]
            if lang_code in self.config.voices:
                return self.config.voices[lang_code]

            if lang_code in _DEFAULT_VOICES:
                gender = str(params.get("gender", "female")).strip().lower()
                voice_pair = _DEFAULT_VOICES[lang_code]
                if gender in voice_pair:
                    return voice_pair[gender]
                return voice_pair.get("female") or next(iter(voice_pair.values()))

            raise UnsupportedLanguageError(
                f"Edge TTS does not support language '{lang_code}'",
                provider="edge_tts",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
                details={"language": lang_code},
            )

        return self.config.default_voice

    async def synthesize_batch(
        self,
        texts: tuple[str, ...],
        *,
        language: LanguageTag | None,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]:
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise InvalidInputError(
                "Edge TTS text cannot be empty", provider="edge_tts", request_id=request_id
            )

        voice = self.resolve_voice(language, options)
        params = options.parameters
        rate = str(params.get("rate", self.config.rate))
        volume = str(params.get("volume", self.config.volume))
        pitch = str(params.get("pitch", self.config.pitch))

        results: list[ProviderTTSResult] = []
        for text in texts:
            audio_bytes = await self._synthesize_single(
                text=text,
                voice=voice,
                rate=rate,
                volume=volume,
                pitch=pitch,
                request_id=request_id,
            )
            results.append(
                ProviderTTSResult(
                    audio=audio_bytes,
                    audio_format="mp3",
                    model_id=voice,
                    request_id=request_id,
                )
            )
        return tuple(results)

    async def _synthesize_single(
        self,
        text: str,
        voice: str,
        rate: str,
        volume: str,
        pitch: str,
        request_id: str,
    ) -> bytes:
        async with self._limiter.slot("edge_tts", CapabilityId.TEXT_TO_SPEECH):
            try:
                return await retry(
                    lambda: self._call_edge_tts(text, voice, rate, volume, pitch),
                    self.config.retry_policy,
                )
            except Exception as exc:
                if isinstance(exc, LanguageUtilsError):
                    raise
                raise TransientProviderError(
                    f"Edge TTS synthesis failed: {exc}",
                    provider="edge_tts",
                    capability=CapabilityId.TEXT_TO_SPEECH.value,
                    request_id=request_id,
                ) from exc

    async def _call_edge_tts(
        self,
        text: str,
        voice: str,
        rate: str,
        volume: str,
        pitch: str,
    ) -> bytes:
        try:
            return await asyncio.wait_for(
                self._stream_audio(text, voice, rate, volume, pitch),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                "Edge TTS request timed out",
                provider="edge_tts",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
            ) from exc

    async def _stream_audio(
        self,
        text: str,
        voice: str,
        rate: str,
        volume: str,
        pitch: str,
    ) -> bytes:
        if self._communicate_factory is not None:
            communicate = self._communicate_factory(
                text=text,
                voice=voice,
                rate=rate,
                volume=volume,
                pitch=pitch,
            )
        else:
            if not HAVE_EDGE_TTS or edge_tts is None:
                raise MissingOptionalDependencyError(
                    "The 'edge-tts' package is required for Edge TTS.",
                    provider="edge_tts",
                )
            communicate = edge_tts.Communicate(
                text,
                voice=voice,
                rate=rate,
                volume=volume,
                pitch=pitch,
            )

        audio_chunks: list[bytes] = []
        try:
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    data = chunk.get("data", b"")
                    if isinstance(data, (bytes, bytearray)):
                        audio_chunks.append(bytes(data))
        except Exception as exc:
            if HAVE_EDGE_TTS and edge_tts is not None and hasattr(edge_tts, "exceptions"):
                if isinstance(exc, edge_tts.exceptions.NoAudioReceived):
                    raise MalformedProviderResponseError(
                        "Edge TTS returned no audio data",
                        provider="edge_tts",
                        capability=CapabilityId.TEXT_TO_SPEECH.value,
                    ) from exc
                if isinstance(
                    exc,
                    (
                        edge_tts.exceptions.WebSocketError,
                        edge_tts.exceptions.UnexpectedResponse,
                        edge_tts.exceptions.UnknownResponse,
                    ),
                ):
                    raise TransientProviderError(
                        f"Edge TTS connection error: {exc}",
                        provider="edge_tts",
                        capability=CapabilityId.TEXT_TO_SPEECH.value,
                    ) from exc
            raise

        audio_bytes = b"".join(audio_chunks)
        if not audio_bytes:
            raise MalformedProviderResponseError(
                "Edge TTS produced empty audio response",
                provider="edge_tts",
                capability=CapabilityId.TEXT_TO_SPEECH.value,
            )
        return audio_bytes
