# Installation and quick start

This guide gets language detection and translation running with either optional local adapters or
Bhashini.

## Requirements

- Python 3.11 or 3.12
- `pip` or `uv`

## Choose an installation

The core package contains the shared API, Bhashini adapters, script detection, routing, retries,
and caches:

```bash
pip install indic-language-utils
```

Use `uv` if your project already manages dependencies with it:

```bash
uv add indic-language-utils
```

The core package does not install local models or select cloud providers. Add the
extras required by your application:

```bash
# Offline pure-Python Aksharamukha transliteration
pip install "indic-language-utils[local-transliteration]"

# Unofficial Google Translate adapter
pip install "indic-language-utils[googletrans]"

# Unofficial Google Free speech-to-text
pip install "indic-language-utils[stt-google-free]"

# Offline local Faster-Whisper speech-to-text
pip install "indic-language-utils[stt-whisper]"

# Keyless online Edge text-to-speech
pip install "indic-language-utils[tts-edge]"
```

## Run without Bhashini credentials

Install both optional adapters and select Google Translate for translation:

```bash
pip install "indic-language-utils[local-tld,googletrans]"
export TRANSLATION_SERVICE_PROVIDER="googletrans"
```

FastText becomes the default detection route when the `local-tld` extra is installed. Google
Translate uses an unofficial network adapter and is best suited to development and non-critical
fallbacks.

Detect a language and script:

```python
from indic_language_utils import detect_sync

result = detect_sync("नमस्ते भारत! आप कैसे हैं?")
print(result.language)  # hi-IN
print(result.script)  # Deva
print(f"{result.candidates[0].confidence:.2%}")
```

Translate text:

```python
from indic_language_utils import translate_sync

result = translate_sync("Welcome to digital governance services.", "en", "hi")
print(result.text)
```

## Use Bhashini

Install the core package, then provide the API endpoint, credential, and service identifiers through
environment variables:

```bash
pip install indic-language-utils
export BHASHINI_API_KEY="your-api-key"
export BHASHINI_ENDPOINT_URL="https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
export BHASHINI_TRANSLATION_SERVICE_ID="your-translation-service-id"
export BHASHINI_DETECTION_SERVICE_ID="your-detection-service-id"
```

The same `detect_sync` and `translate_sync` calls now use the configured Bhashini routes. See the
[configuration reference](configuration.md) for TOML settings, route order, caching, and environment
variable precedence.

## Use the asynchronous API

Network calls and batches have asynchronous equivalents:

```python
import asyncio

from indic_language_utils import translate


async def main() -> None:
    result = await translate("How can I help you today?", "en", "ta")
    print(result.text)


asyncio.run(main())
```

Continue with the [translation guide](translation.md) for batching and Markdown protection, or the
[detection guide](detection.md) for candidate scores and provider setup.

## Try the other capabilities

These calls use the configured route for each capability. They need the matching optional extra or provider credentials. The [provider reference](provider-reference.md) lists those requirements.

```python
import asyncio
from pathlib import Path

from indic_language_utils import (
    get_stt_client,
    get_tts_client,
    transliterate_sync,
)

print(transliterate_sync("namaste", "en", "hi").text)


async def speech_example() -> None:
    async with get_stt_client() as stt:
        audio = Path("hello.wav").read_bytes()
        transcript = await stt.transcribe(
            audio, language="hi", audio_format="wav", sampling_rate=16000
        )
        print(transcript.text)

    async with get_tts_client() as tts:
        speech = await tts.synthesize("नमस्ते", language="hi")
        Path(f"speech.{speech.audio_format or 'bin'}").write_bytes(speech.audio)


asyncio.run(speech_example())
```

The STT sample rate must match the file. The library does not resample audio. TTS format depends on the selected provider. See the [STT](stt.md) and [TTS](tts.md) guides for provider options and limits.

## Run the demo workbench

The browser workbench is a source checkout tool. Its assets are not included in the Python wheel. From a checkout:

```bash
uv sync --dev
pnpm --dir web install --frozen-lockfile
pnpm --dir web build
uv run indic-server
```

Open `http://127.0.0.1:8000`. A wheel installation provides the REST API and its `/docs` page, but shows a build instruction at `/` when the browser assets are absent.
