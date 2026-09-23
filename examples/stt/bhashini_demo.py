"""Transcribe bundled or user-supplied audio with Bhashini batch ASR."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from indic_language_utils import STTClient, STTRequest, get_stt_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("bhashini_stt_demo")

SAMPLE_DIR = Path(__file__).resolve().parent
SAMPLES = (
    (SAMPLE_DIR / "english.wav", "en"),
    (SAMPLE_DIR / "hindi.wav", "hi"),
    (SAMPLE_DIR / "tamil.wav", "ta"),
)


async def transcribe_file(
    client: STTClient, audio_path: Path, language: str, sampling_rate: int
) -> None:
    audio_format = audio_path.suffix.lstrip(".").lower()
    audio = await asyncio.to_thread(audio_path.read_bytes)
    request = STTRequest(audio, language, audio_format, sampling_rate)
    result = await client.transcribe(request)
    logger.info("File: %s", audio_path)
    logger.info("Transcript: %s", result.text)
    logger.info("Language: %s", result.language)
    logger.info("Provider: %s", result.provider)
    logger.info("Model ID: %s\n", result.model_id)


async def run(audio_path: Path | None, language: str | None, sampling_rate: int) -> None:
    async with get_stt_client() as client:
        if audio_path is not None:
            assert language is not None
            await transcribe_file(client, audio_path, language, sampling_rate)
        else:
            for sample_path, sample_language in SAMPLES:
                await transcribe_file(client, sample_path, sample_language, 16000)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio with Bhashini")
    parser.add_argument(
        "audio",
        nargs="?",
        type=Path,
        help="Optional WAV, FLAC, MP3, or OGG file; defaults to bundled samples",
    )
    parser.add_argument("--language", help="Spoken language for a custom file, such as hi or ta")
    parser.add_argument("--sampling-rate", type=int, default=16000, help="Actual sample rate in Hz")
    args = parser.parse_args()
    if args.audio is not None and args.language is None:
        parser.error("--language is required for a custom audio file")
    if args.audio is None and args.language is not None:
        parser.error("--language applies only to a custom audio file")
    asyncio.run(run(args.audio, args.language, args.sampling_rate))


if __name__ == "__main__":
    main()
