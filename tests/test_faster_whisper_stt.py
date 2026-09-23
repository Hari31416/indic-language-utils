from __future__ import annotations

from typing import Any

import pytest

from indic_language_utils.config import Settings
from indic_language_utils.errors import (
    ConfigurationError,
    InvalidInputError,
    MissingOptionalDependencyError,
    TransientProviderError,
)
from indic_language_utils.languages import LanguageTag
from indic_language_utils.stt import (
    FasterWhisperSTTConfig,
    FasterWhisperSTTProvider,
    STTClient,
    get_stt_client,
)
from indic_language_utils.stt.whisper import (
    whisper_language_code,
)


class MockSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class MockInfo:
    def __init__(self, language: str = "hi") -> None:
        self.language = language


class MockWhisperModel:
    def __init__(
        self,
        segments: tuple[str, ...] = ("नमस्ते", "दुनिया"),
        detected_lang: str = "hi",
    ) -> None:
        self.segments = [MockSegment(s) for s in segments]
        self.info = MockInfo(detected_lang)
        self.recorded_lang: str | None = None
        self.recorded_beam_size: int | None = None
        self.call_count = 0

    def transcribe(
        self,
        audio_stream: Any,
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = False,
    ) -> tuple[Any, MockInfo]:
        self.call_count += 1
        self.recorded_lang = language
        self.recorded_beam_size = beam_size
        return iter(self.segments), self.info


def test_faster_whisper_config_defaults() -> None:
    config = FasterWhisperSTTConfig()
    assert config.model_size_or_path == "base"
    assert config.device == "auto"
    assert config.compute_type == "default"
    assert config.beam_size == 5
    assert config.timeout_seconds == 60.0
    assert config.max_concurrency == 2


def test_faster_whisper_config_from_env_and_settings() -> None:
    env = {
        "FASTER_WHISPER_MODEL": "small",
        "FASTER_WHISPER_DEVICE": "cpu",
        "FASTER_WHISPER_COMPUTE_TYPE": "int8",
        "FASTER_WHISPER_TIMEOUT_SECONDS": "45",
        "FASTER_WHISPER_MAX_CONCURRENCY": "3",
        "FASTER_WHISPER_BEAM_SIZE": "3",
    }
    config = FasterWhisperSTTConfig.from_env(env)
    assert config.model_size_or_path == "small"
    assert config.device == "cpu"
    assert config.compute_type == "int8"
    assert config.timeout_seconds == 45.0
    assert config.max_concurrency == 3
    assert config.beam_size == 3

    settings = Settings._from_mapping(
        {"providers": {"faster_whisper": {"model": "medium", "timeout_seconds": 90.0}}}
    )
    from_sett = FasterWhisperSTTConfig.from_settings(settings)
    assert from_sett.model_size_or_path == "medium"
    assert from_sett.timeout_seconds == 90.0


def test_faster_whisper_config_validation() -> None:
    with pytest.raises(ConfigurationError):
        FasterWhisperSTTConfig(timeout_seconds=0)
    with pytest.raises(ConfigurationError):
        FasterWhisperSTTConfig(model_size_or_path="")


def test_whisper_language_code() -> None:
    assert whisper_language_code(None) is None
    assert whisper_language_code(LanguageTag("hi")) == "hi"
    assert whisper_language_code(LanguageTag.parse("ta-IN")) == "ta"
    assert whisper_language_code(LanguageTag("bn")) == "bn"
    assert whisper_language_code(LanguageTag("en")) == "en"


def test_faster_whisper_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import indic_language_utils.stt.whisper as w_module

    monkeypatch.setattr(w_module, "HAVE_FASTER_WHISPER", False)
    with pytest.raises(MissingOptionalDependencyError) as exc_info:
        FasterWhisperSTTProvider()
    assert "faster-whisper" in str(exc_info.value)


@pytest.mark.asyncio
async def test_faster_whisper_transcribe_batch_success() -> None:
    mock_model = MockWhisperModel(segments=("भारत", "एक", "महान", "देश", "है"), detected_lang="hi")
    provider = FasterWhisperSTTProvider(model=mock_model)

    results = await provider.transcribe_batch(
        (b"audio-bytes-1",),
        language=LanguageTag("hi"),
        audio_format="wav",
        sampling_rate=16000,
        request_id="req-w1",
    )

    assert len(results) == 1
    assert results[0].text == "भारत एक महान देश है"
    assert results[0].model_id == "faster-whisper-base"
    assert results[0].detected_language == LanguageTag("hi")
    assert mock_model.recorded_lang == "hi"
    assert mock_model.call_count == 1


@pytest.mark.asyncio
async def test_faster_whisper_auto_detect_language() -> None:
    mock_model = MockWhisperModel(segments=("வணக்கம்",), detected_lang="ta")
    provider = FasterWhisperSTTProvider(model=mock_model)

    results = await provider.transcribe_batch(
        (b"audio-bytes-ta",),
        language=None,
        audio_format="wav",
        sampling_rate=16000,
        request_id="req-w2",
    )

    assert len(results) == 1
    assert results[0].text == "வணக்கம்"
    assert results[0].detected_language == LanguageTag("ta", region="IN")
    assert mock_model.recorded_lang is None


@pytest.mark.asyncio
async def test_faster_whisper_empty_audio_raises() -> None:
    provider = FasterWhisperSTTProvider(model=MockWhisperModel())
    with pytest.raises(InvalidInputError):
        await provider.transcribe_batch(
            (),
            language=None,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req-w3",
        )
    with pytest.raises(InvalidInputError):
        await provider.transcribe_batch(
            (b"",),
            language=None,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req-w4",
        )


@pytest.mark.asyncio
async def test_faster_whisper_transient_error() -> None:
    class FailingModel:
        def transcribe(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Model execution failed")

    config = FasterWhisperSTTConfig()
    object.__setattr__(config.retry_policy, "max_attempts", 1)
    provider = FasterWhisperSTTProvider(config, model=FailingModel())

    with pytest.raises(TransientProviderError):
        await provider.transcribe_batch(
            (b"audio-fail",),
            language=None,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req-w5",
        )


@pytest.mark.asyncio
async def test_faster_whisper_client_integration() -> None:
    mock_model = MockWhisperModel(segments=("integrated", "test"), detected_lang="en")
    provider = FasterWhisperSTTProvider(model=mock_model)
    client = get_stt_client(providers=[provider])

    assert isinstance(client, STTClient)
    res = await client.transcribe(b"audio-bytes", language="en")
    assert res.text == "integrated test"
    assert res.provider == "faster_whisper"
    assert res.model_id == "faster-whisper-base"
