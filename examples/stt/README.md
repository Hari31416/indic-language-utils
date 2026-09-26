# Speech to text example

The repository includes three generated 16 kHz mono WAV clips:

| File | Spoken language | Spoken text |
| --- | --- | --- |
| `english.wav` | English | Hello. This is a speech recognition example. |
| `hindi.wav` | Hindi | नमस्ते। यह भाषण पहचान का उदाहरण है। |
| `tamil.wav` | Tamil | வணக்கம். இது பேச்சு அடையாளம் காணும் எடுத்துக்காட்டு. |

The clips were generated with macOS voices Aman, Lekha, and Vani. They contain synthetic speech only.

## Gnani

Set `GNANI_API_KEY` in `.env` or your shell. The REST example accepts WAV audio and a BCP 47 language code:

```bash
uv run --env-file .env python examples/stt/gnani_demo.py examples/stt/hindi.wav --language hi
```

For realtime recognition, install the optional WebSocket dependency and pass `--stream`. Streaming input must be mono, 16-bit PCM WAV at 8, 16, 44.1, or 48 kHz:

```bash
uv sync --extra streaming
uv run --env-file .env python examples/stt/gnani_demo.py examples/stt/hindi.wav --language hi --stream
```

The repository's `.indic-language-utils.toml` contains the Bhashini endpoint and model IDs. Set `BHASHINI_API_KEY` in your shell or `.env`, then run all three clips against the live API:

```bash
uv run --env-file .env python examples/stt/bhashini_demo.py
```

You can also transcribe your own file:

```bash
uv run --env-file .env python examples/stt/bhashini_demo.py recording.wav --language hi --sampling-rate 16000
```

Pass the file's actual sample rate. The demo prints the transcript and selected model ID for each file.

To run the same bundled clips through Sarvam, set `SARVAM_API_KEY` and run:

```bash
uv run --env-file .env python examples/stt/sarvam_demo.py
```

Sarvam's REST endpoint accepts clips up to 30 seconds. The example explicitly routes to Sarvam and uses the configured `saaras:v4` model. Pass a custom file as the positional argument and `--language hi` if you know its language. Omit the language for automatic detection.

## Google Free STT

Run keyless speech recognition using the unofficial Google Web Speech API backed by `SpeechRecognition`. Install the extra first:

```bash
uv sync --extra stt-google-free
```

Then run the bundled samples:

```bash
uv run python examples/stt/google_free_demo.py
```

Or transcribe a custom file with a specified language:

```bash
uv run python examples/stt/google_free_demo.py recording.wav --language hi --sampling-rate 16000
```

## Faster-Whisper

Run offline, local speech recognition with `faster-whisper`. Install the extra first:

```bash
uv sync --extra stt-whisper
```

Then run the bundled samples with automatic language detection:

```bash
uv run python examples/stt/whisper_demo.py
```

You can customize the model size and inference device:

```bash
uv run python examples/stt/whisper_demo.py recording.wav --model small --device cpu
```
