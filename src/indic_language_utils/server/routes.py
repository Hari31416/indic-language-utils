"""API endpoints for indic-language-utils backend."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..detection import (
    DetectionOptions,
    DetectionRequest,
    detect_script,
    get_detection_client,
)
from ..detection.client import DetectionClient
from ..detection.fasttext import HAVE_FASTTEXT
from ..errors import LanguageUtilsError
from ..languages import DEFAULT_LANGUAGE_REGISTRY
from ..providers import CapabilityId
from ..routing import OrderedRouter
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
from ..transliteration.client import TransliterationClient
from ..transliteration.indicxlit import HAVE_INDICXLIT

logger = logging.getLogger(__name__)

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


class TranslateRequestBody(BaseModel):
    text: str = Field(..., min_length=1, description="Text to translate")
    source: str = Field(..., description="Source language code (e.g., 'en', 'hi')")
    target: str = Field(..., description="Target language code (e.g., 'hi', 'ta')")
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
async def list_providers() -> ProvidersResponse:
    env = _get_env_overrides()
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
            details=sarvam_model
            if has_sarvam_key
            else "Requires SARVAM_API_KEY environment variable",
        ),
        ProviderInfo(
            id="bhashini",
            name="Bhashini (IndicTrans2)",
            available=has_bhashini_key,
            details=bhashini_service_id
            if has_bhashini_key
            else "Requires BHASHINI_API_KEY environment variable",
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
            details="Language Identification (LID)"
            if has_sarvam_key
            else "Requires SARVAM_API_KEY environment variable",
        ),
        ProviderInfo(
            id="bhashini",
            name="Bhashini Detection",
            available=has_bhashini_key and bool(bhashini_detect_id),
            details=bhashini_detect_id
            if (has_bhashini_key and bhashini_detect_id)
            else "Requires BHASHINI_API_KEY and BHASHINI_DETECTION_SERVICE_ID",
        ),
    ]

    bhashini_translit_id = env.get("BHASHINI_TRANSLITERATION_SERVICE_ID")
    transliteration_providers: list[ProviderInfo] = [
        ProviderInfo(
            id="bhashini",
            name="Bhashini Transliteration",
            available=has_bhashini_key and bool(bhashini_translit_id),
            details=bhashini_translit_id
            if (has_bhashini_key and bhashini_translit_id)
            else "Requires BHASHINI_API_KEY and BHASHINI_TRANSLITERATION_SERVICE_ID",
        ),
        ProviderInfo(
            id="indicxlit",
            name="AI4Bharat IndicXlit",
            available=HAVE_INDICXLIT,
            details="Local offline model (IndicXlit)",
        ),
    ]

    return ProvidersResponse(
        translation=translation_providers,
        detection=detection_providers,
        transliteration=transliteration_providers,
    )


@router.post("/translate", response_model=TranslateResponseBody)
async def translate_text(body: TranslateRequestBody) -> TranslateResponseBody:
    env = _get_env_overrides()
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
            request = TranslationRequest(
                body.text,
                body.source,
                body.target,
                options=options,
            )
            result = await client.translate(request)
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
async def detect_language(body: DetectRequestBody) -> DetectResponseBody:
    env = _get_env_overrides()
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
            request = DetectionRequest(body.text, options=options)
            result = await client.detect(request)
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
async def detect_script_endpoint(body: ScriptDetectRequestBody) -> ScriptDetectResponseBody:
    script = detect_script(body.text)
    return ScriptDetectResponseBody(script=script)


class TransliterateRequestBody(BaseModel):
    text: str = Field(..., min_length=1, description="Text to transliterate")
    source: str = Field(..., description="Source language code (e.g., 'en', 'hi')")
    target: str = Field(..., description="Target language code (e.g., 'hi', 'ta')")
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
async def transliterate_text(body: TransliterateRequestBody) -> TransliterateResponseBody:
    env = _get_env_overrides()
    try:
        base_client = get_transliteration_client(env=env)
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
            request = TransliterationRequest(
                body.text,
                source=body.source,
                target=body.target,
                options=options,
            )
            result = await client.transliterate(request)
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
