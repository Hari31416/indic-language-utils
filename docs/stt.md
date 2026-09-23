# Speech to text

The STT client accepts audio bytes and an optional source language. The first provider is Bhashini's batch ASR endpoint. It sends base64 audio through the pipeline compute API and returns the transcript with the selected model ID.

```python
from indic_language_utils import get_stt_client

with open("speech.wav", "rb") as file:
    audio = file.read()

async with get_stt_client() as client:
    result = await client.transcribe(audio, language="hi", audio_format="wav", sampling_rate=16000)
    print(result.text)
```

Set `BHASHINI_API_KEY` in the environment. Configure the endpoint and model IDs in `.indic-language-utils.toml`:

```toml
[providers.bhashini]
endpoint = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
stt_model_id = "default-asr-service-id"

[providers.bhashini.stt_model_ids]
"hi-IN" = "hindi-asr-service-id"
"ta-IN" = "tamil-asr-service-id"

[routes]
speech_to_text = ["bhashini"]
```

Bhashini calls these IDs `serviceId` in its pipeline request. Its [available models list](https://dibd-bhashini.gitbook.io/bhashini-apis/available-models-for-usage) maps service IDs to ASR models and languages. A language-specific entry takes precedence over `stt_model_id`. Without a matching entry or default, the provider reports an unsupported language. You may omit language for a model that infers it; this uses `stt_model_id` and leaves the language field out of the Bhashini task config.

The client accepts `STTRequest` objects and `transcribe_batch` for multiple clips. The initial adapter makes one call per clip, so mixed languages and formats work. Audio must already match the declared format and sample rate; this library does not resample it.

STT requests currently go to the provider every time. The API reports `cached: false` and `cache_backend: "none"`, and the demo app shows that status beside the transcript.

## FastAPI and demo app

The demo app has a Speech to text tab for file upload. It accepts WAV, FLAC, MP3, and OGG files up to 10 MiB. Enter the file's actual sample rate before transcribing.

The FastAPI route accepts the same input as JSON:

```json
{
  "audio_base64": "<base64-encoded audio bytes>",
  "language": "hi",
  "audio_format": "wav",
  "sampling_rate": 16000,
  "provider": "bhashini"
}
```

Send it to `POST /api/stt`. The response includes the transcript, normalized language, provider, model ID, and request IDs. The repository also includes `examples/stt/bhashini_demo.py` for file-based use.
