"""Generate Navana TTS audio with HTTP synthesis or live WebSocket streaming."""

from __future__ import annotations

import argparse
import asyncio
import logging
import wave
from pathlib import Path

from indic_language_utils import Settings, TTSOptions, get_tts_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("navana_tts_demo")


def write_streamed_wav(chunks: list[bytes], output: Path, sample_rate: int) -> int:
    with wave.open(str(output), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"".join(chunks))
    return output.stat().st_size


async def run(
    text: str,
    language: str,
    voice: str,
    output_format: str,
    output: Path,
    *,
    speed: float | None,
    num_step: int | None,
    streaming: bool,
) -> None:
    settings = Settings.load(overrides={"routes": {"text_to_speech": ["navana"]}})
    options: dict[str, object] = {"voice": voice, "output_format": output_format}
    if num_step is not None:
        options["num_step"] = num_step

    async with get_tts_client(settings) as client:
        if streaming:
            if not output_format.endswith(":pcm16"):
                raise ValueError("Streaming output must use a pcm16 format to write a WAV file")
            chunks: list[bytes] = []
            async with client.stream(
                language=language,
                provider="navana",
                options=TTSOptions(options),
            ) as stream:
                await stream.send_text(text)
                await stream.flush()
                async for event in stream.events():
                    if event.kind == "audio" and event.audio:
                        chunks.append(event.audio)

            sample_rate = int(output_format.split(":", maxsplit=1)[0])
            size = await asyncio.to_thread(write_streamed_wav, chunks, output, sample_rate)
            logger.info("Saved %s bytes of streamed audio to %s", size, output)
            return

        if speed is not None:
            options["speed"] = speed
        result = await client.synthesize(text, language=language, options=TTSOptions(options))

    await asyncio.to_thread(output.write_bytes, result.audio)
    logger.info("Saved %s bytes to %s", len(result.audio), output)
    logger.info("Format: %s", result.audio_format or "unknown")
    logger.info("Model ID: %s", result.model_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate speech with Navana Bodhi")
    parser.add_argument("--text", default="नमस्ते, आपका स्वागत है।")
    parser.add_argument("--language", default="hi")
    parser.add_argument("--voice", default="default_female")
    parser.add_argument("--output-format", default="24000:pcm16")
    parser.add_argument("--speed", type=float, help="HTTP synthesis speed (0.25-4.0)")
    parser.add_argument("--num-step", type=int, help="Optional inference steps (1-100)")
    parser.add_argument("--stream", action="store_true", help="Use live WebSocket TTS")
    parser.add_argument("--output", type=Path, default=Path("navana-speech.wav"))
    args = parser.parse_args()
    try:
        asyncio.run(
            run(
                args.text,
                args.language,
                args.voice,
                args.output_format,
                args.output,
                speed=args.speed,
                num_step=args.num_step,
                streaming=args.stream,
            )
        )
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
