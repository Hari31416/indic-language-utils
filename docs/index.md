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

## Getting started

Start with the [installation and quick start guide](getting-started.md). It covers optional extras,
credential-free development, Bhashini configuration, and synchronous and asynchronous examples.

## Documentation Roadmap

Explore the comprehensive documentation guides:

- [Installation and quick start](getting-started.md): Provider setup and first calls.
- [User Guide](user-guide.md): Architecture overview, core capabilities, provider matrix, and usage levels.
- [Translation](translation.md): Synchronous and asynchronous translation, batching, Markdown preservation, and catalogs.
- [Detection](detection.md): Local FastText and cloud Bhashini language detection, script analysis, and candidate scoring.
- [Transliteration](transliteration.md): Script transliteration between Roman and native Indic scripts via Bhashini and AI4Bharat IndicXlit.
- [Speech to text](stt.md): Transcribe audio with Bhashini or Sarvam and select ASR models by language.
- [Text to speech](tts.md): Generate audio with Bhashini or Sarvam and pass model-specific voice controls.
- [Configuration](configuration.md): Project TOML configuration, precedence hierarchy, and environment variables.
- [Processors](processors.md): Structure processors, segment processors, and custom pipeline authoring.
