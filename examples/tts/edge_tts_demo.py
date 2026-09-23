"""Generate speech with Microsoft Edge TTS (free, keyless)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from indic_language_utils import TTSOptions, get_tts_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("edge_tts_demo")


async def run(text: str, language: str | None, parameters: dict[str, object], output: Path) -> None:
    async with get_tts_client() as client:
        result = await client.synthesize(text, language=language, options=TTSOptions(parameters))
    await asyncio.to_thread(output.write_bytes, result.audio)
    logger.info("Saved %s bytes to %s", len(result.audio), output)
    logger.info("Provider: %s", result.provider)
    logger.info("Format: %s", result.audio_format or "unknown")
    logger.info("Language: %s", result.language or "unspecified")
    logger.info("Voice / Model: %s", result.model_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate speech with Microsoft Edge TTS")
    parser.add_argument("--text", default="नमस्ते, आपका स्वागत है।")
    parser.add_argument("--language", default="hi", help="Use an empty value to omit language")
    parser.add_argument(
        "--parameters",
        default='{"gender":"female","rate":"+0%"}',
        help="JSON object of options such as gender, voice, rate, pitch, or volume",
    )
    parser.add_argument("--output", type=Path, default=Path("edge-speech.mp3"))
    args = parser.parse_args()
    try:
        parameters = json.loads(args.parameters)
    except json.JSONDecodeError as exc:
        parser.error(f"Invalid --parameters JSON: {exc.msg}")
    if not isinstance(parameters, dict):
        parser.error("--parameters must be a JSON object")
    asyncio.run(run(args.text, args.language or None, parameters, args.output))


if __name__ == "__main__":
    main()
