"""Sarvam AI translation adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    InvalidInputError,
    MalformedProviderResponseError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..providers.bhashini import JsonResponse, JsonTransport, _header
from ..providers.sarvam import (
    SarvamConfig,
    SarvamJsonTransport,
    _raise_sarvam_status,
    sarvam_language_code,
)
from ..retry import retry
from .models import ProviderTranslationResult, TranslationOptions

if TYPE_CHECKING:
    from ..detection.models import DetectionOptions, ProviderDetectionResult


class SarvamTranslationProvider:
    identity = ProviderIdentity("sarvam", "Sarvam")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: SarvamConfig,
        *,
        transport: JsonTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._owns_transport = transport is None
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TRANSLATION, languages=languages),
            CapabilityDeclaration(CapabilityId.TEXT_LANGUAGE_DETECTION, languages=languages),
        )

    async def start(self) -> None:
        if self._transport is None:
            self._transport = SarvamJsonTransport()

    async def close(self) -> None:
        if self._transport is not None and self._owns_transport:
            await self._transport.close()
            self._transport = None

    async def __aenter__(self) -> SarvamTranslationProvider:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

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
                "Sarvam translation inputs cannot be empty",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            )

        source_code = sarvam_language_code(source)
        target_code = sarvam_language_code(target)

        transport = self._transport
        owns_call_transport = False
        if transport is None:
            transport = SarvamJsonTransport()
            owns_call_transport = True

        try:
            results = await asyncio.gather(
                *(
                    self._translate_single(
                        text,
                        source_code=source_code,
                        target_code=target_code,
                        transport=transport,
                        request_id=request_id,
                    )
                    for text in texts
                )
            )
            translations = tuple(r[0] for r in results)
            provider_request_id = next((r[1] for r in results if r[1]), None)
            return ProviderTranslationResult(
                translations,
                service_id=None,
                model_id=self.config.model,
                request_id=provider_request_id,
            )
        finally:
            if owns_call_transport:
                await transport.close()

    async def _translate_single(
        self,
        text: str,
        *,
        source_code: str,
        target_code: str,
        transport: JsonTransport,
        request_id: str,
    ) -> tuple[str, str | None]:
        url = f"{self.config.endpoint.rstrip('/')}/translate"
        payload = {
            "input": text,
            "source_language_code": source_code,
            "target_language_code": target_code,
            "model": self.config.model,
        }
        headers = {
            "api-subscription-key": self.config.api_key.reveal(),
            "Content-Type": "application/json",
        }

        async def send() -> JsonResponse:
            async with self._limiter.slot(self.identity.provider, CapabilityId.TRANSLATION):
                response = await transport.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
            _raise_sarvam_status(
                self.identity.provider, CapabilityId.TRANSLATION, response, request_id
            )
            return response

        response = await retry(send, self.config.retry_policy)
        return self._parse_single(response, request_id)

    def _parse_single(
        self,
        response: JsonResponse,
        request_id: str,
    ) -> tuple[str, str | None]:
        try:
            if not isinstance(response.data, Mapping):
                raise TypeError("Response is not a JSON object")

            data = response.data
            translated = data.get("translated_text")
            if translated is None or not isinstance(translated, str):
                raise TypeError("translated_text is missing or invalid in Sarvam response")

            resp_request_id = data.get("request_id")
            if not resp_request_id or not isinstance(resp_request_id, str):
                resp_request_id = _header(response.headers, "x-request-id")

            return translated, resp_request_id
        except (KeyError, TypeError, ValueError) as exc:
            raise MalformedProviderResponseError(
                "Sarvam returned a malformed translation response",
                provider=self.identity.provider,
                capability=CapabilityId.TRANSLATION.value,
                request_id=request_id,
            ) from exc

    async def detect_batch(
        self,
        texts: tuple[str, ...],
        *,
        options: DetectionOptions,
        request_id: str,
    ) -> tuple[ProviderDetectionResult, ...]:
        from ..detection.sarvam_detect import SarvamDetectionProvider

        delegate = SarvamDetectionProvider(self.config, transport=self._transport)
        return await delegate.detect_batch(texts, options=options, request_id=request_id)
