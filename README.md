# indic-language-utils

A Python 3.11 and 3.12 library for Indian-language translation, text language detection, transliteration, speech-to-text, and text-to-speech. The project uses `uv` and will be published on PyPI as `indic-language-utils`. Its Python import is `indic_language_utils`. The code is licensed under the MIT License.

Phase 0 implements the shared library foundation, Phase 1 adds structured translation with Bhashini and Google Translate adapters, and Phase 2 adds text language detection with local FastText and cloud Bhashini adapters. Runtime caching can use bounded process memory or persistent SQLite storage. The architecture and ecosystem review is in [plans/architecture-proposal.md](plans/architecture-proposal.md).

The intended shape is a small core with optional provider packages. Applications should be able to start with local or low-cost providers during a proof of concept, then change routing configuration for production without rewriting text and audio handling.

Work will be delivered in this order:

- shared library foundation
- text translation
- text language detection, abbreviated as TLD
- transliteration
- non-streaming speech-to-text, abbreviated as STT
- non-streaming text-to-speech, abbreviated as TTS

Provider work starts with Bhashini and then Sarvam. Unofficial Google or Microsoft adapters can be added later as opt-in extras or external plugins. Optional dependency groups will keep translation-only installations free of speech and audio dependencies.

Cross-cutting requirements include structured-text preservation, bounded concurrency, retries, routing and fallback, versioned terminology, caching, logging, metrics, and explicit data-retention controls.

## Development

Install the locked development environment with `uv sync --dev`. The usual checks are:

```console
uv run pre-commit install
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest
uv build
uv run mkdocs serve
uv run mkdocs build
```

The runtime uses HTTPX for Bhashini's reusable asynchronous HTTP client. For usage and guides, see:

- [docs/user-guide.md](docs/user-guide.md) for system capabilities and getting started
- [docs/translation.md](docs/translation.md) for translation features and examples
- [docs/detection.md](docs/detection.md) for text language and script detection
- [docs/configuration.md](docs/configuration.md) for TOML and environment loading
- [docs/processors.md](docs/processors.md) for processor composition and markdown protection
- [docs/adapter-author-guide.md](docs/adapter-author-guide.md) for provider integration
