"""Generate Gnani speech with inference or streamed WebSocket/SSE audio."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from indic_language_utils import Settings, TTSOptions, get_tts_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("gnani_tts_demo")


async def run(text: str, language: str, voice: str, output: Path, mode: str) -> None:
    settings = Settings.load(overrides={"routes": {"text_to_speech": ["gnani"]}})
    options = TTSOptions({"voice": voice})
    async with get_tts_client(settings) as client:
        if mode == "inference":
            result = await client.synthesize(text, language=language, options=options)
            audio = result.audio
            logger.info("Format: %s; model: %s", result.audio_format or "unknown", result.model_id)
        else:
            options = TTSOptions({"voice": voice, "streaming_transport": mode})
            chunks: list[bytes] = []
            async with client.stream(
                language=language, provider="gnani", options=options
            ) as stream:
                await stream.send_text(text)
                await stream.flush()
                async for event in stream.events():
                    if event.kind == "audio" and event.audio:
                        chunks.append(event.audio)
            audio = b"".join(chunks)
            logger.info("Received %s streamed audio chunks", len(chunks))
    await asyncio.to_thread(output.write_bytes, audio)
    logger.info("Saved %s bytes to %s", len(audio), output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate speech with Gnani")
    parser.add_argument("--text", default="नमस्ते, आपका स्वागत है।")
    parser.add_argument("--language", default="hi", help="BCP 47 language code")
    parser.add_argument("--voice", required=True, help="Gnani voice name")
    parser.add_argument("--mode", choices=("inference", "websocket", "sse"), default="inference")
    parser.add_argument("--output", type=Path, default=Path("gnani-speech.wav"))
    args = parser.parse_args()
    asyncio.run(run(args.text, args.language, args.voice, args.output, args.mode))


if __name__ == "__main__":
    main()
