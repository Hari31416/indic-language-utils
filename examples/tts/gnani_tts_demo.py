"""Generate Gnani speech with inference or streamed WebSocket/SSE audio."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from indic_language_utils import Settings, TTSOptions, get_tts_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("gnani_tts_demo")


async def run(
    text: str,
    language: str,
    voice: str,
    output: Path,
    mode: str,
    speed: float,
    sample_rate: int,
    container: str,
) -> None:
    settings = Settings.load(overrides={"routes": {"text_to_speech": ["gnani"]}})
    parameters: dict[str, object] = {
        "voice": voice,
        "speed": speed,
        "audio_config": {
            "sample_rate": sample_rate,
            "num_channels": 1,
            "sample_width": 2,
            "container": container,
            **({"encoding": "linear_pcm"} if container == "wav" else {}),
        },
    }
    options = TTSOptions(parameters)
    async with get_tts_client(settings) as client:
        if mode == "inference":
            result = await client.synthesize(text, language=language, options=options)
            audio = result.audio
            logger.info("Format: %s; model: %s", result.audio_format or "unknown", result.model_id)
        else:
            options = TTSOptions({**parameters, "streaming_transport": mode})
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
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed, 0.85 to 1.15")
    parser.add_argument(
        "--sample-rate",
        type=int,
        choices=(8000, 16000, 22050, 24000, 44100, 48000),
        default=48000,
    )
    parser.add_argument("--container", choices=("wav", "mp3", "ogg"), default="wav")
    parser.add_argument(
        "--output", type=Path, help="Output path; defaults to gnani-speech.<container>"
    )
    args = parser.parse_args()
    if not 0.85 <= args.speed <= 1.15:
        parser.error("--speed must be between 0.85 and 1.15")
    output = args.output or Path(f"gnani-speech.{args.container}")
    asyncio.run(
        run(
            args.text,
            args.language,
            args.voice,
            output,
            args.mode,
            args.speed,
            args.sample_rate,
            args.container,
        )
    )


if __name__ == "__main__":
    main()
