"""Google Free (unofficial SpeechRecognition) speech-to-text adapter."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import wave
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..concurrency import ConcurrencyLimiter
from ..config import Settings
from ..errors import (
    ConfigurationError,
    InvalidInputError,
    MissingOptionalDependencyError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..retry import RetryPolicy, retry
from .models import ProviderSTTResult
from .protocols import STTProvider

try:
    import speech_recognition as sr

    HAVE_SPEECH_RECOGNITION = True
except ImportError:
    sr = None
    HAVE_SPEECH_RECOGNITION = False

try:
    import av

    HAVE_AV = True
except ImportError:
    av = None  # type: ignore[assignment]
    HAVE_AV = False

logger = logging.getLogger(__name__)

_GOOGLE_SPEECH_KEY = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"

# Default BCP-47 language codes for Google Speech
_DEFAULT_LANGUAGE_CODES: dict[str, str] = {
    "as": "as-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "ne": "ne-NP",
    "or": "or-IN",
    "pa": "pa-guru-IN",
    "sa": "sa-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "ur": "ur-IN",
    "en": "en-IN",
}


def _get_supported_tags() -> frozenset[LanguageTag]:
    tags: set[LanguageTag] = set()
    for definition in DEFAULT_LANGUAGE_REGISTRY.definitions():
        tags.add(definition.tag)
    return frozenset(tags)


@dataclass(frozen=True, slots=True)
class AudioDataFallback:
    """Fallback audio container when SpeechRecognition is not installed."""

    frame_data: bytes
    sample_rate: int
    sample_width: int


def google_speech_language_code(tag: LanguageTag | None) -> str:
    if tag is None:
        return "en-IN"
    normalized = DEFAULT_LANGUAGE_REGISTRY.normalize(tag)
    code = normalized.language.lower()
    if code in _DEFAULT_LANGUAGE_CODES:
        if normalized.region and normalized.region != "IN":
            return f"{code}-{normalized.region}"
        return _DEFAULT_LANGUAGE_CODES[code]
    if normalized.region:
        return f"{code}-{normalized.region}"
    return f"{code}-IN"


@dataclass(frozen=True, slots=True)
class GoogleFreeSTTConfig:
    """Configuration options for Google Free STT adapter."""

    timeout_seconds: float = 20.0
    max_concurrency: int = 4
    default_language: str = "en-IN"
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Google Free STT timeout and concurrency must be positive")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> GoogleFreeSTTConfig:
        values = os.environ if env is None else env
        try:
            timeout = float(values.get("GOOGLE_FREE_STT_TIMEOUT_SECONDS", "20"))
            concurrency = int(values.get("GOOGLE_FREE_STT_MAX_CONCURRENCY", "4"))
            default_language = values.get("GOOGLE_FREE_STT_DEFAULT_LANGUAGE", "en-IN")
        except ValueError as exc:
            raise ConfigurationError(
                "Google Free STT environment configuration is invalid"
            ) from exc
        return cls(
            timeout_seconds=timeout,
            max_concurrency=concurrency,
            default_language=default_language,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        provider_name: str = "google_free",
    ) -> GoogleFreeSTTConfig:
        values = os.environ if env is None else env
        provider = settings.providers.get(provider_name)
        try:
            timeout = float(
                values.get(
                    "GOOGLE_FREE_STT_TIMEOUT_SECONDS",
                    str(provider.timeout_seconds if provider else 20.0),
                )
            )
            concurrency = int(
                values.get(
                    "GOOGLE_FREE_STT_MAX_CONCURRENCY",
                    str(provider.max_concurrency if provider else 4),
                )
            )
            default_language = values.get("GOOGLE_FREE_STT_DEFAULT_LANGUAGE", "en-IN")
        except ValueError as exc:
            raise ConfigurationError("Google Free STT configuration is invalid") from exc
        retry_policy = RetryPolicy(
            settings.retry.max_attempts,
            settings.retry.base_delay_seconds,
            settings.retry.max_delay_seconds,
        )
        return cls(
            timeout_seconds=timeout,
            max_concurrency=concurrency,
            default_language=default_language,
            retry_policy=retry_policy,
        )


def _decode_to_pcm(clip: bytes, audio_format: str, sampling_rate: int) -> tuple[bytes, int]:
    if HAVE_AV and av is not None:
        try:
            container: Any = av.open(io.BytesIO(clip))
            resampler = av.AudioResampler(format="s16", layout="mono", rate=sampling_rate or 16000)
            pcm_chunks: list[bytes] = []
            for frame in container.decode(audio=0):
                for rf in resampler.resample(frame):
                    pcm_chunks.append(rf.to_ndarray().tobytes())
            if pcm_chunks:
                return b"".join(pcm_chunks), sampling_rate or 16000
        except Exception:
            pass

    if clip.startswith(b"RIFF"):
        try:
            with wave.open(io.BytesIO(clip), "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                rate = wf.getframerate()
                return frames, rate
        except Exception:
            pass

    return clip, sampling_rate or 16000


class GoogleFreeSTTProvider(STTProvider):
    """Unofficial Google Speech-to-Text provider backed by SpeechRecognition."""

    identity = ProviderIdentity("google_free", "Google Free STT", unofficial=True)
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: GoogleFreeSTTConfig | None = None,
        *,
        recognizer: Any = None,
    ) -> None:
        if not HAVE_SPEECH_RECOGNITION and recognizer is None:
            raise MissingOptionalDependencyError(
                "The 'SpeechRecognition' package is required for Google Free STT. "
                "Install it with: pip install 'indic-language-utils[stt-google-free]'",
                provider="google_free",
            )
        self.config = config or GoogleFreeSTTConfig()
        self._recognizer = recognizer
        self._limiter = ConcurrencyLimiter(self.config.max_concurrency)
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.SPEECH_TO_TEXT, languages=_get_supported_tags()),
        )

    def _get_recognizer(self) -> Any:
        if self._recognizer is not None:
            return self._recognizer
        if not HAVE_SPEECH_RECOGNITION:
            raise MissingOptionalDependencyError(
                "The 'SpeechRecognition' package is required for Google Free STT. "
                "Install it with: pip install 'indic-language-utils[stt-google-free]'",
                provider="google_free",
            )
        return sr.Recognizer()

    def _bytes_to_audio_data(self, clip: bytes, audio_format: str, sampling_rate: int) -> Any:
        if not HAVE_SPEECH_RECOGNITION and self._recognizer is None:
            raise MissingOptionalDependencyError(
                "The 'SpeechRecognition' package is required for Google Free STT.",
                provider="google_free",
            )
        frames = clip
        rate = sampling_rate
        width = 2
        if clip.startswith(b"RIFF"):
            try:
                with wave.open(io.BytesIO(clip), "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    rate = wf.getframerate()
                    width = wf.getsampwidth()
            except Exception:
                pass
        if sr is not None and hasattr(sr, "AudioData"):
            return sr.AudioData(frames, rate, width)
        return AudioDataFallback(frames, rate, width)

    async def transcribe_batch(
        self,
        audio: tuple[bytes, ...],
        *,
        language: LanguageTag | None,
        audio_format: str,
        sampling_rate: int,
        request_id: str,
    ) -> tuple[ProviderSTTResult, ...]:
        if not audio or any(not isinstance(item, bytes) or not item for item in audio):
            raise InvalidInputError(
                "Google Free STT audio cannot be empty",
                provider="google_free",
                capability=CapabilityId.SPEECH_TO_TEXT.value,
                request_id=request_id,
            )

        lang_code = google_speech_language_code(language)
        recognizer = self._recognizer

        def _transcribe_one(clip: bytes) -> str:
            if recognizer is not None:
                audio_data = self._bytes_to_audio_data(clip, audio_format, sampling_rate)
                try:
                    res = recognizer.recognize_google(audio_data, language=lang_code)
                    return str(res) if res is not None else ""
                except Exception as exc:
                    if sr is not None and isinstance(exc, sr.UnknownValueError):
                        return ""
                    err_msg = str(exc)
                    if "429" in err_msg or "Too Many Requests" in err_msg:
                        raise RateLimitError(
                            f"Google Free STT rate limit exceeded: {err_msg}",
                            provider="google_free",
                            capability=CapabilityId.SPEECH_TO_TEXT.value,
                            request_id=request_id,
                        ) from exc
                    if sr is not None and isinstance(exc, sr.RequestError):
                        raise TransientProviderError(
                            f"Google Free STT request failed: {err_msg}",
                            provider="google_free",
                            capability=CapabilityId.SPEECH_TO_TEXT.value,
                            request_id=request_id,
                        ) from exc
                    raise TransientProviderError(
                        f"Google Free STT error: {err_msg}",
                        provider="google_free",
                        capability=CapabilityId.SPEECH_TO_TEXT.value,
                        request_id=request_id,
                    ) from exc

            # Direct HTTP call to Google Web Speech API (bypasses flac-mac entirely)
            pcm_bytes, rate = _decode_to_pcm(clip, audio_format, sampling_rate)
            url = (
                f"https://www.google.com/speech-api/v2/recognize"
                f"?client=chromium&lang={lang_code}&key={_GOOGLE_SPEECH_KEY}&pFilter=0"
            )
            headers = {"Content-Type": f"audio/l16; rate={rate}"}
            try:
                response = httpx.post(
                    url,
                    headers=headers,
                    content=pcm_bytes,
                    timeout=self.config.timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(
                    "Google Free STT timed out",
                    provider="google_free",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                    request_id=request_id,
                ) from exc
            except httpx.TransportError as exc:
                raise TransientProviderError(
                    f"Google Free STT transport failed: {exc}",
                    provider="google_free",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                    request_id=request_id,
                ) from exc

            if response.status_code == 429:
                raise RateLimitError(
                    "Google Free STT rate limit exceeded (HTTP 429)",
                    provider="google_free",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                    request_id=request_id,
                )
            if response.status_code != 200:
                raise TransientProviderError(
                    f"Google Free STT returned HTTP {response.status_code}",
                    provider="google_free",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                    request_id=request_id,
                )

            for line in response.text.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    for res in data.get("result", []):
                        alts = res.get("alternative", [])
                        if alts and isinstance(alts[0].get("transcript"), str):
                            return str(alts[0]["transcript"])
                except Exception:
                    continue
            return ""

        async def _run_clip(clip: bytes) -> str:
            async with self._limiter.slot("google_free", CapabilityId.SPEECH_TO_TEXT):
                return await asyncio.to_thread(_transcribe_one, clip)

        async def _transcribe_clip(clip_data: bytes) -> str:
            async def _execute() -> str:
                return await _run_clip(clip_data)

            return await retry(_execute, self.config.retry_policy)

        results: list[ProviderSTTResult] = []
        for clip in audio:
            text = await _transcribe_clip(clip)
            results.append(
                ProviderSTTResult(
                    text=text,
                    model_id="google_free",
                    request_id=request_id,
                    detected_language=language,
                )
            )

        return tuple(results)


# Aliases
GoogleSpeechSTTProvider = GoogleFreeSTTProvider
GoogleSpeechSTTConfig = GoogleFreeSTTConfig
