from __future__ import annotations

import pytest

from indic_language_utils.detection.fasttext import (
    HAVE_FASTTEXT,
    FastTextDetectionConfig,
    FastTextDetectionProvider,
    detect_script,
)
from indic_language_utils.detection.models import DetectionOptions
from indic_language_utils.errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
)
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY


def test_detect_script() -> None:
    assert detect_script("नमस्ते दुनिया") == "Deva"
    assert detect_script("হ্যালো বিশ্ব") == "Beng"
    assert detect_script("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ") == "Guru"
    assert detect_script("ગુજરાતી") == "Gujr"
    assert detect_script("ଓଡ଼ିଆ") == "Orya"
    assert detect_script("வணக்கம்") == "Taml"
    assert detect_script("నమస్కారం") == "Telu"
    assert detect_script("ಕನ್ನಡ") == "Knda"
    assert detect_script("മലയാളം") == "Mlym"
    assert detect_script("ᱥᱟᱱᱛᱟᱲᱤ") == "Olck"
    assert detect_script("اردو") == "Arab"
    assert detect_script("Hello world") == "Latn"
    assert detect_script("12345!@#$") is None


def test_fasttext_config_validation() -> None:
    with pytest.raises(ConfigurationError):
        FastTextDetectionConfig(max_concurrency=0)


@pytest.mark.asyncio
async def test_fasttext_empty_input_validation() -> None:
    provider = FastTextDetectionProvider(detector=lambda text, **kw: {"lang": "en", "score": 0.9})
    with pytest.raises(InvalidInputError):
        await provider.detect_batch((), options=DetectionOptions(), request_id="req-1")

    with pytest.raises(InvalidInputError):
        await provider.detect_batch(("",), options=DetectionOptions(), request_id="req-1")

    with pytest.raises(InvalidInputError):
        await provider.detect_batch(("   ",), options=DetectionOptions(), request_id="req-1")


@pytest.mark.asyncio
async def test_fasttext_with_mock_detector() -> None:
    def mock_detector(text: str, low_memory: bool = False, k: int = 1) -> list[dict[str, object]]:
        return [
            {"lang": "hi", "score": 0.85},
            {"lang": "mr", "score": 0.15},
        ]

    provider = FastTextDetectionProvider(detector=mock_detector)
    results = await provider.detect_batch(
        ("नमस्ते दुनिया",),
        options=DetectionOptions(max_candidates=2),
        request_id="req-123",
    )
    assert len(results) == 1
    candidates = results[0].candidates
    assert len(candidates) == 2
    assert candidates[0].language == DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    assert pytest.approx(candidates[0].confidence) == 0.85
    assert candidates[0].script == "Deva"
    assert candidates[1].language == DEFAULT_LANGUAGE_REGISTRY.normalize("mr")
    assert pytest.approx(candidates[1].confidence) == 0.15
    assert candidates[1].script == "Deva"


@pytest.mark.asyncio
async def test_fasttext_with_international_code() -> None:
    def mock_detector(text: str, **kw: object) -> dict[str, object]:
        return {"lang": "fr", "score": 0.99}

    provider = FastTextDetectionProvider(detector=mock_detector)
    results = await provider.detect_batch(
        ("Bonjour tout le monde",),
        options=DetectionOptions(),
        request_id="req-fr",
    )
    assert len(results) == 1
    assert results[0].candidates[0].language.language == "fr"
    assert results[0].candidates[0].script == "Latn"


@pytest.mark.asyncio
async def test_fasttext_malformed_detector_output() -> None:
    provider = FastTextDetectionProvider(detector=lambda text, **kw: "not-a-dict")
    with pytest.raises(MalformedProviderResponseError):
        await provider.detect_batch(
            ("test",),
            options=DetectionOptions(),
            request_id="req-err",
        )


@pytest.mark.asyncio
async def test_fasttext_detector_exception() -> None:
    def failing_detector(text: str, **kw: object) -> None:
        raise RuntimeError("FastText engine crashed")

    provider = FastTextDetectionProvider(detector=failing_detector)
    with pytest.raises(MalformedProviderResponseError, match="FastText detection failed"):
        await provider.detect_batch(
            ("test",),
            options=DetectionOptions(),
            request_id="req-crash",
        )


def test_fasttext_missing_dependency() -> None:
    if not HAVE_FASTTEXT:
        with pytest.raises(MissingOptionalDependencyError):
            FastTextDetectionProvider()


@pytest.mark.skipif(not HAVE_FASTTEXT, reason="fasttext-langdetect not installed")
@pytest.mark.asyncio
async def test_fasttext_live_detection() -> None:
    provider = FastTextDetectionProvider()
    results = await provider.detect_batch(
        ("नमस्ते दुनिया", "Hello how are you doing today?"),
        options=DetectionOptions(max_candidates=2),
        request_id="live-test",
    )
    assert len(results) == 2
    # Devanagari script detected
    assert results[0].candidates[0].script == "Deva"
    # English detected
    assert results[1].candidates[0].language.language == "en"
    assert results[1].candidates[0].script == "Latn"
