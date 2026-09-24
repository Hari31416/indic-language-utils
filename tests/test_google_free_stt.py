from __future__ import annotations

import io
import wave
from typing import Any

import pytest

from indic_language_utils.config import Settings
from indic_language_utils.errors import (
    ConfigurationError,
    InvalidInputError,
    MissingOptionalDependencyError,
    RateLimitError,
    TransientProviderError,
)
from indic_language_utils.languages import LanguageTag
from indic_language_utils.stt import (
    GoogleFreeSTTConfig,
    GoogleFreeSTTProvider,
    STTClient,
    get_stt_client,
)
from indic_language_utils.stt.google_speech import (
    _decode_to_pcm,
    google_speech_language_code,
)


class MockRecognizer:
    def __init__(self, transcript: str = "नमस्ते") -> None:
        self.transcript = transcript
        self.recorded_lang: str | None = None
        self.call_count = 0

    def recognize_google(self, audio_data: Any, language: str | None = None) -> str:
        self.call_count += 1
        self.recorded_lang = language
        return self.transcript


def _make_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 160)
    return buf.getvalue()


def test_google_free_config_defaults() -> None:
    config = GoogleFreeSTTConfig()
    assert config.timeout_seconds == 20.0
    assert config.max_concurrency == 4
    assert config.default_language == "en-IN"


def test_google_free_config_from_env_and_settings() -> None:
    env = {
        "GOOGLE_FREE_STT_TIMEOUT_SECONDS": "15",
        "GOOGLE_FREE_STT_MAX_CONCURRENCY": "2",
        "GOOGLE_FREE_STT_DEFAULT_LANGUAGE": "hi-IN",
    }
    config = GoogleFreeSTTConfig.from_env(env)
    assert config.timeout_seconds == 15.0
    assert config.max_concurrency == 2
    assert config.default_language == "hi-IN"

    settings = Settings._from_mapping(
        {"providers": {"google_free": {"timeout_seconds": 25.0, "max_concurrency": 8}}}
    )
    from_sett = GoogleFreeSTTConfig.from_settings(settings)
    assert from_sett.timeout_seconds == 25.0
    assert from_sett.max_concurrency == 8


def test_google_free_config_validation() -> None:
    with pytest.raises(ConfigurationError):
        GoogleFreeSTTConfig(timeout_seconds=-1)
    with pytest.raises(ConfigurationError):
        GoogleFreeSTTConfig(max_concurrency=0)


def test_google_speech_language_code() -> None:
    assert google_speech_language_code(None) == "en-IN"
    assert google_speech_language_code(LanguageTag("hi")) == "hi-IN"
    assert google_speech_language_code(LanguageTag("ta")) == "ta-IN"
    assert google_speech_language_code(LanguageTag("bn")) == "bn-IN"
    assert google_speech_language_code(LanguageTag("en", region="US")) == "en-US"
    assert google_speech_language_code(LanguageTag("pa")) == "pa-guru-IN"


def test_google_free_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    import indic_language_utils.stt.google_speech as gs_module

    monkeypatch.setattr(gs_module, "HAVE_SPEECH_RECOGNITION", False)
    with pytest.raises(MissingOptionalDependencyError) as exc_info:
        GoogleFreeSTTProvider()
    assert "SpeechRecognition" in str(exc_info.value)


def test_google_free_invalid_factory_config_is_reported() -> None:
    with pytest.raises(ConfigurationError, match="Google Free STT configuration is invalid"):
        get_stt_client(
            Settings._from_mapping({"routes": {"speech_to_text": ["google_free"]}}),
            env={"GOOGLE_FREE_STT_TIMEOUT_SECONDS": "bad"},
        )


@pytest.mark.asyncio
async def test_google_free_transcribe_batch_success() -> None:
    rec = MockRecognizer("भारत एक महान देश है")
    provider = GoogleFreeSTTProvider(recognizer=rec)

    wav = _make_wav_bytes()
    results = await provider.transcribe_batch(
        (wav,),
        language=LanguageTag("hi"),
        audio_format="wav",
        sampling_rate=16000,
        request_id="req-1",
    )

    assert len(results) == 1
    assert results[0].text == "भारत एक महान देश है"
    assert results[0].model_id == "google_free"
    assert rec.recorded_lang == "hi-IN"
    assert rec.call_count == 1


@pytest.mark.asyncio
async def test_google_free_uses_configured_default_language() -> None:
    rec = MockRecognizer()
    provider = GoogleFreeSTTProvider(GoogleFreeSTTConfig(default_language="ta-IN"), recognizer=rec)
    await provider.transcribe_batch(
        (_make_wav_bytes(),),
        language=None,
        audio_format="wav",
        sampling_rate=16000,
        request_id="req-default",
    )
    assert rec.recorded_lang == "ta-IN"


def test_google_free_rejects_undecoded_compressed_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import indic_language_utils.stt.google_speech as gs_module

    monkeypatch.setattr(gs_module, "HAVE_AV", False)
    with pytest.raises(MissingOptionalDependencyError, match="PyAV"):
        _decode_to_pcm(b"ID3compressed-data", "mp3", 16000)


def test_google_free_rejects_invalid_wav_without_decoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import indic_language_utils.stt.google_speech as gs_module

    monkeypatch.setattr(gs_module, "HAVE_AV", False)
    with pytest.raises(InvalidInputError, match="WAV"):
        _decode_to_pcm(b"RIFFbad-data", "wav", 16000)


@pytest.mark.asyncio
async def test_google_free_raw_pcm_and_multiple_clips() -> None:
    rec = MockRecognizer("hello world")
    provider = GoogleFreeSTTProvider(recognizer=rec)

    raw_pcm = b"\x00\x00" * 320
    results = await provider.transcribe_batch(
        (raw_pcm, raw_pcm),
        language=LanguageTag("en"),
        audio_format="pcm",
        sampling_rate=16000,
        request_id="req-2",
    )

    assert len(results) == 2
    assert results[0].text == "hello world"
    assert results[1].text == "hello world"
    assert rec.call_count == 2


@pytest.mark.asyncio
async def test_google_free_empty_audio_raises() -> None:
    provider = GoogleFreeSTTProvider(recognizer=MockRecognizer())
    with pytest.raises(InvalidInputError):
        await provider.transcribe_batch(
            (),
            language=None,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req-3",
        )
    with pytest.raises(InvalidInputError):
        await provider.transcribe_batch(
            (b"",),
            language=None,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req-4",
        )


@pytest.mark.asyncio
async def test_google_free_silence_or_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    import indic_language_utils.stt.google_speech as gs_module

    class DummyUnknownValue(Exception):
        pass

    class DummySR:
        UnknownValueError = DummyUnknownValue

    monkeypatch.setattr(gs_module, "sr", DummySR)

    class FailingRecognizer:
        def recognize_google(self, audio_data: Any, language: str | None = None) -> str:
            raise DummyUnknownValue("silence")

    provider = GoogleFreeSTTProvider(recognizer=FailingRecognizer())
    results = await provider.transcribe_batch(
        (b"some audio",),
        language=LanguageTag("hi"),
        audio_format="wav",
        sampling_rate=16000,
        request_id="req-5",
    )
    assert len(results) == 1
    assert results[0].text == ""


@pytest.mark.asyncio
async def test_google_free_rate_limit_error() -> None:
    class RateLimitRecognizer:
        def recognize_google(self, audio_data: Any, language: str | None = None) -> str:
            raise Exception("429 Client Error: Too Many Requests")

    config = GoogleFreeSTTConfig()
    object.__setattr__(config.retry_policy, "max_attempts", 1)
    provider = GoogleFreeSTTProvider(config, recognizer=RateLimitRecognizer())

    with pytest.raises(RateLimitError):
        await provider.transcribe_batch(
            (b"audio",),
            language=None,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req-6",
        )


@pytest.mark.asyncio
async def test_google_free_transient_error() -> None:
    class FailRecognizer:
        def recognize_google(self, audio_data: Any, language: str | None = None) -> str:
            raise Exception("Connection timed out")

    config = GoogleFreeSTTConfig()
    object.__setattr__(config.retry_policy, "max_attempts", 1)
    provider = GoogleFreeSTTProvider(config, recognizer=FailRecognizer())

    with pytest.raises(TransientProviderError):
        await provider.transcribe_batch(
            (b"audio",),
            language=None,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req-7",
        )


@pytest.mark.asyncio
async def test_google_free_client_integration() -> None:
    rec = MockRecognizer("client transcript")
    provider = GoogleFreeSTTProvider(recognizer=rec)
    client = get_stt_client(providers=[provider])

    assert isinstance(client, STTClient)
    res = await client.transcribe(b"audio", language="hi")
    assert res.text == "client transcript"
    assert res.provider == "google_free"
    assert res.model_id == "google_free"
