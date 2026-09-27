# Server API

Run the optional FastAPI application to expose the library over HTTP and WebSockets:

```bash
uv run uvicorn indic_language_utils.server.app:app --reload
```

The server reads provider credentials from its process environment or a local `.env` file. Set `GNANI_API_KEY` to enable Gnani STT and TTS. The web app can also store a Gnani API key and optional endpoint in its API keys panel; it sends these with API and streaming requests. The panel stores keys in browser local storage.

`GET /api/providers` lists Gnani under both `speech_to_text` and `text_to_speech` when the key and endpoint configuration are valid. API requests can override the server key and endpoint with the `X-Gnani-Api-Key` and `X-Gnani-Endpoint` headers.

## Gnani STT

`POST /api/stt` accepts the standard base64 audio request with `provider` set to `gnani`, a BCP 47 `language`, `audio_format`, and `sampling_rate`. For live microphone transcription, use `WS /api/stt/stream` with a start frame such as:

```json
{"type":"start","provider":"gnani","language":"hi","sampling_rate":16000}
```

After `ready`, send mono signed 16-bit PCM as binary WebSocket messages, then send `{"type":"finish"}`. Gnani supports 8, 16, 44.1, and 48 kHz sample rates. The server selects Gnani when it appears in the start frame, splits input into Gnani's required 1,024-byte frames, and returns `{"type":"done","transcript_count":0}` if no speech was transcribed. A start-frame `api_key` or `endpoint` overrides `GNANI_API_KEY` or `GNANI_ENDPOINT_URL`.

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

For Gnani inference, choose the provider and send its required voice and language:

```json
{
  "text": "नमस्ते।",
  "language": "hi",
  "provider": "gnani",
  "parameters": {"voice": "Nalini"}
}
```

## Streaming TTS

`WS /api/tts/stream` supports Sarvam, Navana, and Gnani live synthesis. Start a Navana session with:

```json
{"type":"start","provider":"navana","language":"hi","parameters":{"voice":"default_female","output_format":"24000:pcm16"}}
```

After the server sends `{"type":"ready"}`, send text and flush the session:

```json
{"type":"text","text":"नमस्ते।"}
{"type":"flush"}
```

The server forwards each audio chunk in a JSON `event` message with the `audio_base64` field. The final `event` has `kind: "done"`, followed by `{"type":"done"}`. Navana's stream yields raw PCM chunks at the negotiated sample rate. An optional `api_key` or `endpoint` in the opening frame overrides `NAVANA_API_KEY` or the default `https://tts.navana.ai` endpoint.

For Gnani, include a voice and request raw PCM to enable live playback:

```json
{"type":"start","provider":"gnani","language":"hi","parameters":{"voice":"Nalini","audio_config":{"sample_rate":24000,"num_channels":1,"sample_width":2,"encoding":"linear_pcm","container":"raw"}}}
```

Set `streaming_transport` to `sse` in `parameters` to use Gnani's SSE transport behind the browser WebSocket bridge; it defaults to Gnani WebSocket. The `api_key` and `endpoint` start-frame overrides work for Gnani as well.

## Provider discovery

`GET /api/providers` reports Gnani under STT and TTS, and Navana under TTS when their credentials are configured. Gnani does not provide translation, detection, or transliteration.
