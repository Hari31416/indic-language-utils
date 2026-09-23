# Transliteration Guide

`indic-language-utils` provides provider-neutral support for script transliteration across Indian languages. Transliteration maps text from one writing system or script to another based on phonetic equivalence, distinct from semantic language translation.

## Overview

In Indian digital communication, text is frequently written phonetically using the Latin alphabet (Romanized Indic text such as "namaste", "aap kaise hain", or "vanakkam"). Transliteration converts between Roman script and native Indic scripts without translating meaning.

The library supports two transliteration adapters:

- **Bhashini**: Cloud transliteration via Government of India ULCA pipeline endpoints (`taskType="transliteration"`).
- **AI4Bharat IndicXlit**: Local offline model inference for 21 scheduled Indic languages, available through the `[local-transliteration]` extra.

## Quick Start

### Synchronous Usage

For notebooks, scripts, and synchronous workflows, use top-level helper functions:

```python
import logging
from indic_language_utils import transliterate_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Transliterate English/Roman text to Hindi Devanagari script
result = transliterate_sync("namaste duniya", source="en", target="hi")
logger.info("Transliterated: %s", result.text)
logger.info("Provider: %s", result.provider.provider)
```

For batch processing multiple strings simultaneously:

```python
from indic_language_utils import transliterate_batch_sync

results = transliterate_batch_sync(
    ["namaste", "shukriya", "dhanyavaad"],
    source="en",
    target="hi",
)
for res in results:
    logger.info("%s -> %s", res.source_text, res.text)
```

### Asynchronous Usage

For asynchronous applications such as FastAPI services or asyncio event loops:

```python
import asyncio
import logging
from indic_language_utils import transliterate, transliterate_batch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    # Single text transliteration
    result = await transliterate("vanakkam", source="en", target="ta")
    logger.info("Tamil: %s", result.text)

    # Batch transliteration
    items = ["namaste", "dhanyavad"]
    batch_results = await transliterate_batch(items, source="en", target="hi")
    for item in batch_results:
        logger.info("Hindi: %s", item.text)


asyncio.run(main())
```

## Client and Lifecycle Management

For high-throughput systems and fine-grained routing control, instantiate `TransliterationClient` directly with an `OrderedRouter`:

```python
import asyncio
import logging
from indic_language_utils import (
    BhashiniConfig,
    BhashiniTransliterationProvider,
    CapabilityId,
    OrderedRouter,
    ProviderRegistry,
    Secret,
    TransliterationClient,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_client() -> None:
    config = BhashiniConfig(
        endpoint="https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
        api_key=Secret("your-bhashini-api-key"),
        transliteration_service_id="bhashini/translit-service-id",
    )
    bhashini_provider = BhashiniTransliterationProvider(config)

    registry = ProviderRegistry()
    registry.register(bhashini_provider)

    router = OrderedRouter(
        registry,
        {CapabilityId.TRANSLITERATION: ("bhashini",)},
    )

    async with TransliterationClient(router) as client:
        result = await client.transliterate("namaste", source="en", target="hi")
        logger.info("Result: %s", result.text)


asyncio.run(run_client())
```

## Local Offline Transliteration

To perform offline transliteration without network requests or API keys, install the `local-transliteration` extra:

```bash
pip install 'indic-language-utils[local-transliteration]'
```

### Aksharamukha (Lightweight, Pure-Python)

Aksharamukha provides instant, zero-setup transliteration across all 22 Eighth Schedule Indian languages, 120+ scripts, and standardized Romanization schemes (ITRANS, ISO 15919, IAST, Harvard-Kyoto) with zero deep-learning dependencies:

```python
import asyncio
import logging
from indic_language_utils import (
    AksharamukhaConfig,
    AksharamukhaTransliterationProvider,
    CapabilityId,
    OrderedRouter,
    ProviderRegistry,
    TransliterationClient,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_aksharamukha() -> None:
    config = AksharamukhaConfig(roman_scheme="ITRANS", nativize=True)
    provider = AksharamukhaTransliterationProvider(config)

    registry = ProviderRegistry()
    registry.register(provider)

    router = OrderedRouter(
        registry,
        {CapabilityId.TRANSLITERATION: ("aksharamukha",)},
    )

    async with TransliterationClient(router) as client:
        # Cross-Indic script conversion (Tamil -> Devanagari)
        res_ta_hi = await client.transliterate("வணக்கம்", source="ta", target="hi")
        logger.info("Tamil to Devanagari: %s", res_ta_hi.text)

        # Roman to Devanagari
        res_en_hi = await client.transliterate("namaste", source="en", target="hi")
        logger.info("Roman to Hindi: %s", res_en_hi.text)

        # Devanagari to Roman
        res_hi_en = await client.transliterate("नमस्ते", source="hi", target="en")
        logger.info("Devanagari to Roman: %s", res_hi_en.text)


asyncio.run(run_aksharamukha())
```

### AI4Bharat IndicXlit (Neural Model)

For neural transformer-based transliteration, install the `neural-transliteration` extra:

```bash
pip install 'indic-language-utils[neural-transliteration]'
```

```python
import asyncio
import logging
from indic_language_utils import (
    CapabilityId,
    IndicXlitConfig,
    IndicXlitTransliterationProvider,
    OrderedRouter,
    ProviderRegistry,
    TransliterationClient,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_offline() -> None:
    config = IndicXlitConfig(beam_width=4, rescore=True)
    provider = IndicXlitTransliterationProvider(config)

    registry = ProviderRegistry()
    registry.register(provider)

    router = OrderedRouter(
        registry,
        {CapabilityId.TRANSLITERATION: ("indicxlit",)},
    )

    async with TransliterationClient(router) as client:
        # Roman to Indic
        hi_result = await client.transliterate("namaste", source="en", target="hi")
        logger.info("Hindi: %s", hi_result.text)

        # Indic to Roman
        en_result = await client.transliterate("नमस्ते", source="hi", target="en")
        logger.info("Roman: %s", en_result.text)


asyncio.run(run_offline())
```

## Multi-Provider Fallback Routing

Configure fallback routing so that if a primary cloud provider encounters rate limits or network failures, requests seamlessly fall back to local offline transliteration:

```python
from indic_language_utils import (
    BhashiniConfig,
    BhashiniTransliterationProvider,
    CapabilityId,
    IndicXlitTransliterationProvider,
    OrderedRouter,
    ProviderRegistry,
    Secret,
    TransliterationClient,
)

registry = ProviderRegistry()
registry.register(
    BhashiniTransliterationProvider(
        BhashiniConfig(
            endpoint="https://example.com/compute",
            api_key=Secret("key"),
            transliteration_service_id="service-1",
        )
    )
)
registry.register(IndicXlitTransliterationProvider())

# Bhashini first, with automatic fallback to IndicXlit
router = OrderedRouter(
    registry,
    {CapabilityId.TRANSLITERATION: ("bhashini", "indicxlit")},
)
client = TransliterationClient(router)
```

## Caching

Transliteration results can be cached in memory or in persistent SQLite databases:

```python
from indic_language_utils import (
    CacheSettings,
    TransliterationClient,
    create_transliteration_cache,
)

cache_settings = CacheSettings(
    enabled=True,
    backend="sqlite",
    path=".cache/transliteration.sqlite3",
    max_entries=50000,
    ttl_seconds=86400,
)
cache = create_transliteration_cache(cache_settings)
client = TransliterationClient(router, cache=cache)
```

## HTTP API Endpoint

When running the bundled backend service with `indic-server`, transliteration is exposed at `POST /api/transliterate`:

### Request

```json
{
  "text": "namaste duniya",
  "source": "en",
  "target": "hi",
  "provider": "bhashini"
}
```

### Response

```json
{
  "text": "नमस्ते दुनिया",
  "source": "en-IN",
  "target": "hi-IN",
  "provider": "bhashini",
  "service_id": "service-1",
  "model_id": "ai4bharat/indicxlit",
  "unofficial": false,
  "elapsed_seconds": 0.0452,
  "cached": false,
  "cache_backend": null,
  "warnings": []
}
```
