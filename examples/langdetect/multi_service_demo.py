"""Runnable examples demonstrating multi-service routing, fallback, and caching."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

from indic_language_utils import (
    BhashiniConfig,
    BhashiniDetectionProvider,
    CacheSettings,
    CapabilityId,
    DetectionClient,
    FastTextDetectionConfig,
    FastTextDetectionProvider,
    OrderedRouter,
    ProviderRegistry,
    Secret,
    create_detection_cache,
)
from indic_language_utils.bhashini import JsonResponse
from indic_language_utils.errors import TransientProviderError

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("multi_service_demo")


class FlakyBhashiniTransport:
    """Simulated transport that succeeds initially, then simulates a transient cloud outage."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        if self.should_fail:
            raise TransientProviderError(
                "Simulated 503 Service Unavailable: upstream Bhashini inference gateway down",
                provider="bhashini",
                capability="detection",
            )

        input_data = json.get("inputData", {})
        inputs: list[dict[str, Any]] = []
        if isinstance(input_data, dict):
            raw_input = input_data.get("input", [])
            if isinstance(raw_input, list):
                inputs = raw_input

        output_items: list[dict[str, Any]] = []
        for _ in inputs:
            output_items.append({"langPrediction": [{"langCode": "ta", "langScore": 0.99}]})

        mock_data: dict[str, Any] = {
            "pipelineResponse": [
                {
                    "taskType": "txt-lang-detection",
                    "config": {"modelId": "bhashini-indic-lid-v1"},
                    "output": output_items,
                }
            ]
        }
        return JsonResponse(status_code=200, data=mock_data)

    async def close(self) -> None:
        pass


async def run_multi_provider_fallback_demo() -> None:
    logger.info("==================================================")
    logger.info("1. Resilient Multi-Provider Fallback Routing")
    logger.info("==================================================")

    flaky_transport = FlakyBhashiniTransport(should_fail=False)
    bhashini_cfg = BhashiniConfig(
        endpoint="https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
        api_key=Secret("demo-api-key"),
        detection_service_id="ai4bharat/indic-lang-detect",
        timeout_seconds=5.0,
    )
    bhashini_provider = BhashiniDetectionProvider(bhashini_cfg, transport=flaky_transport)
    fasttext_provider = FastTextDetectionProvider(FastTextDetectionConfig())

    registry = ProviderRegistry()
    registry.register(bhashini_provider)
    registry.register(fasttext_provider)

    # Route: Try Bhashini cloud first; fallback to FastText local if cloud fails
    routes = {
        CapabilityId.TEXT_LANGUAGE_DETECTION: ("bhashini", "fasttext"),
    }
    router = OrderedRouter(registry, routes)
    cache = create_detection_cache(CacheSettings(enabled=True, backend="memory", max_entries=100))

    async with DetectionClient(router=router, cache=cache) as client:
        sample_text = "வணக்கம், நீங்கள் நலமா?"
        logger.info("Input text: '%s'", sample_text)

        # Stage A: Cloud provider is healthy
        res_healthy = await client.detect(sample_text)
        logger.info("Healthy Cloud Call:")
        logger.info("  Language:       %s", res_healthy.language)
        logger.info("  Active provider: %s", res_healthy.provider.provider)
        logger.info("  Fallback count:  %d", res_healthy.fallback_count)
        logger.info("")

        # Stage B: Cloud provider experiences transient failure (503 / timeout)
        flaky_transport.should_fail = True
        sample_fallback = "తెలుగు భాష సాంస్కృతిక వైభవం."
        logger.info("Simulating cloud gateway outage (503 Service Unavailable)...")
        logger.info("Input text: '%s'", sample_fallback)

        res_fallback = await client.detect(sample_fallback)
        logger.info("Failover Call (Automatic Fallback to FastText):")
        logger.info("  Language:       %s", res_fallback.language)
        logger.info("  Script:         %s", res_fallback.script)
        logger.info("  Active provider: %s", res_fallback.provider.provider)
        logger.info("  Fallback count:  %d", res_fallback.fallback_count)
        logger.info("")


async def run_singleflight_and_cache_demo() -> None:
    logger.info("==================================================")
    logger.info("2. SingleFlight Deduplication and Caching")
    logger.info("==================================================")

    provider = FastTextDetectionProvider(FastTextDetectionConfig())
    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(
        registry,
        {CapabilityId.TEXT_LANGUAGE_DETECTION: ("fasttext",)},
    )
    cache = create_detection_cache(
        CacheSettings(enabled=True, backend="memory", max_entries=500, ttl_seconds=300.0)
    )

    async with DetectionClient(router=router, cache=cache) as client:
        text = "ಕನ್ನಡ ನಾಡು ಮತ್ತು ನುಡಿ ಅತ್ಯಂತ ಪ್ರಾಚೀನವಾದದ್ದು."

        logger.info("Launching 5 concurrent detection requests for identical text...")
        t0 = time.monotonic()
        results = await asyncio.gather(
            client.detect(text),
            client.detect(text),
            client.detect(text),
            client.detect(text),
            client.detect(text),
        )
        total_time = time.monotonic() - t0

        logger.info(
            "All 5 requests resolved in %.4f seconds (coalesced via SingleFlight)",
            total_time,
        )
        for idx, r in enumerate(results, 1):
            logger.info(
                "  Request %d: %s (Hit: %s, Time: %.4fs)",
                idx,
                r.language,
                r.cache.hit,
                r.elapsed_seconds,
            )
        logger.info("")

        # Subsequent call hits the warm cache
        t_cached = time.monotonic()
        warm_result = await client.detect(text)
        cached_time = time.monotonic() - t_cached

        logger.info("Subsequent Warm Call:")
        logger.info(
            "  Resolved in %.6f seconds (Cache Hit: %s)",
            cached_time,
            warm_result.cache.hit,
        )
        logger.info("")


def main() -> None:
    asyncio.run(run_multi_provider_fallback_demo())
    asyncio.run(run_singleflight_and_cache_demo())


if __name__ == "__main__":
    main()
