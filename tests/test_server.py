from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from indic_language_utils.server.app import create_app
from indic_language_utils.transliteration.aksharamukha import HAVE_AKSHARAMUKHA


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "indic-language-utils"


def test_list_languages(client: TestClient) -> None:
    response = client.get("/api/languages")
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    languages = data["languages"]
    assert len(languages) >= 23
    codes = {lang["code"] for lang in languages}
    assert "en" in codes
    assert "hi" in codes
    assert "ta" in codes
    assert "te" in codes
    assert "bn" in codes


def test_list_providers(client: TestClient) -> None:
    response = client.get("/api/providers")
    assert response.status_code == 200
    data = response.json()
    assert "translation" in data
    assert "detection" in data
    assert "transliteration" in data
    trans_ids = [p["id"] for p in data["translation"]]
    detect_ids = [p["id"] for p in data["detection"]]
    translit_ids = [p["id"] for p in data["transliteration"]]
    assert "sarvam" in trans_ids
    assert "sarvam" in detect_ids
    assert "googletrans" in trans_ids or "bhashini" in trans_ids
    assert "fasttext" in detect_ids
    assert "bhashini" in translit_ids
    assert "aksharamukha" in translit_ids
    assert "indicxlit" in translit_ids


def test_detect_script(client: TestClient) -> None:
    response = client.post("/api/detect-script", json={"text": "नमस्ते"})
    assert response.status_code == 200
    assert response.json()["script"] == "Deva"

    response = client.post("/api/detect-script", json={"text": "தமிழ்"})
    assert response.status_code == 200
    assert response.json()["script"] == "Taml"

    response = client.post("/api/detect-script", json={"text": "Hello world"})
    assert response.status_code == 200
    assert response.json()["script"] == "Latn"


def test_detect_language(client: TestClient) -> None:
    response = client.post("/api/detect", json={"text": "வணக்கம் நண்பர்களே"})
    assert response.status_code == 200
    data = response.json()
    assert data["language"] is not None
    assert "candidates" in data
    assert len(data["candidates"]) > 0
    assert data["script"] is not None


def test_translate_text(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from indic_language_utils.translation.google_translate import GoogleTranslateProvider
    from indic_language_utils.translation.models import ProviderTranslationResult

    async def mock_translate_batch(
        self: object,
        texts: tuple[str, ...],
        *,
        source: object,
        target: object,
        options: object,
        request_id: str,
    ) -> ProviderTranslationResult:
        return ProviderTranslationResult(
            tuple(f"translated:{t}" for t in texts),
            service_id=None,
            model_id=None,
            request_id=request_id,
        )

    monkeypatch.setattr(GoogleTranslateProvider, "translate_batch", mock_translate_batch)

    response = client.post(
        "/api/translate",
        json={
            "text": "Good morning",
            "source": "en",
            "target": "hi",
            "provider": "googletrans",
            "text_format": "plain",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "en-IN"
    assert data["target"] == "hi-IN"
    assert data["provider"] == "googletrans"
    assert len(data["text"]) > 0


def test_translate_text_sarvam(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from indic_language_utils.translation.models import ProviderTranslationResult
    from indic_language_utils.translation.sarvam_translate import SarvamTranslationProvider

    async def mock_translate_batch(
        self: object,
        texts: tuple[str, ...],
        *,
        source: object,
        target: object,
        options: object,
        request_id: str,
    ) -> ProviderTranslationResult:
        return ProviderTranslationResult(
            tuple(f"sarvam_translated:{t}" for t in texts),
            service_id=None,
            model_id="sarvam-translate:v1",
            request_id=request_id,
        )

    monkeypatch.setattr(SarvamTranslationProvider, "translate_batch", mock_translate_batch)
    monkeypatch.setenv("SARVAM_API_KEY", "mock-key")

    response = client.post(
        "/api/translate",
        json={
            "text": "Good morning",
            "source": "en",
            "target": "hi",
            "provider": "sarvam",
            "text_format": "plain",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "en-IN"
    assert data["target"] == "hi-IN"
    assert data["provider"] == "sarvam"
    assert data["text"] == "sarvam_translated:Good morning"


def test_translate_invalid_provider(client: TestClient) -> None:
    response = client.post(
        "/api/translate",
        json={
            "text": "Good morning",
            "source": "en",
            "target": "hi",
            "provider": "nonexistent_provider_12345",
        },
    )
    assert response.status_code == 400


def test_translate_invalid_language(client: TestClient) -> None:
    response = client.post(
        "/api/translate",
        json={
            "text": "Good morning",
            "source": "invalid_lang_xyz",
            "target": "hi",
        },
    )
    assert response.status_code == 400


def test_transliterate_text(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from indic_language_utils.transliteration.bhashini_transliterate import (
        BhashiniTransliterationProvider,
    )
    from indic_language_utils.transliteration.models import ProviderTransliterationResult

    async def mock_transliterate_batch(
        self: object,
        texts: tuple[str, ...],
        *,
        source: object,
        target: object,
        options: object,
        request_id: str,
    ) -> ProviderTransliterationResult:
        return ProviderTransliterationResult(
            tuple(f"xlit:{t}" for t in texts),
            service_id="service-1",
            model_id="bhashini-xlit",
            request_id=request_id,
        )

    monkeypatch.setattr(
        BhashiniTransliterationProvider, "transliterate_batch", mock_transliterate_batch
    )
    monkeypatch.setenv("BHASHINI_API_KEY", "mock-key")
    monkeypatch.setenv("BHASHINI_TRANSLITERATION_SERVICE_ID", "service-1")

    response = client.post(
        "/api/transliterate",
        json={
            "text": "namaste",
            "source": "en",
            "target": "hi",
            "provider": "bhashini",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "en-IN"
    assert data["target"] == "hi-IN"
    assert data["provider"] == "bhashini"
    assert data["text"] == "xlit:namaste"


def test_transliterate_invalid_provider(client: TestClient) -> None:
    response = client.post(
        "/api/transliterate",
        json={
            "text": "namaste",
            "source": "en",
            "target": "hi",
            "provider": "nonexistent_xlit_prov",
        },
    )
    assert response.status_code == 400


@pytest.mark.skipif(not HAVE_AKSHARAMUKHA, reason="aksharamukha library is not installed")
def test_transliterate_aksharamukha_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/transliterate",
        json={
            "text": "வணக்கம்",
            "source": "ta",
            "target": "hi",
            "provider": "aksharamukha",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "aksharamukha"
    assert data["text"] == "वणक्कम्"


def test_transliterate_aksharamukha_when_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "indic_language_utils.transliteration.aksharamukha.HAVE_AKSHARAMUKHA", False
    )
    response = client.post(
        "/api/transliterate",
        json={
            "text": "வணக்கம்",
            "source": "ta",
            "target": "hi",
            "provider": "aksharamukha",
        },
    )
    assert response.status_code == 400
    assert "not available" in response.json()["detail"]


def test_static_ui_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Indic Language Utils" in response.text
