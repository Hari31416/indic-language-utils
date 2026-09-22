"""Google Translate (unofficial googletrans) translation adapter."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx

from .concurrency import ConcurrencyLimiter
from .config import Settings
from .errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
    MissingOptionalDependencyError,
    ProviderTimeoutError,
    RateLimitError,
    TransientProviderError,
    UnsupportedLanguagePairError,
)
from .languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from .models import ProviderIdentity
from .providers import CapabilityDeclaration, CapabilityId
from .retry import RetryPolicy, retry
from .translation.models import ProviderTranslationResult, TranslationOptions

try:
    import googletrans  # type: ignore[import-untyped]
    from googletrans import Translator

    HAVE_GOOGLETRANS = True
except ImportError:  # pragma: no cover
    HAVE_GOOGLETRANS = False
    googletrans = None
    Translator = None

logger = logging.getLogger(__name__)

# Map ILU language codes to Google Translate codes where they differ
_ILU_TO_GOOGLETRANS: dict[str, str] = {
    "kok": "gom",  # Konkani -> Goan Konkani in googletrans
    "mni": "mni-mtei",  # Manipuri -> Meiteilon in googletrans
}

# Known supported Indic language tags in googletrans
_FALLBACK_SUPPORTED_CODES: frozenset[str] = frozenset(
    {
        "as",
        "bn",
        "doi",
        "en",
        "gu",
        "hi",
        "kn",
        "kok",
        "mai",
        "ml",
        "mni",
        "mr",
        "ne",
        "or",
        "pa",
        "sa",
        "sat",
        "sd",
        "ta",
        "te",
        "ur",
    }
)


def _get_supported_tags() -> frozenset[LanguageTag]:
    tags: set[LanguageTag] = set()
    for definition in DEFAULT_LANGUAGE_REGISTRY.definitions():
        code = definition.tag.language
        gt_code = _ILU_TO_GOOGLETRANS.get(code, code)
        if HAVE_GOOGLETRANS and googletrans is not None:
            if gt_code in googletrans.LANGUAGES:
                tags.add(definition.tag)
        elif code in _FALLBACK_SUPPORTED_CODES:
            tags.add(definition.tag)
    return frozenset(tags)


def google_translate_language_code(tag: LanguageTag) -> str:
    normalized = DEFAULT_LANGUAGE_REGISTRY.normalize(tag)
    code = normalized.language
    return _ILU_TO_GOOGLETRANS.get(code, code)


@runtime_checkable
class GoogleTranslatorProtocol(Protocol):
    async def translate(
        self,
        text: str | list[str],
        dest: str = "en",
        src: str = "auto",
        **kwargs: Any,
    ) -> Any: ...

    async def __aenter__(self) -> Any: ...

    async def __aexit__(self, *args: object) -> Any: ...


@dataclass(frozen=True, slots=True)
class GoogleTranslateConfig:
    service_urls: tuple[str, ...] = ("translate.googleapis.com",)
    user_agent: str | None = None
    timeout_seconds: float = 20.0
    max_concurrency: int = 4
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.max_concurrency < 1:
            raise ConfigurationError("Google Translate timeout and concurrency must be positive")
        if not self.service_urls or any(not u.strip() for u in self.service_urls):
            raise ConfigurationError("Google Translate service URLs cannot be empty")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> GoogleTranslateConfig:
        values = os.environ if env is None else env
        try:
            timeout = float(values.get("GOOGLETRANS_TIMEOUT_SECONDS", "20"))
            concurrency = int(values.get("GOOGLETRANS_MAX_CONCURRENCY", "4"))
            urls_raw = values.get("GOOGLETRANS_SERVICE_URLS")
            urls = (
                tuple(u.strip() for u in urls_raw.split(",") if u.strip())
                if urls_raw
                else ("translate.googleapis.com",)
            )
            user_agent = values.get("GOOGLETRANS_USER_AGENT")
        except ValueError as exc:
            raise ConfigurationError(
                "Google Translate environment configuration is invalid"
            ) from exc
        return cls(
            service_urls=urls,
            user_agent=user_agent,
            timeout_seconds=timeout,
            max_concurrency=concurrency,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        provider_name: str = "googletrans",
    ) -> GoogleTranslateConfig:
        values = os.environ if env is None else env
        provider = settings.providers.get(provider_name)
        try:
            timeout = float(
                values.get(
                    "GOOGLETRANS_TIMEOUT_SECONDS",
                    str(provider.timeout_seconds if provider else 20.0),
                )
            )
            concurrency = int(
                values.get(
                    "GOOGLETRANS_MAX_CONCURRENCY",
                    str(provider.max_concurrency if provider else 4),
                )
            )
            urls_raw = values.get("GOOGLETRANS_SERVICE_URLS")
            if urls_raw:
                urls = tuple(u.strip() for u in urls_raw.split(",") if u.strip())
            elif provider and provider.endpoint:
                urls = (provider.endpoint,)
            else:
                urls = ("translate.googleapis.com",)
            user_agent = values.get("GOOGLETRANS_USER_AGENT")
        except ValueError as exc:
            raise ConfigurationError("Google Translate configuration is invalid") from exc
        retry_policy = RetryPolicy(
            settings.retry.max_attempts,
            settings.retry.base_delay_seconds,
            settings.retry.max_delay_seconds,
        )
        return cls(
            service_urls=urls,
            user_agent=user_agent,
            timeout_seconds=timeout,
            max_concurrency=concurrency,
            retry_policy=retry_policy,
        )


class GoogleTranslateProvider:
    identity = ProviderIdentity("googletrans", "Google Translate", unofficial=True)
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: GoogleTranslateConfig | None = None,
        *,
        translator: GoogleTranslatorProtocol | None = None,
        owns_translator: bool | None = None,
    ) -> None:
        if not HAVE_GOOGLETRANS and translator is None:
            raise MissingOptionalDependencyError(
                "The 'googletrans' package is required for Google Translate. "
                "Install it with: pip install 'indic-language-utils[googletrans]'"
            )
        self.config = config or GoogleTranslateConfig()
        self._translator = translator
        self._owns_translator = (
            owns_translator if owns_translator is not None else (translator is None)
        )
        self._limiter = ConcurrencyLimiter(self.config.max_concurrency)
        supported_tags = _get_supported_tags()
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TRANSLATION, languages=supported_tags),
        )

    async def start(self) -> None:
        if self._translator is None:
            if not HAVE_GOOGLETRANS:
                raise MissingOptionalDependencyError(
                    "The 'googletrans' package is required for Google Translate. "
                    "Install it with: pip install 'indic-language-utils[googletrans]'"
                )
            timeout = httpx.Timeout(self.config.timeout_seconds)
            kwargs: dict[str, Any] = {
                "service_urls": list(self.config.service_urls),
                "timeout": timeout,
                "raise_exception": True,
            }
            if self.config.user_agent:
                kwargs["user_agent"] = self.config.user_agent
            self._translator = Translator(**kwargs)
            await self._translator.__aenter__()

    async def close(self) -> None:
        if self._translator is not None and self._owns_translator:
            try:
                await self._translator.__aexit__(None, None, None)
            finally:
                self._translator = None

    async def __aenter__(self) -> GoogleTranslateProvider:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def language_code_for(self, tag: LanguageTag) -> str:
        code = google_translate_language_code(tag)
        if HAVE_GOOGLETRANS and googletrans is not None:
            valid_codes = set(googletrans.LANGUAGES.keys())
            if code not in valid_codes:
                raise UnsupportedLanguagePairError(
                    f"Language '{tag}' (mapped to '{code}') is not supported by Google Translate",
                    provider=self.identity.provider,
                    capability=CapabilityId.TRANSLATION.value,
                    details={"tag": str(tag), "code": code},
                )
        return code

    async def translate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TranslationOptions,
        request_id: str,
    ) -> ProviderTranslationResult:
        if not texts or any(not text for text in texts):
            raise InvalidInputError(
                "Google Translate translation inputs cannot be empty",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            )

        source_code = self.language_code_for(source)
        target_code = self.language_code_for(target)

        translator = self._translator
        owns_call_translator = False
        if translator is None:
            if not HAVE_GOOGLETRANS:
                raise MissingOptionalDependencyError(
                    "The 'googletrans' package is required for Google Translate. "
                    "Install it with: pip install 'indic-language-utils[googletrans]'"
                )
            timeout = httpx.Timeout(self.config.timeout_seconds)
            kwargs: dict[str, Any] = {
                "service_urls": list(self.config.service_urls),
                "timeout": timeout,
                "raise_exception": True,
            }
            if self.config.user_agent:
                kwargs["user_agent"] = self.config.user_agent
            translator = Translator(**kwargs)
            await translator.__aenter__()
            owns_call_translator = True

        async def send() -> tuple[str, ...]:
            assert translator is not None
            async with self._limiter.slot(self.identity.provider, CapabilityId.TRANSLATION):
                try:
                    if len(texts) == 1:
                        res = await translator.translate(
                            texts[0], dest=target_code, src=source_code
                        )
                        raw_outputs = [_extract_translated_text(res)]
                    else:
                        res_list = await translator.translate(
                            list(texts), dest=target_code, src=source_code
                        )
                        raw_outputs = [_extract_translated_text(item) for item in res_list]
                except httpx.TimeoutException as exc:
                    raise ProviderTimeoutError(
                        "Google Translate request timed out",
                        provider=self.identity.provider,
                        capability=CapabilityId.TRANSLATION.value,
                        request_id=request_id,
                    ) from exc
                except httpx.TransportError as exc:
                    raise TransientProviderError(
                        "Google Translate transport failed",
                        provider=self.identity.provider,
                        capability=CapabilityId.TRANSLATION.value,
                        request_id=request_id,
                    ) from exc
                except ValueError as exc:
                    raise UnsupportedLanguagePairError(
                        str(exc),
                        provider=self.identity.provider,
                        capability=CapabilityId.TRANSLATION.value,
                        request_id=request_id,
                    ) from exc
                except (
                    ProviderTimeoutError,
                    TransientProviderError,
                    RateLimitError,
                    MalformedProviderResponseError,
                    UnsupportedLanguagePairError,
                ):
                    raise
                except Exception as exc:
                    err_msg = str(exc)
                    if "429" in err_msg or "Too Many Requests" in err_msg:
                        raise RateLimitError(
                            "Google Translate rate limit exceeded",
                            provider=self.identity.provider,
                            capability=CapabilityId.TRANSLATION.value,
                            request_id=request_id,
                        ) from exc
                    if "status code" in err_msg:
                        raise TransientProviderError(
                            f"Google Translate service error: {err_msg}",
                            provider=self.identity.provider,
                            capability=CapabilityId.TRANSLATION.value,
                            request_id=request_id,
                        ) from exc
                    raise MalformedProviderResponseError(
                        f"Google Translate error: {err_msg}",
                        provider=self.identity.provider,
                        capability=CapabilityId.TRANSLATION.value,
                        request_id=request_id,
                    ) from exc

                if len(raw_outputs) != len(texts):
                    raise MalformedProviderResponseError(
                        "Google Translate returned an unexpected number of translations",
                        provider=self.identity.provider,
                        capability=CapabilityId.TRANSLATION.value,
                        request_id=request_id,
                    )

                for translated_text, original_text in zip(raw_outputs, texts, strict=True):
                    if (
                        translated_text is None
                        or translated_text == ""
                        or len(translated_text) < min(3, len(original_text) // 2)
                    ):
                        raise MalformedProviderResponseError(
                            "Google Translate translated text is too short or empty: "
                            f"{translated_text!r}",
                            provider=self.identity.provider,
                            capability=CapabilityId.TRANSLATION.value,
                            request_id=request_id,
                        )

                return tuple(raw_outputs)

        try:
            translations = await retry(send, self.config.retry_policy)
            return ProviderTranslationResult(
                translations,
                service_id="googletrans",
                model_id=None,
                request_id=None,
            )
        finally:
            if owns_call_translator:
                await translator.__aexit__(None, None, None)


def _extract_translated_text(item: Any) -> str:
    if hasattr(item, "text") and isinstance(item.text, str):
        return item.text
    return str(item)


# Aliases
GoogletransConfig = GoogleTranslateConfig
GoogletransTranslationProvider = GoogleTranslateProvider
