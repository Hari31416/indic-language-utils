# Text to speech

The TTS client sends text to Bhashini's pipeline compute API and returns audio bytes. Configure a default model ID or select one per language. Bhashini calls these IDs `serviceId`; its [model list](https://dibd-bhashini.gitbook.io/bhashini-apis/available-models-for-usage) shows supported languages.

```python
from indic_language_utils import TTSOptions, get_tts_client

async with get_tts_client() as client:
    result = await client.synthesize(
        "नमस्ते, आपका स्वागत है।",
        language="hi",
        options=TTSOptions({"gender": "female", "samplingRate": 16000}),
    )
    with open("speech.wav", "wb") as file:
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

The options object accepts nested JSON values. The API and demo app expose the same object, so a model-specific control does not need a library release.

## FastAPI and demo app

The Text to speech tab accepts text, an optional language, and model options as a JSON object. It plays or downloads the returned audio.

Send the equivalent request to `POST /api/tts`:

```json
{
  "text": "नमस्ते, आपका स्वागत है।",
  "language": "hi",
  "parameters": {"gender": "female", "samplingRate": 16000},
  "provider": "bhashini"
}
```

The response contains base64 audio, its detected format when recognized, the selected model ID, and request IDs. TTS is not cached. The API reports `cached: false` and `cache_backend: "none"`. See `examples/tts/bhashini_tts_demo.py` for a runnable file output example.
