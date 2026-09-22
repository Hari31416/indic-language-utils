"""Runnable examples demonstrating translation using the unofficial Google Translate provider."""

from __future__ import annotations

import asyncio
import logging

from indic_language_utils import (
    GoogleTranslateConfig,
    GoogleTranslateProvider,
    TextFormat,
    TranslationOptions,
    get_sync_translation_client,
    get_translation_client,
    translate_sync,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("googletrans_demo")


def run_direct_provider_examples() -> None:
    logger.info("==================================================")
    logger.info("1. Direct GoogleTranslateProvider Usage (Sync Facade)")
    logger.info("==================================================")

    provider = GoogleTranslateProvider(GoogleTranslateConfig(timeout_seconds=15.0))
    sync_client = get_sync_translation_client(providers=[provider])

    result = sync_client.translate("Welcome to India!", "en", "hi")
    logger.info("Source:      Welcome to India!")
    logger.info(f"Translation: {result.text}")
    logger.info(
        f"Provider:    {result.provider.provider} (Unofficial: {result.provider.unofficial})"
    )
    logger.info("")

    messages: list[str] = [
        "Please verify your phone number.",
        "An OTP has been sent to your registered mobile device.",
        "Do not share your password with anyone.",
    ]
    batch_results = sync_client.translate_batch(messages, "en", "ta")
    logger.info("Batch Translation (English to Tamil):")
    for text, r in zip(messages, batch_results, strict=True):
        logger.info(f"  - {text} -> {r.text}")
    logger.info("")


async def run_async_provider_examples() -> None:
    logger.info("==================================================")
    logger.info("2. Asynchronous Translation with Google Translate")
    logger.info("==================================================")

    provider = GoogleTranslateProvider()
    async with get_translation_client(providers=[provider]) as client:
        # Single async translation
        sample_text = "Public services are accessible to all citizens."
        res_single = await client.translate(sample_text, "en", "hi")
        logger.info(f"Source:      {sample_text}")
        logger.info(f"Translation: {res_single.text}")
        logger.info(
            f"Elapsed:     {res_single.elapsed_seconds:.3f}s (Cache Hit: {res_single.cache.hit})"
        )

        # Second identical call resolves from cache
        res_cached = await client.translate(sample_text, "en", "hi")
        logger.info(f"Cached call: {res_cached.text}")
        logger.info(
            f"Elapsed:     {res_cached.elapsed_seconds:.4f}s (Cache Hit: {res_cached.cache.hit})"
        )
        logger.info("")

        # Multi-language translation (English to Bengali)
        logger.info("Translation to Bengali:")
        res_bengali = await client.translate("Your application has been received.", "en", "bn")
        logger.info(f"Bengali:     {res_bengali.text}")
        logger.info("")

        # Markdown preservation
        logger.info("Markdown Translation:")
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
        logger.info(f"Translated Markdown:\n{res_md.text}\n")


def run_env_selection_example() -> None:
    logger.info("==================================================")
    logger.info("3. Automatic Selection via Environment Variable")
    logger.info("==================================================")

    # When TRANSLATION_SERVICE_PROVIDER is set to googletrans,
    # get_translation_client() automatically routes to Google Translate
    env_override: dict[str, str] = {"TRANSLATION_SERVICE_PROVIDER": "googletrans"}
    res = translate_sync("Good morning, have a wonderful day!", "en", "hi", env=env_override)
    logger.info("Source:      Good morning, have a wonderful day!")
    logger.info(f"Translation: {res.text}")
    logger.info(f"Provider:    {res.provider.provider}")
    logger.info("")


def main() -> None:
    run_direct_provider_examples()
    asyncio.run(run_async_provider_examples())
    run_env_selection_example()


if __name__ == "__main__":
    main()
