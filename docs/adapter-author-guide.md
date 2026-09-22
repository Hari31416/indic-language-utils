# Adapter author guide

An adapter is an object with a `ProviderIdentity` and a tuple of `CapabilityDeclaration` values. It implements only its concrete capability protocol. There is no shared provider base class.

Register an adapter explicitly with `ProviderRegistry.register`. Declare canonical `LanguageTag` values, supported pairs, required features, and named limits. Do not place provider-specific language codes in public models. Convert them inside the adapter.

Adapters that own reusable clients implement `start()` and `close()`. `ResourceManager` starts resources in order, closes them in reverse order, and supports `async with`.

Map provider failures to the matching exception in `indic_language_utils.errors`. Exception messages and structured fields must not contain request content, credentials, headers, or raw provider responses. Mark only rate limits, timeouts, and temporary provider failures as retryable.

This illustrative provider declares a fake operation. It is not a supported language capability:

```python
from dataclasses import dataclass

from indic_language_utils.models import ProviderIdentity
from indic_language_utils.providers import CapabilityDeclaration, CapabilityId, ProviderRegistry


@dataclass
class ExampleProvider:
    identity = ProviderIdentity("example")
    capabilities = (CapabilityDeclaration(CapabilityId.TRANSLATION),)

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass


registry = ProviderRegistry()
registry.register(ExampleProvider())
```

Real translation models and provider methods arrive in Phase 1.
