# Translation Examples

This directory provides working translation examples using `indic-language-utils` and the live Bhashini provider.

## Prerequisites

Ensure your `.env` file exists at the repository root with your Bhashini API key:

```bash
BHASHINI_API_KEY="your-actual-bhashini-api-key"
```

The provider inference endpoint and default translation model (`ai4bharat/indictrans-v2-all-gpu--t4`) are loaded automatically from [.indic-language-utils.toml](../../.indic-language-utils.toml).

To execute the runnable demo script against live Bhashini inference:

```console
uv run --env-file .env python examples/translation/demo.py
```

## Special Character Handling in Bhashini

Bhashini's underlying neural machine translation model (IndicTrans2) is sensitive to special characters, punctuation, and non-target script strings:

- **Placeholder Transliteration**: Bhashini attempts to translate or transliterate Latin letters within placeholders (for example, turning `ILU-P-000000` into `आईएलयू-पी-000000` in Hindi or `ஐஎல்யு-பி-000000` in Tamil). The library's placeholder restoration handles script transliteration by targeting the numerical identifier.
- **Bracket and Punctuation Mutation**: Bhashini may drop double brackets down to single brackets or insert whitespace around symbols (e.g., returning `[[...000001]` or `[ ... ]`). The restoration regex accommodates these mutations.
- **Boundary Punctuation Loss**: Punctuation symbols such as trailing asterisks (`*`) or tildes (`~`) at segment boundaries are often dropped by the translation model.
- **Structural Isolation**: The library isolates Markdown structural prefixes (such as `#`, `##`, `-`, `*`, `1.`) and code fences before invoking Bhashini, ensuring structural elements are not sent through neural translation.

## Example 1: Asynchronous Text Translation

Translate single sentences or paragraphs asynchronously:

```python
import asyncio
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


async def main() -> None:
    settings = Settings.load()
    provider = BhashiniTranslationProvider(BhashiniConfig.from_settings(settings))

    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLATION: ("bhashini",)})

    en = DEFAULT_LANGUAGE_REGISTRY.normalize("en")
    hi = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")

    async with provider:
        client = TranslationClient(router)
        request = TranslationRequest("Welcome to the citizen services portal.", en, hi)
        result = await client.translate(request)
        print("Translation:", result.text)


asyncio.run(main())
```

Output:

```text
Translation: नागरिक सेवा पोर्टल में आपका स्वागत है।
```

## Example 2: Batch Translation

Translate multiple inputs in a single batch call. Input ordering is guaranteed to be preserved:

```python
requests = (
    TranslationRequest("Please verify your mobile number.", en, hi),
    TranslationRequest("An OTP has been sent to your registered device.", en, hi),
    TranslationRequest("Do not share your credentials with anyone.", en, hi),
)
batch_results = await client.translate_batch(requests)
for req, res in zip(requests, batch_results, strict=True):
    print(f"{req.text} -> {res.text}")
```

Output:

```text
Please verify your mobile number. -> कृपया अपने मोबाइल नंबर की पुष्टि करें।
An OTP has been sent to your registered device. -> आपके पंजीकृत उपकरण पर एक ओ. टी. पी. भेजा गया है।
Do not share your credentials with anyone. -> अपनी साख किसी के साथ साझा न करें।
```

## Example 3: Multiple Language Targets

Translate from English to different Indian languages using canonical BCP-47 language tags:

```python
ta = DEFAULT_LANGUAGE_REGISTRY.normalize("ta")
req_tamil = TranslationRequest("Your grievance status is resolved.", en, ta)
res_tamil = await client.translate(req_tamil)
print("Tamil:", res_tamil.text)
```

Output:

```text
Tamil: உங்கள் குறைதீர்ப்பு நிலை தீர்க்கப்பட்டது.
```

## Example 4: Markdown Preservation

Enable `TextFormat.MARKDOWN` to translate human-readable text while keeping headings, lists, inline code spans, links, and fenced blocks intact:

```python
from indic_language_utils import TextFormat, TranslationOptions

markdown_input = """# Citizen Registration Portal

Please keep the following information ready:
- Application Reference: `APP-9021-X`
- Portal Link: [National Portal](https://services.india.gov.in)
- Verification Code: `4488`

```
curl -X GET https://api.example.gov.in/status
```

Submit your grievance before the deadline."""

result = await client.translate(
    TranslationRequest(
        markdown_input,
        en,
        hi,
        options=TranslationOptions(text_format=TextFormat.MARKDOWN),
    )
)
print(result.text)
```

Output:

```text
# नागरिक पंजीकरण पोर्टल

कृपया निम्नलिखित जानकारी तैयार रखेंः
- आवेदन संदर्भः `APP-9021-X`
- पोर्टल लिंकः [राष्ट्रीय पोर्टल] (https://services.india.gov.in)
- सत्यापन कोडः `4488`

```
curl -X GET https://api.example.gov.in/status
```

समय सीमा से पहले अपनी शिकायत दर्ज करा दें।
```

## Example 5: Persistent SQLite Caching

Attach a persistent cache to prevent redundant API calls:

```python
from indic_language_utils import CacheKeyBuilder, create_translation_cache

cache = create_translation_cache(settings.cache)
client = TranslationClient(
    router,
    cache=cache,
    cache_keys=CacheKeyBuilder(settings.cache.namespace),
)

# First call performs network inference (cache hit: False)
res1 = await client.translate(request)

# Repeated call resolves immediately from local SQLite database (cache hit: True)
res2 = await client.translate(request)
print(f"Elapsed: {res2.elapsed_seconds:.4f}s, Cache Hit: {res2.cache.hit}")
```

## Robustness and Best-Effort Production Mode

To protect downstream services from crashing when translation providers drop tokens or encounter errors, enable `best_effort=True`:

```python
from indic_language_utils import TextFormat, TranslationOptions, TranslationRequest

options = TranslationOptions(
    text_format=TextFormat.MARKDOWN,
    best_effort=True,
)
result = await client.translate(TranslationRequest(text, en, hi, options=options))
```

Key features of best-effort mode:

- **Natural SOV Reordering**: Enabled by default (`allow_reordered_placeholders=True`). Correctly accepts when Indian language grammar inverts the sequence of nouns, arguments, or links.
- **Placeholder Recovery**: If an external provider drops an inline placeholder (such as a closing delimiter), the missing entity is recovered without raising an unhandled exception.
- **Graceful Provider Fallback**: If all configured providers fail (due to network timeout or provider outage), the client falls back to returning the source text accompanied by a `translation_fallback` warning in `result.warnings`, allowing user-facing workflows to continue uninterrupted.
