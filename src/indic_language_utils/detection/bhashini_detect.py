"""Bhashini text language detection adapter."""

from __future__ import annotations

from ..concurrency import ConcurrencyLimiter
from ..errors import (
    ConfigurationError,
    InvalidInputError,
    MalformedProviderResponseError,
)
from ..languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag
from ..models import ProviderIdentity
from ..providers import CapabilityDeclaration, CapabilityId
from ..providers.bhashini import (
    BhashiniConfig,
    HttpxJsonTransport,
    JsonResponse,
    JsonTransport,
    _list,
    _mapping,
    _raise_bhashini_status,
    _string,
)
from ..retry import retry
from .models import DetectionOptions, LanguageCandidate, ProviderDetectionResult


class BhashiniDetectionProvider:
    identity = ProviderIdentity("bhashini", "Bhashini")
    capabilities: tuple[CapabilityDeclaration, ...]

    def __init__(
        self,
        config: BhashiniConfig,
        *,
        transport: JsonTransport | None = None,
        task_type: str = "txt-lang-detection",
    ) -> None:
        if not config.detection_service_id:
            raise ConfigurationError(
                "A Bhashini detection service ID is required for language detection"
            )
        self.config = config
        self._transport = transport
        self._owns_transport = transport is None
        self._task_type = task_type
        self._limiter = ConcurrencyLimiter(config.max_concurrency)
        languages = frozenset(item.tag for item in DEFAULT_LANGUAGE_REGISTRY.definitions())
        self.capabilities = (
            CapabilityDeclaration(CapabilityId.TEXT_LANGUAGE_DETECTION, languages=languages),
        )

    async def start(self) -> None:
        if self._transport is None:
            self._transport = HttpxJsonTransport()

    async def close(self) -> None:
        if self._transport is not None and self._owns_transport:
            await self._transport.close()
            self._transport = None

    async def __aenter__(self) -> BhashiniDetectionProvider:
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
                "Bhashini detection inputs cannot be empty",
                provider=self.identity.provider,
                capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                request_id=request_id,
            )
        payload = self._payload(texts)
        transport = self._transport
        owns_call_transport = False
        if transport is None:
            transport = HttpxJsonTransport()
            owns_call_transport = True

        async def send() -> JsonResponse:
            async with self._limiter.slot(
                self.identity.provider, CapabilityId.TEXT_LANGUAGE_DETECTION
            ):
                response = await transport.post(
                    self.config.endpoint,
                    headers={
                        "Authorization": self.config.api_key.reveal(),
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout_seconds=self.config.timeout_seconds,
                )
            _raise_bhashini_status(
                self.identity.provider, CapabilityId.TEXT_LANGUAGE_DETECTION, response, request_id
            )
            return response

        try:
            response = await retry(send, self.config.retry_policy)
            return self._parse(response.data, len(texts), request_id)
        finally:
            if owns_call_transport:
                await transport.close()

    def _payload(self, texts: tuple[str, ...]) -> dict[str, object]:
        return {
            "pipelineTasks": [
                {
                    "taskType": self._task_type,
                    "config": {
                        "serviceId": self.config.detection_service_id,
                    },
                }
            ],
            "inputData": {"input": [{"source": text} for text in texts]},
        }

    def _parse(
        self, data: object, expected: int, request_id: str
    ) -> tuple[ProviderDetectionResult, ...]:
        try:
            root = _mapping(data)
            pipeline = _list(root["pipelineResponse"])
            task = _mapping(pipeline[0])
            raw_config = task.get("config")
            config = _mapping(raw_config) if raw_config is not None else {}
            model_id_value = config.get("modelId")
            model_id = str(model_id_value) if model_id_value else None
            output = _list(task["output"])
            if len(output) != expected:
                raise TypeError(f"Expected {expected} outputs, got {len(output)}")

            results: list[ProviderDetectionResult] = []
            for item in output:
                mapping_item = _mapping(item)
                candidates: list[LanguageCandidate] = []
                if "langPrediction" in mapping_item:
                    preds = _list(mapping_item["langPrediction"])
                    for p in preds:
                        pred_map = _mapping(p)
                        raw_code = _string(
                            pred_map.get("langCode")
                            or pred_map.get("language")
                            or pred_map.get("lang")
                        )
                        score = float(pred_map.get("langScore") or pred_map.get("score") or 1.0)
                        norm_tag = (
                            DEFAULT_LANGUAGE_REGISTRY.normalize(raw_code)
                            if raw_code in DEFAULT_LANGUAGE_REGISTRY
                            else LanguageTag.parse(raw_code)
                        )
                        candidates.append(LanguageCandidate(norm_tag, max(0.0, min(1.0, score))))
                elif "langCode" in mapping_item or "language" in mapping_item:
                    raw_code = _string(mapping_item.get("langCode") or mapping_item.get("language"))
                    score = float(
                        mapping_item.get("score") or mapping_item.get("confidence") or 1.0
                    )
                    norm_tag = (
                        DEFAULT_LANGUAGE_REGISTRY.normalize(raw_code)
                        if raw_code in DEFAULT_LANGUAGE_REGISTRY
                        else LanguageTag.parse(raw_code)
                    )
                    candidates.append(LanguageCandidate(norm_tag, max(0.0, min(1.0, score))))
                elif "target" in mapping_item:
                    raw_code = _string(mapping_item["target"])
                    norm_tag = (
                        DEFAULT_LANGUAGE_REGISTRY.normalize(raw_code)
                        if raw_code in DEFAULT_LANGUAGE_REGISTRY
                        else LanguageTag.parse(raw_code)
                    )
                    candidates.append(LanguageCandidate(norm_tag, 1.0))
                else:
                    raise TypeError("Unrecognized language prediction format")

                if not candidates:
                    raise TypeError("No candidates parsed")

                results.append(
                    ProviderDetectionResult(
                        candidates=tuple(candidates),
                        model_id=model_id,
                        request_id=request_id,
                    )
                )
            return tuple(results)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise MalformedProviderResponseError(
                "Bhashini returned a malformed detection response",
                provider=self.identity.provider,
                capability=CapabilityId.TEXT_LANGUAGE_DETECTION.value,
                request_id=request_id,
            ) from exc
