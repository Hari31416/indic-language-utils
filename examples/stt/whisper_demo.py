"""Transcribe bundled or user-supplied audio using local Faster-Whisper."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from indic_language_utils import (
    FasterWhisperSTTConfig,
    FasterWhisperSTTProvider,
    STTClient,
    STTRequest,
    get_stt_client,
)
from indic_language_utils.errors import MissingOptionalDependencyError

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("whisper_stt_demo")

SAMPLE_DIR = Path(__file__).resolve().parent
SAMPLES = (
    (SAMPLE_DIR / "english.wav", "en"),
    (SAMPLE_DIR / "hindi.wav", "hi"),
    (SAMPLE_DIR / "tamil.wav", "ta"),
)


async def transcribe_file(
    client: STTClient, audio_path: Path, language: str | None, sampling_rate: int
) -> None:
    audio_format = audio_path.suffix.lstrip(".").lower()
    audio = await asyncio.to_thread(audio_path.read_bytes)
    request = STTRequest(audio, language, audio_format, sampling_rate)
    result = await client.transcribe(request)
    logger.info("File: %s", audio_path)
    logger.info("Transcript: %s", result.text)
    logger.info("Language: %s", result.language or "auto-detected")
    logger.info("Provider: %s", result.provider)
    logger.info("Model ID: %s\n", result.model_id)


async def run(
    audio_path: Path | None,
    language: str | None,
    sampling_rate: int,
    model_size: str,
    device: str,
) -> None:
    try:
        config = FasterWhisperSTTConfig(model_size_or_path=model_size, device=device)
        provider = FasterWhisperSTTProvider(config)
    except MissingOptionalDependencyError as exc:
        logger.error(str(exc))
        return

    async with get_stt_client(providers=[provider]) as client:
        if audio_path is not None:
            await transcribe_file(client, audio_path, language, sampling_rate)
        else:
            for sample_path, sample_language in SAMPLES:
                await transcribe_file(client, sample_path, sample_language, 16000)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio with Faster-Whisper")
    parser.add_argument(
        "audio",
        nargs="?",
        type=Path,
        help="Optional audio file; defaults to bundled WAV samples",
    )
    parser.add_argument("--language", help="Spoken language; omit for automatic detection")
    parser.add_argument("--sampling-rate", type=int, default=16000, help="Sample rate in Hz")
    parser.add_argument(
        "--model",
        default="base",
        help="Model size: tiny, base, small, medium, or large-v3 (default: base)",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Inference device: auto, cpu, or cuda (default: auto)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.audio, args.language, args.sampling_rate, args.model, args.device))


if __name__ == "__main__":
    main()
