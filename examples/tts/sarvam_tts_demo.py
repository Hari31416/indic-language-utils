"""Generate a WAV file with Sarvam Bulbul."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from indic_language_utils import Settings, TTSOptions, get_tts_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sarvam_tts_demo")


async def run(text: str, language: str, speaker: str, pace: float, output: Path) -> None:
    settings = Settings.load(overrides={"routes": {"text_to_speech": ["sarvam"]}})
    async with get_tts_client(settings) as client:
        result = await client.synthesize(
            text, language=language, options=TTSOptions({"speaker": speaker, "pace": pace})
        )
    await asyncio.to_thread(output.write_bytes, result.audio)
    logger.info("Saved %s bytes to %s", len(result.audio), output)
    logger.info("Model ID: %s", result.model_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate speech with Sarvam")
    parser.add_argument("--text", default="नमस्ते, आपका स्वागत है।")
    parser.add_argument("--language", default="hi", help="Sarvam TTS requires a language")
    parser.add_argument("--speaker", default="shubh")
    parser.add_argument("--pace", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path("sarvam-speech.wav"))
    args = parser.parse_args()
    asyncio.run(run(args.text, args.language, args.speaker, args.pace, args.output))


if __name__ == "__main__":
    main()
