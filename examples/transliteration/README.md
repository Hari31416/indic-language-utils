# Transliteration Examples

This directory provides runnable examples of script transliteration using `indic-language-utils` across local and cloud providers.

## Available Examples

- [aksharamukha_demo.py](aksharamukha_demo.py) - Lightweight, pure-Python script-to-script and Romanization conversion using Aksharamukha.
- [bhashini_demo.py](bhashini_demo.py) - Cloud-based transliteration using the Government of India Bhashini ecosystem.
- [indicxlit_demo.py](indicxlit_demo.py) - Offline AI4Bharat IndicXlit example for an existing, separately managed installation. The beta omits its install extra because upstream dependencies have known vulnerabilities.
- [multi_service_demo.py](multi_service_demo.py) - Resilient multi-provider routing with automatic failover, single-flight deduplication, and caching.

## Prerequisites

For offline Aksharamukha transliteration, install the `local-transliteration` extra:

```bash
uv sync --extra local-transliteration
```

For live Bhashini inference, ensure your credentials are set in `.env` or your shell:

```bash
export BHASHINI_API_KEY="your-bhashini-api-key"
export BHASHINI_TRANSLITERATION_SERVICE_ID="your-bhashini-translit-service-id"
```

## Running the Examples

Run the Aksharamukha pure-Python transliteration demo:

```bash
uv run python examples/transliteration/aksharamukha_demo.py
```

Run the Bhashini cloud transliteration demo (uses mock fallback if credentials are unset):

```bash
uv run --env-file .env python examples/transliteration/bhashini_demo.py
```

If you already manage an IndicXlit installation separately, run its local demo:

```bash
uv run python examples/transliteration/indicxlit_demo.py
```

Run the multi-service resilient routing and caching demo:

```bash
uv run python examples/transliteration/multi_service_demo.py
```

## Quick Transliteration One-Liner

```python
from indic_language_utils import transliterate_sync

result = transliterate_sync("namaste", source="en", target="hi")
print(result.text)  # नमस्ते
```
