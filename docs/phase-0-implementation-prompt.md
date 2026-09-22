# Phase 0 implementation prompt

```text
Work in `/Users/hari/Desktop/sandbox/language-utils`. Treat that directory as the repository root.

Implement Phase 0 of `indic-language-utils`. Read `README.md` and `docs/architecture-proposal.md` completely before changing code.

The distribution name is `indic-language-utils`, the import package is `indic_language_utils`, and the license is MIT. Use `uv`, a `src/` layout, and Python 3.11 and 3.12. Prepare the package for publication on PyPI.

Phase 0 builds the shared library foundation. Do not implement translation, text language detection, transliteration, STT, TTS, Markdown processing, provider payloads, FastAPI, Redis, DiskCache, or any real external provider. Do not call Bhashini. Test the foundation with small fake providers and operations.

The foundation must make later capabilities straightforward without guessing their request shapes. Shared models may describe language, provider identity, execution metadata, caching, warnings, and errors. Do not create a generic operation request or result filled with optional text, audio, voice, and translation fields. Each capability will define its own request and result models later.

Required work

1. Package scaffold

- Create `pyproject.toml`, `uv.lock`, a `src/indic_language_utils` package, and tests. Preserve the existing MIT `LICENSE` and design documents.
- Set `requires-python` for Python 3.11 and 3.12.
- Keep runtime dependencies small and justify each one in the final report.
- Put pytest, linting, formatting, and type checking tools in development dependency groups rather than published runtime dependencies.
- Add CI for Python 3.11 and 3.12.
- Add package metadata, a typed-package marker, version handling, and build verification.
- Document setup, formatting, linting, type checking, tests, and package build commands using `uv`.

2. Shared models and language registry

- Use immutable typed models for `LanguageTag`, provider identity, model or service identity, request context, execution timing, cache metadata, warnings, and provider capability declarations.
- Normalize public language input to canonical BCP 47-like tags such as `hi-IN` while retaining script information when supplied.
- Include English and all 22 Eighth Schedule languages in the registry. Include known aliases such as the Odia variants used by different providers, but do not leak provider-specific codes into public models.
- Registry presence means the library can represent a language. It does not claim that a provider supports a capability for that language.
- Make models serializable without serializing secrets.

3. Provider and capability extension mechanism

- Define a small capability identifier and provider capability declaration.
- Implement explicit provider registration and lookup. Do not add Python entry-point discovery yet.
- Providers must declare supported capabilities and relevant constraints without inheriting unrelated methods.
- Define lifecycle protocols for async startup and shutdown where needed.
- Supply fake providers in the test support package, not in the published production namespace.
- Write an adapter-author guide that explains registration, capability declarations, lifecycle, and error mapping.

4. Errors, routing, retries, and concurrency

- Define stable typed exceptions for invalid input, unsupported capability, unsupported language or pair, missing optional dependency, authentication, permission, rate limiting, timeout, transient provider failure, malformed response, output validation failure, and configuration errors.
- Give exceptions safe structured attributes. Do not include secrets or content in default string representations.
- Implement deterministic ordered provider selection from capability requirements and provider declarations.
- Never silently treat failure as success.
- Define retry policy and error classification independently from a specific HTTP library. Retry only rate limits, timeouts, and classified transient failures. Support `Retry-After` data and bounded exponential backoff with jitter.
- Implement a reusable per-provider concurrency limiter.
- Test routing, fallback eligibility, retry decisions, cancellation, and concurrency limits with fake providers. Do not use real sleeps in unit tests when an injectable clock or delay function works.

5. Configuration and secrets

- Provide validated Python configuration and environment-variable loading.
- Keep secrets in a secret type whose representation is redacted.
- Define shared settings for provider ordering, timeouts, retries, concurrency, cache selection, and telemetry behavior.
- Support explicit constructor overrides for tests.
- Do not add YAML or TOML application configuration yet. `pyproject.toml` remains the package and tool configuration file.

6. Cache foundation

- Define an async generic cache protocol with get, set, delete, and clear behavior.
- Implement a null cache and a bounded in-memory TTL/LRU cache.
- Make caching opt-in.
- Define a canonical cache-key builder that hashes a versioned envelope. Capability implementations must supply their behavior-changing key material later.
- Cache keys must never contain raw user content, credentials, or tenant secrets.
- Support a namespace and optional tenant boundary.
- Implement in-process single-flight request coalescing for identical keys.
- Test expiry, LRU bounds, namespaces, stable keys, secret exclusion, concurrent misses, cancellation, and exception cleanup.
- Do not implement catalogs in Phase 0. Reviewed localization catalogs have different semantics and enter with translation.

7. Logging, metrics, and lifecycle

- Use standard-library logging with structured event fields or a small protocol. Do not choose a logging vendor.
- Define lightweight metric and trace hook protocols with no-op defaults. Do not add an OpenTelemetry dependency yet.
- Provide shared operation context and timing helpers.
- Default telemetry must exclude raw text, transcripts, audio, base64 data, credentials, headers, and provider response bodies.
- Keep request IDs in logs and traces, not metric labels.
- Implement predictable client and resource shutdown with async context-manager support.

8. Test kit and documentation

- Add reusable contract tests for provider declaration, lifecycle, error safety, routing participation, concurrency, and cancellation.
- Normal tests must not need network access, credentials, external services, or nondeterministic timing.
- Test the installed wheel, not only imports from the working tree.
- Add architecture notes explaining which concerns belong in core and which must stay capability-specific.
- Add a short example showing a fake capability and provider using the foundation. Make clear that it is illustrative and not a supported language operation.

Engineering constraints

- Prefer protocols and composition over base-class inheritance.
- Do not add abstractions solely because a future feature might need them.
- Do not create empty packages for future capabilities or providers.
- Keep synchronous wrappers out of Phase 0. They wrap concrete capability clients, starting with translation in Phase 1.
- Preserve unrelated files and user changes.

Before finishing, run formatting, linting, type checking, tests, and package build checks. Review runtime dependencies and remove unused ones. Report the public foundation API, directory structure, dependency choices, commands run, test results, and deliberate deferrals to Phase 1.
```
