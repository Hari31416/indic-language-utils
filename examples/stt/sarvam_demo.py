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


async def transcribe_file(
    client: STTClient, path: Path, language: str | None, *, with_timestamps: bool = True
) -> None:
    audio = await asyncio.to_thread(path.read_bytes)
    result = await client.transcribe(
        STTRequest(
            audio,
            language,
            path.suffix.lstrip("."),
            16000,
            with_timestamps=with_timestamps,
        )
    )
    logger.info("File: %s", path)
    logger.info("Transcript: %s", result.text)
    logger.info("Language: %s", result.language or "undetected")
    logger.info("Model ID: %s", result.model_id)
    if result.segments:
        logger.info("Segments (%d):", len(result.segments))
        for seg in result.segments:
            logger.info("  [%0.2fs - %0.2fs] %s", seg.start, seg.end, seg.text)
    if result.words:
        logger.info("Words (%d):", len(result.words))
        for w in result.words:
            prob = f" (p={w.probability:0.2f})" if w.probability is not None else ""
            logger.info("  %0.2fs - %0.2fs: %s%s", w.start, w.end, w.word, prob)
    logger.info("")


async def run(path: Path | None, language: str | None, with_timestamps: bool = True) -> None:
    settings = Settings.load(overrides={"routes": {"speech_to_text": ["sarvam"]}})
    async with get_stt_client(settings) as client:
        if path is not None:
            await transcribe_file(client, path, language, with_timestamps=with_timestamps)
        else:
            for name, sample_language in SAMPLES:
                await transcribe_file(
                    client,
                    Path(__file__).parent / name,
                    sample_language,
                    with_timestamps=with_timestamps,
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio with Sarvam")
    parser.add_argument("audio", nargs="?", type=Path, help="Defaults to bundled WAV clips")
    parser.add_argument("--language", help="Spoken language; omit for automatic detection")
    parser.add_argument(
        "--timestamps",
        action="store_true",
        default=True,
        help="Enable timestamp extraction (default: True)",
    )
    parser.add_argument(
        "--no-timestamps",
        dest="timestamps",
        action="store_false",
        help="Disable timestamp extraction",
    )
    args = parser.parse_args()
    asyncio.run(run(args.audio, args.language, args.timestamps))


if __name__ == "__main__":
    main()
