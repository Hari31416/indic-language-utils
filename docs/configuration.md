# Configuration

`Settings.load()` combines TOML configuration, environment variables, and explicit overrides. It uses this precedence, from lowest to highest:

1. Library defaults
2. `~/.config/indic-language-utils/config.toml`, or `$XDG_CONFIG_HOME/indic-language-utils/config.toml`
3. The nearest `.indic-language-utils.toml` found by walking upward from the working directory
4. A file passed to `Settings.load(path=...)`, or selected with `ILU_CONFIG_FILE`
5. Environment variables
6. The `overrides` mapping passed to `Settings.load()`

Only existing discovered files participate. An explicitly selected file must exist. Malformed TOML, unknown fields, invalid types, and invalid values raise `ConfigurationError`.

## Project configuration

This example can be stored as `.indic-language-utils.toml` at the project root:

```toml
[cache]
enabled = true
backend = "sqlite"
path = ".cache/translations.sqlite3"
namespace = "my-application"
max_entries = 50000
ttl_seconds = 86400

[retry]
max_attempts = 3
base_delay_seconds = 0.25
max_delay_seconds = 5.0

[telemetry]
logging_enabled = true
metrics_enabled = true
traces_enabled = true
include_content = false

[providers.bhashini]
endpoint = "https://your-bhashini-inference-endpoint"
translation_service_id = "your-default-translation-service-id"
timeout_seconds = 20
max_concurrency = 8

[providers.bhashini.translation_service_ids]
"hi-IN" = "service-for-any-target-to-hindi"
"en-IN>ta-IN" = "service-for-english-to-tamil"

[routes]
translation = ["bhashini"]
```

Relative cache paths resolve from the process working directory. Use an absolute path when the application may start from different directories.

## Secrets and environment overrides

TOML files cannot contain fields whose names indicate credentials, API keys, passwords, secrets, authorization values, or tokens. Keep Bhashini's API key in the environment:

```console
export BHASHINI_API_KEY="..."
```

`translation_service_id` is the default. Entries in `translation_service_ids` override it. An exact `source>target` entry wins first, followed by a target-language entry and then the default. Selectors accept registry aliases and normalize to canonical tags.

The Bhashini endpoint and default translation service ID may also come from the environment. Environment values override TOML:

```console
export BHASHINI_ENDPOINT_URL="https://your-bhashini-inference-endpoint"
export BHASHINI_TRANSLATION_SERVICE_ID="your-translation-service-id"
export BHASHINI_TIMEOUT_SECONDS="20"
export BHASHINI_MAX_CONCURRENCY="8"
```

Shared settings use the `ILU_` prefix:

```console
export ILU_CACHE_ENABLED="true"
export ILU_CACHE_BACKEND="sqlite"
export ILU_CACHE_PATH="/var/lib/indic-language-utils/translations.sqlite3"
export ILU_CACHE_NAMESPACE="my-application"
export ILU_CACHE_MAX_ENTRIES="50000"
export ILU_CACHE_TTL_SECONDS="86400"
export ILU_RETRY_MAX_ATTEMPTS="3"
export ILU_ROUTE_TRANSLATION="bhashini"
```

## Loading a client

```python
from indic_language_utils import (
    BhashiniConfig,
    BhashiniTranslationProvider,
    CacheKeyBuilder,
    CapabilityId,
    ProviderRegistry,
    Settings,
    TranslationClient,
    create_translation_cache,
)
from indic_language_utils.routing import OrderedRouter

settings = Settings.load()
bhashini = BhashiniTranslationProvider(BhashiniConfig.from_settings(settings))

registry = ProviderRegistry()
registry.register(bhashini)

configured_route = settings.routes.get("translation", ("bhashini",))
router = OrderedRouter(registry, {CapabilityId.TRANSLATION: configured_route})

client = TranslationClient(
    router,
    cache=create_translation_cache(settings.cache),
    cache_keys=CacheKeyBuilder(settings.cache.namespace),
)
```

Tests and embedding applications can apply final overrides without changing process environment:

```python
settings = Settings.load(
    overrides={
        "cache": {"enabled": False},
        "retry": {"max_attempts": 1},
    }
)
```
