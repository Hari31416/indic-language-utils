"""Runnable examples demonstrating the translation service with live Bhashini inference."""

from __future__ import annotations

import asyncio

from indic_language_utils import (
    DEFAULT_LANGUAGE_REGISTRY,
    BhashiniConfig,
    BhashiniTranslationProvider,
    CacheKeyBuilder,
    CapabilityId,
    ProviderRegistry,
    Settings,
    TextFormat,
    TranslationClient,
    TranslationOptions,
    TranslationRequest,
    create_translation_cache,
)
from indic_language_utils.routing import OrderedRouter


async def main() -> None:
    # 1. Load configuration and initialize Bhashini provider
    settings = Settings.load()
    provider = BhashiniTranslationProvider(BhashiniConfig.from_settings(settings))

    registry = ProviderRegistry()
    registry.register(provider)
    router = OrderedRouter(registry, {CapabilityId.TRANSLATION: ("bhashini",)})

    # Normalized canonical language tags
    en = DEFAULT_LANGUAGE_REGISTRY.normalize("en")
    hi = DEFAULT_LANGUAGE_REGISTRY.normalize("hi")
    ta = DEFAULT_LANGUAGE_REGISTRY.normalize("ta")

    # Persistent SQLite cache configured from .indic-language-utils.toml
    cache = create_translation_cache(settings.cache)
    cache_keys = CacheKeyBuilder(settings.cache.namespace)

    async with provider:
        client = TranslationClient(router, cache=cache, cache_keys=cache_keys)

        # ---------------------------------------------------------
        # Example 1: Single Text Translation & Caching
        # ---------------------------------------------------------
        print("=== 1. Single Text Translation & SQLite Caching ===")
        req1 = TranslationRequest("Welcome to the citizen services portal.", en, hi)

        res1 = await client.translate(req1)
        print("Source:     ", req1.text)
        print("Translation:", res1.text)
        print(f"Elapsed:     {res1.elapsed_seconds:.3f}s (Cache Hit: {res1.cache.hit})")

        # Second identical request hits the cache instantly
        res1_cached = await client.translate(req1)
        print(
            f"Elapsed:     {res1_cached.elapsed_seconds:.4f}s "
            f"(Cache Hit: {res1_cached.cache.hit})\n"
        )

        # ---------------------------------------------------------
        # Example 2: Batch Translation (Preserves Ordering)
        # ---------------------------------------------------------
        print("=== 2. Batch Translation (English to Hindi) ===")
        batch_requests = (
            TranslationRequest("Please verify your mobile number.", en, hi),
            TranslationRequest("An OTP has been sent to your registered device.", en, hi),
            TranslationRequest("Do not share your credentials with anyone.", en, hi),
        )
        batch_results = await client.translate_batch(batch_requests)
        for req, res in zip(batch_requests, batch_results, strict=True):
            print(f"- Source:      {req.text}")
            print(f"  Translation: {res.text}")
        print()

        # ---------------------------------------------------------
        # Example 3: Multiple Language Targets (English to Tamil)
        # ---------------------------------------------------------
        print("=== 3. Translation to Another Language (English to Tamil) ===")
        req_tamil = TranslationRequest("Your grievance status is resolved.", en, ta)
        res_tamil = await client.translate(req_tamil)
        print("Source:     ", req_tamil.text)
        print("Translation (Tamil):", res_tamil.text)
        print(f"Elapsed:     {res_tamil.elapsed_seconds:.3f}s\n")

        # ---------------------------------------------------------
        # Example 4: Markdown Preservation
        # ---------------------------------------------------------
        print("=== 4. Markdown Preservation with Protected Elements ===")
        markdown_input = """# Citizen Registration Portal

Please keep the following information ready:
- Application Reference: `APP-9021-X`
- Portal Link: [National Portal](https://services.india.gov.in)
- Verification Code: `4488`

```
curl -X GET https://api.example.gov.in/status
```

Submit your grievance before the deadline."""

        res_md = await client.translate(
            TranslationRequest(
                markdown_input,
                en,
                hi,
                options=TranslationOptions(text_format=TextFormat.MARKDOWN),
            )
        )
        print("Source Markdown:\n" + markdown_input + "\n")
        print("Translated Markdown:\n" + res_md.text + "\n")


if __name__ == "__main__":
    asyncio.run(main())
