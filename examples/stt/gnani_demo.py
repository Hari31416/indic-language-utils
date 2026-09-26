"""Transcribe audio with Gnani REST or realtime WebSocket STT."""

from __future__ import annotations

import argparse
import asyncio
import logging
import wave
from pathlib import Path

from indic_language_utils import Settings, STTRequest, get_stt_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("gnani_stt_demo")


async def run(audio_path: Path, language: str, streaming: bool) -> None:
    settings = Settings.load(overrides={"routes": {"speech_to_text": ["gnani"]}})
    async with get_stt_client(settings) as client:
        if not streaming:
            audio = await asyncio.to_thread(audio_path.read_bytes)
            result = await client.transcribe(STTRequest(audio, language, "wav", 16000))
            logger.info("Transcript: %s", result.text)
            logger.info("Model ID: %s", result.model_id)
            return

        with wave.open(str(audio_path), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise ValueError("Gnani streaming requires mono 16-bit PCM WAV audio")
            sample_rate = wav.getframerate()
            if sample_rate not in {8000, 16000, 44100, 48000}:
                raise ValueError("Gnani streaming supports 8, 16, 44.1, or 48 kHz audio")
            chunks = iter(lambda: wav.readframes(4096), b"")
            async with client.stream(
                language=language, sampling_rate=sample_rate, provider="gnani"
            ) as stream:
                for chunk in chunks:
                    await stream.send_audio(chunk)
                await stream.finish()
                async for event in stream.events():
                    if event.kind == "final" and event.text:
                        logger.info("Transcript: %s", event.text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio with Gnani")
    parser.add_argument("audio", type=Path, help="Mono 16-bit PCM WAV file")
    parser.add_argument("--language", default="hi", help="BCP 47 language code")
    parser.add_argument("--stream", action="store_true", help="Use realtime WebSocket STT")
    args = parser.parse_args()
    asyncio.run(run(args.audio, args.language, args.stream))


if __name__ == "__main__":
    main()
