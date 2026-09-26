# User Guide

The `indic-language-utils` library provides provider-neutral foundations for Indian language operations in Python applications. It standardizes language identification, text translation, transliteration, and speech capabilities through a unified runtime architecture. Applications can start with local or low-cost providers during prototyping, then switch routing configuration for production without rewriting text processing or domain logic.

## System Architecture

The system decouples application code from concrete provider APIs through four coordinated layers:

- Canonical language tags: A shared language registry maps language codes, regional variants, and script aliases to canonical BCP 47 tags.
- Unified routing and failover: The router dispatches requests to configured providers and manages multi-provider fallback when services encounter transient errors.
- Shared resilience and persistence: Concurrency limiters bound inflight requests per provider, retries handle exponential backoff, and caching prevents duplicate downstream calls.
- Processor pipelines: Pre-processing and post-processing preserve document structure, markdown syntax, URLs, and code blocks across neural translation models.

## Core Capabilities

The library currently supports the following capabilities:

- Text Translation: Translates plain text or structured Markdown across 22 scheduled Indian languages and English, with support for batching, best-effort recovery, and localization catalogs.
- Text Transliteration: Converts phonetic or Romanized text to native Indic scripts and native scripts to Romanized forms using Bhashini and Aksharamukha.
- Text Language Detection: Identifies languages across short and long texts using local FastText models or cloud inference pipelines.
- Script Identification: Analyzes Unicode code points to detect 12+ Indic scripts and Latin without external dependencies.
- Multi-Provider Routing: Routes requests sequentially across an ordered list of providers, falling back when primary services fail.
- Concurrency and Rate Limiting: Limits active calls per provider to adhere to service quotas and prevent client exhaustion.
- Automatic Retries: Retries transient network failures, timeouts, and rate limits with exponential backoff and jitter.
- Multi-Backend Caching: Caches operation results in process memory or persistent SQLite databases with WAL mode and size limits.
- Structured Content Protection: Isolates headings, bullet markers, code spans, links, and formatting before invoking neural translation.

## Installation

See the [installation and quick start guide](getting-started.md) for provider extras, a
credential-free development setup, Bhashini environment variables, and working examples.

## Supported Providers

The system provides built-in adapters for multiple local and cloud providers:

- Bhashini: Official Government of India ecosystem providing neural translation (IndicTrans2), text language detection, and transliteration via pipeline inference endpoints. Requires an API key and service identifiers.
- Aksharamukha: Lightweight, offline, pure-Python transliteration engine supporting 120+ scripts, cross-Indic script conversions, and standardized Romanization schemes.
- IndicXlit: The adapter remains in the codebase, but its install extra is omitted from this beta because upstream dependencies have known vulnerabilities.
- FastText: Offline, high-speed language detection using Facebook's compressed language identification model (`lid.176.ftz`). Requires no network access or credentials.
- Google Translate: Unofficial translation adapter powered by `googletrans`, useful for local development and testing without credentials.

Custom adapters can be registered by implementing the translation, transliteration, or detection provider protocols
and adding their capability declarations to a `ProviderRegistry`.

## Language Tags and Registry

All library operations operate on canonical `LanguageTag` objects defined in `indic_language_utils.languages`. The default registry recognizes all 22 Eighth Schedule Indian languages plus English.

Canonical tags follow the `language-Region` pattern for Indian locales, such as `hi-IN` for Hindi, `ta-IN` for Tamil, `bn-IN` for Bengali, and `en-IN` for Indian English.

The registry accepts common abbreviations, ISO 639-1 two-letter codes, ISO 639-3 three-letter codes, and case-insensitive aliases:

```python
from indic_language_utils import DEFAULT_LANGUAGE_REGISTRY

# All of the following resolve to LanguageTag("hi", region="IN")
tag1 = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
tag2 = DEFAULT_LANGUAGE_REGISTRY.normalize("hin")
tag3 = DEFAULT_LANGUAGE_REGISTRY.normalize("hi-IN")
tag4 = DEFAULT_LANGUAGE_REGISTRY.normalize("HI_in")

print(tag1)
```

Higher-level library functions accept plain string codes directly and normalize them automatically.

## Usage Styles

The library provides three levels of abstraction to accommodate different application architectures.

### One-Liner Functions

Top-level functions offer zero-setup invocation with automatic client lifecycle and settings discovery:

```python
from indic_language_utils import detect_sync, transliterate_sync, translate_sync

# Detect language
detection = detect_sync("नमस्ते भारत!")
print(f"Language: {detection.language}, Script: {detection.script}")

# Transliterate text (Roman to Devanagari)
transliteration = transliterate_sync("namaste", "en", "hi")
print(f"Transliteration: {transliteration.text}")

# Translate text
translation = translate_sync("Welcome to India!", "en", "hi")
print(f"Translation: {translation.text}")
```

Asynchronous equivalents (`detect`, `transliterate`, `translate`, `detect_batch`, `transliterate_batch`, `translate_batch`) are available for async runtimes:

```python
import asyncio
from indic_language_utils import detect, transliterate, translate


async def run() -> None:
    detected = await detect("வணக்கம், நீங்கள் நலமா?")
    print(detected.language)

    transliterated = await transliterate("vanakkam", "en", "ta")
    print(transliterated.text)

    translated = await translate("How are you?", "en", "ta")
    print(translated.text)


asyncio.run(run())
```

### Managed Client Lifecycle

For services handling multiple requests, create a managed client that reuses HTTP connections, connection pools, and caches:

```python
import asyncio
from indic_language_utils import get_translation_client, get_transliteration_client


async def service() -> None:
    async with (
        get_translation_client() as trans_client,
        get_transliteration_client() as xlit_client,
    ):
        xlit = await xlit_client.transliterate("bharat", "en", "hi")
        result1 = await trans_client.translate("Please enter your name.", "en", "hi")
        result2 = await trans_client.translate("Please enter your email.", "en", "hi")
        print(xlit.text)
        print(result1.text)
        print(result2.text)


asyncio.run(service())
```

For synchronous environments without an active event loop, use `get_sync_translation_client()`, `get_sync_transliteration_client()`, or `get_sync_detection_client()`:

```python
from indic_language_utils import get_sync_translation_client

client = get_sync_translation_client()
result = client.translate("Status: Approved", "en", "hi")
print(result.text)
```

### Low-Level Composition

Applications requiring custom routing, bespoke caches, or specific adapter configurations can assemble components explicitly:

```python
from indic_language_utils import (
    CapabilityId,
    FastTextDetectionConfig,
    FastTextDetectionProvider,
    MemoryCache,
    OrderedRouter,
    ProviderRegistry,
)
from indic_language_utils.detection import DetectionClient

registry = ProviderRegistry()
registry.register(FastTextDetectionProvider(FastTextDetectionConfig(low_memory=True)))

router = OrderedRouter(
    registry,
    {CapabilityId.TEXT_LANGUAGE_DETECTION: ("fasttext",)},
)

client = DetectionClient(router=router, cache=MemoryCache(max_entries=5000))
```

## Resilience and Fault Tolerance

Production deployments face transient network failures, provider rate limits, and service degradations. The library builds resilience into every level of execution.

### Multi-Provider Fallback

Routers evaluate provider candidates in configured order. When a primary provider fails due to a retryable error (such as HTTP 429, HTTP 503, or a connection timeout), the router seamlessly invokes the next provider in the route tuple:

```toml
[routes]
translation = ["bhashini", "googletrans"]
transliteration = ["bhashini", "aksharamukha"]
text_language_detection = ["bhashini", "fasttext"]
```

### Concurrency Limits

Each adapter enforces a concurrency limiter to prevent flooding provider endpoints:

```toml
[providers.bhashini]
max_concurrency = 8
timeout_seconds = 20.0
```

Calls exceeding the limit wait asynchronously for an open slot without blocking other threads or processes.

### Retries with Backoff

Adapters retry transient errors using exponential backoff with random jitter:

```toml
[retry]
max_attempts = 3
base_delay_seconds = 0.25
max_delay_seconds = 5.0
```

Non-retryable errors (authentication failures, invalid input, unsupported language pairs) fail immediately without retrying.

## Caching Strategy

The library provides pluggable caching backends to reduce latency and downstream API costs:

- `NullCache`: Disables caching entirely (default).
- `MemoryCache`: Fast in-memory LRU cache for transient scripts and tests.
- `SQLiteCache`: Persistent single-host storage using SQLite WAL mode and LRU eviction.

Translation checks an exact document cache first, then reuses unchanged translatable segments
when a document has changed. Cache keys incorporate the hashed input text, normalized source
and target languages, provider identity, service and configured model IDs, request options, and
active processor pipeline versions. `cache.hit` is true only when no provider call was needed.

To prevent cache stampedes under high concurrency, requests for identical keys are coalesced using `SingleFlight`.

## Content Protection and Markdown

Neural translation models often corrupt code blocks, syntax markers, and URLs. The built-in translation processor pipeline isolates and protects these elements:

- Markdown headings, blockquotes, and lists are isolated from translatable body text.
- Inline code spans, URLs, and Markdown links are replaced with protected numeric tokens before translation.
- After translation, tokens are replaced with the original content, accommodating language-specific Subject-Object-Verb (SOV) reordering.

See [processors.md](processors.md) for custom processor creation and pipeline customization.

## Configuration and Secrets

Settings are loaded with unified precedence from project TOML files, user configurations, and environment variables. Secrets such as API keys are rejected from TOML files and must be supplied via environment variables.

See [configuration.md](configuration.md) for detailed configuration syntax, precedence rules, and environment variables.

## Next Steps

Explore the detailed capability guides for practical recipes and API references:

- [transliteration.md](transliteration.md): Comprehensive guide to text transliteration, Roman-Indic conversion, suggestions, and offline IndicXlit usage.
- [translation.md](translation.md): Comprehensive guide to text translation, Markdown preservation, batching, and localization catalogs.
- [detection.md](detection.md): Comprehensive guide to text language detection, script identification, and candidate ranking.
- [configuration.md](configuration.md): Complete configuration file format, precedence rules, and environment variables.
- [processors.md](processors.md): Deep dive into translation processor pipelines and custom segment processors.
