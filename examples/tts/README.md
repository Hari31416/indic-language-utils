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
