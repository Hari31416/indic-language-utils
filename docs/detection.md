# Text Language Detection

The text language detection subsystem identifies the natural language and writing script of text across Indian languages. It supports offline local classification via FastText models, cloud-based inference pipelines via Bhashini, rule-based Unicode script identification, and multi-provider failover routing.

## Script Detection

Script identification determines the primary writing script of a text using Unicode block analysis. The `detect_script` function requires no external dependencies and operates with negligible latency:

```python
from indic_language_utils import detect_script

script = detect_script("नमस्ते दुनिया")
print(script)  # Deva

script = detect_script("வணக்கம் உலகம்")
print(script)  # Taml
```

The function inspects character code points and returns the dominant ISO 15924 four-letter script code:

- `Deva`: Devanagari (Hindi, Marathi, Sanskrit, Nepali, Konkani, Bodo, Dogri, Maithili)
- `Beng`: Bengali and Assamese
- `Guru`: Gurmukhi (Punjabi)
- `Gujr`: Gujarati
- `Orya`: Odia
- `Taml`: Tamil
- `Telu`: Telugu
- `Knda`: Kannada
- `Mlym`: Malayalam
- `Olck`: Ol Chiki (Santali)
- `Mtei`: Meetei Mayek (Manipuri)
- `Arab`: Perso-Arabic (Urdu, Sindhi, Kashmiri)
- `Latn`: Latin (English and romanized text)

If the input contains no letters belonging to these script blocks, `detect_script` returns `None`.

## High-Level Detection APIs

For common applications, top-level convenience functions handle client initialization and lifecycle management automatically.

### Synchronous Detection

Use `detect_sync` for single inputs in scripts or command-line tools:

```python
from indic_language_utils import detect_sync

result = detect_sync("നമസ്കാരം, സുഖമാണോ?")
print(f"Language: {result.language}")
print(f"Script: {result.script}")
print(f"Confidence: {result.candidates[0].confidence:.2%}")
print(f"Provider: {result.provider.provider}")
```

### Asynchronous Detection

Use `detect` inside asynchronous applications:

```python
import asyncio
from indic_language_utils import detect


async def main() -> None:
    result = await detect("ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?")
    print(f"Language: {result.language}")
    print(f"Confidence: {result.candidates[0].confidence:.2%}")


asyncio.run(main())
```

### Batch Detection

When processing collections of texts, batch functions preserve input ordering and improve throughput:

```python
from indic_language_utils import detect_batch_sync

inputs = [
    "नमस्ते भारत! आपका स्वागत है।",
    "வணக்கம், நீங்கள் நலமா?",
    "হ্যালো, আপনি কেমন আছেন?",
    "నమస్కారం, మీరు ఎలా ఉన్నారు?",
]

results = detect_batch_sync(inputs)
for text, result in zip(inputs, results, strict=True):
    print(f"{result.language} ({result.script}) -> {text}")
```

The asynchronous counterpart is `detect_batch(texts, options=...)`.

## Detection Options and Candidate Ranking

Pass `DetectionOptions` to configure the number of predicted language candidates and the minimum confidence threshold:

```python
from indic_language_utils import DetectionOptions, detect_sync

options = DetectionOptions(max_candidates=3, threshold=0.05)
result = detect_sync("भारत सरकार गृह मंत्रालय", options=options)

print(f"Primary language: {result.language}")
print("Candidate breakdown:")
for candidate in result.candidates:
    print(f"- {candidate.language} ({candidate.script}): {candidate.confidence * 100:.1f}%")
```

### Detection Result Structure

Every detection call returns a `DetectionResult` containing complete operation metadata:

- `language`: Canonical `LanguageTag` of the top prediction.
- `confidence`: Prediction score between `0.0` and `1.0`.
- `script`: Detected script code (such as `Deva` or `Taml`).
- `candidates`: Tuple of `LanguageCandidate` objects, sorted by descending confidence.
- `provider`: `ProviderIdentity` of the provider that produced the result.
- `model_id`: Identifier of the model that executed the detection (e.g., `lid.176.ftz`).
- `request_id`: Tracing correlation identifier.
- `elapsed_seconds`: Wall-clock execution time.
- `cache`: `CacheMetadata` indicating whether the result came from cache (`hit=True/False`).
- `warnings`: Tuple of `WarningInfo` messages encountered during execution.

## Supported Providers

### FastText Provider

The `FastTextDetectionProvider` uses the pre-trained FastText `lid.176.ftz` model for offline classification. It delivers high throughput without network overhead and requires the `local-tld` extra:

```bash
pip install "indic-language-utils[local-tld]"
```

Usage with custom configuration:

```python
from indic_language_utils import (
    FastTextDetectionConfig,
    FastTextDetectionProvider,
    get_sync_detection_client,
)

config = FastTextDetectionConfig(
    low_memory=False,
    max_concurrency=8,
)
provider = FastTextDetectionProvider(config)
client = get_sync_detection_client(providers=[provider])

result = client.detect("ગુજરાતી સાહિત્ય પરિષદ")
print(result.language)
```

The FastText adapter combines statistical language identification with Unicode script detection to validate and enrich predictions.

### Bhashini Provider

The `BhashiniDetectionProvider` calls the Government of India Bhashini text language detection pipeline. It requires network access, an API key, and a detection service ID:

```bash
export BHASHINI_ENDPOINT_URL="https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
export BHASHINI_API_KEY="your-api-key"
export BHASHINI_DETECTION_SERVICE_ID="your-tld-service-id"
```

Programmatic instantiation:

```python
import asyncio
from indic_language_utils import (
    BhashiniConfig,
    BhashiniDetectionProvider,
    CapabilityId,
    DetectionClient,
    OrderedRouter,
    ProviderRegistry,
    Secret,
)


async def main() -> None:
    config = BhashiniConfig(
        endpoint="https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
        api_key=Secret("your-api-key"),
        detection_service_id="your-tld-service-id",
        max_concurrency=8,
    )
    provider = BhashiniDetectionProvider(config)
    registry = ProviderRegistry()
    registry.register(provider)

    router = OrderedRouter(
        registry,
        {CapabilityId.TEXT_LANGUAGE_DETECTION: ("bhashini",)},
    )

    async with DetectionClient(router=router) as client:
        result = await client.detect("தமிழ்நாடு அரசு")
        print(f"Detected: {result.language} via {result.provider.provider}")


asyncio.run(main())
```

### Sarvam AI Provider

The `SarvamDetectionProvider` calls the Sarvam AI Language Identification API (`POST https://api.sarvam.ai/text-lid`). It identifies the language and script of input text across 22 scheduled Indian languages plus English:

```bash
export SARVAM_API_KEY="your-sarvam-api-key"
export SARVAM_ENDPOINT_URL="https://api.sarvam.ai"
```

Programmatic instantiation:

```python
import asyncio
from indic_language_utils import (
    CapabilityId,
    DetectionClient,
    OrderedRouter,
    ProviderRegistry,
    SarvamConfig,
    SarvamDetectionProvider,
    Secret,
)


async def main() -> None:
    config = SarvamConfig(
        api_key=Secret("your-api-key"),
        endpoint="https://api.sarvam.ai",
        max_concurrency=8,
    )
    provider = SarvamDetectionProvider(config)
    registry = ProviderRegistry()
    registry.register(provider)

    router = OrderedRouter(
        registry,
        {CapabilityId.TEXT_LANGUAGE_DETECTION: ("sarvam",)},
    )

    async with DetectionClient(router=router) as client:
        result = await client.detect("தமிழ்நாடு அரசு")
        print(f"Detected: {result.language} via {result.provider.provider}")


asyncio.run(main())
```

## Resilient Routing and Failover

In production systems, combine cloud inference with local models to ensure uninterrupted operation during network outages:

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

    # Cloud primary
    registry.register(
        BhashiniDetectionProvider(
            BhashiniConfig(
                endpoint="https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
                api_key=Secret("your-api-key"),
                detection_service_id="your-tld-service-id",
            )
        )
    )

    # Local offline fallback
    registry.register(FastTextDetectionProvider(FastTextDetectionConfig()))

    # Ordered route: try Bhashini first, fall back to FastText
    router = OrderedRouter(
        registry,
        {CapabilityId.TEXT_LANGUAGE_DETECTION: ("bhashini", "fasttext")},
    )

    async with DetectionClient(router=router) as client:
        result = await client.detect("ಕನ್ನಡ ಸಾಹಿತ್ಯ ಸಮ್ಮೇಳನ")
        print(f"Result: {result.language} (Provider: {result.provider.provider})")


asyncio.run(main())
```

The router attempts Bhashini first. If the request times out or receives a transient HTTP 5xx error, it automatically invokes FastText without throwing an exception to the caller.

The same fallback can be configured declaratively in `.indic-language-utils.toml`:

```toml
[routes]
text_language_detection = ["bhashini", "fasttext"]
```

## Caching Detection Results

Language detection is deterministic for identical input strings. Enabling cache reduces latency from milliseconds to microseconds and eliminates redundant inference:

```python
from indic_language_utils import (
    CacheSettings,
    create_detection_cache,
    get_sync_detection_client,
)

cache_settings = CacheSettings(
    enabled=True,
    backend="sqlite",
    path=".cache/detection.sqlite3",
    namespace="language-detection",
    max_entries=100000,
    ttl_seconds=604800,  # 7 days
)

cache = create_detection_cache(cache_settings)
client = get_sync_detection_client()

# First run evaluates the model
res1 = client.detect("తెలుగు భాష సాంస్కృతిక వైభవం")
print(f"Hit 1: {res1.cache.hit}")  # False

# Subsequent run hits cache
res2 = client.detect("తెలుగు భాష సాంస్కృతిక వైభవం")
print(f"Hit 2: {res2.cache.hit}")  # True
```

The cache uses `SingleFlight` concurrency locks to prevent duplicate inflight calls for identical strings during burst traffic.

## Error Handling

All detection exceptions inherit from `LanguageUtilsError`:

```python
from indic_language_utils import detect_sync
from indic_language_utils.errors import (
    ConfigurationError,
    InvalidInputError,
    MissingOptionalDependencyError,
    ProviderTimeoutError,
    RateLimitError,
)

try:
    result = detect_sync(" ")
except InvalidInputError:
    print("Input string was empty or contained only whitespace")
except MissingOptionalDependencyError:
    print("FastText dependency missing; install with [local-tld]")
except RateLimitError:
    print("Provider rate limit reached; retries exhausted")
except ProviderTimeoutError:
    print("Provider timed out after configured deadline")
except ConfigurationError as exc:
    print(f"Configuration error: {exc}")
```
