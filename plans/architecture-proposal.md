# Architecture proposal

## Recommendation

Build a Python library with five capability interfaces and a shared execution pipeline. The capabilities are translation, text language detection, transliteration, non-streaming STT, and non-streaming TTS. Keep provider adapters thin. Put chunking, structured-text protection, cache policy, retries, concurrency limits, routing, logging, and metrics in provider-independent layers.

Do not expose one large `LanguageService` base class. Providers rarely support the same combination of languages, models, streaming modes, audio formats, voices, and batch operations. One interface per capability lets a provider implement only what it actually supports.

The public API should be asynchronous first. Network calls and batch operations are naturally asynchronous. A small synchronous facade can serve scripts and notebooks.

```python
result = await client.translate(
    "Your grievance has been registered.",
    source="en-IN",
    target="hi-IN",
    context=TranslationContext(domain="cpgrams", format="plain"),
)
```

The project will use `uv`, support Python 3.11 and 3.12, and publish the library on PyPI as `indic-language-utils`. The Python import is `indic_language_utils`, and the project uses the MIT License. A FastAPI service may be added later as a separate package or application. Provider selection belongs in configuration and routing policy, not application code.

## What already exists

No existing library covers the whole requirement well. Several are useful references or adapter dependencies.

| Project                                                                                                                   | Useful part                                                                                                          | Why it is not sufficient                                                                                                          |
| ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| [LiveKit Agents](https://docs.livekit.io/agents/models/stt/)                                                              | Clean plugin model for many STT and TTS providers, streaming abstractions, provider capability discovery             | Voice-agent focused; translation, Indic TLD, terminology catalogs, and structured document translation are outside its main scope |
| [Pipecat](https://docs.pipecat.ai/)                                                                                       | Real-time audio pipelines and pluggable STT/TTS services                                                             | Pipeline framework rather than a reusable Indic language utility layer; text translation and catalog semantics need separate work |
| [SpeechRecognition](https://github.com/Uberi/speech_recognition)                                                          | A familiar multi-engine STT facade                                                                                   | STT only, mostly synchronous, and too little control over production routing and provider-specific features                       |
| [deep-translator](https://github.com/nidhaloff/deep-translator) and [translate](https://translate-python.readthedocs.io/) | Simple translation facade over multiple services                                                                     | Translation only; neither solves structured text, model routing, governed terminology, audio, or production observability         |
| [Fasiri](https://fasiri.readthedocs.io/en/latest/)                                                                        | The closest conceptual match: translation, STT, TTS, routing, cloud and bring-your-own-key modes                     | Built for African-language providers and does not cover the Indian provider/model ecosystem                                       |
| [AI4Bharat IndicTrans2](https://github.com/AI4Bharat/IndicTrans2)                                                         | Strong local translation option for 22 scheduled Indian languages; its tooling includes sentence-level preprocessing | A model and inference toolkit, not a multi-provider application library                                                           |
| [AI4Bharat IndicLID](https://github.com/AI4Bharat/IndicLID)                                                               | Local TLD for native and romanized text across all 22 scheduled languages                                            | TLD only; packaging and operational integration need an adapter                                                                   |
| [AI4Bharat Indic-TTS](https://github.com/AI4Bharat/Indic-TTS)                                                             | Local TTS models for 13 Indian languages                                                                             | Model stack rather than a stable cross-provider API                                                                               |
| Provider SDKs from [Sarvam](https://docs.sarvam.ai/api-reference/introduction), Google Cloud, and others                  | Best access to provider-specific options and response metadata                                                       | Each SDK has different language codes, result types, error behavior, limits, and lifecycle                                        |

The gap is real: a provider-neutral Indic application layer with strong preprocessing and operational semantics. This library should integrate existing SDKs and models, not replace them.

### What to build upon

Use existing libraries selectively. None should define the public API.

- Do not add `deep-translator` to the core or the first translation release. A developer can later publish or register a provider adapter backed by it. If the project decides to ship unofficial Google translation, add `deep-translator` only to a `translate-google-free` extra after live compatibility tests. Its latest PyPI release is from June 2023, and its Microsoft adapter requires an Azure key.
- Do not add `translate` as a dependency for unofficial Microsoft translation. Its `MicrosoftProvider` accepts a secret access key and uses the official service. It therefore does not solve the keyless PoC requirement. A direct LibreTranslate adapter would also be clearer than nesting its provider abstraction.
- [`SpeechRecognition`](https://github.com/Uberi/speech_recognition) is actively packaged and already isolates many online and offline STT engines behind optional extras. It can back PoC STT adapters. Its synchronous recognizer API and audio assumptions should remain inside an adapter rather than becoming our common API.
- LiveKit Agents has good provider and capability patterns. Since the current roadmap excludes streaming, taking a dependency on the whole framework would add weight without enough benefit. Treat LiveKit as an integration target later, and borrow its plugin isolation ideas now.
- Use [`edge-tts`](https://github.com/rany2/edge-tts) directly for the unofficial Microsoft Edge TTS adapter. Use [`gTTS`](https://gtts.readthedocs.io/) as the likely unofficial Google TTS adapter. Neither belongs in a translation-only installation.
- Use Bhashini as the first TLD adapter and [AI4Bharat IndicLID](https://github.com/AI4Bharat/IndicLID) as the Indic-specific local adapter. IndicLID covers all 22 scheduled languages in native and romanized forms. For a small general-purpose local fallback, prefer fastText's `lid.176.ftz` through [`fasttext-langdetect`](https://github.com/zafercavdar/fasttext-langdetect); the compressed model is about 917 KB and covers 176 language codes. The older `langdetect` and Lingua do not cover every scheduled language, though either can still be supplied by an external adapter.
- Use [AI4Bharat IndicXlit](https://github.com/AI4Bharat/IndicXlit) as an optional local transliteration adapter. It handles native-to-Roman and Roman-to-native conversion for 21 Indic languages, but its model runtime should not enter the core dependency set.

This gives us useful provider integrations without inheriting another library's lowest-common-denominator API.

The unofficial Microsoft translation choice needs a spike before it becomes a declared dependency. The actively released [`translators`](https://pypi.org/project/translators/) package supports Bing and Microsoft web translators, but version 6 is GPL-3.0 and may require a JavaScript runtime for parts of its provider set. That is a poor default dependency for a permissively licensed PyPI library. [`mintrans`](https://github.com/DedInc/mintrans) is MIT-licensed and exposes Bing without a key, but it is small and young. It is useful as a protocol reference and experiment, not yet as a required dependency. Test it against the scheduled-language matrix and failure cases. If it proves useful, ship it in a clearly experimental extra or separate adapter package. Otherwise omit free Microsoft translation until a maintainable option exists. Copying its request logic into the core would merely transfer maintenance of an undocumented endpoint to this project.

Do not use `deep-translator` for TLD. Its standalone `single_detection` and `batch_detection` functions call DetectLanguage.com and require an API key. Google translation's `source="auto"` detects a source language as part of translation, but `deep-translator` does not expose that as an independent detector.

## Lessons from the two reference projects

The Nyaya Setu and CPGRAMS code contains behavior worth extracting, but it currently sits beside provider calls or is duplicated between projects.

- Translation must preserve Markdown list markers, indentation, links, and standard legal-document names.
- Large text cannot be sent as one opaque string. The current code groups lines, caps chunk size, translates groups concurrently, detects output-count mismatches, and retries failed values individually.
- Separators are not stable across scripts. Urdu and Kashmiri can transform `;` into `؛`. A library should use protected placeholder IDs and validate their round trip instead of depending on punctuation.
- Provider output requires validation. Empty or implausibly short translations already trigger retries in both projects.
- STT needs audio normalization. Existing code converts inputs to mono, 16 kHz PCM before calling Bhashini.
- Bhashini model selection is language-dependent for ASR and TTS. These mappings have already drifted between the two projects.
- TTS preprocessing differs from translation preprocessing. Years, long numbers, identifiers, abbreviations, and mixed alphanumeric tokens need pronunciation rules.
- Fixed legal terms, links, dropdown values, progress messages, and form labels need reviewed translations. CPGRAMS already builds per-language JSON catalogs for them.
- Metrics need the provider, capability, model or service ID, language pair, attempt count, latency, cache status, and failure class. Raw user text should not be logged by default.
- Concurrency must be bounded per provider and capability. `asyncio.gather` without a semaphore can exceed quotas during a burst even when it performs well in a small load test.
- A new HTTP client/session per request defeats connection pooling. Adapters should own reusable clients and close them through an explicit lifecycle.

There are also bugs that a shared library can prevent once: character count is currently called a word count in a chunker, temporary input files may be deleted even when the caller owns them, sync and async implementations have diverged, and language codes such as `or`, `od-IN`, and `ory_Orya` are mixed across systems.

## Proposed module boundaries

```text
language_utils/
  api/                 public client and typed request/result models
  capabilities/        Translate, DetectTextLanguage, Transliterate, Transcribe, Synthesize
  providers/           optional adapters: bhashini, google_free, microsoft_free, sarvam
  routing/             capability matching, profiles, fallback and circuit breaking
  processing/
    text/              segmentation, Unicode normalization, placeholders, structure
    audio/             decoding, resampling, channel conversion, duration inspection
    translation/       batching, reconstruction, terminology application, validation
    tts/               pronunciation and synthesis chunking
    stt/               transcript normalization and timestamp assembly
  cache/               cache protocol, key builder, memory, disk and Redis adapters
  catalog/             reviewed labels and terminology, import/export and provenance
  config/              validated schemas, profiles and secret references
  telemetry/           logs, metrics and traces
  testing/             provider contract kit, fakes and recorded fixtures
```

Provider adapters should translate between normalized library types and provider SDK types. They should not decide how Markdown is parsed or whether a response is cached.

### Capability contracts

Use `typing.Protocol` so an adapter does not inherit unrelated default behavior. Requests and results should be immutable typed models.

Every result should preserve:

- normalized output plus optional raw provider response
- requested and detected language
- provider, model, model version or Bhashini service ID
- request ID and timing
- warnings, such as fallback used or timestamps unavailable
- usage units when the provider returns them

Capabilities need a machine-readable declaration. A declaration answers whether an adapter supports a language, pair, streaming, batch mode, timestamps, voices, SSML, audio format, or provider-side language detection. Routing can then reject impossible configurations at startup.

## Execution pipeline

Each operation follows the same outer flow, with capability-specific stages inside it.

```text
validate request
  -> normalize language codes and input
  -> apply protected terms and structural placeholders
  -> build cache key and look up
  -> select provider/model
  -> segment or batch
  -> apply rate and concurrency limits
  -> call with timeout and classified retries
  -> validate provider output
  -> reconstruct and post-process
  -> store cache entry
  -> emit redacted telemetry
```

Middleware or hooks should wrap this flow. Avoid a generic event bus in the first release. Explicit stages are easier to reason about when a processor changes text and therefore cache identity.

### Structured translation

Represent an input as a small intermediate document, not a list of strings. Nodes can be translatable text, whitespace, Markdown syntax, URLs, code, identifiers, or protected terms. Each translatable node receives a stable opaque ID. Reconstruction must fail or fall back safely if IDs are missing or reordered.

Start with `plain` and `markdown`. Add HTML and JSON only after defining whether keys, values, embedded Markdown, and arrays are translated. "Translate this dict" is otherwise ambiguous and dangerous.

Chunking should use provider limits plus sentence boundaries. Limits may be bytes, Unicode code points, provider billing characters, audio duration, or item count. Name each unit explicitly. Preserve order, use bounded concurrency, and retry only failures that the error classifier marks transient.

### Audio handling

Use an `AudioInput` type that accepts bytes, a path, or an async byte stream. Do not make URL downloading an implicit provider concern. Normalize only when the selected adapter requires it, and never delete caller-owned files.

The initial STT and TTS contracts are non-streaming. STT accepts a complete audio input and returns a complete result. TTS returns audio bytes plus codec, sample rate, duration if known, and provider metadata. If a real project later needs streaming, add separate streaming protocols rather than changing these method semantics.

## Caching and catalogs

### Keep two concepts separate

A runtime cache is disposable. A localization catalog is reviewed application data.

Use the catalog for UI labels, ministry and department names, legal terms, standard messages, named schemes, and pronunciation overrides. Each entry should carry a stable message ID, source text, target language, translated text, domain, status, provenance, reviewer, and version. Source text alone is not a safe identifier because English copy changes.

Use runtime caching for repeated provider calls. Cache-aside is enough for the first release.

### Cache backends

| Backend                  | Use                                       | Recommendation                                                                                                                                                  |
| ------------------------ | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| In-process memory        | Unit tests, notebooks, hot L1 cache       | Required. Bounded TTL and LRU; never a plain unbounded dictionary                                                                                               |
| SQLite-backed disk cache | PoCs, CLI tools, one-node deployments     | Recommended optional backend. Prefer [DiskCache](https://pypi.org/project/diskcache/) over loose JSON files because writes are atomic and safe across processes |
| Redis                    | Multi-worker and multi-node production    | Recommended production backend. Supports shared TTLs, eviction, locks, counters, and operational inspection                                                     |
| Null cache               | Sensitive flows and deterministic testing | Required                                                                                                                                                        |

Allow composition such as memory L1 plus Redis L2. Do not promote stale values from a reviewed catalog into the runtime cache namespace.

### Cache keys

Hash a canonical request envelope. It must include:

- schema and library cache-key version
- capability
- normalized input hash or audio-content hash
- source and target language in canonical form
- provider and model identity
- behavior-changing options such as voice, gender, pace, output mode, punctuation, diarization, and audio codec
- preprocessing and post-processing policy version
- terminology catalog version

Do not include credentials or tenant secrets. Add a tenant or project namespace when data must not cross boundaries.

Recommended defaults:

- Translation and TLD may use normal TTL caching.
- TTS can use a long TTL when text and voice settings are deterministic. Store large audio in object storage and cache a reference if Redis memory would become expensive.
- STT caching should be off by default because audio can contain personal data. Let deployments opt in with a short TTL, encryption, and a retention policy.
- Cache negative results only briefly and only for deterministic failures such as an unsupported language. Never cache timeouts or quota failures.
- Add single-flight request coalescing so concurrent identical misses cause one provider call.

## Configuration

Use validated Python models, preferably `pydantic-settings`, for the final merged configuration. YAML or TOML holds non-secret routing and model policy. Environment variables and secret-manager references supply credentials.

Keep these configuration layers in increasing precedence:

1. library defaults
2. a checked-in base file
3. an environment profile such as `poc`, `uat`, or `production`
4. environment variables and secret references
5. explicit constructor overrides for tests

Do not place every model mapping in environment variables. A language-to-model matrix is structured application policy and belongs in a reviewed config file.

```yaml
version: 1

profiles:
  poc:
    routes:
      translation: [bhashini, google_free]
      tld: [bhashini]
      transliteration: [bhashini]
      stt: [bhashini, google_free]
      tts: [bhashini, edge_tts, gtts]

  production:
    routes:
      translation: [bhashini, sarvam]
      tld: [bhashini, sarvam]
      transliteration: [bhashini, sarvam]
      stt: [bhashini, sarvam]
      tts: [bhashini, sarvam]

providers:
  bhashini:
    adapter: bhashini
    credential: env://BHASHINI_API_KEY
    timeout_seconds: 20
    max_concurrency: 8
    models:
      translation:
        default: ai4bharat/indictrans-v2-all-gpu--t4
      stt:
        hi-IN: ai4bharat/conformer-hi-gpu--t4
        default: ai4bharat/conformer-multilingual-indo_aryan-gpu--t4
      tts:
        hi-IN: ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4
        default: Bhashini/IITM/TTS

cache:
  backend: redis
  url: env://LANGUAGE_UTILS_REDIS_URL
  namespace: cpgrams
```

Bhashini deserves a resolver that can use its pipeline config response and cache the resolved endpoint and service information. The developer guide describes pipeline configuration as mandatory unless the caller already has the IDs, and recommends logging pipeline and service IDs on failures. Pin service IDs for reproducibility, but support controlled discovery and a startup validation command to detect retired or incompatible services.

### Language identifiers

Define one internal `LanguageTag` based on BCP 47, such as `hi-IN`, and keep provider mappings inside adapters. Script matters for TLD, so detection results may include both a language tag and script. IndicLID labels such as `hin_Deva` and `hin_Latn` should not leak into the common API.

Aliases must be explicit and tested. Examples include `or`, `od-IN`, `ory`, and `ori_Orya` for Odia, and `kok` versus project-specific Konkani codes. Never silently accept an unknown code and send it to a provider.

The library registry will include every language in the Eighth Schedule, and it may include additional languages and locale variants. Registry support means the library can represent and normalize the language. It does not claim that every provider supports every capability for that language. Each provider advertises its own compatibility matrix, and the router raises a clear unsupported-language error when no configured provider matches.

The library validates transport and structural behavior, not linguistic quality. Provider contract tests should catch malformed responses, lost placeholders, wrong ordering, invalid audio, unsupported options, and broken metadata. They should not assert that a translation, transcript, or synthesized voice is linguistically good. Applications choose the provider and model and own domain-level quality evaluation.

## Routing and fallback

Routing should use ordered policies, not scattered `if APP_ENV` checks. A route evaluates capability, language, mode, data policy, required features, provider health, and optionally cost.

Start with deterministic ordered fallback. Add weighted or cost-aware routing only after collecting comparable quality and latency data. Fallback is safe only when the second provider has compatible semantics. For example, an STT request requiring diarization must not fall back to an adapter without diarization.

Provider failures need stable categories:

- invalid request
- unsupported capability or language
- authentication
- quota or rate limit
- transient provider failure
- timeout
- malformed provider response
- output validation failure

Retry timeouts, rate limits with `Retry-After`, and transient failures using bounded exponential backoff with jitter. Do not retry authentication or invalid input. Add a per-provider circuit breaker after the basic behavior is tested.

## Logging, metrics, and privacy

Emit structured logs and OpenTelemetry-compatible metrics and traces. The library should not own a database table or CSV metrics file.

Useful metric dimensions are capability, provider, model, source language, target language, streaming or batch mode, outcome, cache level, and fallback count. Keep request IDs in traces and logs, not metric labels, to avoid unbounded cardinality.

Record latency histograms for total time, provider time, queue wait, preprocessing, and cache lookup. Count input/output characters, audio seconds, retries, cache hits, validation failures, and fallbacks.

Default logs must exclude raw text, transcripts, audio, authorization headers, and base64 payloads. Offer a deliberate debug content hook with redaction and sampling. Government workloads may contain grievance details and personal data, so each deployment should set retention and residency policy explicitly.

## Provider plan

### Adapter order

1. Bhashini adapters for each capability as that capability is implemented.
2. Sarvam adapters.
3. Optional unofficial Google adapters for PoCs, only when a project needs them. `deep-translator`, `SpeechRecognition`, and `gTTS` are candidates, not baseline dependencies.
4. Official Google Cloud and Microsoft Azure adapters when production consumers need them.
5. Local model adapters where deployment cost and model lifecycle justify them.

Unofficial adapters must be visibly marked as such in package metadata, documentation, capability declarations, and result metadata. Their documentation should warn that undocumented endpoints can change, may have usage restrictions, and may be unsuitable for production or sensitive government data. Users must opt in by installing and selecting them. The library should never silently fall back from an official provider to an unofficial one.

Local STT and TTS should come later unless a current project needs them. Their model weights, GPU requirements, licenses, cold starts, and deployment shape make them different from an ordinary pip dependency.

### Packaging

Keep the core install small. Installing translation support must not install audio codecs, STT SDKs, or TTS packages. Use [`uv`](https://docs.astral.sh/uv/concepts/projects/dependencies/) to maintain the lock file and test every supported extra independently. Published extras belong in `[project.optional-dependencies]`; development tools belong in dependency groups.

```text
language-utils
language-utils[bhashini]
language-utils[translate-google-free]
language-utils[stt-speechrecognition]
language-utils[tts-edge]
language-utils[tts-google-free]
language-utils[sarvam]
language-utils[google-cloud]
language-utils[azure]
language-utils[redis]
language-utils[local-tld]
language-utils[local-transliteration]
language-utils[local-translation]
language-utils[all]
```

Extras are conveniences, not architecture boundaries. Import each optional dependency lazily and raise an error that names the exact extra to install. Do not import speech modules when a process only uses translation.

If one distribution develops too many conflicting dependency groups, move adapters into separate distributions such as `language-utils-bhashini` and `language-utils-sarvam`. Discover external adapters through Python entry points. The core API and provider contract kit should work with both built-in and separately published adapters.

## Additions worth including

- Transliteration is the third capability in the delivery plan. Romanized Indic input is common, and it should not be conflated with translation.
- Automatic language detection for audio should be represented as STT metadata or a later audio-language-detection capability, not forced into text TLD.
- A CLI will pay for itself early: `providers validate`, `routes explain`, `catalog build`, `catalog lint`, `translate`, `transcribe`, and `cache inspect`.
- Ship a provider contract test suite. Every adapter runs the same tests for lifecycle, language validation, timeouts, error mapping, metadata, and cancellation.
- Provide an evaluation harness without prescribing output quality. Applications may plug in golden datasets and linguistic metrics when comparing providers or models.
- Make processor policies versioned. A change to sentence splitting or number pronunciation can change output and must invalidate relevant cache entries.

## Suggested delivery order

### Phase 0: library foundation

Create the publishable package and the shared machinery that every capability needs. This includes typed core metadata, language tags and the scheduled-language registry, provider capability declarations and registration, error taxonomy, configuration loading, deterministic routing policy, retry and concurrency policy, cache contracts with null and bounded memory implementations, request coalescing, structured logging hooks, metric hooks, lifecycle management, and the provider contract test kit.

Phase 0 uses fake providers to test the machinery. It does not define translation, detection, transliteration, STT, or TTS request models. It does not call Bhashini or any other external service. Capability-specific models and processing belong in their own phases. This boundary matters because a generic request or result that tries to anticipate text and audio operations will become a bag of optional fields.

### Phase 1: translation

Build translation on the Phase 0 contracts. Add translation-specific request and result models, Bhashini, plain-text and Markdown processing, bounded batching, exact-match catalogs, translation cache-key material, and a synchronous facade. Prove the provider API before adding convenience dependencies for unofficial providers.

Use real structural examples from Nyaya Setu and CPGRAMS. Assert preservation, ordering, retries, routing, and metadata. Do not assert linguistic quality.

### Phase 2: text language detection

Add TLD with Bhashini, then suitable free or local adapters. Complete the scheduled-language registry and provider compatibility reporting.

### Phase 3: transliteration

Add transliteration with Bhashini and then available free or local adapters. Reuse the text pipeline without treating transliteration as translation.

### Phase 4: non-streaming STT

Add the shared audio input model and Bhashini STT. Then add optional PoC adapters based on free Google or Microsoft access where practical. Include audio normalization, duration limits, privacy policy, and transcript metadata.

### Phase 5: non-streaming TTS

Add Bhashini TTS, then Edge TTS and gTTS. Include pronunciation processing, voice discovery, output format metadata, and TTS cache policy.

### Phase 6: Sarvam and production hardening

Add Sarvam capability by capability, Redis, official Google Cloud and Azure adapters as demanded, pipeline discovery, circuit breaking, OpenTelemetry exporters, and the catalog CLI.

Streaming STT and TTS are outside the current roadmap. Add them only after a consumer supplies a concrete use case and latency requirements.

## Recorded decisions

- Publish the distribution as `indic-language-utils` with the import package `indic_language_utils`.
- Use the MIT License.
- Use `uv` and support Python 3.11 and 3.12.
- Publish a transport-neutral library on PyPI. Consider a separate FastAPI server later.
- Build and test the shared library foundation before adding a real capability or provider.
- Deliver capabilities after Phase 0 in this order: translation, TLD, transliteration, non-streaming STT, non-streaming TTS.
- Defer streaming speech until a real use case requires it.
- Implement Bhashini first and Sarvam next. Keep the provider API open so applications or later extras can add unofficial Google or Microsoft PoC adapters without changing the core.
- Represent all Eighth Schedule languages in the common registry. Provider compatibility remains explicit.
- Test interface correctness and structural integrity. Consumers own linguistic quality evaluation for their selected provider and model.
- Use exact-match catalog overrides by default. Allow protected terminology inside longer text only through an explicit policy because grammatical inflection and word order can make blind substitution wrong.
- Keep capability and provider dependencies optional. A translation-only installation must not fetch STT, TTS, or audio dependencies.
