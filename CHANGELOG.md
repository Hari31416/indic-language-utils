# Changelog

All notable changes to the `indic-language-utils` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Translation segment caching reuses unchanged Markdown lines and size-limited chunks across document edits, including with persistent SQLite caches.

### Fixed
- Translation cache keys now include the configured provider model, so switching Sarvam models cannot reuse an earlier model's result.

## [0.6.0b1] - 2026-09-24

### Added
- Per-request model and service ID overrides for translation, transliteration, detection, STT, and TTS in the demo API.
- Workbench settings for provider API keys and endpoints, plus model presets, voice controls, audio input, searchable language listings, and recent runs.
- A model and voice reference covering Bhashini service IDs, Sarvam speaker presets, and Edge TTS voices.

### Changed
- Refreshed the workbench layout and provider controls, including Bhashini Bodhan ASR and Sarvam Bulbul voice presets.
- Omit the `neural-transliteration` install extra from this beta while its upstream dependency stack has known vulnerabilities. The adapter remains available to existing installations with separately managed dependencies.

### Fixed
- Google Free STT now decodes compressed audio before transcription, rejects invalid audio instead of treating it as PCM, and uses the configured default language.
- Faster-Whisper loads models outside the event loop and enforces timeouts without starting overlapping retries.
- STT client setup now reports missing optional dependencies and invalid provider settings instead of silently skipping them.
- Bhashini errors now include useful upstream details even when the response is plain text.
- Bhashini failure logs no longer print entire provider response bodies, which may contain request data.
- GitHub releases attach only wheel and source archives.
- Exclude local web dependencies and generated files from the Python source distribution.
- Fail tagged releases when the changelog entry is missing, and run dependency audit, format, lint, type, test, and wheel checks before publishing.

## [0.5.0] - 2026-09-24

### Added
- Provider-specific TTS fallback settings through `TTSOptions.provider_parameters` and the `/api/tts` request body.
- Voice controls for Bhashini, Sarvam, and Edge TTS in the web workbench.
- Provider reference covering capabilities, setup requirements, routing, and errors.

### Changed
- The STT workbench reads sample rates from WAV files and asks for the actual rate for other formats.
- The quick start covers transliteration and speech, and documents that web assets are built from a source checkout.
- CI builds the web workbench and checks documentation with strict warnings.

### Fixed
- TTS routing skips providers that require a language when none is supplied.
- TTS fallback keeps model options with their intended provider.
- Invalid Edge TTS settings are reported instead of silently removing the provider.
- GitHub release notes are written to the GitHub Actions output file.

## [0.4.0] - 2026-09-23

### Added
- Microsoft Edge TTS adapter (`EdgeTTSProvider`) for free, keyless neural speech synthesis across Indian languages (Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Urdu, Nepali, Assamese, and English).
- Edge TTS voice selection with female/male defaults and support for explicit `voice`, `rate`, `pitch`, and `volume` options in `TTSOptions.parameters`.
- `tts-edge` optional dependency extra for `edge-tts`.
- Support for keyless Google Free Speech-to-Text (`GoogleFreeSTTProvider`) via `SpeechRecognition` (`stt-google-free` extra).
- Support for local offline Faster-Whisper Speech-to-Text (`FasterWhisperSTTProvider`) via `faster-whisper` (`stt-whisper` extra).
- Runnable Edge TTS demo script (`examples/tts/edge_tts_demo.py`) and documentation in `docs/tts.md`.
- Automated provider discovery and routing for Edge TTS and free STT providers in `get_tts_client` and `get_stt_client`.

### Changed
- Web workbench Text-to-Speech tab updated with Edge TTS parameter presets and option key hints.
- Web workbench Providers view updated with structured status cards for multiple speech and TTS engines.

## [0.3.0] - 2026-09-23

### Added
- Speech to text clients with Bhashini and Sarvam providers, language-specific model IDs, and optional input language when the model supports detection.
- Text to speech clients with Bhashini and Sarvam providers, language-specific model IDs, and model-specific voice options.
- FastAPI speech endpoints and web workbench tabs for audio transcription and speech generation.
- Runnable speech examples, including bundled English, Hindi, and Tamil audio clips for STT.

### Changed
- The web workbench now shows whether a speech result came from a cache. Speech requests currently go directly to the selected provider.

## [0.2.2] - 2026-09-23

### Fixed
- Preserve inline code and URLs in long Markdown input when splitting text for translation, and recover protected content when a provider drops a placeholder.
- Keep source text that resembles a protected placeholder, recognize tilde and longer backtick code fences, and preserve CRLF line endings in Markdown translation.
- Apply transliteration segment and batch limits, preferring word boundaries when splitting long input.
- Require a configured Bhashini transliteration service ID for the live example instead of using a rejected default.

## [0.2.1] - 2026-09-23

### Fixed
- Added mypy module overrides for optional transliteration dependencies (`aksharamukha` and `ai4bharat`) to resolve CI typechecking failures in clean environments.
- Added skipif marker for `HAVE_AKSHARAMUKHA` on the FastAPI server transliteration endpoint test.
- Added explicit unit test verifying HTTP 400 response when transliteration is requested with an unavailable provider.

### Added
- Added `RELEASING.md` documenting the pre-release verification checklist, tag matching validation, and release workflow.

## [0.2.0] - 2026-09-23

### Added
- Transliteration engine capability with core protocols (`TransliterationProvider`), request/response models, and unified routing.
- Cloud Bhashini transliteration adapter (`BhashiniTransliterationProvider`).
- Offline neural transliteration adapter using AI4Bharat IndicXlit (`IndicXlitTransliterationProvider`) via `neural-transliteration` optional extra.
- Offline pure-Python transliteration and Romanization adapter using Aksharamukha (`AksharamukhaTransliterationProvider`) via `local-transliteration` optional extra.
- Transliteration client routing with automatic failover, caching (`TransliterationClientCache`), and singleflight request coalescing.
- Synchronous and asynchronous transliteration convenience helpers (`transliterate_text`, `atransliterate_text`, and `build_transliteration_client`).
- Sarvam AI provider integration for translation (`SarvamTranslationProvider`) and language detection (`SarvamDetectionProvider`) with rate limiting and concurrency control.
- FastAPI server module (`indic_language_utils.server`) with REST endpoints for translation, transliteration, language detection, script identification, and provider discovery.
- `indic-server` CLI entry point for running the API and workbench server.
- Interactive web workbench UI built with React, Vite, and Tailwind CSS for evaluating translations, transliterations, and language detection in real time.
- Runnable example scripts and demos for Bhashini, Sarvam AI, IndicXlit, and Aksharamukha.

### Changed
- Refactored `local-transliteration` dependency to use Aksharamukha and created `neural-transliteration` for AI4Bharat IndicXlit.
- Updated documentation suite with dedicated transliteration guide, Sarvam provider documentation, and workbench instructions.

### Fixed
- Eliminated live network calls in test suite by mocking providers and gating live network tests behind the `RUN_LIVE_TESTS` environment variable.
- Corrected repository URLs in documentation and configuration.

## [0.1.1] - 2026-09-22

### Added
- A dedicated installation and quick start guide for optional providers and Bhashini setup.
- A release check that rejects tags that do not match the package version.

### Changed
- Documentation deployment now treats warnings, including broken links, as build failures.
- Shell command examples now use the correct Markdown language identifier.

### Fixed
- Detection examples now read confidence from the highest-ranked language candidate.
- Removed links to the deleted adapter author guide.
- Clarified the provider installation and selection required by the quick start examples.

## [0.1.0] - 2026-09-22

### Added
- Initial release of provider-neutral foundations for Indian language operations.
- Text translation capability with Bhashini (IndicTrans2) and Google Translate adapters.
- Text language detection (TLD) with offline FastText (`lid.176.ftz`) and cloud Bhashini pipelines.
- Unicode script identification across 12+ Indic scripts and Latin without external dependencies.
- BCP 47 canonical language tags and registry supporting all 22 Eighth Schedule Indian languages plus English.
- Multi-provider fallback routing with sequential candidate evaluation on transient errors.
- Bounded concurrency limiters and retries with exponential backoff and jitter.
- Caching system supporting bounded in-memory LRU and persistent SQLite with WAL mode and size bounds.
- Structured document protection preserving Markdown syntax, code fences, inline spans, and links across neural translation.
- Localization catalogs (`LocalizationCatalog`) for exact reviewed UI and legal string overrides.
- Material for MkDocs documentation suite with dark and light themes and automated GitHub Pages deployment.
