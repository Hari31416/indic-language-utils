# Translation Examples

This directory provides working translation examples using `indic-language-utils` and the live Bhashini provider.

## Prerequisites

Ensure your `.env` file exists at the repository root with your Bhashini API key:

```bash
BHASHINI_API_KEY="your-actual-bhashini-api-key"
```

The provider inference endpoint and default translation model (`ai4bharat/indictrans-v2-all-gpu--t4`) are loaded automatically from [.indic-language-utils.toml](../../.indic-language-utils.toml).

To execute the runnable demo script against live Bhashini inference:

```bash
uv run --env-file .env python examples/translation/demo.py
```

To execute the Sarvam AI translation demo:

```bash
uv run --env-file .env python examples/translation/sarvam_demo.py
```

To execute the Google Translate demo without requiring any API keys:

```bash
uv run python examples/translation/googletrans_demo.py
```

## Quick One-Liner Translation

For quick translation without manual initialization, use `translate_sync` or `translate`:

```python
from indic_language_utils import translate, translate_sync

# Synchronous one-liner
result_sync = translate_sync("Welcome to India!", "en", "hi")
print(result_sync.text)  # भारत में आपका स्वागत है!

# Asynchronous one-liner
# result_async = await translate("Welcome to India!", "en", "hi")
```

Language parameters accept standard string language codes (`"en"`, `"hi"`, `"ta"`, `"te"`, `"kn"`, `"bn"`, `"mr"`, `"gu"`, `"ml"`, `"pa"`, `"or"`, `"as"`, `"ur"`, etc.) without requiring manual registry normalization.

## Batch Translation

Translate multiple inputs in a single batch call. Input ordering is guaranteed to be preserved:

```python
from indic_language_utils import translate_batch_sync

messages = [
    "Please verify your mobile number.",
    "An OTP has been sent to your registered device.",
    "Do not share your credentials with anyone.",
]

results = translate_batch_sync(messages, "en", "hi")
for req, res in zip(messages, results, strict=True):
    print(f"{req} -> {res.text}")
```

Output:

```text
Please verify your mobile number. -> कृपया अपने मोबाइल नंबर की पुष्टि करें।
An OTP has been sent to your registered device. -> आपके पंजीकृत उपकरण पर एक ओ. टी. पी. भेजा गया है।
Do not share your credentials with anyone. -> अपनी साख किसी के साथ साझा न करें।
```

## Managed Translation Client with Caching

When performing multiple translations or managing application lifecycle, use `get_translation_client`:

```python
import asyncio
from indic_language_utils import get_translation_client


async def main() -> None:
    async with get_translation_client() as client:
        # First call hits the translation provider
        res1 = await client.translate("Welcome to citizen services.", "en", "hi")
        print(f"Translation: {res1.text} (Cached: {res1.cache.hit})")

        # Second identical call resolves instantly from persistent cache
        res2 = await client.translate("Welcome to citizen services.", "en", "hi")
        print(f"Translation: {res2.text} (Cached: {res2.cache.hit})")


asyncio.run(main())
```

## Synchronous Client Facade

If your application runs in a synchronous codebase without an event loop, use `get_sync_translation_client`:

```python
from indic_language_utils import get_sync_translation_client

client = get_sync_translation_client()
result = client.translate("Thank you for your feedback.", "en", "hi")
print(result.text)  # आपकी प्रतिक्रिया के लिए धन्यवाद।
```

## Google Translate Provider

You can also use the unofficial Google Translate provider (`googletrans`) directly without requiring any API keys:

```python
from indic_language_utils import GoogleTranslateProvider, get_sync_translation_client

provider = GoogleTranslateProvider()
client = get_sync_translation_client(providers=[provider])
result = client.translate("Welcome to India!", "en", "hi")
print(result.text)
```

Alternatively, select it as the active translation service provider via environment variable:

```bash
export TRANSLATION_SERVICE_PROVIDER="googletrans"
```

Or configure it as a fallback in `.indic-language-utils.toml`:

```toml
[providers.googletrans]
timeout_seconds = 20.0
max_concurrency = 4

[routes]
translation = ["bhashini", "googletrans"]
```

See [googletrans_demo.py](googletrans_demo.py) for complete runnable examples.

## Multi-Language Translation

Translate from English to any supported Indian language using canonical BCP-47 codes:

```python
from indic_language_utils import translate_sync

# Tamil
res_ta = translate_sync("Your grievance status is resolved.", "en", "ta")
print("Tamil:", res_ta.text)  # உங்கள் குறைதீர்ப்பு நிலை தீர்க்கப்பட்டது.

# Telugu
res_te = translate_sync("Your grievance status is resolved.", "en", "te")
print("Telugu:", res_te.text)
```

## Markdown Preservation

Enable `TextFormat.MARKDOWN` to translate human-readable text while preserving headings, lists, inline code spans, links, and code blocks:

```python
from indic_language_utils import TextFormat, TranslationOptions, translate_sync

markdown_input = """# Citizen Registration Portal

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

result = translate_sync(markdown_input, "en", "hi", options=options)
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

## Special Character Handling in Bhashini

Bhashini's underlying neural machine translation model (IndicTrans2) is sensitive to special characters, punctuation, and non-target script strings:

- **Placeholder Transliteration**: Bhashini attempts to translate or transliterate Latin letters within placeholders (for example, turning `ILU-P-000000` into `आईएलयू-पी-000000` in Hindi or `ஐஎல்யு-பி-000000` in Tamil). The library's placeholder restoration handles script transliteration by targeting the numerical identifier.
- **Bracket and Punctuation Mutation**: Bhashini may drop double brackets down to single brackets or insert whitespace around symbols (e.g., returning `[[...000001]` or `[ ... ]`). The restoration regex accommodates these mutations.
- **Boundary Punctuation Loss**: Punctuation symbols such as trailing asterisks (`*`) or tildes (`~`) at segment boundaries are often dropped by the translation model.
- **Structural Isolation**: The library isolates Markdown structural prefixes (such as `#`, `##`, `-`, `*`, `1.`) and code fences before invoking Bhashini, ensuring structural elements are not sent through neural translation.

## Robustness and Best-Effort Production Mode

To protect downstream services from crashing when translation providers drop tokens or encounter errors, enable `best_effort=True`:

```python
from indic_language_utils import TextFormat, TranslationOptions, translate_sync

options = TranslationOptions(
    text_format=TextFormat.MARKDOWN,
    best_effort=True,
)
result = translate_sync(text, "en", "hi", options=options)
```

Key features of best-effort mode:

- **Natural SOV Reordering**: Enabled by default (`allow_reordered_placeholders=True`). Correctly accepts when Indian language grammar inverts the sequence of nouns, arguments, or links.
- **Placeholder Recovery**: If an external provider drops an inline placeholder (such as a closing delimiter), the missing entity is recovered without raising an unhandled exception.
- **Graceful Provider Fallback**: If all configured providers fail (due to network timeout or provider outage), the client falls back to returning the source text accompanied by a `translation_fallback` warning in `result.warnings`, allowing user-facing workflows to continue uninterrupted.
