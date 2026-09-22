"""Runnable examples demonstrating translation with live Bhashini inference."""

from __future__ import annotations

import asyncio

from indic_language_utils import (
    TextFormat,
    TranslationOptions,
    get_sync_translation_client,
    get_translation_client,
    translate,
    translate_batch,
    translate_batch_sync,
    translate_sync,
)


def run_sync_examples() -> None:
    print("==================================================")
    print("1. Synchronous Translation (Quick One-Liners)")
    print("==================================================")
    # Quick one-liner translation
    res = translate_sync("Welcome to India!", "en", "hi")
    print("Source:     ", "Welcome to India!")
    print("Translation:", res.text)
    print()

    # Quick batch translation
    messages = [
        "Please verify your mobile number.",
        "An OTP has been sent to your registered device.",
        "Do not share your credentials with anyone.",
    ]
    batch_results = translate_batch_sync(messages, "en", "hi")
    print("Batch Translation (English to Hindi):")
    for text, r in zip(messages, batch_results, strict=True):
        print(f"  - {text} -> {r.text}")
    print()

    # Synchronous client facade
    sync_client = get_sync_translation_client()
    res_facade = sync_client.translate("Thank you for your feedback.", "en", "hi")
    print("Sync Client Facade:", res_facade.text)
    print()


async def run_async_examples() -> None:
    print("==================================================")
    print("2. Asynchronous Translation (Quick One-Liners)")
    print("==================================================")
    res_async = await translate("Namaste world!", "en", "hi")
    print("Async One-Liner:", res_async.text)

    batch_async = await translate_batch(["Good morning", "Good night"], "en", "hi")
    for r in batch_async:
        print(f"Async Batch Item: {r.text}")
    print()

    print("==================================================")
    print("3. Managed Async TranslationClient with Caching")
    print("==================================================")
    async with get_translation_client() as client:
        # First call hits provider and stores in SQLite cache
        res1 = await client.translate("Welcome to the citizen services portal.", "en", "hi")
        print("Source:     ", "Welcome to the citizen services portal.")
        print("Translation:", res1.text)
        print(f"Elapsed:     {res1.elapsed_seconds:.3f}s (Cache Hit: {res1.cache.hit})")

        # Second identical call resolves instantly from cache
        res1_cached = await client.translate("Welcome to the citizen services portal.", "en", "hi")
        print(
            f"Elapsed:     {res1_cached.elapsed_seconds:.4f}s (Cache Hit: {res1_cached.cache.hit})"
        )
        print()

        # Multi-language support (English to Tamil)
        print("Translation to Tamil:")
        res_tamil = await client.translate("Your grievance status is resolved.", "en", "ta")
        print("Tamil Translation:", res_tamil.text)
        print()

        # Markdown preservation with best_effort=True
        print("Markdown Preservation:")
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
            markdown_input,
            "en",
            "hi",
            options=TranslationOptions(
                text_format=TextFormat.MARKDOWN,
                best_effort=True,
            ),
        )
        print("Translated Markdown:\n" + res_md.text + "\n")


def main() -> None:
    run_sync_examples()
    asyncio.run(run_async_examples())


if __name__ == "__main__":
    main()
