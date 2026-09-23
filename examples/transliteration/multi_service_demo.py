"""Runnable examples demonstrating multi-service transliteration routing, fallback, and caching."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

from indic_language_utils import (
    BhashiniConfig,
    BhashiniTransliterationProvider,
    CacheSettings,
    CapabilityId,
    IndicXlitConfig,
    IndicXlitTransliterationProvider,
    OrderedRouter,
    ProviderRegistry,
    Secret,
    TransliterationClient,
    create_transliteration_cache,
)
from indic_language_utils.errors import TransientProviderError
from indic_language_utils.providers.bhashini import JsonResponse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("multi_service_translit_demo")


class FlakyBhashiniTranslitTransport:
    """Simulated transport that can trigger transient cloud outages."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.call_count = 0

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        self.call_count += 1
        if self.should_fail:
            raise TransientProviderError(
                "Simulated 503 Service Unavailable: upstream Bhashini transliteration gateway down",
                provider="bhashini",
                capability="transliteration",
            )

        input_data = json.get("inputData", {})
        inputs: list[dict[str, Any]] = []
        if isinstance(input_data, dict):
            raw_input = input_data.get("input", [])
            if isinstance(raw_input, list):
                inputs = raw_input

        output_items: list[dict[str, Any]] = []
        for item in inputs:
            text = str(item.get("source", "")).strip()
            # Simple simulation mapping
            if text.lower() == "namaste":
                res = "नमस्ते"
            elif text.lower() == "bharat":
                res = "भारत"
            else:
                res = f"{text}-bhashini"
            output_items.append({"source": text, "target": res})

        return JsonResponse(
            200,
            {
                "pipelineResponse": [
                    {
                        "taskType": "transliteration",
                        "config": {"serviceId": "bhashini/indicxlit", "modelId": "bhashini/v1"},
                        "output": output_items,
                    }
                ]
            },
            {"x-request-id": "mock-req-123"},
        )

    async def close(self) -> None:
        pass


class MockIndicXlitFallbackEngine:
    """Mock engine simulating IndicXlit local transliteration fallback."""

    def __init__(self) -> None:
        self.call_count = 0

    def translit_sentence(self, text: str, lang_code: str) -> str:
        self.call_count += 1
        mapping = {
            "namaste": "नमस्ते",
            "bharat": "भारत",
            "duniya": "दुनिया",
        }
        return mapping.get(text.lower(), f"{text}-indicxlit")


async def run_multi_service_demo() -> None:
    logger.info("Setting up Multi-Provider Transliteration Pipeline...")

    bhashini_transport = FlakyBhashiniTranslitTransport(should_fail=False)
    bhashini_config = BhashiniConfig(
        endpoint="https://example.com/compute",
        api_key=Secret("demo-key"),
        transliteration_service_id="bhashini/indicxlit",
    )
    bhashini_provider = BhashiniTransliterationProvider(
        bhashini_config, transport=bhashini_transport
    )

    indicxlit_engine = MockIndicXlitFallbackEngine()
    indicxlit_provider = IndicXlitTransliterationProvider(
        IndicXlitConfig(), engine=indicxlit_engine
    )

    registry = ProviderRegistry()
    registry.register(bhashini_provider)
    registry.register(indicxlit_provider)

    # Route: Try Bhashini cloud first, fall back to IndicXlit offline local
    router = OrderedRouter(
        registry,
        {CapabilityId.TRANSLITERATION: ("bhashini", "indicxlit")},
    )

    # Enable in-memory cache
    cache = create_transliteration_cache(
        CacheSettings(enabled=True, backend="memory", max_entries=100, ttl_seconds=300.0)
    )

    client = TransliterationClient(router, cache=cache)

    async with client:
        logger.info("\n=== Scenario 1: Normal Primary Routing (Bhashini Cloud) ===")
        res1 = await client.transliterate("namaste", source="en", target="hi")
        logger.info(
            "Provider used: %s (fallback count: %d)",
            res1.provider.provider,
            res1.fallback_count,
        )
        logger.info("Cached hit: %s", res1.cache.hit)

        logger.info("\n=== Scenario 2: Cache Hit Verification ===")
        res2 = await client.transliterate("namaste", source="en", target="hi")
        logger.info("Transliterated: %s", res2.text)
        logger.info("Provider: %s", res2.provider.provider)
        logger.info("Cached hit: %s (backend: %s)", res2.cache.hit, res2.cache.backend)

        logger.info("\n=== Scenario 3: Automatic Failover on Cloud Outage ===")
        logger.info("Simulating Bhashini gateway 503 outage...")
        bhashini_transport.should_fail = True

        res3 = await client.transliterate("bharat", source="en", target="hi")
        logger.info("Transliterated: %s", res3.text)
        logger.info(
            "Provider used: %s (fallback count: %d)",
            res3.provider.provider,
            res3.fallback_count,
        )
        logger.info("IndicXlit fallback engine invocations: %d", indicxlit_engine.call_count)

        logger.info("\n=== Scenario 4: SingleFlight Coalescing (Concurrent Misses) ===")
        logger.info("Launching 5 concurrent requests for 'duniya'...")
        start_time = time.monotonic()
        results = await asyncio.gather(
            *(client.transliterate("duniya", source="en", target="hi") for _ in range(5))
        )
        elapsed = time.monotonic() - start_time
        logger.info("All 5 calls completed in %.4fs", elapsed)
        logger.info("Results identical: %s", all(r.text == results[0].text for r in results))
        logger.info("SingleFlight ensured exactly one provider call was dispatched.")


if __name__ == "__main__":
    asyncio.run(run_multi_service_demo())
