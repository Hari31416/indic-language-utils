"""Runnable examples demonstrating cloud text language detection with Bhashini."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from indic_language_utils import (
    BhashiniConfig,
    BhashiniDetectionProvider,
    DetectionOptions,
    Secret,
    get_sync_detection_client,
)
from indic_language_utils.providers.bhashini import JsonResponse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("bhashini_demo")


class MockBhashiniTransport:
    """Mock JSON transport for demonstration when live credentials are not available."""

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json: Mapping[str, object],
        timeout_seconds: float,
    ) -> JsonResponse:
        input_data = json.get("inputData", {})
        inputs: list[dict[str, Any]] = []
        if isinstance(input_data, dict):
            raw_input = input_data.get("input", [])
            if isinstance(raw_input, list):
                inputs = raw_input

        output_items: list[dict[str, Any]] = []
        for item in inputs:
            text = str(item.get("source", ""))
            # Simulate Bhashini multi-candidate detection response
            if any("\u0900" <= ch <= "\u097f" for ch in text):
                preds = [
                    {"langCode": "hi", "langScore": 0.96},
                    {"langCode": "mr", "langScore": 0.03},
                ]
            elif any("\u0b80" <= ch <= "\u0bff" for ch in text):
                preds = [
                    {"langCode": "ta", "langScore": 0.98},
                ]
            elif any("\u0c00" <= ch <= "\u0c7f" for ch in text):
                preds = [
                    {"langCode": "te", "langScore": 0.95},
                ]
            else:
                preds = [
                    {"langCode": "en", "langScore": 0.99},
                ]
            output_items.append({"langPrediction": preds})

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


def run_live_bhashini_demo(api_key: str, endpoint: str, detection_service_id: str) -> None:
    logger.info("==================================================")
    logger.info("Bhashini Cloud Detection (Live Inference)")
    logger.info("==================================================")

    config = BhashiniConfig(
        endpoint=endpoint,
        api_key=Secret(api_key),
        detection_service_id=detection_service_id,
        timeout_seconds=20.0,
    )
    provider = BhashiniDetectionProvider(config)
    client = get_sync_detection_client(providers=[provider])

    sample_text = "भारत सरकार के विभिन्न मंत्रालयों की आधिकारिक सेवाएं।"
    logger.info("Input text:        %s", sample_text)

    options = DetectionOptions(max_candidates=3, threshold=0.01)
    result = client.detect(sample_text, options=options)

    logger.info("Detected language: %s", result.language)
    logger.info("Detected script:   %s", result.script)
    logger.info("Provider:          %s", result.provider.provider)
    if result.provider.model_id:
        logger.info("Model:             %s", result.provider.model_id)
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

    # Batch detection across multiple sentences
    batch_samples = [
        "தமிழ்நாடு அரசின் மின் ஆளுமை முகமை.",
        "ఆంధ్రప్రదేశ్ ప్రభుత్వ అధికారిక సమాచార పోర్టల్.",
        "Welcome to the national single window portal.",
    ]
    logger.info("Batch Detection:")
    batch_results = client.detect_batch(batch_samples)
    for text, res in zip(batch_samples, batch_results, strict=True):
        top_cand = res.candidates[0] if res.candidates else None
        conf = f"{top_cand.confidence * 100:.1f}%" if top_cand else "N/A"
        logger.info("  - %s (Conf: %s) -> '%s'", res.language, conf, text)
    logger.info("")


def run_simulated_bhashini_demo() -> None:
    logger.info("==================================================")
    logger.info("Bhashini Cloud Detection (Simulated Provider)")
    logger.info("==================================================")
    logger.info("Note: BHASHINI_API_KEY or BHASHINI_DETECTION_SERVICE_ID not found in environment.")
    logger.info("Running simulated demonstration of Bhashini pipeline request/response flow.")
    logger.info("")

    config = BhashiniConfig(
        endpoint="https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
        api_key=Secret("demo-api-key"),
        detection_service_id="ai4bharat/indic-lang-detect",
        timeout_seconds=20.0,
    )
    transport = MockBhashiniTransport()
    provider = BhashiniDetectionProvider(config, transport=transport)
    client = get_sync_detection_client(providers=[provider])

    sample_text = "भारत सरकार के विभिन्न मंत्रालयों की आधिकारिक सेवाएं।"
    logger.info("Input text:        %s", sample_text)

    options = DetectionOptions(max_candidates=3, threshold=0.01)
    result = client.detect(sample_text, options=options)

    logger.info("Detected language: %s", result.language)
    logger.info("Detected script:   %s", result.script)
    logger.info("Provider:          %s", result.provider.provider)
    if result.provider.model_id:
        logger.info("Model:             %s", result.provider.model_id)
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
        "ఆంధ్రప్రదేశ్ ప్రభుత్వ అధికారిక సమాచార పోర్టల్.",
        "Welcome to the national single window portal.",
    ]
    logger.info("Batch Detection:")
    batch_results = client.detect_batch(batch_samples)
    for text, res in zip(batch_samples, batch_results, strict=True):
        top_cand = res.candidates[0] if res.candidates else None
        conf = f"{top_cand.confidence * 100:.1f}%" if top_cand else "N/A"
        logger.info("  - %s (Conf: %s) -> '%s'", res.language, conf, text)
    logger.info("")


def main() -> None:
    api_key = os.environ.get("BHASHINI_API_KEY")
    endpoint = os.environ.get(
        "BHASHINI_ENDPOINT_URL",
        "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
    )
    detection_service_id = os.environ.get("BHASHINI_DETECTION_SERVICE_ID") or os.environ.get(
        "BHASHINI_TLD_SERVICE_ID"
    )

    if api_key and detection_service_id:
        run_live_bhashini_demo(api_key, endpoint, detection_service_id)
    else:
        run_simulated_bhashini_demo()
        logger.info("To run against live Bhashini inference:")
        logger.info("  export BHASHINI_API_KEY='your-actual-api-key'")
        logger.info("  export BHASHINI_DETECTION_SERVICE_ID='your-pipeline-service-id'")
        logger.info("  uv run --env-file .env python examples/langdetect/bhashini_demo.py")
        logger.info("")


if __name__ == "__main__":
    main()
