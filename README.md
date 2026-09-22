# indic-language-utils

Provider-neutral foundations for Indian language operations in Python.

`indic-language-utils` standardizes language detection, neural machine translation, script identification, and text processing across Indian languages. It abstracts concrete cloud and local engines behind unified, resilient interfaces, allowing applications to start with local or low-cost providers and switch routing configuration for production without rewriting business logic.

## Key Features

- Provider Neutrality: Code against high-level capability interfaces. Swap, configure, or chain providers without changing text processing or domain code.
- Text Translation: Translate plain text or complex Markdown documents across 22 scheduled Indian languages and English.
- Text Language Detection: Identify languages using offline FastText classification (`lid.176.ftz`) or cloud inference pipelines via Bhashini.
- Script Identification: Fast, zero-dependency Unicode script identification across 12+ Indic scripts and Latin.
- Document and Code Protection: Structural pre-processors and post-processors protect headings, bullet markers, inline code spans, URLs, and code blocks from neural translation corruption.
- Resilient Execution: Automatic multi-provider fallback routing, bounded concurrency limits per provider, and exponential backoff retries with jitter.
- High-Performance Caching: In-memory LRU and multi-process SQLite caches with write-ahead logging (WAL mode) and stampede protection.
- Canonical Normalization: Shared language registry recognizing all 22 Eighth Schedule Indian languages plus English, mapping aliases and regional codes to BCP 47.
- Localization Catalogs: Match reviewed human translations for critical UI strings before dispatching to neural engines.

## Installation

Install the core package using `pip`:

```bash
pip install indic-language-utils
```

Or with `uv`:

```bash
uv add indic-language-utils
```

### Optional Dependency Extras

Install optional provider packages based on your requirements:

```bash
# Local offline FastText language detection
pip install "indic-language-utils[local-tld]"

# Unofficial Google Translate adapter
pip install "indic-language-utils[googletrans]"

# All optional adapters
pip install "indic-language-utils[local-tld,googletrans]"
```

## Quick Start

### Text Language and Script Detection

Detect natural language and script synchronously:

```python
from indic_language_utils import detect_sync

result = detect_sync("नमस्ते भारत! आप कैसे हैं?")
print(f"Language: {result.language}")  # hi-IN
print(f"Script: {result.script}")  # Deva
print(f"Confidence: {result.confidence:.2%}")
```

Inspect multiple candidate predictions and scores:

```python
from indic_language_utils import DetectionOptions, detect_sync

options = DetectionOptions(max_candidates=3, threshold=0.05)
result = detect_sync("தமிழ்நாடு அரசு தலைமைச் செயலகம்", options=options)

for candidate in result.candidates:
    print(f"- {candidate.language} ({candidate.script}): {candidate.confidence:.2%}")
```

### Text Translation

Translate single strings with automatic language code normalization:

```python
from indic_language_utils import translate_sync

result = translate_sync("Welcome to digital governance services.", "en", "hi")
print(result.text)  # डिजिटल शासन सेवाओं में आपका स्वागत है।
```

Translate in asynchronous applications:

```python
import asyncio
from indic_language_utils import translate


async def main() -> None:
    result = await translate("How can I help you today?", "en", "ta")
    print(result.text)


asyncio.run(main())
```

### Batch Processing

Process multiple texts while guaranteeing input order:

```python
from indic_language_utils import translate_batch_sync

inputs = [
    "Please verify your mobile number.",
    "An OTP has been sent to your registered device.",
    "Do not share your credentials with anyone.",
]

results = translate_batch_sync(inputs, "en", "hi")
for src, res in zip(inputs, results, strict=True):
    print(f"{src} -> {res.text}")
```

### Markdown Translation with Protected Content

Preserve Markdown layout, URLs, inline code, and code blocks using `TextFormat.MARKDOWN` and `best_effort=True`:

````python
from indic_language_utils import TextFormat, TranslationOptions, translate_sync

markdown_input = """# Citizen Registration Portal

Please keep the following information ready:
- Application Reference: `APP-9021-X`
- Portal Link: [National Portal](https://services.india.gov.in)
- Verification Code: `4488`

```bash
curl -X GET https://api.example.gov.in/status
```

Submit your grievance before the deadline."""

options = TranslationOptions(
    text_format=TextFormat.MARKDOWN,
    best_effort=True,
)

result = translate_sync(markdown_input, "en", "hi", options=options)
print(result.text)
````

## Supported Providers

| Provider             | Capability              | Mode               | Prerequisites                 |
| :------------------- | :---------------------- | :----------------- | :---------------------------- |
| **Bhashini**         | Translation, Detection  | Cloud API          | API key, Endpoint, Service ID |
| **FastText**         | Text Language Detection | Offline / Local    | `[local-tld]` extra           |
| **Google Translate** | Translation             | Cloud (unofficial) | `[googletrans]` extra         |

## Configuration

The library uses a tiered configuration system combining project TOML files (`.indic-language-utils.toml`), environment variables, and programmatic overrides.

Example `.indic-language-utils.toml`:

```toml
[cache]
enabled = true
backend = "sqlite"
path = ".cache/translations.sqlite3"
max_entries = 50000
ttl_seconds = 86400

[retry]
max_attempts = 3
base_delay_seconds = 0.25
max_delay_seconds = 5.0

[providers.bhashini]
endpoint = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
translation_service_id = "default-translation-model-id"
detection_service_id = "default-tld-model-id"
max_concurrency = 8

[routes]
translation = ["bhashini", "googletrans"]
text_language_detection = ["bhashini", "fasttext"]
```

Supply credentials securely through environment variables:

```bash
export BHASHINI_API_KEY="your-bhashini-api-key"
```

## Documentation

Comprehensive guides are available in the documentation site:

- [User Guide](docs/user-guide.md): Architecture overview, core capabilities, and usage styles.
- [Translation Guide](docs/translation.md): Synchronous and asynchronous translation, Markdown preservation, and catalogs.
- [Detection Guide](docs/detection.md): Local FastText and cloud Bhashini detection, script analysis, and candidate scoring.
- [Configuration Reference](docs/configuration.md): Project TOML file formats, precedence rules, and environment variables.
- [Processor Pipelines](docs/processors.md): Structural processors, segment processors, and custom pipeline authoring.
- [Adapter Author Guide](docs/adapter-author-guide.md): Implementing and contributing new provider adapters.
- [Architecture Proposal](plans/architecture-proposal.md): Design philosophy and ecosystem review.
- [Changelog](CHANGELOG.md): Release history adhering to Keep a Changelog.

## Development

Install the locked development environment with `uv`:

```bash
uv sync --dev
uv run pre-commit install
```

Run test suite, code quality checks, and local documentation server:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
uv run mkdocs serve
uv run mkdocs build --strict
```

## License

This project is licensed under the [MIT License](LICENSE).
