# Translation

`TranslationClient` is the canonical API. Requests use canonical `LanguageTag` values and return provider identity, service or model IDs, request IDs, elapsed time, cache status, fallback count, and warnings.

## Bhashini configuration

Bhashini's current pipeline flow supplies the inference endpoint, authorization key, and translation service ID through pipeline configuration. Phase 1 does not run pipeline discovery, so all three values are required:

```console
export BHASHINI_ENDPOINT_URL="https://your-inference-endpoint"
export BHASHINI_API_KEY="..."
export BHASHINI_TRANSLATION_SERVICE_ID="..."
```

The library does not supply a service ID. Configuration can provide a default `translation_service_id` plus language-specific `translation_service_ids`. Exact language-pair overrides take precedence over target-language overrides and the default.

## Asynchronous use

```python
from indic_language_utils import (
    BhashiniConfig,
    BhashiniTranslationProvider,
    CapabilityId,
    DEFAULT_LANGUAGE_REGISTRY,
    ProviderRegistry,
    Settings,
    TranslationClient,
    TranslationRequest,
)
from indic_language_utils.routing import OrderedRouter

settings = Settings.load()
provider = BhashiniTranslationProvider(BhashiniConfig.from_settings(settings))
registry = ProviderRegistry()
registry.register(provider)
router = OrderedRouter(registry, {CapabilityId.TRANSLATION: ("bhashini",)})

async with provider:
    client = TranslationClient(router)
    result = await client.translate(
        TranslationRequest(
            "Your grievance has been registered.",
            DEFAULT_LANGUAGE_REGISTRY.normalize("en-IN"),
            DEFAULT_LANGUAGE_REGISTRY.normalize("hi-IN"),
        )
    )
    print(result.text)
```

`translate_batch()` accepts a tuple of requests and preserves input order. `TranslationOptions` sets the input format, maximum characters per segment, and maximum items per provider batch. These units are explicit. The Bhashini adapter also limits concurrent calls per provider.

Pass a `TranslationProcessorPipeline` to choose preprocessing and post-processing behavior. The default pipeline handles plain text and Markdown structure, then protects URLs, code, and Markdown markers. See the processor guide for composition and custom processor examples.

## Markdown and failures

Set `text_format=TextFormat.MARKDOWN` to preserve indentation, list markers, headings, links, URLs, inline code, fenced code blocks, and blank lines. The processor replaces protected values with numbered placeholders and rejects missing, duplicated, or reordered placeholders. It never returns source text as a substitute for a failed translation.

Rate limits, timeouts, and temporary provider failures use the shared retry policy. The router may then try the next compatible configured provider. Authentication, permission, configuration, and invalid-input errors fail immediately.

## Caching and catalogs

Caching remains off by default. Use `MemoryCache` for a process-local cache or configure `SQLiteCache` for persistence across restarts:

```python
from indic_language_utils import CacheKeyBuilder, CacheSettings, create_translation_cache

cache_settings = CacheSettings(
    enabled=True,
    backend="sqlite",
    path="/var/lib/indic-language-utils/translations.sqlite3",
    namespace="my-application",
    max_entries=50_000,
    ttl_seconds=86_400,
)
cache = create_translation_cache(cache_settings)
client = TranslationClient(
    router,
    cache=cache,
    cache_keys=CacheKeyBuilder(cache_settings.namespace),
)
```

The equivalent environment settings are `ILU_CACHE_ENABLED`, `ILU_CACHE_BACKEND`, `ILU_CACHE_PATH`, `ILU_CACHE_NAMESPACE`, `ILU_CACHE_MAX_ENTRIES`, and `ILU_CACHE_TTL_SECONDS`.

The SQLite cache uses WAL mode and a busy timeout so several processes on one host can share it. Writes remove expired entries and enforce an LRU size bound. Namespaced `clear()` calls do not remove another application's entries. New database files receive owner-only permissions on POSIX systems.

Cache identity includes the input hash, language pair, provider, service ID, options, processor versions, and catalog version. Raw input, credentials, and tenant names do not appear in cache keys. Persistent values use versioned JSON, not pickle. The database contains translated output and provider metadata without encryption, so place it on storage whose permissions, encryption, backup, and retention policy match the data being translated.

SQLite is intended for scripts, PoCs, and single-host deployments. It is not a shared cache for multiple hosts. A network cache such as Redis remains outside the current implementation.

`LocalizationCatalog` is separate reviewed data. A catalog entry applies only when its stable message ID, exact source text, source language, and target language all match, and its status is `reviewed`. The library does not replace terms inside longer sentences.

## Synchronous use

Wrap an asynchronous client with `SyncTranslationClient` in a script:

```python
sync_client = SyncTranslationClient(client)
result = sync_client.translate(request)
```

The synchronous facade rejects calls made inside an active event loop. Use the asynchronous client in that case.

## External adapters

An external adapter implements `TranslationProvider`, declares only `CapabilityId.TRANSLATION`, and registers with `ProviderRegistry`. It must accept canonical language tags, map provider codes internally, return one output per input in order, preserve cancellation, and map failures to the shared exception types. See the adapter author guide for lifecycle and telemetry rules.
