# Speech to text example

The repository includes three generated 16 kHz mono WAV clips:

| File | Spoken language | Spoken text |
| --- | --- | --- |
| `english.wav` | English | Hello. This is a speech recognition example. |
| `hindi.wav` | Hindi | नमस्ते। यह भाषण पहचान का उदाहरण है। |
| `tamil.wav` | Tamil | வணக்கம். இது பேச்சு அடையாளம் காணும் எடுத்துக்காட்டு. |

The clips were generated with macOS voices Aman, Lekha, and Vani. They contain synthetic speech only.

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
