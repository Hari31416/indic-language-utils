from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from indic_language_utils import (
    BhashiniConfig,
    BhashiniSTTProvider,
    Secret,
    Settings,
    STTClient,
    STTRequest,
    get_stt_client,
)
from indic_language_utils.errors import MalformedProviderResponseError, UnsupportedLanguageError
from indic_language_utils.providers.bhashini import JsonResponse


@dataclass
class FakeTransport:
    responses: list[JsonResponse]
    payloads: list[Mapping[str, object]] = field(default_factory=list)

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        self.payloads.append(json)
        return self.responses.pop(0)

    async def close(self) -> None:
        pass


def response(*texts: str) -> JsonResponse:
    return JsonResponse(
        200,
        {"pipelineResponse": [{"taskType": "asr", "output": [{"source": text} for text in texts]}]},
        {"x-request-id": "provider-123"},
    )


def config() -> BhashiniConfig:
    return BhashiniConfig(
        "https://example.test/inference",
        Secret("key"),
        stt_model_id="default",
        stt_model_ids={"hi": "hindi-model"},
        tts_model_ids={"hi": "hindi-voice"},
    )


@pytest.mark.asyncio
async def test_bhashini_stt_payload_and_language_model() -> None:
    transport = FakeTransport([response("नमस्ते")])
    provider = BhashiniSTTProvider(config(), transport=transport)
    result = await provider.transcribe_batch(
        (b"some audio",),
        language=STTRequest(b"x", "hi").language,
        audio_format="wav",
        sampling_rate=16000,
        request_id="request-123",
    )
    assert result[0].text == "नमस्ते"
    assert result[0].model_id == "hindi-model"
    assert result[0].request_id == "provider-123"
    payload = transport.payloads[0]
    task = payload["pipelineTasks"][0]  # type: ignore[index]
    assert task["config"]["serviceId"] == "hindi-model"
    assert task["config"]["language"] == {"sourceLanguage": "hi"}
    assert task["config"]["audioFormat"] == "wav"
    assert task["config"]["samplingRate"] == 16000
    assert payload["inputData"] == {
        "audio": [{"audioContent": base64.b64encode(b"some audio").decode()}]
    }


@pytest.mark.asyncio
async def test_stt_client_returns_transcript() -> None:
    transport = FakeTransport([response("hello")])
    provider = BhashiniSTTProvider(config(), transport=transport)
    client = get_stt_client(providers=[provider])
    assert isinstance(client, STTClient)
    result = await client.transcribe(b"audio", language="en")
    assert result.text == "hello"
    assert result.model_id == "default"
    assert result.provider == "bhashini"


@pytest.mark.asyncio
async def test_malformed_response_is_rejected() -> None:
    provider = BhashiniSTTProvider(config(), transport=FakeTransport([response()]))
    with pytest.raises(MalformedProviderResponseError):
        await provider.transcribe_batch(
            (b"x",),
            language=STTRequest(b"x", "hi").language,
            audio_format="wav",
            sampling_rate=16000,
            request_id="req",
        )


def test_stt_model_mapping_from_settings() -> None:
    settings = Settings._from_mapping(
        {
            "providers": {
                "bhashini": {
                    "endpoint": "https://example.test/inference",
                    "stt_model_ids": {"hi": "model-hi", "ta-IN": "model-ta"},
                    "tts_model_ids": {"hi": "voice-hi"},
                }
            }
        }
    )
    cfg = BhashiniConfig.from_settings(settings, env={"BHASHINI_API_KEY": "key"})
    assert cfg.stt_model_ids["hi-IN"] == "model-hi"
    assert cfg.tts_model_ids["hi-IN"] == "voice-hi"
    assert BhashiniSTTProvider(cfg).model_id_for(STTRequest(b"x", "ta").language) == "model-ta"
    with pytest.raises(UnsupportedLanguageError):
        BhashiniSTTProvider(cfg).model_id_for(STTRequest(b"x", "en").language)


@pytest.mark.asyncio
async def test_stt_without_language_uses_default_model() -> None:
    transport = FakeTransport([response("hello")])
    provider = BhashiniSTTProvider(config(), transport=transport)
    result = await get_stt_client(providers=[provider]).transcribe(b"audio")
    assert result.language is None
    assert result.model_id == "default"
    task = transport.payloads[0]["pipelineTasks"][0]  # type: ignore[index]
    assert "language" not in task["config"]


def test_stt_timestamp_data_models() -> None:
    from indic_language_utils.stt import STTSegment, STTWord

    word = STTWord(word="hello", start=0.0, end=0.5, probability=0.98)
    assert word.word == "hello"
    assert word.start == 0.0
    assert word.end == 0.5
    assert word.probability == 0.98

    seg = STTSegment(text="hello world", start=0.0, end=1.2, words=(word,))
    assert seg.text == "hello world"
    assert seg.start == 0.0
    assert seg.end == 1.2
    assert seg.words == (word,)


@pytest.mark.asyncio
async def test_stt_client_propagates_timestamps() -> None:
    from indic_language_utils.models import ProviderIdentity
    from indic_language_utils.providers import CapabilityDeclaration, CapabilityId
    from indic_language_utils.stt import (
        ProviderSTTResult,
        STTProvider,
        STTSegment,
        STTWord,
    )

    class FakeTimestampProvider(STTProvider):
        identity = ProviderIdentity("fake", "Fake Provider", unofficial=False)
        capabilities = (CapabilityDeclaration(CapabilityId.SPEECH_TO_TEXT),)

        async def transcribe_batch(
            self,
            audio: tuple[bytes, ...],
            *,
            language: object,
            audio_format: str,
            sampling_rate: int,
            request_id: str,
            with_timestamps: bool = False,
            word_timestamps: bool = False,
        ) -> tuple[ProviderSTTResult, ...]:
            word = STTWord(word="test", start=0.1, end=0.4, probability=0.95)
            seg = STTSegment(text="test", start=0.1, end=0.4, words=(word,))
            return (
                ProviderSTTResult(
                    text="test",
                    model_id="fake-model",
                    request_id="fake-req",
                    segments=(seg,) if with_timestamps else (),
                    words=(word,) if word_timestamps else (),
                ),
            )

    provider = FakeTimestampProvider()
    client = get_stt_client(providers=[provider])

    res_no_ts = await client.transcribe(b"audio", language="en")
    assert res_no_ts.segments == ()
    assert res_no_ts.words == ()

    res_with_ts = await client.transcribe(b"audio", language="en", with_timestamps=True)
    assert len(res_with_ts.segments) == 1
    assert res_with_ts.segments[0].text == "test"
    assert res_with_ts.segments[0].start == 0.1

    res_with_words = await client.transcribe(b"audio", language="en", word_timestamps=True)
    assert len(res_with_words.words) == 1
    assert res_with_words.words[0].word == "test"
    assert res_with_words.words[0].end == 0.4


def test_stt_request_positional_context() -> None:
    from indic_language_utils.models import OperationContext

    ctx = OperationContext(request_id="custom-req-id")
    # Call with 5 positional arguments (the legacy signature)
    req = STTRequest(b"audio", "hi", "wav", 16000, ctx)
    assert req.context.request_id == "custom-req-id"
    assert req.with_timestamps is False
    assert req.word_timestamps is False

    # Calling with keyword-only timestamp arguments
    req_ts = STTRequest(b"audio", "hi", with_timestamps=True)
    assert req_ts.with_timestamps is True
    assert req_ts.word_timestamps is False

    req_words = STTRequest(b"audio", "hi", word_timestamps=True)
    assert req_words.with_timestamps is True
    assert req_words.word_timestamps is True


@pytest.mark.asyncio
async def test_stt_client_legacy_provider_signature() -> None:
    from indic_language_utils.models import ProviderIdentity
    from indic_language_utils.providers import CapabilityDeclaration, CapabilityId
    from indic_language_utils.stt import ProviderSTTResult

    class LegacyProvider:
        identity = ProviderIdentity("legacy", "Legacy Provider", unofficial=False)
        capabilities = (CapabilityDeclaration(CapabilityId.SPEECH_TO_TEXT),)

        async def transcribe_batch(
            self,
            audio: tuple[bytes, ...],
            *,
            language: object,
            audio_format: str,
            sampling_rate: int,
            request_id: str,
        ) -> tuple[ProviderSTTResult, ...]:
            return (
                ProviderSTTResult(
                    text="legacy text",
                    model_id="legacy-model",
                    request_id="legacy-req",
                ),
            )

    # Intentionally tests runtime backward compatibility with legacy provider signatures
    client = get_stt_client(providers=[LegacyProvider()])  # type: ignore[list-item]
    res = await client.transcribe(b"audio", language="en", with_timestamps=True)
    assert res.text == "legacy text"
    assert res.segments == ()
    assert res.words == ()


@pytest.mark.asyncio
async def test_stt_client_internal_type_error_not_retried() -> None:
    from indic_language_utils.models import ProviderIdentity
    from indic_language_utils.providers import CapabilityDeclaration, CapabilityId
    from indic_language_utils.stt import ProviderSTTResult, STTProvider

    call_count = 0

    class BuggyProvider(STTProvider):
        identity = ProviderIdentity("buggy", "Buggy Provider", unofficial=False)
        capabilities = (CapabilityDeclaration(CapabilityId.SPEECH_TO_TEXT),)

        async def transcribe_batch(
            self,
            audio: tuple[bytes, ...],
            *,
            language: object,
            audio_format: str,
            sampling_rate: int,
            request_id: str,
            with_timestamps: bool = False,
            word_timestamps: bool = False,
        ) -> tuple[ProviderSTTResult, ...]:
            nonlocal call_count
            call_count += 1
            # Internal TypeError mentioning with_timestamps
            raise TypeError("internal operation failed on with_timestamps")

    client = get_stt_client(providers=[BuggyProvider()])
    with pytest.raises(TypeError, match="internal operation failed on with_timestamps"):
        await client.transcribe(b"audio", language="en", with_timestamps=True)

    # Should not have retried
    assert call_count == 1


@pytest.mark.asyncio
async def test_stt_client_provider_with_only_segment_timestamps() -> None:
    from indic_language_utils.models import ProviderIdentity
    from indic_language_utils.providers import CapabilityDeclaration, CapabilityId
    from indic_language_utils.stt import ProviderSTTResult, STTSegment

    class SegmentOnlyProvider:
        identity = ProviderIdentity("segment_only", "Segment Only Provider", unofficial=False)
        capabilities = (CapabilityDeclaration(CapabilityId.SPEECH_TO_TEXT),)

        async def transcribe_batch(
            self,
            audio: tuple[bytes, ...],
            *,
            language: object,
            audio_format: str,
            sampling_rate: int,
            request_id: str,
            with_timestamps: bool = False,
        ) -> tuple[ProviderSTTResult, ...]:
            seg = STTSegment(text="seg text", start=0.0, end=1.0)
            return (
                ProviderSTTResult(
                    text="seg text",
                    model_id="seg-model",
                    request_id="seg-req",
                    segments=(seg,) if with_timestamps else (),
                ),
            )

    client = get_stt_client(providers=[SegmentOnlyProvider()])  # type: ignore[list-item]
    # Requesting both timestamp types
    res = await client.transcribe(
        b"audio", language="en", with_timestamps=True, word_timestamps=True
    )
    assert res.text == "seg text"
    # Supported with_timestamps should NOT have been dropped
    assert len(res.segments) == 1
    assert res.segments[0].text == "seg text"
    assert res.segments[0].start == 0.0
    assert res.segments[0].end == 1.0
    assert res.words == ()
