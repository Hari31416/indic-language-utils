# Core boundaries

Phase 0 contains code shared by every language operation: language identifiers, provider declarations and registration, routing, retry and concurrency policy, configuration, caching, telemetry hooks, and lifecycle management.

Concrete capabilities own their request and result models. They also own input processing, output validation, provider payloads, and behavior-specific cache material. Translation begins in Phase 1. Text language detection, transliteration, speech-to-text, and text-to-speech follow in later phases.

The core does not discover plugins, make network calls, load application YAML, or offer synchronous wrappers. It has no runtime dependencies outside the Python standard library.
