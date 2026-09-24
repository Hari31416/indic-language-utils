# Provider reference

Choose an adapter by capability, dependency, and credential. A configured route tries providers in order. Each provider still has its own language and model limits, so consult its guide before depending on a fallback.

| Provider ID      | Translation | Detection | Transliteration | STT | TTS | Setup                                                |
| ---------------- | ----------- | --------- | --------------- | --- | --- | ---------------------------------------------------- |
| `bhashini`       | Yes         | Yes       | Yes             | Yes | Yes | API key, endpoint, capability service IDs            |
| `sarvam`         | Yes         | Yes       | No              | Yes | Yes | `SARVAM_API_KEY`; STT/TTS model IDs                  |
| `googletrans`    | Yes         | No        | No              | No  | No  | `[googletrans]` extra; unofficial online adapter     |
| `fasttext`       | No          | Yes       | No              | No  | No  | `[local-tld]` extra; local model                     |
| `aksharamukha`   | No          | No        | Yes             | No  | No  | `[local-transliteration]` extra                      |
| `indicxlit`      | No          | No        | Yes             | No  | No  | Adapter retained; install extra omitted from beta   |
| `google_free`    | No          | No        | No              | Yes | No  | `[stt-google-free]` extra; unofficial online adapter |
| `faster_whisper` | No          | No        | No              | Yes | No  | `[stt-whisper]` extra; local model                   |
| `edge_tts`       | No          | No        | No              | No  | Yes | `[tts-edge]` extra; unofficial online adapter        |

## Routing and errors

Set route order under `[routes]` in `.indic-language-utils.toml`. For example:

```toml
[routes]
text_to_speech = ["sarvam", "bhashini", "edge_tts"]
```

The client selects providers whose declarations support the requested language. It retries or falls back on rate limits, timeouts, transient provider errors, malformed responses, and output validation failures. Authentication, invalid input, and unsupported language errors stop the request. For TTS with no language, Sarvam is skipped because it requires one. Bhashini can handle an unspecified language only when it has a default TTS model.

TTS options are provider-specific. `TTSOptions.parameters` applies to the first compatible provider only. Use `TTSOptions(provider_parameters={...})` when fallback providers need their own voice settings. See the [TTS guide](tts.md) for an example.

## Before integrating

- Install only the extras your route needs. Local model adapters may download or load model files on first use.
- Verify a provider's supported languages and its model version. See the [Models and voices reference](models-and-voices.md) for a catalog of model IDs, service IDs, neural voices, and parameters.
- Use `async with get_translation_client()`, `get_stt_client()`, or the matching client factory when making repeated calls. This closes network resources after use.
- Inspect `result.provider`, `model_id`, and `fallback_count` where available to see which engine produced the result.
- The demo workbench's web assets are built from a source checkout. They are not part of the Python wheel.
