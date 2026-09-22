"""Runnable examples demonstrating cloud text language detection with Sarvam AI."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from indic_language_utils import (
    DetectionOptions,
    SarvamConfig,
    SarvamDetectionProvider,
    Secret,
    get_sync_detection_client,
)
from indic_language_utils.providers.bhashini import JsonResponse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sarvam_demo")


class MockSarvamTransport:
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
        if any("\u0900" <= ch <= "\u097f" for ch in text):
            data: dict[str, Any] = {
                "request_id": "mock-lid-hi",
                "language_code": "hi-IN",
                "script_code": "Deva",
            }
        elif any("\u0b80" <= ch <= "\u0bff" for ch in text):
            data = {
                "request_id": "mock-lid-ta",
                "language_code": "ta-IN",
                "script_code": "Taml",
            }
        elif any("\u0c00" <= ch <= "\u0c7f" for ch in text):
            data = {
                "request_id": "mock-lid-te",
                "language_code": "te-IN",
                "script_code": "Telu",
            }
        elif any("\u0b00" <= ch <= "\u0b7f" for ch in text):
            data = {
                "request_id": "mock-lid-or",
                "language_code": "od-IN",
                "script_code": "Orya",
            }
        else:
            data = {
                "request_id": "mock-lid-en",
                "language_code": "en-IN",
                "script_code": "Latn",
            }
        return JsonResponse(status_code=200, data=data)

    async def close(self) -> None:
        pass


def run_live_sarvam_demo(api_key: str, endpoint: str) -> None:
    logger.info("==================================================")
    logger.info("Sarvam AI Cloud Detection (Live Inference)")
    logger.info("==================================================")

    config = SarvamConfig(
        api_key=Secret(api_key),
        endpoint=endpoint,
        timeout_seconds=20.0,
    )
    provider = SarvamDetectionProvider(config)
    client = get_sync_detection_client(providers=[provider])

    sample_text = "भारत सरकार के विभिन्न मंत्रालयों की आधिकारिक सेवाएं।"
    logger.info("Input text:        %s", sample_text)

    options = DetectionOptions()
    result = client.detect(sample_text, options=options)

    logger.info("Detected language: %s", result.language)
    logger.info("Detected script:   %s", result.script)
    logger.info("Provider:          %s", result.provider.provider)
    logger.info("Elapsed seconds:   %.4f", result.elapsed_seconds)

    logger.info("Candidates:")
    for idx, cand in enumerate(result.candidates, 1):
        logger.info(
            "  %d. %s (Confidence: %.2f%%, Script: %s)",
            idx,
            cand.language,
            cand.confidence * 100,
            cand.script,
        )
    logger.info("")

    # Batch detection across multiple sentences and scripts
    batch_samples = [
        "தமிழ்நாடு அரசின் மின் ஆளுமை முகமை.",
        "ఆంధ్రప్రదేశ్ ప్రభుత్వ అధికారিক సమాచార పోర్టల్.",
        "ଓଡ଼ିଶା ସରକାରଙ୍କ ଅଫିସିଆଲ୍ ପୋର୍ଟାଲ୍।",
        "Welcome to the national single window portal.",
    ]
    logger.info("Batch Detection:")
    batch_results = client.detect_batch(batch_samples)
    for text, res in zip(batch_samples, batch_results, strict=True):
        top_cand = res.candidates[0] if res.candidates else None
        conf = f"{top_cand.confidence * 100:.1f}%" if top_cand else "N/A"
        script = top_cand.script if top_cand else "N/A"
        logger.info("  - %s (Script: %s, Conf: %s) -> '%s'", res.language, script, conf, text)
    logger.info("")


def run_simulated_sarvam_demo() -> None:
    logger.info("==================================================")
    logger.info("Sarvam AI Cloud Detection (Simulated Provider)")
    logger.info("==================================================")
    logger.info("Note: SARVAM_API_KEY not found in environment.")
    logger.info("Running simulated demonstration of Sarvam LID request/response flow.")
    logger.info("")

    config = SarvamConfig(
        api_key=Secret("demo-api-key"),
        endpoint="https://api.sarvam.ai",
        timeout_seconds=20.0,
    )
    transport = MockSarvamTransport()
    provider = SarvamDetectionProvider(config, transport=transport)
    client = get_sync_detection_client(providers=[provider])

    sample_text = "भारत सरकार के विभिन्न मंत्रालयों की आधिकारिक सेवाएं।"
    logger.info("Input text:        %s", sample_text)

    options = DetectionOptions()
    result = client.detect(sample_text, options=options)

    logger.info("Detected language: %s", result.language)
    logger.info("Detected script:   %s", result.script)
    logger.info("Provider:          %s", result.provider.provider)
    logger.info("Elapsed seconds:   %.4f", result.elapsed_seconds)

    logger.info("Candidates:")
    for idx, cand in enumerate(result.candidates, 1):
        logger.info(
            "  %d. %s (Confidence: %.2f%%, Script: %s)",
            idx,
            cand.language,
            cand.confidence * 100,
            cand.script,
        )
    logger.info("")

    batch_samples = [
        "தமிழ்நாடு அரசின் மின் ஆளுமை முகமை.",
        "ఆంధ్రప్రదేశ్ ప్రభుత్వ అధికారিক సమాచార పోర్టల్.",
        "ଓଡ଼ିଶା ସରକାରଙ୍କ ଅଫିସିଆଲ୍ ପୋର୍ଟାଲ୍।",
        "Welcome to the national single window portal.",
    ]
    logger.info("Batch Detection:")
    batch_results = client.detect_batch(batch_samples)
    for text, res in zip(batch_samples, batch_results, strict=True):
        top_cand = res.candidates[0] if res.candidates else None
        conf = f"{top_cand.confidence * 100:.1f}%" if top_cand else "N/A"
        script = top_cand.script if top_cand else "N/A"
        logger.info("  - %s (Script: %s, Conf: %s) -> '%s'", res.language, script, conf, text)
    logger.info("")


def main() -> None:
    api_key = os.environ.get("SARVAM_API_KEY")
    endpoint = os.environ.get("SARVAM_ENDPOINT_URL", "https://api.sarvam.ai")

    if api_key:
        run_live_sarvam_demo(api_key, endpoint)
    else:
        run_simulated_sarvam_demo()
        logger.info("To run against live Sarvam AI inference:")
        logger.info("  export SARVAM_API_KEY='your-actual-api-key'")
        logger.info("  uv run --env-file .env python examples/langdetect/sarvam_demo.py")
        logger.info("")


if __name__ == "__main__":
    main()
