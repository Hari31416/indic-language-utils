"""Faster-Whisper speech-to-text adapter."""

from __future__ import annotations

import asyncio
import io
import logging
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..concurrency import ConcurrencyLimiter
from ..config import Settings
from ..errors import (
    ConfigurationError,
    InvalidInputError,
    MissingOptionalDependencyError,
    ProviderTimeoutError,
    TransientProviderError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..retry import RetryPolicy, retry
from .models import ProviderSTTResult, STTSegment, STTWord
from .protocols import STTProvider

try:
    from faster_whisper import WhisperModel

    HAVE_FASTER_WHISPER = True
except ImportError:
    WhisperModel = None
    HAVE_FASTER_WHISPER = False

logger = logging.getLogger(__name__)


class _WhisperWaitTimeout(Exception):
    """Stop retries while a timed-out worker finishes in the background."""


def _observe_background_result(task: asyncio.Task[Any]) -> None:
    if not task.cancelled():
        task.exception()


# Known Whisper Indic languages by ISO 639-1 code
_WHISPER_INDIC_CODES: frozenset[str] = frozenset(
    {
        "as",
        "bn",
        "en",
        "gu",
        "hi",
        "kn",
        "ml",
        "mr",
        "ne",
        "pa",
        "sa",
        "sd",
        "ta",
        "te",
        "ur",
    }
)


def _get_whisper_supported_tags() -> frozenset[LanguageTag]:
    tags: set[LanguageTag] = set()
    for definition in DEFAULT_LANGUAGE_REGISTRY.definitions():
        if definition.tag.language in _WHISPER_INDIC_CODES:
            tags.add(definition.tag)
    return frozenset(tags)


def whisper_language_code(tag: LanguageTag | None) -> str | None:
    if tag is None:
        return None
    normalized = DEFAULT_LANGUAGE_REGISTRY.normalize(tag)
    return normalized.language.lower()


@dataclass(frozen=True, slots=True)
class FasterWhisperSTTConfig:
    """Configuration options for the Faster-Whisper STT adapter."""

    model_size_or_path: str = "base"
    device: str = "auto"
    compute_type: str = "default"
    cpu_threads: int = 4
    num_workers: int = 1
    download_root: str | None = None
    beam_size: int = 5
    vad_filter: bool = False
    word_timestamps: bool = False
    timeout_seconds: float = 60.0
    max_concurrency: int = 2
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Faster-Whisper timeout and concurrency must be positive")
        if not self.model_size_or_path or not self.model_size_or_path.strip():
            raise ConfigurationError("Faster-Whisper model_size_or_path cannot be empty")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> FasterWhisperSTTConfig:
        values = os.environ if env is None else env
        try:
            model = values.get("FASTER_WHISPER_MODEL", "base")
            device = values.get("FASTER_WHISPER_DEVICE", "auto")
            compute_type = values.get("FASTER_WHISPER_COMPUTE_TYPE", "default")
            cpu_threads = int(values.get("FASTER_WHISPER_CPU_THREADS", "4"))
            num_workers = int(values.get("FASTER_WHISPER_NUM_WORKERS", "1"))
            beam_size = int(values.get("FASTER_WHISPER_BEAM_SIZE", "5"))
            vad_filter = values.get("FASTER_WHISPER_VAD_FILTER", "false").lower() in (
                "true",
                "1",
                "yes",
            )
            word_timestamps = values.get("FASTER_WHISPER_WORD_TIMESTAMPS", "false").lower() in (
                "true",
                "1",
                "yes",
            )
            timeout = float(values.get("FASTER_WHISPER_TIMEOUT_SECONDS", "60"))
            concurrency = int(values.get("FASTER_WHISPER_MAX_CONCURRENCY", "2"))
            download_root = values.get("FASTER_WHISPER_DOWNLOAD_ROOT")
        except ValueError as exc:
            raise ConfigurationError("Faster-Whisper environment configuration is invalid") from exc
        return cls(
            model_size_or_path=model,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            num_workers=num_workers,
            beam_size=beam_size,
            vad_filter=vad_filter,
            word_timestamps=word_timestamps,
            timeout_seconds=timeout,
            max_concurrency=concurrency,
            download_root=download_root,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        provider_name: str = "faster_whisper",
    ) -> FasterWhisperSTTConfig:
        values = os.environ if env is None else env
        provider = settings.providers.get(provider_name)
        try:
            model = values.get(
                "FASTER_WHISPER_MODEL",
                str(provider.model if provider and provider.model else "base"),
            )
            timeout = float(
                values.get(
                    "FASTER_WHISPER_TIMEOUT_SECONDS",
                    str(provider.timeout_seconds if provider else 60.0),
                )
            )
            concurrency = int(
                values.get(
                    "FASTER_WHISPER_MAX_CONCURRENCY",
                    str(provider.max_concurrency if provider else 2),
                )
            )
            device = values.get("FASTER_WHISPER_DEVICE", "auto")
            compute_type = values.get("FASTER_WHISPER_COMPUTE_TYPE", "default")
            cpu_threads = int(values.get("FASTER_WHISPER_CPU_THREADS", "4"))
            num_workers = int(values.get("FASTER_WHISPER_NUM_WORKERS", "1"))
            beam_size = int(values.get("FASTER_WHISPER_BEAM_SIZE", "5"))
            vad_filter = values.get("FASTER_WHISPER_VAD_FILTER", "false").lower() in (
                "true",
                "1",
                "yes",
            )
            word_timestamps = values.get("FASTER_WHISPER_WORD_TIMESTAMPS", "false").lower() in (
                "true",
                "1",
                "yes",
            )
            download_root = values.get("FASTER_WHISPER_DOWNLOAD_ROOT")
        except ValueError as exc:
            raise ConfigurationError("Faster-Whisper configuration is invalid") from exc
        retry_policy = RetryPolicy(
            settings.retry.max_attempts,
            settings.retry.base_delay_seconds,
            settings.retry.max_delay_seconds,
        )
        return cls(
            model_size_or_path=model,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            num_workers=num_workers,
            beam_size=beam_size,
            vad_filter=vad_filter,
            word_timestamps=word_timestamps,
            timeout_seconds=timeout,
            max_concurrency=concurrency,
            download_root=download_root,
            retry_policy=retry_policy,
        )


class FasterWhisperSTTProvider(STTProvider):
    """Local, offline Speech-to-Text provider backed by faster-whisper."""

    identity = ProviderIdentity("faster_whisper", "Faster Whisper", unofficial=False)
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: FasterWhisperSTTConfig | None = None,
        *,
        model: Any = None,
    ) -> None:
        if not HAVE_FASTER_WHISPER and model is None:
            raise MissingOptionalDependencyError(
                "The 'faster-whisper' package is required for Faster-Whisper STT. "
                "Install it with: pip install 'indic-language-utils[stt-whisper]'",
                provider="faster_whisper",
            )
        self.config = config or FasterWhisperSTTConfig()
        self._model = model
        self._model_lock = threading.Lock()
        self._limiter = ConcurrencyLimiter(self.config.max_concurrency)
        self.capabilities = (
            CapabilityDeclaration(
                CapabilityId.SPEECH_TO_TEXT, languages=_get_whisper_supported_tags()
            ),
        )

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not HAVE_FASTER_WHISPER:
            raise MissingOptionalDependencyError(
                "The 'faster-whisper' package is required for Faster-Whisper STT. "
                "Install it with: pip install 'indic-language-utils[stt-whisper]'",
                provider="faster_whisper",
            )
        with self._model_lock:
            if self._model is None:
                kwargs: dict[str, Any] = {
                    "device": self.config.device,
                    "compute_type": self.config.compute_type,
                    "cpu_threads": self.config.cpu_threads,
                    "num_workers": self.config.num_workers,
                }
                if self.config.download_root:
                    kwargs["download_root"] = self.config.download_root
                self._model = WhisperModel(self.config.model_size_or_path, **kwargs)
            return self._model

    async def transcribe_batch(
        self,
        audio: tuple[bytes, ...],
        *,
        language: LanguageTag | None,
        audio_format: str,
        sampling_rate: int,
        request_id: str,
        with_timestamps: bool = False,
        word_timestamps: bool = False,
    ) -> tuple[ProviderSTTResult, ...]:
        if not audio or any(not isinstance(item, bytes) or not item for item in audio):
            raise InvalidInputError(
                "Faster-Whisper STT audio cannot be empty",
                provider="faster_whisper",
                capability=CapabilityId.SPEECH_TO_TEXT.value,
                request_id=request_id,
            )

        lang_code = whisper_language_code(language)
        want_timestamps = with_timestamps or word_timestamps or self.config.word_timestamps
        need_word_timestamps = word_timestamps or self.config.word_timestamps

        def _transcribe_one(
            clip: bytes,
        ) -> tuple[str, LanguageTag | None, tuple[STTSegment, ...], tuple[STTWord, ...]]:
            try:
                model = self._get_model()
                audio_stream = io.BytesIO(clip)
                transcribe_kwargs: dict[str, Any] = {
                    "language": lang_code,
                    "beam_size": self.config.beam_size,
                    "vad_filter": self.config.vad_filter,
                }
                if need_word_timestamps:
                    transcribe_kwargs["word_timestamps"] = True

                segments, info = model.transcribe(audio_stream, **transcribe_kwargs)
                text_parts: list[str] = []
                extracted_segments: list[STTSegment] = []
                all_words: list[STTWord] = []

                for s in segments:
                    seg_text = getattr(s, "text", "")
                    if seg_text and seg_text.strip():
                        text_parts.append(seg_text.strip())

                    if want_timestamps:
                        seg_words: list[STTWord] = []
                        raw_words = getattr(s, "words", None)
                        if raw_words:
                            for w in raw_words:
                                w_word = str(getattr(w, "word", ""))
                                w_start = float(getattr(w, "start", 0.0))
                                w_end = float(getattr(w, "end", 0.0))
                                w_prob = getattr(w, "probability", None)
                                w_prob_val = float(w_prob) if w_prob is not None else None
                                word_obj = STTWord(
                                    word=w_word,
                                    start=w_start,
                                    end=w_end,
                                    probability=w_prob_val,
                                )
                                seg_words.append(word_obj)
                                all_words.append(word_obj)

                        start_sec = float(getattr(s, "start", 0.0))
                        end_sec = float(getattr(s, "end", 0.0))
                        extracted_segments.append(
                            STTSegment(
                                text=seg_text.strip() if seg_text else "",
                                start=start_sec,
                                end=end_sec,
                                words=tuple(seg_words),
                            )
                        )

                text = " ".join(text_parts).strip()
                detected: LanguageTag | None = language
                if detected is None and hasattr(info, "language") and info.language:
                    try:
                        detected = DEFAULT_LANGUAGE_REGISTRY.normalize(info.language)
                    except Exception:
                        detected = None

                return text, detected, tuple(extracted_segments), tuple(all_words)
            except Exception as exc:
                raise TransientProviderError(
                    f"Faster-Whisper STT failed: {exc}",
                    provider="faster_whisper",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                    request_id=request_id,
                ) from exc

        async def _run_clip(
            clip: bytes,
        ) -> tuple[str, LanguageTag | None, tuple[STTSegment, ...], tuple[STTWord, ...]]:
            async with self._limiter.slot("faster_whisper", CapabilityId.SPEECH_TO_TEXT):
                return await asyncio.to_thread(_transcribe_one, clip)

        async def _transcribe_clip(
            clip_data: bytes,
        ) -> tuple[str, LanguageTag | None, tuple[STTSegment, ...], tuple[STTWord, ...]]:
            async def _execute() -> tuple[
                str, LanguageTag | None, tuple[STTSegment, ...], tuple[STTWord, ...]
            ]:
                task = asyncio.create_task(_run_clip(clip_data))
                try:
                    return await asyncio.wait_for(
                        asyncio.shield(task), timeout=self.config.timeout_seconds
                    )
                except TimeoutError as exc:
                    # The worker cannot be stopped safely. Keep its slot until it finishes.
                    task.add_done_callback(_observe_background_result)
                    raise _WhisperWaitTimeout from exc
                except asyncio.CancelledError:
                    task.add_done_callback(_observe_background_result)
                    raise

            try:
                return await retry(_execute, self.config.retry_policy)
            except _WhisperWaitTimeout as exc:
                raise ProviderTimeoutError(
                    "Faster-Whisper STT timed out",
                    provider="faster_whisper",
                    capability=CapabilityId.SPEECH_TO_TEXT.value,
                    request_id=request_id,
                ) from exc

        results: list[ProviderSTTResult] = []
        for clip in audio:
            text, detected_lang, segs, words = await _transcribe_clip(clip)
            results.append(
                ProviderSTTResult(
                    text=text,
                    model_id=f"faster-whisper-{self.config.model_size_or_path}",
                    request_id=request_id,
                    detected_language=detected_lang,
                    segments=segs,
                    words=words,
                )
            )

        return tuple(results)


# Aliases
WhisperSTTProvider = FasterWhisperSTTProvider
WhisperSTTConfig = FasterWhisperSTTConfig
