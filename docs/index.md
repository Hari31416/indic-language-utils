# Indic Language Utils

`indic-language-utils` is a Python library providing provider-neutral foundations for Indian language applications. It standardizes language identification, neural machine translation, transliteration, and speech capabilities across diverse cloud and local providers.

## Core Philosophy

Indian language processing often requires stitching together disparate vendor APIs, handling unique writing scripts, preserving formatting structure, and accommodating Subject-Object-Verb (SOV) grammatical reordering.

`indic-language-utils` addresses these challenges by offering:

- Provider neutrality: Code against high-level capability interfaces rather than provider-specific SDKs. Swap or chain providers via configuration without changing application logic.
- Resilient architecture: Built-in multi-provider fallback routing, concurrency limits, and automatic retries with exponential backoff and jitter.
- Document and code protection: Specialized pre-processors and post-processors ensure Markdown structure, code blocks, links, and formatting tokens survive neural translation intact.
- High-performance caching: Process-local memory and multi-process SQLite caches with write-ahead logging (WAL mode) to reduce latency and API costs.
- Canonical language normalization: Shared registry recognizing all 22 Eighth Schedule Indian languages plus English, standardizing dialect codes and script tags to canonical BCP 47.

## Quick Start

Install the package with your desired provider extras:

```console
# Core library with Bhashini cloud support
pip install indic-language-utils

# With local FastText language detection
pip install "indic-language-utils[local-tld]"

# With unofficial Google Translate fallback
pip install "indic-language-utils[googletrans]"

# All providers
pip install "indic-language-utils[local-tld,googletrans]"
```

### Language Detection in One Line

```python
from indic_language_utils import detect_sync

result = detect_sync("नमस्ते भारत! आप कैसे हैं?")
print(f"Language: {result.language}")
print(f"Script: {result.script}")
print(f"Confidence: {result.confidence:.2%}")
```

### Text Translation in One Line

```python
from indic_language_utils import translate_sync

result = translate_sync("Welcome to digital governance services.", "en", "hi")
print(result.text)  # डिजिटल शासन सेवाओं में आपका स्वागत है।
```

### Markdown Translation with Protected Content

```python
from indic_language_utils import TextFormat, TranslationOptions, translate_sync

markdown_text = """# User Portal

Please verify your credentials:
- Reference ID: `REF-2024-99`
- Portal Link: [Services Portal](https://services.india.gov.in)

```bash
curl -X GET https://api.example.gov.in/health
```

Thank you for your cooperation."""

options = TranslationOptions(
    text_format=TextFormat.MARKDOWN,
    best_effort=True,
)

result = translate_sync(markdown_text, "en", "ta", options=options)
print(result.text)
```

## Documentation Roadmap

Explore the comprehensive documentation guides:

- [User Guide](user-guide.md): Architecture overview, core capabilities, provider matrix, and usage levels.
- [Translation](translation.md): Synchronous and asynchronous translation, batching, Markdown preservation, and catalogs.
- [Detection](detection.md): Local FastText and cloud Bhashini language detection, script analysis, and candidate scoring.
- [Configuration](configuration.md): Project TOML configuration, precedence hierarchy, and environment variables.
- [Processors](processors.md): Structure processors, segment processors, and custom pipeline authoring.
- [Adapter Author Guide](adapter-author-guide.md): Implementing and contributing new provider adapters.
