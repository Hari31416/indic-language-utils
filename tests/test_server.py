from __future__ import annotations

from pathlib import Path

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


def test_invalid_edge_tts_settings_are_visible(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from indic_language_utils.server import routes

    monkeypatch.setattr(routes, "_get_env_overrides", lambda: {"EDGE_TTS_TIMEOUT_SECONDS": "0"})
    response = client.get("/api/providers")
    assert response.status_code == 200
    edge = next(item for item in response.json()["text_to_speech"] if item["id"] == "edge_tts")
    assert edge["available"] is False
    assert "Invalid configuration" in edge["details"]


def test_navana_is_listed_as_tts_only_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from indic_language_utils.server import routes

    monkeypatch.setattr(routes, "_get_env_overrides", lambda: {"NAVANA_API_KEY": "test-key"})
    response = client.get("/api/providers")
    navana = next(item for item in response.json()["text_to_speech"] if item["id"] == "navana")
    assert navana["available"] is True
    assert "navana" not in [item["id"] for item in response.json()["speech_to_text"]]


@pytest.mark.parametrize(
    "overrides",
    [
        {"NAVANA_ENDPOINT_URL": "ftp://tts.navana.ai"},
        {"NAVANA_TIMEOUT_SECONDS": "invalid"},
        {"NAVANA_MAX_CONCURRENCY": "0"},
    ],
)
def test_navana_invalid_configuration_is_not_reported_available(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, str],
) -> None:
    from indic_language_utils.server import routes

    monkeypatch.setattr(
        routes,
        "_get_env_overrides",
        lambda: {"NAVANA_API_KEY": "test-key", **overrides},
    )
    response = client.get("/api/providers")
    navana = next(item for item in response.json()["text_to_speech"] if item["id"] == "navana")
    assert navana["available"] is False
    assert navana["details"] != "Requires NAVANA_API_KEY"


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
    from indic_language_utils.translation.google_translate import (
        GoogleTranslateProvider,
    )
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
    from indic_language_utils.translation.sarvam_translate import (
        SarvamTranslationProvider,
    )

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
    from indic_language_utils.transliteration.models import (
        ProviderTransliterationResult,
    )

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


def test_stt_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import base64

    from indic_language_utils.server import routes
    from indic_language_utils.stt.bhashini import BhashiniSTTProvider
    from indic_language_utils.stt.models import ProviderSTTResult

    monkeypatch.setattr(
        routes,
        "_get_env_overrides",
        lambda: {
            "BHASHINI_API_KEY": "test-key",
            "BHASHINI_ENDPOINT_URL": "https://example.test/inference",
            "BHASHINI_STT_MODEL_ID": "default-asr",
        },
    )

    seen_languages: list[object] = []

    async def mock_transcribe_batch(
        self: BhashiniSTTProvider,
        audio: tuple[bytes, ...],
        *,
        language: object,
        audio_format: str,
        sampling_rate: int,
        request_id: str,
    ) -> tuple[ProviderSTTResult, ...]:
        seen_languages.append(language)
        assert audio == (b"test-audio",)
        assert audio_format == "wav"
        assert sampling_rate == 16000
        return (ProviderSTTResult("नमस्ते", "default-asr", "provider-123"),)

    monkeypatch.setattr(BhashiniSTTProvider, "transcribe_batch", mock_transcribe_batch)
    providers = client.get("/api/providers").json()["speech_to_text"]
    assert providers[0]["available"] is True

    response = client.post(
        "/api/stt",
        json={
            "audio_base64": base64.b64encode(b"test-audio").decode(),
            "language": "hi",
            "audio_format": "wav",
            "sampling_rate": 16000,
            "provider": "bhashini",
        },
    )
    assert response.status_code == 200
    assert response.json()["text"] == "नमस्ते"
    assert response.json()["model_id"] == "default-asr"
    assert response.json()["language"] == "hi-IN"
    assert response.json()["cached"] is False
    assert response.json()["cache_backend"] == "none"

    no_language = client.post(
        "/api/stt",
        json={"audio_base64": base64.b64encode(b"test-audio").decode()},
    )
    assert no_language.status_code == 200
    assert no_language.json()["language"] is None
    assert len(seen_languages) == 2
    assert seen_languages[1] is None


def test_stt_rejects_bad_audio(client: TestClient) -> None:
    response = client.post(
        "/api/stt",
        json={"audio_base64": "not base64", "language": "hi"},
    )
    assert response.status_code == 400


def test_tts_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import base64

    from indic_language_utils.server import routes
    from indic_language_utils.tts.bhashini import BhashiniTTSProvider
    from indic_language_utils.tts.models import ProviderTTSResult, TTSOptions

    monkeypatch.setattr(
        routes,
        "_get_env_overrides",
        lambda: {
            "BHASHINI_API_KEY": "test-key",
            "BHASHINI_ENDPOINT_URL": "https://example.test/inference",
            "BHASHINI_TTS_MODEL_ID": "test-tts",
            "ILU_CACHE_ENABLED": "false",
        },
    )

    async def mock_synthesize_batch(
        self: BhashiniTTSProvider,
        texts: tuple[str, ...],
        *,
        language: object,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]:
        assert texts == ("Hello",)
        assert language is None
        assert options.parameters == {"gender": "female", "tone": "calm"}
        return (ProviderTTSResult(b"fake-wav", "wav", "test-tts", "provider-123"),)

    monkeypatch.setattr(BhashiniTTSProvider, "synthesize_batch", mock_synthesize_batch)
    response = client.post(
        "/api/tts",
        json={"text": "Hello", "parameters": {"gender": "female", "tone": "calm"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert base64.b64decode(data["audio_base64"]) == b"fake-wav"
    assert data["audio_format"] == "wav"
    assert data["language"] is None
    assert data["model_id"] == "test-tts"
    assert data["cached"] is False
    assert data["cache_backend"] == "none"
    providers = client.get("/api/providers").json()["text_to_speech"]
    assert providers[0]["available"] is True
    named_response = client.post(
        "/api/tts",
        json={
            "text": "Hello",
            "provider": "bhashini",
            "provider_parameters": {"bhashini": {"gender": "female", "tone": "calm"}},
        },
    )
    assert named_response.status_code == 200


def test_explicit_navana_tts_ignores_unselected_provider_keys(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from indic_language_utils.server import routes
    from indic_language_utils.tts.models import ProviderTTSResult, TTSOptions
    from indic_language_utils.tts.navana import NavanaTTSProvider

    monkeypatch.setattr(
        routes,
        "_get_env_overrides",
        lambda: {
            "NAVANA_API_KEY": "navana-test-key",
            "BHASHINI_API_KEY": "incomplete-bhashini-key",
            "ILU_CACHE_ENABLED": "false",
        },
    )

    async def mock_synthesize_batch(
        self: NavanaTTSProvider,
        texts: tuple[str, ...],
        *,
        language: object,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]:
        assert texts == ("Hello",)
        assert language is not None
        assert options.parameters["voice"] == "achu"
        return (ProviderTTSResult(b"RIFFfake", "wav", None, "navana-provider-1"),)

    monkeypatch.setattr(NavanaTTSProvider, "synthesize_batch", mock_synthesize_batch)
    response = client.post(
        "/api/tts",
        json={
            "text": "Hello",
            "language": "en",
            "provider": "navana",
            "parameters": {"voice": "achu"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "navana"
    assert data["audio_format"] == "wav"


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_tts_endpoint_uses_cache(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, backend: str
) -> None:
    from indic_language_utils.server import routes
    from indic_language_utils.tts.bhashini import BhashiniTTSProvider
    from indic_language_utils.tts.models import ProviderTTSResult, TTSOptions

    monkeypatch.setattr(
        routes,
        "_get_env_overrides",
        lambda: {
            "BHASHINI_API_KEY": "test-key",
            "BHASHINI_ENDPOINT_URL": "https://example.test/inference",
            "BHASHINI_TTS_MODEL_ID": "test-tts",
            "ILU_CACHE_ENABLED": "true",
            "ILU_CACHE_BACKEND": backend,
            "ILU_CACHE_PATH": str(tmp_path / "tts.sqlite3"),
        },
    )
    calls: list[str] = []

    async def mock_synthesize_batch(
        self: BhashiniTTSProvider,
        texts: tuple[str, ...],
        *,
        language: object,
        options: TTSOptions,
        request_id: str,
    ) -> tuple[ProviderTTSResult, ...]:
        calls.extend(texts)
        return (ProviderTTSResult(b"cached-audio", "wav", "test-tts", "provider-123"),)

    monkeypatch.setattr(BhashiniTTSProvider, "synthesize_batch", mock_synthesize_batch)
    first = client.post("/api/tts", json={"text": "Repeat", "provider": "bhashini"})
    second = client.post("/api/tts", json={"text": "Repeat", "provider": "bhashini"})

    assert first.status_code == second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert second.json()["cache_backend"] == (
        "MemoryCache" if backend == "memory" else "SQLiteCache"
    )
    assert second.json()["provider_request_id"] is None
    assert first.json()["request_id"] != second.json()["request_id"]
    assert calls == ["Repeat"]


def test_tts_rejects_reserved_parameters(client: TestClient) -> None:
    response = client.post("/api/tts", json={"text": "Hello", "parameters": {"serviceId": "other"}})
    assert response.status_code == 400


def test_client_api_key_headers_enable_providers(client: TestClient) -> None:
    response = client.get(
        "/api/providers",
        headers={
            "x-sarvam-api-key": "test-sarvam-key",
            "x-bhashini-api-key": "test-bhashini-key",
        },
    )
    assert response.status_code == 200
    data = response.json()
    sarvam_trans = next(p for p in data["translation"] if p["id"] == "sarvam")
    assert sarvam_trans["available"] is True
    bhashini_trans = next(p for p in data["translation"] if p["id"] == "bhashini")
    assert bhashini_trans["available"] is True
