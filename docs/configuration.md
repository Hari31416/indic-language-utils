# Configuration

The library uses a tiered configuration system combining TOML project files, user configurations, environment variables, and programmatic overrides. Settings are validated strictly on load; unknown keys or invalid data types raise a `ConfigurationError`.

## Configuration Precedence

`Settings.load()` evaluates configuration sources in the following order, from lowest to highest precedence:

- Library defaults
- User configuration at `~/.config/indic-language-utils/config.toml` (or `$XDG_CONFIG_HOME/indic-language-utils/config.toml`)
- The nearest `.indic-language-utils.toml` found by walking upward from the current working directory
- An explicit configuration file specified via `Settings.load(path=...)` or the `ILU_CONFIG_FILE` environment variable
- Environment variables (`ILU_*`, `BHASHINI_*`, and `TRANSLATION_SERVICE_PROVIDER`)
- Programmatic overrides passed via `Settings.load(overrides=...)`

Only existing discovered files are merged. If an explicit configuration path is provided, that file must exist.

## Project Configuration File

A project configuration file (`.indic-language-utils.toml`) can be placed at the root of a project repository. The following example illustrates all supported configuration sections:

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
endpoint = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
translation_service_id = "default-translation-model-id"
detection_service_id = "default-tld-model-id"
timeout_seconds = 20.0
max_concurrency = 8

[providers.bhashini.translation_service_ids]
"hi-IN" = "service-for-any-source-to-hindi"
"en-IN>ta-IN" = "service-for-english-to-tamil"

[providers.googletrans]
timeout_seconds = 20.0
max_concurrency = 4

[routes]
translation = ["bhashini", "googletrans"]
text_language_detection = ["bhashini", "fasttext"]
```

Relative cache paths resolve relative to the current working directory of the process. In production containers or multi-directory environments, specify an absolute path.

## Secrets and Environment Variables

TOML files are strictly prohibited from storing credentials, passwords, tokens, or API keys. Attempting to define fields containing sensitive terms (such as `api_key`, `token`, `secret`, or `password`) raises a `ConfigurationError`.

All sensitive values must be supplied via environment variables.

### Provider Credentials and Overrides

Bhashini credentials and service endpoints:

```bash
# Required for Bhashini live API calls
export BHASHINI_API_KEY="your-bhashini-api-key"

# Optional overrides for endpoints and service IDs
export BHASHINI_ENDPOINT_URL="https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
export BHASHINI_TRANSLATION_SERVICE_ID="your-translation-service-id"
export BHASHINI_DETECTION_SERVICE_ID="your-tld-service-id"
export BHASHINI_TIMEOUT_SECONDS="20"
export BHASHINI_MAX_CONCURRENCY="8"
```

To quickly select an active translation provider during development without editing configuration files:

```bash
export TRANSLATION_SERVICE_PROVIDER="googletrans"
```

### Shared System Settings

Global cache, retry, telemetry, and routing settings use the `ILU_` prefix:

```bash
# Caching settings
export ILU_CACHE_ENABLED="true"
export ILU_CACHE_BACKEND="sqlite"
export ILU_CACHE_PATH="/var/lib/indic-language-utils/cache.sqlite3"
export ILU_CACHE_NAMESPACE="my-app"
export ILU_CACHE_MAX_ENTRIES="50000"
export ILU_CACHE_TTL_SECONDS="86400"

# Retry settings
export ILU_RETRY_MAX_ATTEMPTS="3"
export ILU_RETRY_BASE_DELAY_SECONDS="0.25"
export ILU_RETRY_MAX_DELAY_SECONDS="5.0"

# Telemetry settings
export ILU_LOGGING_ENABLED="true"
export ILU_METRICS_ENABLED="true"
export ILU_TRACES_ENABLED="true"
export ILU_TELEMETRY_INCLUDE_CONTENT="false"

# Route overrides (comma-separated provider names in priority order)
export ILU_ROUTE_TRANSLATION="bhashini,googletrans"
export ILU_ROUTE_TEXT_LANGUAGE_DETECTION="bhashini,fasttext"
```

## Programmatic Loading and Overrides

### Automatic Discovery

The easiest way to initialize a client is via the built-in factories, which call `Settings.load()` automatically:

```python
from indic_language_utils import get_translation_client

# Automatically reads .indic-language-utils.toml and environment variables
client = get_translation_client()
```

### Explicit Settings Loading

For granular control over settings loading:

```python
from pathlib import Path
from indic_language_utils import Settings

# Load settings from a specific TOML file
settings = Settings.load(path=Path("/etc/indic-language-utils/production.toml"))

# Load settings with test overrides
test_settings = Settings.load(
    overrides={
        "cache": {"enabled": False},
        "retry": {"max_attempts": 1},
    }
)
```

### Building Custom Clients from Settings

Assemble a client pipeline explicitly using loaded settings:

```python
from indic_language_utils import (
    BhashiniConfig,
    BhashiniTranslationProvider,
    CacheKeyBuilder,
    CapabilityId,
    GoogleTranslateProvider,
    OrderedRouter,
    ProviderRegistry,
    Settings,
    TranslationClient,
    create_translation_cache,
)

settings = Settings.load()

registry = ProviderRegistry()
if "bhashini" in settings.providers:
    registry.register(BhashiniTranslationProvider(BhashiniConfig.from_settings(settings)))
registry.register(GoogleTranslateProvider())

route = settings.routes.get("translation", ("bhashini", "googletrans"))
router = OrderedRouter(registry, {CapabilityId.TRANSLATION: route})

client = TranslationClient(
    router=router,
    cache=create_translation_cache(settings.cache),
    cache_keys=CacheKeyBuilder(settings.cache.namespace),
)
```
