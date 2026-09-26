---
name: indic-language-utils
description: Build Python features with indic-language-utils for Indian-language detection, translation, transliteration, speech recognition, or speech synthesis. Use when integrating the library into an application.
---

# Use indic-language-utils

Use the installed package's public `indic_language_utils` API. Check its installed version and signatures when an application pins an older release. The package supports Python 3.11 and 3.12.

## Install and get started

Install the core package with the project's dependency manager:

```bash
uv add indic-language-utils
# or: python -m pip install indic-language-utils
```

The core package includes script detection. It needs no provider or credentials:

```python
from indic_language_utils import detect_script

print(detect_script("नमस्ते भारत"))  # Deva
```

For a first language detection and translation call without cloud credentials, install the FastText and Google Translate extras and select the translation provider:

```bash
uv add "indic-language-utils[local-tld,googletrans]"
# or: python -m pip install "indic-language-utils[local-tld,googletrans]"
export TRANSLATION_SERVICE_PROVIDER=googletrans
```

```python
from indic_language_utils import detect_sync, translate_sync

detection = detect_sync("नमस्ते भारत! आप कैसे हैं?")
print(detection.language, detection.script)  # hi-IN Deva

translation = translate_sync("Welcome to India", "en", "hi")
print(translation.text)
```

Short samples can confuse language detection even when the script is clear. FastText may download its local model on first use. Google Translate is an unofficial network adapter suited to development. For Bhashini or Sarvam, install the core package, set the provider's API key and required service or model IDs in environment variables, then use the same high-level calls. The [configuration guide](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/configuration.md) lists exact variable names and route settings.

## Choose the capability and provider

The core install is `indic-language-utils`. Add only the extra the chosen provider needs:

| Task                    | Entry point                              | Provider choices                                                                                      |
| ----------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Text language detection | `detect_sync`, `detect`, `detect_script` | FastText `[local-tld]`; Bhashini or Sarvam with credentials. `detect_script` needs no provider.       |
| Translation             | `translate_sync`, `translate`            | Bhashini or Sarvam with credentials; Google Translate `[googletrans]` for development.                |
| Transliteration         | `transliterate_sync`, `transliterate`    | Aksharamukha `[local-transliteration]`; Bhashini with credentials.                                    |
| Speech to text          | `get_stt_client`                         | Faster-Whisper `[stt-whisper]`; Google Free `[stt-google-free]`; Bhashini or Sarvam with credentials. |
| Text to speech          | `get_tts_client`                         | Edge TTS `[tts-edge]`; Bhashini or Sarvam with credentials.                                           |

Select a provider whose language, model, and format support fit the request. The [provider reference](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/provider-reference.md) and capability guides contain those limits. Optional local models can require a download on first use; the unofficial Google and Edge adapters require network access.

## Integrate

1. Configure provider routes and IDs in `.indic-language-utils.toml` or `Settings`; put cloud credentials in environment variables. Use the configuration guide for precedence and exact keys.
2. Normalize language input through the library's string arguments or `DEFAULT_LANGUAGE_REGISTRY`. Use canonical result tags such as `hi-IN` rather than assuming the caller's alias is returned unchanged.
3. Use a top-level sync helper for an occasional call. For repeated calls in an async service, keep one `get_*_client()` open with `async with` so it can reuse its transport and cache. STT and TTS use async clients.
4. Use the structured results: translation, transliteration, and STT expose `.text`; TTS exposes `.audio` plus `.audio_format`. Preserve provider and error details where the application needs diagnostics.
5. Verify the feature with a provider-independent test or an injected fake provider. Make a live provider call only when the task calls for it and credentials and network access are available.

For speech, pass audio bytes with the actual `audio_format` and `sampling_rate`; the library does not resample input. Treat generated TTS bytes according to the returned `audio_format`, which varies by provider. Use provider-specific `TTSOptions` only after checking the selected provider's guide.

## Find the relevant detail

- [Getting started](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/getting-started.md) covers installation and first calls.
- [Translation](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/translation.md), [detection](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/detection.md), and [transliteration](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/transliteration.md) cover options, batching, and result models.
- [STT](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/stt.md) and [TTS](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/tts.md) cover formats, models, and streaming.
- [Contributing a provider](https://raw.githubusercontent.com/hari31416/indic-language-utils/main/docs/contributing-providers.md) covers custom adapters and registration.
