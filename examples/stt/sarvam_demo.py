"""Transcribe bundled audio with Sarvam Saaras."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from indic_language_utils import Settings, STTClient, STTRequest, get_stt_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sarvam_stt_demo")

SAMPLES = (("english.wav", "en"), ("hindi.wav", "hi"), ("tamil.wav", "ta"))


async def transcribe_file(client: STTClient, path: Path, language: str | None) -> None:
    audio = await asyncio.to_thread(path.read_bytes)
    result = await client.transcribe(STTRequest(audio, language, path.suffix.lstrip("."), 16000))
    logger.info("File: %s", path)
    logger.info("Transcript: %s", result.text)
    logger.info("Language: %s", result.language or "undetected")
    logger.info("Model ID: %s\n", result.model_id)


async def run(path: Path | None, language: str | None) -> None:
    settings = Settings.load(overrides={"routes": {"speech_to_text": ["sarvam"]}})
    async with get_stt_client(settings) as client:
        if path is not None:
            await transcribe_file(client, path, language)
        else:
            for name, sample_language in SAMPLES:
                await transcribe_file(client, Path(__file__).parent / name, sample_language)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio with Sarvam")
    parser.add_argument("audio", nargs="?", type=Path, help="Defaults to bundled WAV clips")
    parser.add_argument("--language", help="Spoken language; omit for automatic detection")
    args = parser.parse_args()
    asyncio.run(run(args.audio, args.language))


if __name__ == "__main__":
    main()
