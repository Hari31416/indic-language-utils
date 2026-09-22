# indic-language-utils

A Python 3.11 and 3.12 library for Indian-language translation, text language detection, transliteration, speech-to-text, and text-to-speech. The project uses `uv` and will be published on PyPI as `indic-language-utils`. Its Python import is `indic_language_utils`. The code is licensed under the MIT License.

This repository is in the design phase. The architecture and ecosystem review is in [docs/architecture-proposal.md](docs/architecture-proposal.md). Implementation starts with the [Phase 0 foundation prompt](docs/phase-0-implementation-prompt.md), followed by the [Phase 1 translation prompt](docs/phase-1-translation-prompt.md).

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
