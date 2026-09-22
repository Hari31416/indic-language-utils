# indic-language-utils

A Python 3.11 and 3.12 library for Indian-language translation, text language detection, transliteration, speech-to-text, and text-to-speech. The project uses `uv` and will be published on PyPI as `indic-language-utils`. Its Python import is `indic_language_utils`. The code is licensed under the MIT License.

Phase 0 implements the shared library foundation, and Phase 1 adds structured translation with a Bhashini adapter. Runtime caching can use bounded process memory or persistent SQLite storage. The architecture and ecosystem review is in [docs/architecture-proposal.md](docs/architecture-proposal.md).

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
```

The runtime uses HTTPX for Bhashini's reusable asynchronous HTTP client. See [docs/configuration.md](docs/configuration.md) for TOML and environment loading, [docs/translation.md](docs/translation.md) for translation examples, [docs/processors.md](docs/processors.md) for processor composition, [docs/core-boundaries.md](docs/core-boundaries.md) for the shared foundation's scope, and [docs/adapter-author-guide.md](docs/adapter-author-guide.md) for provider integration.
