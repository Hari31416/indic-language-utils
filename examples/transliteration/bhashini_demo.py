"""Runnable examples demonstrating cloud transliteration with Bhashini."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from typing import Any

from indic_language_utils import (
    BhashiniConfig,
    BhashiniTransliterationProvider,
    CapabilityId,
    OrderedRouter,
    ProviderRegistry,
    Secret,
    TransliterationClient,
    TransliterationOptions,
    TransliterationRequest,
)
from indic_language_utils.providers.bhashini import JsonResponse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("bhashini_translit_demo")


class MockBhashiniTranslitTransport:
    """Mock JSON transport for demonstration when live credentials are not available."""

    def __init__(self) -> None:
        self._sample_dict: dict[tuple[str, str], dict[str, str]] = {
            ("en", "hi"): {
                "namaste": "नमस्ते",
                "duniya": "दुनिया",
                "aap kaise hain": "आप कैसे हैं",
                "mera naam hari hai": "मेरा नाम हरी है",
            },
            ("en", "ta"): {
                "vanakkam": "வணக்கம்",
                "nanri": "நன்றி",
            },
        }

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        pipeline_tasks = json.get("pipelineTasks", [])
        src_lang = "en"
        tgt_lang = "hi"
        service_id = "default-service"
        if isinstance(pipeline_tasks, list) and pipeline_tasks:
            first_task = pipeline_tasks[0]
            if isinstance(first_task, dict):
                task_cfg = first_task.get("config", {})
                if isinstance(task_cfg, dict):
                    lang_cfg = task_cfg.get("language", {})
                    if isinstance(lang_cfg, dict):
                        src_lang = str(lang_cfg.get("sourceLanguage", "en"))
                        tgt_lang = str(lang_cfg.get("targetLanguage", "hi"))
                    service_id = str(task_cfg.get("serviceId", "default-service"))

        input_data = json.get("inputData", {})
        inputs: list[dict[str, Any]] = []
        if isinstance(input_data, dict):
            raw_input = input_data.get("input", [])
            if isinstance(raw_input, list):
                inputs = raw_input

        output_items: list[dict[str, Any]] = []
        pair_dict = self._sample_dict.get((src_lang, tgt_lang), {})
        for item in inputs:
            text = str(item.get("source", "")).strip()
            transliterated = pair_dict.get(text.lower(), f"{text}-transliterated")
            output_items.append({"source": text, "target": transliterated})

        return JsonResponse(
            200,
            {
                "pipelineResponse": [
                    {
                        "taskType": "transliteration",
                        "config": {"serviceId": service_id, "modelId": "ai4bharat/indicxlit"},
                        "output": output_items,
                    }
                ]
            },
            {"x-request-id": "mock-req-bhashini-xlit"},
        )

    async def close(self) -> None:
        pass


async def run_bhashini_demo() -> None:
    api_key = os.environ.get("BHASHINI_API_KEY")
    endpoint = os.environ.get(
        "BHASHINI_ENDPOINT_URL",
        "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
    )
    service_id = os.environ.get("BHASHINI_TRANSLITERATION_SERVICE_ID")

    if api_key and service_id:
        logger.info("Initializing live Bhashini transliteration client...")
        config = BhashiniConfig(
            endpoint=endpoint,
            api_key=Secret(api_key),
            transliteration_service_id=service_id,
        )
        provider = BhashiniTransliterationProvider(config)
    else:
        logger.info(
            "Live Bhashini transliteration requires BHASHINI_API_KEY and "
            "BHASHINI_TRANSLITERATION_SERVICE_ID; running with Mock Transport."
        )
        config = BhashiniConfig(
            endpoint=endpoint,
            api_key=Secret("demo-api-key"),
            transliteration_service_id=service_id or "demo-service",
        )
        provider = BhashiniTransliterationProvider(
            config, transport=MockBhashiniTranslitTransport()
        )

    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("bhashini",)})

    async with TransliterationClient(router) as client:
        logger.info("\n--- Single Text Transliteration (en -> hi) ---")
        request = TransliterationRequest(
            "namaste",
            source="en",
            target="hi",
            options=TransliterationOptions(),
        )
        result = await client.transliterate(request)
        logger.info("Source: %s", result.source_text)
        logger.info("Target: %s", result.text)
        logger.info("Provider: %s (model: %s)", result.provider.provider, result.provider.model_id)

        logger.info("\n--- Batch Text Transliteration (en -> hi) ---")
        batch_inputs = ["duniya", "aap kaise hain", "mera naam hari hai"]
        batch_results = await client.transliterate_batch(batch_inputs, source="en", target="hi")
        for item in batch_results:
            logger.info("  %s -> %s", item.source_text, item.text)

        logger.info("\n--- Transliteration to Tamil (en -> ta) ---")
        ta_result = await client.transliterate("vanakkam", source="en", target="ta")
        logger.info("Source: %s", ta_result.source_text)
        logger.info("Target: %s", ta_result.text)


if __name__ == "__main__":
    asyncio.run(run_bhashini_demo())
