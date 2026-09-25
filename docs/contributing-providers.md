# Contributing a provider

A provider implements one or more capability protocols. You can use an adapter in your own application without changing the library. Add it to the repository when other users would benefit from the integration.

## Start with one capability

Install the development environment with `uv sync --dev`. Choose the protocol for the operation you support: `TranslationProvider`, `DetectionProvider`, `TransliterationProvider`, `STTProvider`, or `TTSProvider`. Speech streaming has separate `StreamingSTTProvider` and `StreamingTTSProvider` protocols. Read a nearby adapter and its tests before adding a new one.

This small translation adapter shows the required shape. It changes the text in a predictable way so it can be tried without credentials:

```python
from indic_language_utils import (
    CapabilityDeclaration,
    CapabilityId,
    ProviderIdentity,
    Settings,
    get_translation_client,
)
from indic_language_utils.languages import LanguageTag
from indic_language_utils.translation import (
    ProviderTranslationResult,
    TranslationOptions,
    TranslationProvider,
)


class PrefixTranslationProvider:
    identity = ProviderIdentity("prefix", "Prefix example")
    capabilities = (CapabilityDeclaration(CapabilityId.TRANSLATION),)

    async def translate_batch(
        self,
        texts: tuple[str, ...],
        *,
        source: LanguageTag,
        target: LanguageTag,
        options: TranslationOptions,
        request_id: str,
    ) -> ProviderTranslationResult:
        return ProviderTranslationResult(
            tuple(f"[{target}] {text}" for text in texts),
            request_id=request_id,
        )


async def example() -> None:
    provider: TranslationProvider = PrefixTranslationProvider()
    settings = Settings(routes={"translation": ("prefix",)})
    async with get_translation_client(settings, additional_providers=[provider], env={}) as client:
        result = await client.translate("Hello", "en", "hi")
        assert result.provider.provider == "prefix"
```

`additional_providers` registers adapters alongside configured built-ins. `providers` supplies an explicit replacement list. When you pass `Settings` explicitly, its route order applies to either list. If you pass only `providers`, their order is used; this keeps application tests independent of a discovered project configuration. A configured route names the providers eligible for that capability, so include your new ID in the route when one exists. Duplicate provider IDs raise `ConfigurationError`.

## Register a builder

If your application constructs the adapter from settings, register a builder. Builders receive the loaded `Settings` and the environment mapping, and return an adapter or `None` when the adapter is not configured:

```python
from collections.abc import Mapping

from indic_language_utils import CapabilityId, Settings, get_translation_client
from indic_language_utils.providers import default_provider_factories


def build_prefix_provider(settings: Settings, env: Mapping[str, str]) -> PrefixTranslationProvider:
    return PrefixTranslationProvider()


factories = default_provider_factories()
factories.register(CapabilityId.TRANSLATION, "prefix", build_prefix_provider)
client = get_translation_client(
    Settings(routes={"translation": ("prefix",)}),
    provider_factories=factories,
)
```

The example reuses `PrefixTranslationProvider` from above. A builder has the signature `(settings, env) -> provider | None`. The client copies the registry before use, so the caller's registry remains available for other clients. A builder must return an adapter whose identity matches its registered ID and whose capability declaration includes the registered capability.

An installed third-party package can advertise a builder through an entry point in its `pyproject.toml`:

```toml
[project.entry-points."indic_language_utils.providers.translation"]
prefix = "my_package.indic_provider:build_prefix_provider"
```

Use the same group suffix as the capability ID: `translation`, `text_language_detection`, `transliteration`, `speech_to_text`, or `text_to_speech`. The entry point name must equal the provider identity. The library loads the entry point only when that name appears in `[providers.<id>]` or the matching `[routes]` list. A selected plugin that cannot load, returns `None`, or builds an adapter with the wrong identity raises `ConfigurationError` naming the provider. `providers=` skips all builder and entry point loading.

For a plugin-specific option, place values under `[providers.prefix.options]`, validate them in the builder, and read credentials from `env` or another caller-supplied secret source. Do not store credentials in TOML. Set an explicit route when you need the plugin before or after built-in adapters.

Declare only the capabilities you implement. `CapabilityDeclaration` can restrict languages, language pairs, or features; an empty language set means unrestricted routing. Use the normalized `LanguageTag` values received by the method. Return one output per input and preserve their order. Include the upstream request ID and model or service ID when available.

## Turn the example into a network adapter

- Give the adapter an immutable config type for its endpoint, timeout, model, and concurrency limit. Read adapter-specific values from `[providers.<id>.options]` and validate their names, types, and ranges in the adapter config. The settings loader checks that options contain TOML-compatible values and no secret-like keys. Read credentials from the environment or a caller-supplied `Secret`, which redacts its value in logs. See the [configuration guide](configuration.md#provider-specific-options).
- Accept an injectable transport or client so tests can provide deterministic responses. If the adapter owns a network client, implement async `start()` and `close()`; the capability client calls them when used as an async context manager.
- Translate upstream errors into the library's exceptions in `indic_language_utils.errors`. Rate limits, timeouts, transient failures, malformed responses, and output validation failures can trigger the next routed provider. Authentication, invalid input, and unsupported language errors stop the request. Do not catch `asyncio.CancelledError`.
- Use `ConcurrencyLimiter` and `retry()` if the upstream service needs the same bounds and retry behavior as the existing cloud adapters. Validate response shape before returning a provider result.
- Keep optional SDK dependencies behind an extra in `pyproject.toml`. The core package should import without that SDK installed.

For a concrete network implementation, compare `translation/bhashini_translate.py` with `providers/bhashini.py`. The adapter owns the translation contract; the shared provider module owns transport and configuration. Other capabilities can use the same split.

## Test the contract

Start with an offline test using an injected fake transport. Cover a successful batch, wrong output count, authentication failure, rate limiting or timeout, cancellation, and lifecycle cleanup. Check route order and fallback through a capability client, not only the adapter method. `tests/provider_contract.py` contains declaration, lifecycle, and cancellation checks; `tests/translation_support.py` has a small fake translation provider and router.

Run the same checks as CI before opening a pull request:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
uv run --group docs mkdocs build --strict
```

Document the provider ID, supported languages, model IDs, credentials, optional dependencies, and any provider-specific options. Add it to the capability guide and provider reference. Register it in a convenience factory only when the library should construct it automatically; users can otherwise pass an instance through `additional_providers`.
