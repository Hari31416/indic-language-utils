from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from indic_language_utils.server.app import create_app


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
    trans_ids = [p["id"] for p in data["translation"]]
    detect_ids = [p["id"] for p in data["detection"]]
    assert "googletrans" in trans_ids or "bhashini" in trans_ids
    assert "fasttext" in detect_ids


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


def test_translate_text(client: TestClient) -> None:
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


def test_static_ui_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Indic Language Utils" in response.text
