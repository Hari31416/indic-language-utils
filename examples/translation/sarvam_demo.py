"""Runnable examples demonstrating translation using Sarvam AI."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from typing import Any

from indic_language_utils import (
    SarvamConfig,
    SarvamTranslationProvider,
    Secret,
    TextFormat,
    TranslationOptions,
    get_sync_translation_client,
    get_translation_client,
)
from indic_language_utils.providers.bhashini import JsonResponse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sarvam_translation_demo")


class MockSarvamTranslateTransport:
    """Mock JSON transport for demonstration when live credentials are not available."""

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        text = str(json.get("input", ""))
        target = str(json.get("target_language_code", "hi-IN"))

        if "Welcome" in text:
            translated = "भारत में आपका स्वागत है!" if "hi" in target else "இந்தியாவிற்கு நல்வரவு!"
        elif "Application" in text:
            translated = "आपकी शिकायत का समाधान हो गया है।"
        else:
            translated = f"[Translated to {target}]: {text}"

        mock_data: dict[str, Any] = {
            "request_id": "mock-sarvam-tx-123",
            "translated_text": translated,
            "source_language_code": str(json.get("source_language_code", "en-IN")),
        }
        return JsonResponse(status_code=200, data=mock_data)

    async def close(self) -> None:
        pass


def get_configured_provider() -> SarvamTranslationProvider:
    api_key = os.environ.get("SARVAM_API_KEY")
    endpoint = os.environ.get("SARVAM_ENDPOINT_URL", "https://api.sarvam.ai")
    model = os.environ.get("SARVAM_MODEL", "sarvam-translate:v1")

    if api_key:
        config = SarvamConfig(
            api_key=Secret(api_key),
            endpoint=endpoint,
            model=model,
            timeout_seconds=20.0,
        )
        return SarvamTranslationProvider(config)

    logger.info("Note: SARVAM_API_KEY not found. Using simulated provider transport.")
    logger.info("")
    config = SarvamConfig(
        api_key=Secret("demo-api-key"),
        endpoint="https://api.sarvam.ai",
        model="sarvam-translate:v1",
        timeout_seconds=20.0,
    )
    return SarvamTranslationProvider(config, transport=MockSarvamTranslateTransport())


def run_sync_examples(provider: SarvamTranslationProvider) -> None:
    logger.info("==================================================")
    logger.info("1. Synchronous Translation with Sarvam AI")
    logger.info("==================================================")

    sync_client = get_sync_translation_client(providers=[provider])

    result = sync_client.translate("Welcome to India!", "en", "hi")
    logger.info("Source:      Welcome to India!")
    logger.info("Translation: %s", result.text)
    logger.info("Provider:    %s", result.provider.provider)
    if result.provider.model_id:
        logger.info("Model:       %s", result.provider.model_id)
    logger.info("")

    messages = [
        "Please verify your phone number.",
        "An OTP has been sent to your registered mobile device.",
        "Do not share your password with anyone.",
    ]
    batch_results = sync_client.translate_batch(messages, "en", "ta")
    logger.info("Batch Translation (English to Tamil):")
    for text, r in zip(messages, batch_results, strict=True):
        logger.info("  - %s -> %s", text, r.text)
    logger.info("")


async def run_async_examples(provider: SarvamTranslationProvider) -> None:
    logger.info("==================================================")
    logger.info("2. Asynchronous Translation with Caching")
    logger.info("==================================================")

    async with get_translation_client(providers=[provider]) as client:
        sample_text = "Citizen services are accessible through the unified portal."

        # First call hits Sarvam API and caches result
        res1 = await client.translate(sample_text, "en", "hi")
        logger.info("Source:      %s", sample_text)
        logger.info("Translation: %s", res1.text)
        logger.info("Elapsed:     %.3fs (Cache Hit: %s)", res1.elapsed_seconds, res1.cache.hit)

        # Second identical call resolves immediately from cache
        res1_cached = await client.translate(sample_text, "en", "hi")
        logger.info(
            "Cached call: %.4fs (Cache Hit: %s)",
            res1_cached.elapsed_seconds,
            res1_cached.cache.hit,
        )
        logger.info("")

        # Multi-language translation (English to Odia)
        logger.info("Translation to Odia:")
        res_odia = await client.translate("Your grievance status is resolved.", "en", "or")
        logger.info("Odia:        %s", res_odia.text)
        logger.info("")

        # Markdown preservation
        logger.info("Markdown Translation (English to Hindi):")
        markdown_text = """# Information Notice

Please keep the following documents ready:
- Identification: `ID-1042-X`
- Official Portal: [National Portal](https://services.india.gov.in)

Submit before the deadline."""

        res_md = await client.translate(
            markdown_text,
            "en",
            "hi",
            options=TranslationOptions(
                text_format=TextFormat.MARKDOWN,
                best_effort=True,
            ),
        )
        logger.info("Translated Markdown:\n%s\n", res_md.text)


def main() -> None:
    provider = get_configured_provider()
    run_sync_examples(provider)
    asyncio.run(run_async_examples(provider))


if __name__ == "__main__":
    main()
