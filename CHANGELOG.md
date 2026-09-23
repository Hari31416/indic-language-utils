# Changelog

All notable changes to the `indic-language-utils` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
