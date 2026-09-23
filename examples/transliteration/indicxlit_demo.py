"""Runnable examples demonstrating local offline transliteration with AI4Bharat IndicXlit."""

from __future__ import annotations

import asyncio
import logging

from indic_language_utils import (
    CapabilityId,
    IndicXlitConfig,
    IndicXlitTransliterationProvider,
    OrderedRouter,
    ProviderRegistry,
    TransliterationClient,
)
from indic_language_utils.transliteration.indicxlit import HAVE_INDICXLIT

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("indicxlit_demo")


class MockXlitEngine:
    """Mock engine simulating IndicXlit transliteration when model weights are not installed."""

    def __init__(self, src_script_type: str = "roman") -> None:
        self.src_script_type = src_script_type
        self._roman_to_indic: dict[str, dict[str, str]] = {
            "hi": {
                "namaste": "नमस्ते",
                "bharat": "भारत",
                "dhanyavaad": "धन्यवाद",
            },
            "ta": {
                "vanakkam": "வணக்கம்",
                "nanri": "நன்றி",
            },
            "te": {
                "namaskaram": "నమస్కారం",
                "dhanyavadalu": "ధన్యవాదాలు",
            },
        }
        self._indic_to_roman: dict[str, str] = {
            "नमस्ते": "namaste",
            "भारत": "bharat",
            "வணக்கம்": "vanakkam",
            "நன்றி": "nanri",
        }

    def translit_sentence(self, text: str, lang_code: str) -> str:
        if any("\u0900" <= ch <= "\u0d7f" for ch in text):
            return self._indic_to_roman.get(text, "namaste")
        return self._roman_to_indic.get(lang_code, {}).get(text.lower(), f"{text}-indic")


async def run_indicxlit_demo() -> None:
    if HAVE_INDICXLIT:
        logger.info("Initializing live AI4Bharat IndicXlit local engine...")
        config = IndicXlitConfig(beam_width=4, rescore=True)
        provider = IndicXlitTransliterationProvider(config)
    else:
        logger.info("ai4bharat-transliteration not installed; using Mock IndicXlit engine.")
        provider = IndicXlitTransliterationProvider(engine=MockXlitEngine())

    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLITERATION: ("indicxlit",)})

    async with TransliterationClient(router) as client:
        logger.info("\n--- Roman to Indic Transliteration ---")
        hindi_res = await client.transliterate("namaste", source="en", target="hi")
        logger.info("English -> Hindi: %s -> %s", hindi_res.source_text, hindi_res.text)

        tamil_res = await client.transliterate("vanakkam", source="en", target="ta")
        logger.info("English -> Tamil: %s -> %s", tamil_res.source_text, tamil_res.text)

        telugu_res = await client.transliterate("namaskaram", source="en", target="te")
        logger.info("English -> Telugu: %s -> %s", telugu_res.source_text, telugu_res.text)

        logger.info("\n--- Indic to Roman Transliteration ---")
        roman_res = await client.transliterate("नमस्ते", source="hi", target="en")
        logger.info("Hindi -> Roman: %s -> %s", roman_res.source_text, roman_res.text)


if __name__ == "__main__":
    asyncio.run(run_indicxlit_demo())
