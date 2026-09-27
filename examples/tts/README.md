# Text to speech example

## Gnani

Set `GNANI_API_KEY` in `.env` or your shell. Provide a voice supported by your Gnani account. The inference endpoint writes the returned audio bytes to the output path:

```bash
uv run --env-file .env python examples/tts/gnani_tts_demo.py --voice YOUR_VOICE --mode inference --output gnani-speech.wav
```

The example also supports Gnani's WebSocket and server-sent-event (SSE) streaming transports. Install the `streaming` extra for WebSocket mode; SSE uses HTTP and does not require it:

```bash
uv sync --extra streaming
uv run --env-file .env python examples/tts/gnani_tts_demo.py --voice YOUR_VOICE --mode websocket --output gnani-live.wav
uv run --env-file .env python examples/tts/gnani_tts_demo.py --voice YOUR_VOICE --mode sse --output gnani-sse.wav
```

Streaming output is saved as the concatenated audio chunks returned by Gnani. Use an extension appropriate to the `audio_config.container` selected for your account/model.

The [official Timbre v2.5 voice catalog](https://docs.gnani.ai/api/TTS/available-voices) groups 42 voices by preferred language. For example, use Nalini with Hindi, Kaveri with English, or Poorvi with Hinglish:

```bash
uv run --env-file .env python examples/tts/gnani_tts_demo.py --language hi-en --voice Poorvi --text "Namaste, how are you?" --output gnani-hinglish.wav
```

Use `--speed` between 0.85 and 1.15, `--sample-rate` with a documented rate, and `--container wav|mp3|ogg` to choose the output. For example:

```bash
uv run --env-file .env python examples/tts/gnani_tts_demo.py --language en --voice Kaveri --speed 1.1 --sample-rate 48000 --container mp3
```

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
