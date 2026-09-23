# Translation

The translation subsystem provides neural machine translation across 22 Eighth Schedule Indian languages and English. It includes adapters for Bhashini and Google Translate, multi-provider fallback routing, Markdown syntax preservation, Subject-Object-Verb (SOV) reordering support, and localization catalog overrides.

## Quick Start One-Liners

Top-level functions manage client lifecycles and settings discovery automatically. Language arguments accept standard language codes (such as `"en"`, `"hi"`, `"ta"`, `"te"`, `"bn"`, `"gu"`) as strings or canonical `LanguageTag` objects.

### Synchronous Translation

Use `translate_sync` in scripts, synchronous views, and command-line utilities:

```python
from indic_language_utils import translate_sync

result = translate_sync("Welcome to India!", "en", "hi")
print(result.text)  # भारत में आपका स्वागत है!
```

### Asynchronous Translation

Use `translate` in asynchronous applications and web services:

```python
import asyncio
from indic_language_utils import translate


async def main() -> None:
    result = await translate("How can I help you today?", "en", "ta")
    print(result.text)


asyncio.run(main())
```

### Batch Translation

Translate collections of strings with preserved input order:

```python
from indic_language_utils import translate_batch_sync

queries = [
    "Please verify your mobile number.",
    "An OTP has been sent to your registered device.",
    "Do not share your credentials with anyone.",
]

results = translate_batch_sync(queries, "en", "hi")
for source, result in zip(queries, results, strict=True):
    print(f"{source} -> {result.text}")
```

The asynchronous counterpart is `translate_batch(texts, source, target, options=...)`.

## Managed Client Lifecycle

When translating repeatedly or managing application lifecycle, construct a managed client via `get_translation_client` or `get_sync_translation_client`. The factory automatically loads configuration from project files and initializes configured caches:

```python
import asyncio
from indic_language_utils import get_translation_client


async def main() -> None:
    async with get_translation_client() as client:
        # First call queries the translation provider
        res1 = await client.translate("Welcome to citizen services.", "en", "hi")
        print(f"Translation: {res1.text} (Cached: {res1.cache.hit})")

        # Second call resolves instantly from cache
        res2 = await client.translate("Welcome to citizen services.", "en", "hi")
        print(f"Translation: {res2.text} (Cached: {res2.cache.hit})")


asyncio.run(main())
```

In synchronous applications without an event loop:

```python
from indic_language_utils import get_sync_translation_client

client = get_sync_translation_client()
result = client.translate("Thank you for your feedback.", "en", "hi")
print(result.text)
```

The synchronous facade rejects calls made inside an active event loop to prevent blocking async execution.

## Supported Providers

### Bhashini Provider

Bhashini is the Government of India language technology initiative, hosting high-quality neural translation models (IndicTrans2).

Configuration requires an inference endpoint, authorization key, and translation service ID:

```bash
export BHASHINI_ENDPOINT_URL="https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
export BHASHINI_API_KEY="your-api-key"
export BHASHINI_TRANSLATION_SERVICE_ID="your-default-service-id"
```

The provider supports language-specific service ID overrides via configuration. Exact language pairs take precedence over target-language defaults:

```toml
[providers.bhashini]
endpoint = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
translation_service_id = "default-service-id"
timeout_seconds = 20.0
max_concurrency = 8

[providers.bhashini.translation_service_ids]
"hi-IN" = "service-for-any-source-to-hindi"
"en-IN>ta-IN" = "service-for-english-to-tamil"
```

### Sarvam AI Provider

The `SarvamTranslationProvider` calls the Sarvam AI translation API (`POST https://api.sarvam.ai/translate`). It supports translation between English and 22 scheduled Indian languages using Sarvam models (such as `sarvam-translate:v1` or `mayura:v1`).

Environment variables:

```bash
export SARVAM_API_KEY="your-sarvam-api-key"
export SARVAM_ENDPOINT_URL="https://api.sarvam.ai"
export SARVAM_MODEL="sarvam-translate:v1"
```

Usage in Python:

```python
from indic_language_utils import (
    SarvamConfig,
    SarvamTranslationProvider,
    Secret,
    get_sync_translation_client,
)

config = SarvamConfig(
    api_key=Secret("your-sarvam-api-key"),
    model="sarvam-translate:v1",
)
provider = SarvamTranslationProvider(config)
client = get_sync_translation_client(providers=[provider])

result = client.translate("Hello world", "en", "hi")
```

### Google Translate Provider

The `GoogleTranslateProvider` integrates the unofficial `googletrans` package. It requires no API keys or accounts and serves as an effective provider for local development, tests, and non-critical fallbacks.

Install the optional dependency:

```bash
pip install "indic-language-utils[googletrans]"
```

Usage in Python:

```python
from indic_language_utils import GoogleTranslateProvider, get_sync_translation_client

provider = GoogleTranslateProvider()
client = get_sync_translation_client(providers=[provider])

result = client.translate("Hello world", "en", "hi")
print(result.text)
```

The adapter automatically maps internal language tags to Google Translate dialect codes (e.g., Konkani `kok` maps to `gom`, and Manipuri `mni` maps to `mni-mtei`).

## Multi-Provider Fallback Routing

To prevent single points of failure, configure an ordered route. If the primary cloud service suffers downtime or rate limiting, the router automatically attempts the secondary provider:

```python
import asyncio
from indic_language_utils import (
    BhashiniConfig,
    BhashiniTranslationProvider,
    CapabilityId,
    GoogleTranslateProvider,
    OrderedRouter,
    ProviderRegistry,
    Secret,
    TranslationClient,
)


async def main() -> None:
    registry = ProviderRegistry()
    registry.register(
        BhashiniTranslationProvider(
            BhashiniConfig(
                endpoint="https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
                api_key=Secret("your-api-key"),
                translation_service_id="bhashini-service-id",
            )
        )
    )
    registry.register(GoogleTranslateProvider())

    router = OrderedRouter(
        registry,
        {CapabilityId.TRANSLATION: ("bhashini", "googletrans")},
    )

    async with TranslationClient(router=router) as client:
        result = await client.translate("System update available", "en", "ta")
        print(f"Result: {result.text} (via {result.provider.provider})")


asyncio.run(main())
```

The same route can be declared in `.indic-language-utils.toml`:

```toml
[routes]
translation = ["bhashini", "googletrans"]
```

## Markdown Preservation and Best-Effort Mode

Standard neural translation engines frequently mutilate Markdown markup, translate code terms, or drop URLs. The library uses a specialized structural pipeline to protect formatted text.

### Preserving Markdown Structure

Set `text_format=TextFormat.MARKDOWN` to preserve formatting syntax:

````python
from indic_language_utils import TextFormat, TranslationOptions, translate_sync

markdown_text = """# Citizen Registration Portal

Please keep the following information ready:
- Application Reference: `APP-9021-X`
- Portal Link: [National Portal](https://services.india.gov.in)
- Verification Code: `4488`

```
curl -X GET https://api.example.gov.in/status
```

Submit your grievance before the deadline."""

options = TranslationOptions(
    text_format=TextFormat.MARKDOWN,
    best_effort=True,
)

result = translate_sync(markdown_text, "en", "hi", options=options)
print(result.text)
````

The structure processor protects:

- Headings (`#`, `##`, etc.) and list item markers (`-`, `*`, `1.`).
- Inline code spans (`` `APP-9021-X` ``) and fenced code blocks (` ``` ... ``` `).
- Markdown links (`[text](url)`) and raw URLs (`https://...`).
- Blank lines and paragraph indentation.

Long Markdown lines are split without cutting through inline code or URLs. If a provider drops a
protected placeholder, the client retries the segment and then translates the text around each
protected value separately. This preserves the value and avoids an output validation error, though
the translated wording around that value may be less natural.

### Indic Neural Translation Nuances

Indian language translation presents unique structural challenges:

- SOV Reordering: English follows Subject-Verb-Object (SVO) order, whereas Indic languages follow Subject-Object-Verb (SOV) order. This naturally shifts the position of placeholders, links, and arguments in translated text. The library accommodates this reordering without rejecting the output.
- Placeholder Transliteration: Some neural models attempt to transliterate Latin placeholder characters into native scripts (for example, converting `ILU-P-000000` into `आईएलयू-पी-000000`). The library's restoration logic identifies identifiers by numerical sequence to reliably match placeholders.
- Bracket Mutation: Models occasionally drop outer brackets (turning `[[P_0]]` into `[P_0]`) or inject spaces. The placeholder decoder tolerates these mutations.

### Best-Effort Production Mode

Enable `best_effort=True` in production to maximize uptime and prevent user-facing crashes:

- Allows natural reordering of placeholders.
- Recovers dropped placeholders by appending or restoring missing entities.
- If all providers fail due to network outage, falls back to returning the source text accompanied by a warning in `result.warnings`.

```python
options = TranslationOptions(
    text_format=TextFormat.MARKDOWN,
    best_effort=True,
)
```

## Caching and Localization Catalogs

### Caching Backends

Caching is disabled by default. Configure `MemoryCache` for transient in-memory storage or `SQLiteCache` for persistent disk storage across application restarts:

```python
from indic_language_utils import (
    CacheKeyBuilder,
    CacheSettings,
    create_translation_cache,
)

settings = CacheSettings(
    enabled=True,
    backend="sqlite",
    path=".cache/translations.sqlite3",
    namespace="production-app",
    max_entries=50000,
    ttl_seconds=86400,
)

cache = create_translation_cache(settings)
```

The SQLite cache uses write-ahead logging (WAL mode) with a busy timeout, allowing concurrent processes on one host to read and write safely. Expired entries are evicted automatically, and database files receive owner-only permissions (`0600`) on POSIX systems.

Cache keys incorporate the input text hash, normalized language pair, provider identity, service IDs, request options, processor versions, and catalog version. Cache entries store versioned JSON without using pickle.

### Localization Catalogs

A `LocalizationCatalog` stores verified human translations for critical UI strings, error messages, and legal notices.

A catalog entry takes precedence over neural translation only when:

- The message ID, exact source text, source language, and target language all match.
- The entry status is marked as `reviewed`.

```python
from indic_language_utils import (
    CatalogEntry,
    CatalogStatus,
    DEFAULT_LANGUAGE_REGISTRY,
    LocalizationCatalog,
    TranslationClient,
    TranslationRequest,
)

catalog = LocalizationCatalog(
    (
        CatalogEntry(
            message_id="auth.logout",
            source_text="Log Out",
            source_language=DEFAULT_LANGUAGE_REGISTRY.normalize("en-IN"),
            target_language=DEFAULT_LANGUAGE_REGISTRY.normalize("hi-IN"),
            target_text="लॉग आउट करें",
            status=CatalogStatus.REVIEWED,
        ),
    )
)

client = TranslationClient(router=router, catalog=catalog)

request = TranslationRequest(
    text="Log Out",
    source=DEFAULT_LANGUAGE_REGISTRY.normalize("en-IN"),
    target=DEFAULT_LANGUAGE_REGISTRY.normalize("hi-IN"),
    message_id="auth.logout",
)
result = await client.translate(request)
print(result.text)  # Uses vetted catalog entry: "लॉग आउट करें"
```

The catalog matches entire messages and does not substitute terms inside longer sentences.

## Translation Result Structure

`TranslationResult` encapsulates the translation output and comprehensive execution metadata:

- `text`: The translated and reconstructed string.
- `source`: Canonical `LanguageTag` of the source text.
- `target`: Canonical `LanguageTag` of the target text.
- `provider`: `ProviderIdentity` of the provider that fulfilled the request.
- `service_id`: Model or service identifier (such as Bhashini service ID or Google engine).
- `request_id`: Tracing correlation identifier.
- `elapsed_seconds`: Wall-clock execution time in seconds.
- `cache`: `CacheMetadata` indicating cache hit status.
- `fallbacks`: Number of fallback providers invoked before success.
- `warnings`: Tuple of `WarningInfo` items documenting any non-fatal irregularities.

## Custom Processor Pipelines

For custom preprocessing (such as stripping sensitive fields, wrapping terms, or applying custom normalizations), pass a `TranslationProcessorPipeline` to `TranslationClient`.

See [processors.md](processors.md) for custom segment processor examples and protocol specifications.
