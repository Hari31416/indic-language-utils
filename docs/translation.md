# Translation

`TranslationClient` is the canonical API. Requests use canonical `LanguageTag` values and return provider identity, service or model IDs, request IDs, elapsed time, cache status, fallback count, and warnings.

## Bhashini configuration

Bhashini's current pipeline flow supplies the inference endpoint, authorization key, and translation service ID through pipeline configuration. Phase 1 does not run pipeline discovery, so all three values are required:

```console
export BHASHINI_ENDPOINT_URL="https://your-inference-endpoint"
export BHASHINI_API_KEY="..."
export BHASHINI_TRANSLATION_SERVICE_ID="..."
```

The library does not default the service ID. Bhashini service availability depends on the selected pipeline and language pair.

## Asynchronous use

```python
from indic_language_utils import (
    BhashiniConfig,
    BhashiniTranslationProvider,
    CapabilityId,
    DEFAULT_LANGUAGE_REGISTRY,
    ProviderRegistry,
    TranslationClient,
    TranslationRequest,
)
from indic_language_utils.routing import OrderedRouter

provider = BhashiniTranslationProvider(BhashiniConfig.from_env())
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

## Markdown and failures

Set `text_format=TextFormat.MARKDOWN` to preserve indentation, list markers, headings, links, URLs, inline code, fenced code blocks, and blank lines. The processor replaces protected values with numbered placeholders and rejects missing, duplicated, or reordered placeholders. It never returns source text as a substitute for a failed translation.

Rate limits, timeouts, and temporary provider failures use the shared retry policy. The router may then try the next compatible configured provider. Authentication, permission, configuration, and invalid-input errors fail immediately.

## Caching and catalogs

Pass `MemoryCache` to opt into runtime caching. Cache identity includes the input hash, language pair, provider, service ID, options, processor versions, and catalog version. Raw input, credentials, and tenant names do not appear in cache keys.

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
