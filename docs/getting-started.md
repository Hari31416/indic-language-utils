# Installation and quick start

This guide gets language detection and translation running with either optional local adapters or
Bhashini.

## Requirements

- Python 3.11 or 3.12
- `pip` or `uv`

## Choose an installation

The core package contains the shared API, Bhashini adapters, script detection, routing, retries,
and caches:

```bash
pip install indic-language-utils
```

Use `uv` if your project already manages dependencies with it:

```bash
uv add indic-language-utils
```

The core package does not install a local language model or select a translation provider. Add the
extras required by your application:

```bash
# Offline FastText language detection
pip install "indic-language-utils[local-tld]"

# Unofficial Google Translate adapter
pip install "indic-language-utils[googletrans]"

# Both optional adapters
pip install "indic-language-utils[local-tld,googletrans]"
```

## Run without Bhashini credentials

Install both optional adapters and select Google Translate for translation:

```bash
pip install "indic-language-utils[local-tld,googletrans]"
export TRANSLATION_SERVICE_PROVIDER="googletrans"
```

FastText becomes the default detection route when the `local-tld` extra is installed. Google
Translate uses an unofficial network adapter and is best suited to development and non-critical
fallbacks.

Detect a language and script:

```python
from indic_language_utils import detect_sync

result = detect_sync("नमस्ते भारत! आप कैसे हैं?")
print(result.language)  # hi-IN
print(result.script)  # Deva
print(f"{result.confidence:.2%}")
```

Translate text:

```python
from indic_language_utils import translate_sync

result = translate_sync("Welcome to digital governance services.", "en", "hi")
print(result.text)
```

## Use Bhashini

Install the core package, then provide the API endpoint, credential, and service identifiers through
environment variables:

```bash
pip install indic-language-utils
export BHASHINI_API_KEY="your-api-key"
export BHASHINI_ENDPOINT_URL="https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
export BHASHINI_TRANSLATION_SERVICE_ID="your-translation-service-id"
export BHASHINI_DETECTION_SERVICE_ID="your-detection-service-id"
```

The same `detect_sync` and `translate_sync` calls now use the configured Bhashini routes. See the
[configuration reference](configuration.md) for TOML settings, route order, caching, and environment
variable precedence.

## Use the asynchronous API

Network calls and batches have asynchronous equivalents:

```python
import asyncio

from indic_language_utils import translate


async def main() -> None:
    result = await translate("How can I help you today?", "en", "ta")
    print(result.text)


asyncio.run(main())
```

Continue with the [translation guide](translation.md) for batching and Markdown protection, or the
[detection guide](detection.md) for candidate scores and provider setup.
