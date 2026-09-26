# Server API

Run the optional FastAPI application to expose the library over HTTP and WebSockets:

```bash
uv run uvicorn indic_language_utils.server.app:app --reload
```

The server reads provider credentials from its process environment or a local `.env` file. Set `NAVANA_API_KEY` to enable Navana TTS. The web app can also store a Navana API key in its API keys panel and send it with synthesis requests.

## Non-streaming TTS

`POST /api/tts` accepts the same provider-neutral request format as the Python client:

```json
{
  "text": "नमस्ते, आपका स्वागत है।",
  "language": "hi",
  "provider": "navana",
  "parameters": {
    "voice": "default_female",
    "output_format": "24000:pcm16"
  }
}
```

The response includes base64-encoded WAV audio and provider metadata. The Navana provider wraps the raw PCM response in a WAV container for browser playback.

## Streaming TTS

`WS /api/tts/stream` supports Sarvam and Navana live synthesis. Start a Navana session with:

```json
{"type":"start","provider":"navana","language":"hi","parameters":{"voice":"default_female","output_format":"24000:pcm16"}}
```

After the server sends `{"type":"ready"}`, send text and flush the session:

```json
{"type":"text","text":"नमस्ते।"}
{"type":"flush"}
```

The server forwards each audio chunk in a JSON `event` message with the `audio_base64` field. The final `event` has `kind: "done"`, followed by `{"type":"done"}`. Navana's stream yields raw PCM chunks at the negotiated sample rate. An optional `api_key` or `endpoint` in the opening frame overrides `NAVANA_API_KEY` or the default `https://tts.navana.ai` endpoint.

## Provider discovery

`GET /api/providers` reports Navana TTS as available when `NAVANA_API_KEY` is configured. The response lists it under `text_to_speech`; the service does not add Navana to translation, detection, transliteration, or transcription.
