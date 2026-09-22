"""Sarvam AI text language detection adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

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
)
from ..retry import retry
from .models import DetectionOptions, LanguageCandidate, ProviderDetectionResult


class SarvamDetectionProvider:
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
            CapabilityDeclaration(CapabilityId.TEXT_LANGUAGE_DETECTION, languages=languages),
        )

    async def start(self) -> None:
        if self._transport is None:
            self._transport = SarvamJsonTransport()

    async def close(self) -> None:
        if self._transport is not None and self._owns_transport:
            await self._transport.close()
            self._transport = None

    async def __aenter__(self) -> SarvamDetectionProvider:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def detect_batch(
        self,
        texts: tuple[str, ...],
        *,
        options: DetectionOptions,
        request_id: str,
    ) -> tuple[ProviderDetectionResult, ...]:
        if not texts or any(not text or not text.strip() for text in texts):
            raise InvalidInputError(
                "Sarvam detection inputs cannot be empty",
                provider=self.identity.provider,
                capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                request_id=request_id,
            )

        transport = self._transport
        owns_call_transport = False
        if transport is None:
            transport = SarvamJsonTransport()
            owns_call_transport = True

        try:
            results = await asyncio.gather(
                *(self._detect_single(text, transport, request_id) for text in texts)
            )
            return tuple(results)
        finally:
            if owns_call_transport:
                await transport.close()

    async def _detect_single(
        self,
        text: str,
        transport: JsonTransport,
        request_id: str,
    ) -> ProviderDetectionResult:
        url = f"{self.config.endpoint.rstrip('/')}/text-lid"
        payload = {"input": text}
        headers = {
            "api-subscription-key": self.config.api_key.reveal(),
            "Content-Type": "application/json",
        }

        async def send() -> JsonResponse:
            async with self._limiter.slot(
                self.identity.provider, CapabilityId.TEXT_LANGUAGE_DETECTION
            ):
                response = await transport.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
            _raise_sarvam_status(
                self.identity.provider, CapabilityId.TEXT_LANGUAGE_DETECTION, response, request_id
            )
            return response

        response = await retry(send, self.config.retry_policy)
        return self._parse_single(response, request_id)

    def _parse_single(
        self,
        response: JsonResponse,
        request_id: str,
    ) -> ProviderDetectionResult:
        try:
            if not isinstance(response.data, Mapping):
                raise TypeError("Response is not a JSON object")

            data = response.data
            raw_code = data.get("language_code")
            if not raw_code or not isinstance(raw_code, str):
                raise TypeError("language_code is missing or invalid in Sarvam response")

            resp_request_id = data.get("request_id")
            if not resp_request_id or not isinstance(resp_request_id, str):
                resp_request_id = _header(response.headers, "x-request-id") or request_id

            norm_tag = (
                DEFAULT_LANGUAGE_REGISTRY.normalize(raw_code)
                if raw_code in DEFAULT_LANGUAGE_REGISTRY
                else LanguageTag.parse(raw_code)
            )
            raw_script = data.get("script_code")
            script = (
                str(raw_script).strip()
                if isinstance(raw_script, str) and raw_script.strip()
                else None
            )
            candidate = LanguageCandidate(norm_tag, 1.0, script=script)
            return ProviderDetectionResult(
                candidates=(candidate,),
                model_id=None,
                request_id=resp_request_id,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MalformedProviderResponseError(
                "Sarvam returned a malformed detection response",
                provider=self.identity.provider,
                capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                request_id=request_id,
            ) from exc
