# Speech to text

The STT client accepts audio bytes and an optional source language. Bhashini sends base64 audio through its pipeline API. Sarvam uploads a file to its REST API. Both return the transcript with the selected model ID.

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

## Sarvam

Set `SARVAM_API_KEY`, then configure Saaras and route to it:

```toml
[providers.sarvam]
endpoint = "https://api.sarvam.ai"
stt_model_id = "saaras:v4"

[providers.sarvam.stt_model_ids]
"hi-IN" = "saaras:v3"

[routes]
speech_to_text = ["sarvam", "bhashini"]
```

Sarvam accepts an optional `language_code`. Omit the language for automatic detection; the result uses Sarvam's detected language when it provides one. Its synchronous REST endpoint accepts clips up to 30 seconds; longer recordings need Sarvam's batch API, which this adapter does not provide. The model ID can also come from `SARVAM_STT_MODEL_ID`.

### Live ASR

Install `indic-language-utils[streaming]` to use Sarvam's Realtime WebSocket. The streaming client accepts **mono signed 16-bit PCM bytes**, at 8 or 16 kHz. It does not resample microphone audio. Each stream yields the same `STTStreamEvent` shape regardless of provider: `kind` is `speech_start`, `speech_end`, `partial`, or `final`; `text` is present for transcript events; all events include language, provider, model ID, and request ID.

```python
import asyncio

from indic_language_utils import get_stt_client

async with get_stt_client() as client:
    async with client.stream(language="hi", sampling_rate=16000) as stream:

        async def send_audio():
            async for pcm_chunk in microphone_pcm_chunks():
                await stream.send_audio(pcm_chunk)
            await stream.finish()

        async def receive_events():
            async for event in stream.events():
                if event.kind in {"partial", "final"}:
                    print(event.kind, event.text)

        await asyncio.gather(send_audio(), receive_events())
```

`finish()` ends the Sarvam session after the last audio chunk. The adapter uses `saaras:v3-realtime` by default, or `saaras:v4` when that model is configured. Pass `model_id="saaras:v4"` to `client.stream()` to choose it explicitly. Sarvam's [Realtime API guide](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming) describes the underlying partial and final events. A stream selects one provider when it opens; it does not switch providers after audio has been sent.

## Google Free STT

The Google Free STT adapter (`google_free`) provides keyless, zero-setup transcription using the unofficial Google Web Speech API backed by `SpeechRecognition`.

Install the optional extra:

```bash
pip install 'indic-language-utils[stt-google-free]'
```

Configure `google_free` in `.indic-language-utils.toml`:

```toml
[providers.google_free]
timeout_seconds = 20.0
max_concurrency = 4

[routes]
speech_to_text = ["google_free", "bhashini"]
```

Usage in Python:

```python
from indic_language_utils import GoogleFreeSTTConfig, GoogleFreeSTTProvider, get_stt_client

provider = GoogleFreeSTTProvider(GoogleFreeSTTConfig())
client = get_stt_client(providers=[provider])

with open("speech.wav", "rb") as file:
    audio = file.read()

result = await client.transcribe(audio, language="hi")
print(result.text)
```

The adapter automatically maps language tags to Google BCP-47 codes such as `hi-IN`, `ta-IN`, `te-IN`, `bn-IN`, `mr-IN`, `pa-guru-IN`, and `en-IN`. Because this uses an unofficial API, it is intended for PoCs and local testing rather than high-throughput production workloads.
The extra installs PyAV to decode compressed audio such as MP3, FLAC, and OGG. Raw PCM must be mono, signed 16-bit audio; provide its actual sample rate. Set `GOOGLE_FREE_STT_DEFAULT_LANGUAGE` to choose the language used when a request omits one.

## Faster-Whisper

The Faster-Whisper adapter (`faster_whisper`) provides local, offline speech recognition powered by `faster-whisper` and CTranslate2.
Its timeout covers model loading and each transcription attempt. A timed-out call stops waiting, but an already running model operation may finish in the background; its concurrency slot remains occupied until then.

Install the optional extra:

```bash
pip install 'indic-language-utils[stt-whisper]'
```

Configure `faster_whisper` in `.indic-language-utils.toml`:

```toml
[providers.faster_whisper]
model = "base"
timeout_seconds = 60.0
max_concurrency = 2

[routes]
speech_to_text = ["faster_whisper", "bhashini"]
```

Usage in Python:

```python
from indic_language_utils import (
    FasterWhisperSTTConfig,
    FasterWhisperSTTProvider,
    get_stt_client,
)

config = FasterWhisperSTTConfig(
    model_size_or_path="base",
    device="auto",
    compute_type="default",
)
provider = FasterWhisperSTTProvider(config)
client = get_stt_client(providers=[provider])

with open("speech.wav", "rb") as file:
    audio = file.read()

# Omit language for automatic language detection
result = await client.transcribe(audio)
print(f"Transcript: {result.text}")
print(f"Detected language: {result.language}")
```

Available model sizes include `tiny`, `base`, `small`, `medium`, and `large-v3`. Setting `device="cuda"` with `compute_type="float16"` enables GPU acceleration.

## FastAPI and demo app

The demo app has a Speech to text tab for file upload. It accepts WAV, FLAC, MP3, and OGG files up to 10 MiB. Enter the file's actual sample rate before transcribing.

The FastAPI route accepts the same input as JSON:

```json
{
  "audio_base64": "<base64-encoded audio bytes>",
  "language": "hi",
  "audio_format": "wav",
  "sampling_rate": 16000,
  "provider": "google_free"
}
```

Send it to `POST /api/stt`. The response includes the transcript, normalized language, provider, model ID, and request IDs.

The repository includes CLI demos for each provider:

- `examples/stt/bhashini_demo.py`: live Bhashini inference
- `examples/stt/sarvam_demo.py`: live Sarvam Saaras inference
- `examples/stt/google_free_demo.py`: keyless Google Web Speech
- `examples/stt/whisper_demo.py`: local offline Faster-Whisper
