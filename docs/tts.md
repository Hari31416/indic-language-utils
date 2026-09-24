# Text to speech

The TTS client sends text to Bhashini, Sarvam, or Edge TTS and returns audio bytes. Configure a default model ID or select one per language. Bhashini calls these IDs `serviceId`; its [model list](https://dibd-bhashini.gitbook.io/bhashini-apis/available-models-for-usage) shows supported languages.

```python
from indic_language_utils import TTSOptions, get_tts_client

async with get_tts_client() as client:
    result = await client.synthesize(
        "नमस्ते, आपका स्वागत है।",
        language="hi",
        options=TTSOptions({"gender": "female", "samplingRate": 16000}),
    )
    with open(f"speech.{result.audio_format or 'bin'}", "wb") as file:
        file.write(result.audio)
```

Set `BHASHINI_API_KEY` in the environment. Configure models in `.indic-language-utils.toml`:

```toml
[providers.bhashini]
endpoint = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
tts_model_id = "Bhashini/IITM/TTS"

[providers.bhashini.tts_model_ids]
"hi-IN" = "your-hindi-tts-service-id"

[routes]
text_to_speech = ["bhashini"]
```

A language-specific model ID takes precedence over `tts_model_id`. You may omit `language` when the selected model infers it; the default model ID is then required. The same optional-language behavior is available for STT. Some models still require a language. Check the model's requirements before omitting it.

## Model options

`TTSOptions.parameters` sends JSON fields directly into Bhashini's TTS task config. For example, `gender` and `samplingRate` are common fields. A model may expose `voiceId`, `speaker`, `tone`, or other fields. Use the keys and values accepted by that model. The library rejects `serviceId` and `language` in this object because it sets those fields from the configured model and request language.

The options object accepts nested JSON values. For a single provider, `parameters` keeps its existing behavior. With an automatic route, `parameters` goes only to the first compatible provider. Fallback providers use their defaults unless you set `provider_parameters`:

```python
options = TTSOptions(
    provider_parameters={
        "sarvam": {"speaker": "shubh", "pace": 1.0},
        "edge_tts": {"voice": "hi-IN-SwaraNeural", "rate": "+10%"},
        "bhashini": {"gender": "female", "samplingRate": 16000},
    }
)
```

This prevents Sarvam's `speaker` or `pace` fields from reaching Bhashini or Edge TTS on fallback. The client also skips Sarvam when `language` is omitted, because Sarvam requires it. Bhashini can accept an omitted language only when a default TTS model is configured.

## Sarvam

Set `SARVAM_API_KEY` and configure Bulbul:

```toml
[providers.sarvam]
endpoint = "https://api.sarvam.ai"
tts_model_id = "bulbul:v3"

[providers.sarvam.tts_model_ids]
"ta-IN" = "bulbul:v2"

[routes]
text_to_speech = ["sarvam", "bhashini"]
```

Sarvam TTS requires a language. Use `TTSOptions({"speaker": "shubh", "pace": 1.0})` with Bulbul v3. Bulbul v2 also supports `pitch` and `loudness`; v3 does not. Sarvam returns base64 audio, which the provider decodes into `TTSResult.audio`. Its model ID can also come from `SARVAM_TTS_MODEL_ID`.

## Microsoft Edge TTS

Microsoft Edge TTS provides high-quality neural voice synthesis for Indian languages without requiring an API key. Install the optional dependency:

```bash
pip install 'indic-language-utils[tts-edge]'
```

Configure Edge TTS in `.indic-language-utils.toml` or via environment variables:

```toml
[providers.edge_tts]
tts_model_id = "hi-IN-SwaraNeural"
timeout_seconds = 30.0
max_concurrency = 4

[providers.edge_tts.tts_model_ids]
"hi-IN" = "hi-IN-SwaraNeural"
"ta-IN" = "ta-IN-PallaviNeural"

[routes]
text_to_speech = ["edge_tts", "sarvam", "bhashini"]
```

Edge TTS synthesizes audio in MP3 format. When `language` is supplied, it automatically resolves to an appropriate female or male neural voice based on `gender` in `TTSOptions.parameters` (defaults to female):

```python
from indic_language_utils import TTSOptions, get_tts_client

async with get_tts_client() as client:
    result = await client.synthesize(
        "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?",
        language="ta",
        options=TTSOptions({"gender": "female", "rate": "+0%", "pitch": "+0Hz"}),
    )
    with open("tamil.mp3", "wb") as file:
        file.write(result.audio)
```

Supported options in `TTSOptions.parameters`:

- `gender`: `"female"` or `"male"` to select the built-in voice for the requested language.
- `voice` or `voiceId`: Direct override with an exact voice name (e.g. `"hi-IN-MadhurNeural"`).
- `rate`: Speaking speed adjustment string (e.g. `"+10%"` or `"-5%"`).
- `volume`: Output volume adjustment string (e.g. `"+0%"` or `"-10%"`).
- `pitch`: Voice pitch adjustment string (e.g. `"+2Hz"` or `"-5Hz"`).

Supported languages with built-in voice pairs include Hindi (`hi`), Bengali (`bn`), Tamil (`ta`), Telugu (`te`), Marathi (`mr`), Gujarati (`gu`), Kannada (`kn`), Malayalam (`ml`), Urdu (`ur`), Nepali (`ne`), and English (India) (`en`).

## FastAPI and demo app

The Text to speech tab accepts text, an optional language, and model options as a JSON object. It plays or downloads the returned audio.
Selecting a provider shows its common voice controls. Advanced settings remain available for model-specific fields. Auto routing uses provider defaults unless you enter advanced JSON keyed by provider ID.

Send the equivalent request to `POST /api/tts`:

```json
{
  "text": "नमस्ते, आपका स्वागत है।",
  "language": "hi",
  "parameters": {"gender": "female", "samplingRate": 16000},
  "provider": "bhashini"
}
```

For auto routing, omit `provider` and pass `provider_parameters` with provider IDs as keys. The API accepts the same `TTSOptions` structure as the Python client.

The response contains base64 audio, its detected format when recognized, the selected model ID, and request IDs. TTS is not cached. The API reports `cached: false` and `cache_backend: "none"`. See `examples/tts/bhashini_tts_demo.py` for a runnable file output example.

Use `"provider": "sarvam"` and Sarvam's option names to select Bulbul. `examples/tts/sarvam_tts_demo.py` writes the generated audio to a file.
