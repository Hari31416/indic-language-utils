"""API endpoints for indic-language-utils backend."""

from __future__ import annotations

import base64
import binascii
import logging
import os
from dataclasses import replace
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import Settings
from ..detection import (
    DetectionOptions,
    DetectionRequest,
    detect_script,
    get_detection_client,
)
from ..detection.client import DetectionClient
from ..detection.fasttext import HAVE_FASTTEXT
from ..errors import ConfigurationError, LanguageUtilsError
from ..languages import DEFAULT_LANGUAGE_REGISTRY
from ..providers import CapabilityId
from ..providers.bhashini import BhashiniConfig
from ..providers.navana import NavanaConfig
from ..providers.sarvam import SarvamConfig
from ..routing import OrderedRouter
from ..stt import (
    HAVE_FASTER_WHISPER,
    HAVE_SPEECH_RECOGNITION,
    STTClient,
    STTRequest,
    get_stt_client,
)
from ..translation import (
    TextFormat,
    TranslationOptions,
    TranslationRequest,
    get_translation_client,
)
from ..translation.client import TranslationClient
from ..translation.google_translate import HAVE_GOOGLETRANS
from ..transliteration import (
    TransliterationOptions,
    TransliterationRequest,
    get_transliteration_client,
)
from ..transliteration.aksharamukha import HAVE_AKSHARAMUKHA
from ..transliteration.client import TransliterationClient
from ..transliteration.indicxlit import HAVE_INDICXLIT
from ..tts import HAVE_EDGE_TTS, TTSClient, TTSOptions, TTSRequest, create_tts_cache, get_tts_client
from ..tts.edge_tts import EdgeTTSConfig

logger = logging.getLogger(__name__)
MAX_STT_AUDIO_BYTES = 10 * 1024 * 1024

router = APIRouter(prefix="/api")


def _get_env_overrides() -> dict[str, str]:
    env = dict(os.environ)
    env_file = Path(".env")
    if env_file.is_file():
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip("'\"")
        except OSError as exc:
            logger.warning("Could not read .env file: %s", exc)
    return env


def _apply_request_overrides(env: dict[str, str], request: Request | None) -> dict[str, str]:
    if request is not None:
        sarvam_key = request.headers.get("x-sarvam-api-key")
        if sarvam_key:
            env["SARVAM_API_KEY"] = sarvam_key.strip()
        sarvam_endpoint = request.headers.get("x-sarvam-endpoint")
        if sarvam_endpoint:
            env["SARVAM_ENDPOINT_URL"] = sarvam_endpoint.strip()

        bhashini_key = request.headers.get("x-bhashini-api-key")
        if bhashini_key:
            env["BHASHINI_API_KEY"] = bhashini_key.strip()
        bhashini_endpoint = request.headers.get("x-bhashini-endpoint")
        if bhashini_endpoint:
            env["BHASHINI_ENDPOINT_URL"] = bhashini_endpoint.strip()
        navana_key = request.headers.get("x-navana-api-key")
        if navana_key:
            env["NAVANA_API_KEY"] = navana_key.strip()
        navana_endpoint = request.headers.get("x-navana-endpoint")
        if navana_endpoint:
            env["NAVANA_ENDPOINT_URL"] = navana_endpoint.strip()
    return env


class LanguageItem(BaseModel):
    tag: str
    code: str
    name: str
    script: str | None = None
    region: str | None = None


class LanguagesResponse(BaseModel):
    languages: list[LanguageItem]


class ProviderInfo(BaseModel):
    id: str
    name: str
    available: bool
    details: str


class ProvidersResponse(BaseModel):
    translation: list[ProviderInfo]
    detection: list[ProviderInfo]
    transliteration: list[ProviderInfo]
    speech_to_text: list[ProviderInfo]
    text_to_speech: list[ProviderInfo]


class TTSRequestBody(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize")
    language: str | None = Field(default=None, description="Optional output language")
    model_id: str | None = Field(default=None, description="Optional model ID or voice ID override")
    api_key: str | None = Field(default=None, description="Optional API key override")
    parameters: dict[str, object] = Field(
        default_factory=dict, description="Settings for the first selected TTS provider"
    )
    provider_parameters: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="Provider-specific settings used on each route",
    )
    provider: str | None = Field(default=None, description="Provider ID or null for auto routing")


class TTSResponseBody(BaseModel):
    audio_base64: str
    audio_format: str | None
    language: str | None
    provider: str
    model_id: str | None
    request_id: str
    provider_request_id: str | None
    fallback_count: int
    cached: bool
    cache_backend: str


class STTRequestBody(BaseModel):
    audio_base64: str = Field(
        ...,
        min_length=1,
        max_length=14_000_000,
        description="Base64-encoded audio bytes",
    )
    language: str | None = Field(default=None, description="Optional source language code")
    model_id: str | None = Field(default=None, description="Optional model ID override")
    api_key: str | None = Field(default=None, description="Optional API key override")
    audio_format: str = Field(default="wav", description="Audio container format")
    sampling_rate: int = Field(default=16000, gt=0, description="Audio sample rate in Hz")
    provider: str | None = Field(default=None, description="Provider ID or null for auto routing")


class STTResponseBody(BaseModel):
    text: str
    language: str | None
    provider: str
    model_id: str | None = None
    request_id: str
    provider_request_id: str | None = None
    fallback_count: int
    cached: bool
    cache_backend: str


class TranslateRequestBody(BaseModel):
    text: str = Field(..., min_length=1, description="Text to translate")
    source: str = Field(..., description="Source language code (e.g., 'en', 'hi')")
    target: str = Field(..., description="Target language code (e.g., 'hi', 'ta')")
    model_id: str | None = Field(
        default=None, description="Optional model ID / service ID override"
    )
    api_key: str | None = Field(default=None, description="Optional API key override")
    provider: str | None = Field(default=None, description="Provider ID or null for auto routing")
    text_format: str = Field(default="plain", description="'plain' or 'markdown'")


class TranslateResponseBody(BaseModel):
    text: str
    source: str
    target: str
    provider: str
    service_id: str | None = None
    model_id: str | None = None
    unofficial: bool = False
    elapsed_seconds: float
    cached: bool
    cache_backend: str | None = None
    warnings: list[str] = Field(default_factory=list)


class DetectRequestBody(BaseModel):
    text: str = Field(..., min_length=1, description="Text to detect language for")
    model_id: str | None = Field(default=None, description="Optional model ID override")
    api_key: str | None = Field(default=None, description="Optional API key override")
    provider: str | None = Field(default=None, description="Provider ID or null for auto routing")


class DetectCandidateItem(BaseModel):
    language: str
    name: str | None = None
    confidence: float
    script: str | None = None


class DetectResponseBody(BaseModel):
    language: str | None
    language_name: str | None = None
    script: str | None
    candidates: list[DetectCandidateItem]
    provider: str
    model_id: str | None = None
    unofficial: bool = False
    elapsed_seconds: float
    cached: bool


class ScriptDetectRequestBody(BaseModel):
    text: str = Field(..., min_length=1, description="Text to identify script for")


class ScriptDetectResponseBody(BaseModel):
    script: str | None


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "indic-language-utils"}


@router.get("/languages", response_model=LanguagesResponse)
async def list_languages() -> LanguagesResponse:
    languages: list[LanguageItem] = []
    for definition in sorted(DEFAULT_LANGUAGE_REGISTRY.definitions(), key=lambda d: d.name):
        languages.append(
            LanguageItem(
                tag=str(definition.tag),
                code=definition.tag.language,
                name=definition.name,
                script=definition.tag.script,
                region=definition.tag.region,
            )
        )
    return LanguagesResponse(languages=languages)


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(request: Request) -> ProvidersResponse:
    env = _apply_request_overrides(_get_env_overrides(), request)
    has_bhashini_key = bool(env.get("BHASHINI_API_KEY"))
    bhashini_service_id = env.get(
        "BHASHINI_TRANSLATION_SERVICE_ID", "ai4bharat/indictrans-v2-all-gpu--t4"
    )
    bhashini_detect_id = env.get("BHASHINI_DETECTION_SERVICE_ID") or env.get(
        "BHASHINI_TLD_SERVICE_ID"
    )

    has_sarvam_key = bool(env.get("SARVAM_API_KEY"))
    sarvam_model = env.get("SARVAM_MODEL", "sarvam-translate:v1")

    translation_providers: list[ProviderInfo] = [
        ProviderInfo(
            id="sarvam",
            name="Sarvam AI",
            available=has_sarvam_key,
            details=(
                sarvam_model if has_sarvam_key else "Requires SARVAM_API_KEY environment variable"
            ),
        ),
        ProviderInfo(
            id="bhashini",
            name="Bhashini (IndicTrans2)",
            available=has_bhashini_key,
            details=(
                bhashini_service_id
                if has_bhashini_key
                else "Requires BHASHINI_API_KEY environment variable"
            ),
        ),
        ProviderInfo(
            id="googletrans",
            name="Google Translate",
            available=HAVE_GOOGLETRANS,
            details="Web endpoint (unofficial)",
        ),
    ]

    detection_providers: list[ProviderInfo] = [
        ProviderInfo(
            id="fasttext",
            name="FastText (lid.176)",
            available=HAVE_FASTTEXT,
            details="Local offline model",
        ),
        ProviderInfo(
            id="sarvam",
            name="Sarvam Detection",
            available=has_sarvam_key,
            details=(
                "Language Identification (LID)"
                if has_sarvam_key
                else "Requires SARVAM_API_KEY environment variable"
            ),
        ),
        ProviderInfo(
            id="bhashini",
            name="Bhashini Detection",
            available=has_bhashini_key and bool(bhashini_detect_id),
            details=(
                bhashini_detect_id
                if (has_bhashini_key and bhashini_detect_id)
                else "Requires BHASHINI_API_KEY and BHASHINI_DETECTION_SERVICE_ID"
            ),
        ),
    ]

    bhashini_translit_id = env.get("BHASHINI_TRANSLITERATION_SERVICE_ID")
    transliteration_providers: list[ProviderInfo] = [
        ProviderInfo(
            id="aksharamukha",
            name="Aksharamukha",
            available=HAVE_AKSHARAMUKHA,
            details="Offline pure-Python engine (120+ scripts)",
        ),
        ProviderInfo(
            id="bhashini",
            name="Bhashini Transliteration",
            available=has_bhashini_key and bool(bhashini_translit_id),
            details=(
                bhashini_translit_id
                if (has_bhashini_key and bhashini_translit_id)
                else "Requires BHASHINI_API_KEY and BHASHINI_TRANSLITERATION_SERVICE_ID"
            ),
        ),
        ProviderInfo(
            id="indicxlit",
            name="AI4Bharat IndicXlit",
            available=HAVE_INDICXLIT,
            details="Local offline model (IndicXlit)",
        ),
    ]

    stt_model_summary: str | None = None
    tts_model_summary: str | None = None
    sarvam_stt_summary: str | None = None
    sarvam_tts_summary: str | None = None
    if has_bhashini_key:
        try:
            stt_config = BhashiniConfig.from_settings(Settings.load(env=env), env=env)
            if stt_config.stt_model_id or stt_config.stt_model_ids:
                model_count = len(stt_config.stt_model_ids)
                stt_model_summary = f"{model_count} language model(s)" + (
                    f", default: {stt_config.stt_model_id}" if stt_config.stt_model_id else ""
                )
            if stt_config.tts_model_id or stt_config.tts_model_ids:
                model_count = len(stt_config.tts_model_ids)
                tts_model_summary = f"{model_count} language model(s)" + (
                    f", default: {stt_config.tts_model_id}" if stt_config.tts_model_id else ""
                )
        except ConfigurationError:
            pass
    if has_sarvam_key:
        try:
            sarvam_config = SarvamConfig.from_settings(Settings.load(env=env), env=env)
            sarvam_stt_summary = sarvam_config.stt_model_id or (
                f"{len(sarvam_config.stt_model_ids)} language model(s)"
                if sarvam_config.stt_model_ids
                else None
            )
            sarvam_tts_summary = sarvam_config.tts_model_id or (
                f"{len(sarvam_config.tts_model_ids)} language model(s)"
                if sarvam_config.tts_model_ids
                else None
            )
        except ConfigurationError:
            pass
    navana_configured = False
    navana_details = "Requires NAVANA_API_KEY"
    if env.get("NAVANA_API_KEY"):
        try:
            NavanaConfig.from_settings(Settings.load(env=env), env=env)
            navana_configured = True
            navana_details = "Non-streaming and WebSocket synthesis"
        except ConfigurationError as exc:
            navana_details = str(exc)
    edge_tts_error: str | None = None
    if HAVE_EDGE_TTS:
        try:
            EdgeTTSConfig.from_settings(Settings.load(env=env), env=env)
        except ConfigurationError as exc:
            edge_tts_error = str(exc)
    stt_providers = [
        ProviderInfo(
            id="bhashini",
            name="Bhashini ASR",
            available=stt_model_summary is not None,
            details=stt_model_summary or "Requires BHASHINI_API_KEY, endpoint, and an STT model ID",
        ),
        ProviderInfo(
            id="sarvam",
            name="Sarvam STT",
            available=sarvam_stt_summary is not None,
            details=sarvam_stt_summary or "Requires SARVAM_API_KEY and an STT model ID",
        ),
        ProviderInfo(
            id="google_free",
            name="Google Free STT",
            available=HAVE_SPEECH_RECOGNITION,
            details=(
                "Unofficial Google Web Speech via SpeechRecognition"
                if HAVE_SPEECH_RECOGNITION
                else "Requires 'SpeechRecognition' package"
            ),
        ),
        ProviderInfo(
            id="faster_whisper",
            name="Faster Whisper",
            available=HAVE_FASTER_WHISPER,
            details=(
                "Local offline STT via faster-whisper"
                if HAVE_FASTER_WHISPER
                else "Requires 'faster-whisper' package"
            ),
        ),
    ]
    tts_providers = [
        ProviderInfo(
            id="edge_tts",
            name="Microsoft Edge TTS",
            available=HAVE_EDGE_TTS and edge_tts_error is None,
            details=(
                f"Invalid configuration: {edge_tts_error}"
                if edge_tts_error
                else (
                    "Free online TTS via Microsoft Edge neural voices"
                    if HAVE_EDGE_TTS
                    else "Requires 'edge-tts' package"
                )
            ),
        ),
        ProviderInfo(
            id="bhashini",
            name="Bhashini TTS",
            available=tts_model_summary is not None,
            details=tts_model_summary or "Requires BHASHINI_API_KEY, endpoint, and a TTS model ID",
        ),
        ProviderInfo(
            id="sarvam",
            name="Sarvam TTS",
            available=sarvam_tts_summary is not None,
            details=sarvam_tts_summary or "Requires SARVAM_API_KEY and a TTS model ID",
        ),
        ProviderInfo(
            id="navana",
            name="Navana AI TTS",
            available=navana_configured,
            details=navana_details,
        ),
    ]

    return ProvidersResponse(
        translation=translation_providers,
        detection=detection_providers,
        transliteration=transliteration_providers,
        speech_to_text=stt_providers,
        text_to_speech=tts_providers,
    )


@router.post("/translate", response_model=TranslateResponseBody)
async def translate_text(body: TranslateRequestBody, request: Request) -> TranslateResponseBody:
    env = _apply_request_overrides(_get_env_overrides(), request)
    if body.api_key:
        if body.provider == "sarvam":
            env["SARVAM_API_KEY"] = body.api_key
        elif body.provider == "bhashini":
            env["BHASHINI_API_KEY"] = body.api_key
        else:
            env["SARVAM_API_KEY"] = body.api_key
            env["BHASHINI_API_KEY"] = body.api_key

    if body.model_id:
        if body.provider == "sarvam" or not body.provider or body.provider == "auto":
            env["SARVAM_MODEL"] = body.model_id
        if body.provider == "bhashini" or not body.provider or body.provider == "auto":
            env["BHASHINI_TRANSLATION_SERVICE_ID"] = body.model_id

    try:
        base_client = get_translation_client(env=env)
    except Exception as exc:
        logger.error("Failed to initialize translation client: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Translation setup error: {exc}") from exc

    client: TranslationClient = base_client
    if body.provider and body.provider != "auto":
        available_names = {p.identity.provider for p in base_client.router.registry.all()}
        if body.provider not in available_names:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{body.provider}' is not available or registered.",
            )
        custom_router = OrderedRouter(
            base_client.router.registry,
            {CapabilityId.TRANSLATION: (body.provider,)},
        )
        client = TranslationClient(
            custom_router,
            cache=base_client._cache,
            processors=base_client._processors,
            catalog=base_client._catalog,
        )

    text_format = TextFormat.MARKDOWN if body.text_format == "markdown" else TextFormat.PLAIN
    options = TranslationOptions(text_format=text_format)

    try:
        async with client:
            request_obj = TranslationRequest(
                body.text,
                body.source,
                body.target,
                options=options,
            )
            result = await client.translate(request_obj)
    except LanguageUtilsError as exc:
        logger.warning("Translation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected translation error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Translation failed: {exc}") from exc

    return TranslateResponseBody(
        text=result.text,
        source=str(result.source),
        target=str(result.target),
        provider=result.provider.provider,
        service_id=result.provider.service_id,
        model_id=result.provider.model_id,
        unofficial=result.provider.unofficial,
        elapsed_seconds=round(result.elapsed_seconds, 4),
        cached=result.cache.hit,
        cache_backend=result.cache.backend,
        warnings=[w.message for w in result.warnings],
    )


@router.post("/detect", response_model=DetectResponseBody)
async def detect_language(body: DetectRequestBody, request: Request) -> DetectResponseBody:
    env = _apply_request_overrides(_get_env_overrides(), request)
    if body.api_key:
        if body.provider == "sarvam":
            env["SARVAM_API_KEY"] = body.api_key
        elif body.provider == "bhashini":
            env["BHASHINI_API_KEY"] = body.api_key
        else:
            env["SARVAM_API_KEY"] = body.api_key
            env["BHASHINI_API_KEY"] = body.api_key

    if body.model_id:
        if body.provider == "bhashini" or not body.provider or body.provider == "auto":
            env["BHASHINI_DETECTION_SERVICE_ID"] = body.model_id
            env["BHASHINI_TLD_SERVICE_ID"] = body.model_id

    try:
        base_client = get_detection_client(env=env)
    except Exception as exc:
        logger.error("Failed to initialize detection client: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection setup error: {exc}") from exc

    client: DetectionClient = base_client
    if body.provider and body.provider != "auto":
        available_names = {p.identity.provider for p in base_client.router.registry.all()}
        if body.provider not in available_names:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{body.provider}' is not available or registered.",
            )
        custom_router = OrderedRouter(
            base_client.router.registry,
            {CapabilityId.TEXT_LANGUAGE_DETECTION: (body.provider,)},
        )
        client = DetectionClient(
            custom_router,
            cache=base_client._cache,
        )

    options = DetectionOptions(threshold=0.0, max_candidates=5)

    try:
        async with client:
            request_obj = DetectionRequest(body.text, options=options)
            result = await client.detect(request_obj)
    except LanguageUtilsError as exc:
        logger.warning("Detection error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected detection error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {exc}") from exc

    script_found = result.script or detect_script(body.text)

    # Resolve language names for candidates
    candidates_list: list[DetectCandidateItem] = []
    for cand in result.candidates:
        cand_tag = str(cand.language)
        name: str | None = None
        try:
            norm_tag = DEFAULT_LANGUAGE_REGISTRY.normalize(cand_tag)
            for defn in DEFAULT_LANGUAGE_REGISTRY.definitions():
                if defn.tag.language == norm_tag.language:
                    name = defn.name
                    break
        except Exception:
            name = None

        candidates_list.append(
            DetectCandidateItem(
                language=cand_tag,
                name=name,
                confidence=round(cand.confidence, 4),
                script=cand.script,
            )
        )

    top_lang_str = str(result.language) if result.language else None
    top_lang_name: str | None = None
    if top_lang_str:
        try:
            norm_tag = DEFAULT_LANGUAGE_REGISTRY.normalize(top_lang_str)
            for defn in DEFAULT_LANGUAGE_REGISTRY.definitions():
                if defn.tag.language == norm_tag.language:
                    top_lang_name = defn.name
                    break
        except Exception:
            pass

    return DetectResponseBody(
        language=top_lang_str,
        language_name=top_lang_name,
        script=script_found,
        candidates=candidates_list,
        provider=result.provider.provider,
        model_id=result.provider.model_id,
        unofficial=result.provider.unofficial,
        elapsed_seconds=round(result.elapsed_seconds, 4),
        cached=result.cache.hit,
    )


@router.post("/detect-script", response_model=ScriptDetectResponseBody)
async def detect_script_endpoint(
    body: ScriptDetectRequestBody,
) -> ScriptDetectResponseBody:
    script = detect_script(body.text)
    return ScriptDetectResponseBody(script=script)


class TransliterateRequestBody(BaseModel):
    text: str = Field(..., min_length=1, description="Text to transliterate")
    source: str = Field(..., description="Source language code (e.g., 'en', 'hi')")
    target: str = Field(..., description="Target language code (e.g., 'hi', 'ta')")
    model_id: str | None = Field(default=None, description="Optional model ID override")
    api_key: str | None = Field(default=None, description="Optional API key override")
    provider: str | None = Field(default=None, description="Provider ID or null for auto routing")


class TransliterateResponseBody(BaseModel):
    text: str
    source: str
    target: str
    provider: str
    service_id: str | None = None
    model_id: str | None = None
    unofficial: bool = False
    elapsed_seconds: float
    cached: bool
    cache_backend: str | None = None
    warnings: list[str] = Field(default_factory=list)


@router.post("/transliterate", response_model=TransliterateResponseBody)
async def transliterate_text(
    body: TransliterateRequestBody, request: Request
) -> TransliterateResponseBody:
    env = _apply_request_overrides(_get_env_overrides(), request)
    if body.api_key:
        if body.provider == "bhashini":
            env["BHASHINI_API_KEY"] = body.api_key
        else:
            env["BHASHINI_API_KEY"] = body.api_key

    if body.model_id:
        if body.provider == "bhashini" or not body.provider or body.provider == "auto":
            env["BHASHINI_TRANSLITERATION_SERVICE_ID"] = body.model_id
            env["BHASHINI_TRANSLATION_SERVICE_ID"] = body.model_id

    try:
        base_client = get_transliteration_client(env=env)
    except ConfigurationError as exc:
        if body.provider and body.provider != "auto":
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{body.provider}' is not available or registered.",
            ) from exc
        raise HTTPException(
            status_code=503, detail="Transliteration provider is not configured"
        ) from exc
    except Exception as exc:
        logger.error("Failed to initialize transliteration client: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transliteration setup error: {exc}") from exc

    client: TransliterationClient = base_client
    if body.provider and body.provider != "auto":
        available_names = {p.identity.provider for p in base_client.router.registry.all()}
        if body.provider not in available_names:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{body.provider}' is not available or registered.",
            )
        custom_router = OrderedRouter(
            base_client.router.registry,
            {CapabilityId.TRANSLITERATION: (body.provider,)},
        )
        client = TransliterationClient(
            custom_router,
            cache=base_client._cache,
        )

    options = TransliterationOptions()

    try:
        async with client:
            request_obj = TransliterationRequest(
                body.text,
                source=body.source,
                target=body.target,
                options=options,
            )
            result = await client.transliterate(request_obj)
    except LanguageUtilsError as exc:
        logger.warning("Transliteration error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected transliteration error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transliteration failed: {exc}") from exc

    return TransliterateResponseBody(
        text=result.text,
        source=str(result.source),
        target=str(result.target),
        provider=result.provider.provider,
        service_id=result.provider.service_id,
        model_id=result.provider.model_id,
        unofficial=result.provider.unofficial,
        elapsed_seconds=round(result.elapsed_seconds, 4),
        cached=result.cache.hit,
        cache_backend=result.cache.backend,
        warnings=[w.message for w in result.warnings],
    )


@router.post("/stt", response_model=STTResponseBody)
async def transcribe_audio(body: STTRequestBody, request: Request) -> STTResponseBody:
    try:
        audio = base64.b64decode(body.audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail="audio_base64 must contain valid base64"
        ) from exc
    if not audio:
        raise HTTPException(status_code=400, detail="Audio cannot be empty")
    if len(audio) > MAX_STT_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio exceeds the 10 MiB limit")

    try:
        request_obj = STTRequest(audio, body.language, body.audio_format, body.sampling_rate)
    except (LanguageUtilsError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    env = _apply_request_overrides(_get_env_overrides(), request)
    if body.api_key:
        if body.provider == "sarvam":
            env["SARVAM_API_KEY"] = body.api_key
        elif body.provider == "bhashini":
            env["BHASHINI_API_KEY"] = body.api_key
        else:
            env["SARVAM_API_KEY"] = body.api_key
            env["BHASHINI_API_KEY"] = body.api_key

    if body.model_id:
        if body.provider == "sarvam" or not body.provider or body.provider == "auto":
            env["SARVAM_STT_MODEL_ID"] = body.model_id
        if body.provider == "bhashini" or not body.provider or body.provider == "auto":
            env["BHASHINI_STT_MODEL_ID"] = body.model_id
        if body.provider == "faster_whisper" or not body.provider or body.provider == "auto":
            env["FASTER_WHISPER_MODEL"] = body.model_id
            env["WHISPER_MODEL"] = body.model_id

    try:
        base_client = get_stt_client(env=env)
    except ConfigurationError as exc:
        logger.warning("STT setup error: %s", exc)
        raise HTTPException(status_code=503, detail="STT provider is not configured") from exc

    client = base_client
    if body.provider and body.provider != "auto":
        available_names = {
            provider.identity.provider for provider in base_client.router.registry.all()
        }
        if body.provider not in available_names:
            raise HTTPException(
                status_code=400, detail=f"Provider '{body.provider}' is unavailable"
            )
        client = STTClient(
            OrderedRouter(
                base_client.router.registry,
                {CapabilityId.SPEECH_TO_TEXT: (body.provider,)},
            )
        )

    try:
        async with client:
            result = await client.transcribe(request_obj)
    except LanguageUtilsError as exc:
        logger.warning("STT error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected STT error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="STT failed") from exc

    return STTResponseBody(
        text=result.text,
        language=str(result.language) if result.language else None,
        provider=result.provider,
        model_id=result.model_id,
        request_id=result.request_id,
        provider_request_id=result.provider_request_id,
        fallback_count=result.fallback_count,
        cached=False,
        cache_backend="none",
    )


@router.post("/tts", response_model=TTSResponseBody)
async def synthesize_speech(body: TTSRequestBody, request: Request) -> TTSResponseBody:
    env = _apply_request_overrides(_get_env_overrides(), request)
    if body.api_key:
        if body.provider == "sarvam":
            env["SARVAM_API_KEY"] = body.api_key
        elif body.provider == "bhashini":
            env["BHASHINI_API_KEY"] = body.api_key
        elif body.provider == "navana":
            env["NAVANA_API_KEY"] = body.api_key
        else:
            env["SARVAM_API_KEY"] = body.api_key
            env["BHASHINI_API_KEY"] = body.api_key
            env["NAVANA_API_KEY"] = body.api_key

    if body.provider == "navana":
        env.pop("BHASHINI_API_KEY", None)
        env.pop("SARVAM_API_KEY", None)

    parameters = dict(body.parameters)
    if body.model_id:
        if body.provider == "sarvam" or not body.provider or body.provider == "auto":
            env["SARVAM_TTS_MODEL_ID"] = body.model_id
        if body.provider == "bhashini" or not body.provider or body.provider == "auto":
            env["BHASHINI_TTS_MODEL_ID"] = body.model_id
        if body.provider in ("edge_tts", "edge") or not body.provider or body.provider == "auto":
            parameters["voice"] = body.model_id
            env["EDGE_TTS_VOICE"] = body.model_id
        if body.provider == "navana":
            parameters["voice"] = body.model_id

    try:
        request_obj = TTSRequest(
            body.text,
            body.language,
            TTSOptions(parameters, body.provider_parameters),
        )
    except (LanguageUtilsError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        settings = Settings.load(env=env)
        if body.provider == "navana":
            settings = replace(
                settings,
                routes={
                    **settings.routes,
                    CapabilityId.TEXT_TO_SPEECH.value: ("navana",),
                },
            )
        cache = None
        if settings.cache.enabled and settings.cache.backend == "memory":
            memory_caches = getattr(request.app.state, "tts_memory_caches", None)
            if memory_caches is None:
                memory_caches = {}
                request.app.state.tts_memory_caches = memory_caches
            cache = memory_caches.get(settings.cache)
            if cache is None:
                cache = create_tts_cache(settings.cache)
                memory_caches[settings.cache] = cache
        base_client = get_tts_client(settings=settings, env=env, cache=cache)
    except ConfigurationError as exc:
        logger.warning("TTS setup error: %s", exc)
        raise HTTPException(status_code=503, detail="TTS provider is not configured") from exc

    client = base_client
    if body.provider and body.provider != "auto":
        target_provider = (
            "edge_tts"
            if body.provider == "edge"
            and any(p.identity.provider == "edge_tts" for p in base_client.router.registry.all())
            else body.provider
        )
        available_names = {
            provider.identity.provider for provider in base_client.router.registry.all()
        }
        if target_provider not in available_names:
            raise HTTPException(
                status_code=400, detail=f"Provider '{body.provider}' is unavailable"
            )
        client = TTSClient(
            OrderedRouter(
                base_client.router.registry,
                {CapabilityId.TEXT_TO_SPEECH: (target_provider,)},
            ),
            cache=base_client._cache,
            cache_keys=base_client._cache_keys,
        )

    try:
        async with client:
            result = await client.synthesize(request_obj)
    except LanguageUtilsError as exc:
        logger.warning("TTS error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected TTS error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="TTS failed") from exc

    return TTSResponseBody(
        audio_base64=base64.b64encode(result.audio).decode("ascii"),
        audio_format=result.audio_format,
        language=str(result.language) if result.language else None,
        provider=result.provider,
        model_id=result.model_id,
        request_id=result.request_id,
        provider_request_id=result.provider_request_id,
        fallback_count=result.fallback_count,
        cached=result.cache.hit,
        cache_backend=result.cache.backend,
    )
