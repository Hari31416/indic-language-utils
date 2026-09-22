# Phase 1 translation implementation prompt

```text
Work in `/Users/hari/Desktop/sandbox/language-utils`. Treat that directory as the repository root.

Implement Phase 1, translation, after verifying that Phase 0 is complete and all Phase 0 checks pass. Read `README.md`, `docs/architecture-proposal.md`, and `docs/phase-0-implementation-prompt.md` before changing code.

The two projects below are read-only sources of translation behavior and edge cases. Do not modify them.

- `/Users/hari/Desktop/kpmg/nyayasetu-backend`
- `/Users/hari/Desktop/kpmg/cpgrams-bot`

Phase 1 adds translation and one production provider, Bhashini. Do not implement text language detection, transliteration, STT, TTS, streaming, FastAPI, Redis, DiskCache, Sarvam, Google, Microsoft, `deep-translator`, or local ML models.

Use the Phase 0 models, registry, provider registration, routing, errors, retry policy, concurrency limiter, cache, configuration, lifecycle, and telemetry hooks. Extend them only when translation exposes a concrete missing requirement. Do not duplicate them inside the translation package.

Required work

1. Translation API

- Define immutable translation request, result, options, provider metadata, cache metadata, and warning models.
- Define an async translation provider protocol containing only translation behavior.
- Provide an async translation client as the canonical API and a safe synchronous facade for scripts.
- Support `translate()` and `translate_batch()`.
- Accept canonical language tags publicly and map them to Bhashini codes inside the adapter.
- Preserve provider, service or model ID, request ID when available, elapsed time, cache status, fallback information, and warnings.
- Never silently return source text after failure.

2. Bhashini adapter

- Support a configured inference endpoint, API key, translation service ID, timeout, retry policy, and maximum concurrency.
- Default the service ID only if current official Bhashini documentation still recommends `ai4bharat/indictrans-v2-all-gpu--t4`; otherwise require it explicitly.
- Use a reusable async HTTP client with lifecycle management and injected transport for tests.
- Keep pipeline discovery outside Phase 1, while allowing a resolver to be added later.
- Parse responses defensively and map failures into Phase 0 exception types.
- Never log authorization headers, request bodies, source text, or translated text by default.

3. Text structure and batching

- Support `plain` and `markdown` inputs.
- Preserve Markdown list markers, indentation, links, code spans and blocks, and blank lines. Translate visible text rather than syntax or URLs.
- Use opaque protected placeholders rather than punctuation separators. Validate every placeholder during reconstruction.
- Segment large inputs at sentence and structural boundaries. Give every configured limit an explicit unit.
- Batch segments with bounded concurrency while preserving order.
- When a batch fails validation, retry at the smallest safe unit according to the common retry policy.
- Version preprocessing and post-processing policies for cache identity.
- Use Nyaya Setu and CPGRAMS examples as structural fixtures. Do not copy credentials or application-specific legal terminology.

4. Catalog and translation caching

- Add a reviewed localization catalog separate from runtime caching.
- Implement exact-match catalog overrides using stable message IDs, source text, language tags, version, provenance, and review status.
- Do not perform blind term replacement inside longer sentences.
- Build translation cache keys through the Phase 0 key builder. Include normalized input hash, source and target languages, provider and service or model ID, options, processor-policy version, and catalog version.
- Use the Phase 0 null and memory caches and its single-flight behavior. Do not add new cache backends.

5. Verification and documentation

- Test translation contracts, language mapping, routing, retry classification, concurrency, Bhashini payloads, response parsing, strict failures, Markdown reconstruction, missing or reordered placeholders, batching and output order, catalog hits, cache identity, and the synchronous facade.
- Use fake providers and injected HTTP transports. Normal tests must not need network access or credentials.
- Mark live Bhashini tests separately and skip them unless the required environment variables exist.
- Assert transport behavior and structural integrity, not linguistic quality.
- Document async use, synchronous use, configuration, batch translation, caching, catalog overrides, failure handling, and creation of an external translation adapter.

Before finishing, run formatting, linting, type checking, all Phase 0 and Phase 1 tests, and package build checks. Report the public translation API, changes made to Phase 0 contracts and why, commands run, test results, remaining limitations, and any live Bhashini behavior that could not be verified without credentials.
```
