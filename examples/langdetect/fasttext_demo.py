"""Runnable examples demonstrating local text language detection with FastText."""

from __future__ import annotations

import asyncio
import logging
import time

from indic_language_utils import (
    CacheSettings,
    DetectionOptions,
    FastTextDetectionConfig,
    FastTextDetectionProvider,
    Settings,
    detect_batch_sync,
    detect_script,
    detect_sync,
    get_detection_client,
    get_sync_detection_client,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("fasttext_demo")


def run_sync_examples() -> None:
    logger.info("==================================================")
    logger.info("1. Synchronous Local Detection (Quick One-Liners)")
    logger.info("==================================================")

    # Quick one-liner detection
    sample = "नमस्ते भारत! आप कैसे हैं?"
    result = detect_sync(sample)
    logger.info("Input text:        %s", sample)
    logger.info("Detected language: %s", result.language)
    logger.info("Detected script:   %s", result.script)
    if result.candidates:
        logger.info("Confidence:        %.2f%%", result.candidates[0].confidence * 100)
    logger.info("Provider:          %s", result.provider.provider)
    logger.info("")

    # Batch detection across diverse Indic languages and scripts
    samples = [
        ("Hindi", "नमस्ते भारत! आपका स्वागत है।"),
        ("Tamil", "வணக்கம், நீங்கள் நலமா?"),
        ("Bengali", "হ্যালো, আপনি কেমন আছেন?"),
        ("Telugu", "నమస్కారం, మీరు ఎలా ఉన్నారు?"),
        ("Kannada", "ನಮಸ್ಕಾರ, ನೀವು ಹೇಗಿದ್ದೀರಿ?"),
        ("Malayalam", "നമസ്കാരം, സുഖമാണോ?"),
        ("Gujarati", "નમસ્તે, તમે કેમ છો?"),
        ("Punjabi", "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?"),
        ("English", "Welcome to the government digital services portal."),
    ]

    texts = [text for _, text in samples]
    batch_results = detect_batch_sync(texts)

    logger.info("Batch Detection across Indic Scripts:")
    for (expected_name, text), res in zip(samples, batch_results, strict=True):
        top_cand = res.candidates[0] if res.candidates else None
        conf_str = f"{top_cand.confidence * 100:.1f}%" if top_cand else "N/A"
        logger.info(
            "  - [%s] Detected: %s (Script: %s, Conf: %s) -> '%s'",
            expected_name,
            res.language,
            res.script,
            conf_str,
            text,
        )
    logger.info("")


def run_candidate_ranking_examples() -> None:
    logger.info("==================================================")
    logger.info("2. Candidate Ranking and Script Detection")
    logger.info("==================================================")

    provider = FastTextDetectionProvider(FastTextDetectionConfig(low_memory=False))
    client = get_sync_detection_client(providers=[provider])

    ambiguous_text = "भारत सरकार के गृह मंत्रालय"
    options = DetectionOptions(max_candidates=3, threshold=0.05)
    result = client.detect(ambiguous_text, options=options)

    logger.info("Input text: %s", ambiguous_text)
    logger.info("Script identified: %s", detect_script(ambiguous_text))
    logger.info("Top %d Candidates:", len(result.candidates))
    for idx, cand in enumerate(result.candidates, 1):
        logger.info(
            "  %d. %s (Confidence: %.2f%%, Script: %s)",
            idx,
            cand.language,
            cand.confidence * 100,
            cand.script,
        )
    logger.info("")


async def run_async_and_caching_examples() -> None:
    logger.info("==================================================")
    logger.info("3. Async Detection with Response Caching")
    logger.info("==================================================")

    # Enable in-memory caching to showcase single-flight and repeat hits
    settings = Settings(
        cache=CacheSettings(enabled=True, backend="memory", max_entries=500, ttl_seconds=300.0)
    )

    provider = FastTextDetectionProvider()
    async with get_detection_client(settings=settings, providers=[provider]) as client:
        test_text = "ప్రజా సమస్యల పరిష్కార వేదిక"

        # First call: executes detection and populates cache
        t0 = time.monotonic()
        res1 = await client.detect(test_text)
        d1 = time.monotonic() - t0
        logger.info("First call (Cache Miss):")
        logger.info("  Detected: %s (Script: %s)", res1.language, res1.script)
        logger.info("  Elapsed:  %.4f seconds (Cache Hit: %s)", d1, res1.cache.hit)

        # Second call: resolves from cache
        t0 = time.monotonic()
        res2 = await client.detect(test_text)
        d2 = time.monotonic() - t0
        logger.info("Second call (Cache Hit):")
        logger.info("  Detected: %s (Script: %s)", res2.language, res2.script)
        logger.info("  Elapsed:  %.4f seconds (Cache Hit: %s)", d2, res2.cache.hit)
    logger.info("")


def main() -> None:
    run_sync_examples()
    run_candidate_ranking_examples()
    asyncio.run(run_async_and_caching_examples())


if __name__ == "__main__":
    main()
