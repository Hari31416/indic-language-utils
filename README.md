# indic-language-utils

Provider-neutral foundations for Indian language operations in Python.

`indic-language-utils` standardizes language detection, neural machine translation, script identification, and text processing across Indian languages. It abstracts concrete cloud and local engines behind unified, resilient interfaces, allowing applications to start with local or low-cost providers and switch routing configuration for production without rewriting business logic.

## Key Features

- Provider Neutrality: Code against high-level capability interfaces. Swap, configure, or chain providers without changing text processing or domain code.
- Text Translation: Translate plain text or complex Markdown documents across 22 scheduled Indian languages and English.
- Text Language Detection: Identify languages using offline FastText classification (`lid.176.ftz`) or cloud inference pipelines via Bhashini.
- Transliteration: Convert between Roman script and native Indic scripts via Bhashini or AI4Bharat IndicXlit.
- Speech to text: Transcribe audio with Bhashini and configure ASR models by language.
- Text to speech: Generate audio with Bhashini and pass model-specific voice settings.
- Script Identification: Fast, zero-dependency Unicode script identification across 12+ Indic scripts and Latin.
- Document and Code Protection: Structural pre-processors and post-processors protect headings, bullet markers, inline code spans, URLs, and code blocks from neural translation corruption.
- Resilient Execution: Automatic multi-provider fallback routing, bounded concurrency limits per provider, and exponential backoff retries with jitter.
- High-Performance Caching: In-memory LRU and multi-process SQLite caches with write-ahead logging (WAL mode) and stampede protection.
- Canonical Normalization: Shared language registry recognizing all 22 Eighth Schedule Indian languages plus English, mapping aliases and regional codes to BCP 47.
- Localization Catalogs: Match reviewed human translations for critical UI strings before dispatching to neural engines.

## Getting started

Install the core package with `pip install indic-language-utils`. Provider selection is explicit,
and local detection requires an optional extra. The
[installation and quick start guide](docs/getting-started.md) covers a credential-free setup,
Bhashini configuration, and the first detection and translation calls.

## Supported Providers

| Provider             | Capability                              | Mode               | Prerequisites                 |
| :------------------- | :-------------------------------------- | :----------------- | :---------------------------- |
| **Aksharamukha**     | Transliteration (120+ scripts)          | Offline / Local    | `[local-transliteration]` extra |
| **Bhashini**         | Translation, Detection, Transliteration, STT, TTS | Cloud API          | API key, Endpoint, Service ID |
| **Sarvam AI**        | Translation, Detection, STT, TTS        | Cloud API          | API key (`SARVAM_API_KEY`)    |
| **AI4Bharat IndicXlit** | Transliteration                      | Offline / Local    | `[neural-transliteration]` extra |
| **FastText**         | Text Language Detection                 | Offline / Local    | `[local-tld]` extra           |
| **Google Translate** | Translation                             | Cloud (unofficial) | `[googletrans]` extra         |

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
transliteration_service_id = "default-transliteration-model-id"
max_concurrency = 8

[providers.sarvam]
endpoint = "https://api.sarvam.ai"
model = "sarvam-translate:v1"
stt_model_id = "saaras:v4"
tts_model_id = "bulbul:v3"
max_concurrency = 8

[routes]
translation = ["sarvam", "bhashini", "googletrans"]
text_language_detection = ["sarvam", "bhashini", "fasttext"]
transliteration = ["bhashini", "indicxlit"]
speech_to_text = ["bhashini", "sarvam"]
text_to_speech = ["bhashini", "sarvam"]
```

Supply credentials securely through environment variables:

```bash
export BHASHINI_API_KEY="your-bhashini-api-key"
export SARVAM_API_KEY="your-sarvam-api-key"
```

## Documentation

Comprehensive guides are available in the documentation site:

- [Installation and Quick Start](docs/getting-started.md): Provider setup and first calls.
- [User Guide](docs/user-guide.md): Architecture overview, core capabilities, and usage styles.
- [Translation Guide](docs/translation.md): Synchronous and asynchronous translation, Markdown preservation, and catalogs.
- [Detection Guide](docs/detection.md): Local FastText and cloud Bhashini detection, script analysis, and candidate scoring.
- [Speech to text guide](docs/stt.md): Bhashini and Sarvam transcription and model IDs.
- [STT example](examples/stt/README.md): Transcribe audio with Bhashini or Sarvam.
- [Text to speech guide](docs/tts.md): Bhashini and Sarvam synthesis and voice options.
- [TTS example](examples/tts/README.md): Generate audio with Bhashini or Sarvam.
- [Configuration Reference](docs/configuration.md): Project TOML file formats, precedence rules, and environment variables.
- [Processor Pipelines](docs/processors.md): Structural processors, segment processors, and custom pipeline authoring.
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

## Interactive Testing Workbench

A local evaluation workbench and REST API server is included for testing translation, language detection, and script identification interactively:

```bash
# Build the web interface
cd web && pnpm install && pnpm build && cd ..

# Launch the FastAPI server with static UI mounted at http://127.0.0.1:8000
uv run indic-server
```

Explore interactive API documentation at `http://127.0.0.1:8000/docs`.

## License

This project is licensed under the [MIT License](LICENSE).
