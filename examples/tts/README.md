# Text to speech example

The repository config selects Bhashini's `Bhashini/IITM/TTS` model. Set `BHASHINI_API_KEY` in your shell or `.env`, then run:

```bash
uv run --env-file .env python examples/tts/bhashini_tts_demo.py
```

The demo writes `bhashini-speech.wav` in the current directory. Change the text, language, output path, and model options as needed:

```bash
uv run --env-file .env python examples/tts/bhashini_tts_demo.py \
  --text "नमस्ते दुनिया" --language hi \
  --parameters '{"gender":"female","samplingRate":16000}' \
  --output /tmp/hindi.wav
```

Model options are passed to Bhashini's TTS task config. Use the keys supported by your selected model. Pass `--language ''` for models that infer language.

To generate audio with Sarvam, set `SARVAM_API_KEY` and run:

```bash
uv run --env-file .env python examples/tts/sarvam_tts_demo.py --speaker shubh --pace 1.0
```

The example explicitly routes to Sarvam and writes `sarvam-speech.wav`. Sarvam Bulbul requires `--language`; its options use `speaker` and `pace` rather than Bhashini's `gender` and `samplingRate`.

To generate audio with Navana Bodhi, set `NAVANA_API_KEY` in your shell or `.env` and run:

```bash
uv run --env-file .env python examples/tts/navana_tts_demo.py --voice achu --speed 1.0
```

The example explicitly routes to Navana and writes `navana-speech.wav`. Use `--stream` to synthesize over Navana's WebSocket API and save the returned PCM chunks in a WAV file:

```bash
uv run --env-file .env python examples/tts/navana_tts_demo.py \
  --stream --language hi --voice achu --output /tmp/navana-live.wav
```

Streaming requires the `streaming` optional dependency (`uv sync --extra streaming`). The stream demo accepts `pcm16` output formats such as `24000:pcm16`; `--speed` applies to HTTP synthesis only. Other options include `--num-step`, `--output-format`, and `--output`.

To generate audio with Microsoft Edge TTS (free, keyless), run:

```bash
uv run python examples/tts/edge_tts_demo.py --language hi --parameters '{"gender":"female"}'
```

Edge TTS produces MP3 audio without requiring any API keys. You can specify gender (`female`, `male`), exact voice (`voice`), speaking rate (`rate`), volume (`volume`), or pitch (`pitch`).
