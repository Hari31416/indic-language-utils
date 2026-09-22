# Text Language Detection Examples

This directory provides working examples of text language detection (TLD) using `indic-language-utils` across local and cloud providers.

## Available Examples

- [fasttext_demo.py](fasttext_demo.py) - Offline, high-speed language and script detection using FastText (`lid.176.ftz`).
- [bhashini_demo.py](bhashini_demo.py) - Cloud-based language identification using the Government of India Bhashini ecosystem.
- [multi_service_demo.py](multi_service_demo.py) - Resilient multi-provider routing with automatic cloud-to-local failover, `SingleFlight` deduplication, and caching.

## Prerequisites

For local FastText detection, install the optional `local-tld` dependency group:

```console
uv sync --extra local-tld
```

For live Bhashini inference, ensure your credentials are set in `.env` or your shell:

```bash
BHASHINI_API_KEY="your-actual-bhashini-api-key"
BHASHINI_DETECTION_SERVICE_ID="your-bhashini-tld-pipeline-service-id"
```

## Running the Examples

Run the FastText local detection demo (no API keys required):

```console
uv run python examples/langdetect/fasttext_demo.py
```

Run the Bhashini cloud detection demo:

```console
uv run --env-file .env python examples/langdetect/bhashini_demo.py
```

Run the multi-service resilient routing and caching demo:

```console
uv run python examples/langdetect/multi_service_demo.py
```

## Quick Detection One-Liner

Detect text language synchronously using `detect_sync`:

```python
from indic_language_utils import detect_sync

result = detect_sync("नमस्ते भारत! आप कैसे हैं?")
print(result.language)
print(result.script)
```

Detect text language asynchronously using `detect`:

```python
import asyncio
from indic_language_utils import detect


async def main() -> None:
    result = await detect("வணக்கம், நீங்கள் நலமா?")
    print(result.language)
    print(result.script)


asyncio.run(main())
```

## Batch Detection across Indic Scripts

Detect languages and scripts across multiple inputs in a single call:

```python
from indic_language_utils import detect_batch_sync

samples = [
    "नमस्ते भारत! आपका स्वागत है।",
    "வணக்கம், நீங்கள் நலமா?",
    "হ্যালো, আপনি কেমন আছেন?",
    "నమస్కారం, మీరు ఎలా ఉన్నారు?",
    "ನಮಸ್ಕಾರ, ನೀವು ಹೇಗಿದ್ದೀರಿ?",
    "നമസ്കാരം, സുഖമാണോ?",
    "નમસ્તે, તમે કેમ છો?",
    "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?",
]

results = detect_batch_sync(samples)
for text, res in zip(samples, results, strict=True):
    print(f"{res.language} ({res.script}) -> {text}")
```

## Candidate Ranking and Confidence Scoring

Configure confidence thresholds and candidate limits with `DetectionOptions`:

```python
from indic_language_utils import (
    DetectionOptions,
    FastTextDetectionConfig,
    FastTextDetectionProvider,
    get_sync_detection_client,
)

provider = FastTextDetectionProvider(FastTextDetectionConfig())
client = get_sync_detection_client(providers=[provider])

options = DetectionOptions(max_candidates=3, threshold=0.05)
result = client.detect("भारत सरकार के गृह मंत्रालय", options=options)

for idx, candidate in enumerate(result.candidates, 1):
    print(f"{idx}. {candidate.language} ({candidate.confidence * 100:.1f}%)")
```

## Multi-Provider Resilient Routing

Configure cloud inference with automatic fallback to local models on network failure or service downtime:

```python
import asyncio
from indic_language_utils import (
    BhashiniConfig,
    BhashiniDetectionProvider,
    CapabilityId,
    DetectionClient,
    FastTextDetectionConfig,
    FastTextDetectionProvider,
    OrderedRouter,
    ProviderRegistry,
    Secret,
)


async def main() -> None:
    registry = ProviderRegistry()
    registry.register(
        BhashiniDetectionProvider(
            BhashiniConfig(
                endpoint="https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
                api_key=Secret("your-api-key"),
                detection_service_id="ai4bharat/indic-lang-detect",
            )
        )
    )
    registry.register(FastTextDetectionProvider(FastTextDetectionConfig()))

    router = OrderedRouter(
        registry,
        {CapabilityId.TEXT_LANGUAGE_DETECTION: ("bhashini", "fasttext")},
    )

    async with DetectionClient(router=router) as client:
        result = await client.detect("తెలుగు భాష సాంస్కృతిక వైభవం.")
        print(f"Detected: {result.language} via {result.provider.provider}")


asyncio.run(main())
```
