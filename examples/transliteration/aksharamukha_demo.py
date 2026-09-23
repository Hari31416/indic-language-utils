"""Aksharamukha offline transliteration demo.

Demonstrates lightweight, pure-Python script-to-script and Romanization
transliteration across Indian languages with zero deep-learning dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import time

from indic_language_utils import (
    HAVE_AKSHARAMUKHA,
    AksharamukhaConfig,
    AksharamukhaTransliterationProvider,
    CapabilityId,
    OrderedRouter,
    ProviderRegistry,
    TransliterationClient,
    transliterate_sync,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("aksharamukha_demo")


async def run_aksharamukha_demo() -> None:
    if not HAVE_AKSHARAMUKHA:
        logger.error(
            "aksharamukha is not installed. Install it with: uv sync --extra local-transliteration"
        )
        return

    logger.info("Initializing Aksharamukha offline transliteration provider...")
    config = AksharamukhaConfig(roman_scheme="ITRANS", nativize=True)
    provider = AksharamukhaTransliterationProvider(config)

    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("aksharamukha",)})

    client = TransliterationClient(router)

    async with client:
        # Scenario 1: Cross-Indic Script Conversion (Tamil to Devanagari)
        logger.info("\n=== Scenario 1: Cross-Indic Script (Tamil -> Devanagari) ===")
        t_src = "வணக்கம், நீங்கள் நலமா?"
        res1 = await client.transliterate(t_src, source="ta", target="hi")
        logger.info("Input (Tamil):        %s", t_src)
        logger.info("Output (Devanagari):  %s", res1.text)
        logger.info("Latency:              %.4fs", res1.elapsed_seconds)

        # Scenario 2: Cross-Indic Script Conversion (Devanagari to Bengali & Telugu)
        logger.info("\n=== Scenario 2: Cross-Indic Script (Devanagari -> Bengali & Telugu) ===")
        d_src = "नमस्ते भारत आपका स्वागत है"
        res_bn = await client.transliterate(d_src, source="hi", target="bn")
        res_te = await client.transliterate(d_src, source="hi", target="te")
        logger.info("Input (Devanagari):   %s", d_src)
        logger.info("Output (Bengali):     %s", res_bn.text)
        logger.info("Output (Telugu):      %s", res_te.text)

        # Scenario 3: Roman to Indic (ITRANS convention)
        logger.info("\n=== Scenario 3: Roman to Indic Script ===")
        r_src = "namaste bhaarata"
        res_hi = await client.transliterate(r_src, source="en", target="hi")
        res_ta = await client.transliterate("vanakkam", source="en", target="ta")
        logger.info("Input: 'namaste bhaarata' -> Devanagari: %s", res_hi.text)
        logger.info("Input: 'vanakkam'         -> Tamil:      %s", res_ta.text)

        # Scenario 4: High-throughput Batch Conversion
        logger.info("\n=== Scenario 4: High-throughput Batch Processing ===")
        sentences = (
            "भारत एक विशाल और विविध देश है।",
            "संस्कृति और भाषा की विविधता हमारी पहचान है।",
            "विज्ञान और प्रौद्योगिकी में देश निरंतर प्रगति कर रहा है।",
        )
        start_t = time.monotonic()
        batch_res = await client.transliterate_batch(sentences, source="hi", target="ta")
        elapsed = time.monotonic() - start_t
        logger.info("Transliterated %d sentences in %.4fs:", len(sentences), elapsed)
        for original, res in zip(sentences, batch_res, strict=True):
            logger.info("  %s -> %s", original, res.text)


def run_sync_demo() -> None:
    logger.info("\n=== Scenario 5: Synchronous One-Liner ===")
    quick = transliterate_sync("வணக்கம்", source="ta", target="hi")
    logger.info(
        "transliterate_sync('வணக்கம்', 'ta', 'hi') -> %s (provider: %s)",
        quick.text,
        quick.provider.provider,
    )


if __name__ == "__main__":
    asyncio.run(run_aksharamukha_demo())
    run_sync_demo()
