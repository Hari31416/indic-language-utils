# Models and Voice Reference

This reference catalogs the available models, service IDs, voice identifiers, and provider parameters across all supported cloud and local engines in `indic-language-utils`.

## Sarvam AI

Sarvam AI provides high-performance generative models for Indian languages via API. Set `SARVAM_API_KEY` to enable.

### Translation Models

| Model ID              | Capability  | Description                                          | Supported Languages                                              |
| --------------------- | ----------- | ---------------------------------------------------- | ---------------------------------------------------------------- |
| `sarvam-translate:v1` | Translation | Standard multi-way Indic translation model (Default) | `en`, `hi`, `ta`, `te`, `bn`, `mr`, `gu`, `kn`, `ml`, `or`, `pa` |
| `mayura:v1`           | Translation | High-accuracy Indic translation model                | `en`, `hi`, `ta`, `te`, `bn`, `mr`, `gu`, `kn`, `ml`, `or`, `pa` |

Environment variable override: `SARVAM_MODEL`

### Speech to Text Models

| Model ID        | Capability     | Description                         | Limits / Notes                  |
| --------------- | -------------- | ----------------------------------- | ------------------------------- |
| `saarika:v1`    | Speech to Text | Standard Indic ASR model (Default)  | Synchronous REST, max 30s clips |
| `saarika:v2`    | Speech to Text | Enhanced vocabulary and punctuation | Synchronous REST, max 30s clips |
| `saarika:flash` | Speech to Text | Ultra low-latency transcription     | Synchronous REST, fast response |

Environment variable override: `SARVAM_STT_MODEL_ID`

### Text to Speech Models and Voices

| Model ID          | Generation / Status           | Supported Parameters                   | Notes                                                     |
| ----------------- | ----------------------------- | -------------------------------------- | --------------------------------------------------------- |
| `bulbul:v3`       | Flagship 2026 (Default)       | `speaker`, `pace`, `temperature`       | Ultra-natural prosody, 35+ speakers, 11 languages         |
| `bulbul:v4-flash` | Low-Latency / Conversational  | `speaker`, `pace`                      | Sub-150ms TTFT, intent-specialized conversational voices  |
| `bulbul:v3-beta`  | Experimental Preview          | `speaker`, `pace`, `temperature`       | Early release of Bulbul v3 improvements                   |
| `bulbul:v2`       | Stable Legacy                 | `speaker`, `pace`, `pitch`, `loudness` | Previous generation TTS model                             |

Available Speaker Voices for `bulbul:v3`:

- `aditya`, `ritu`, `ashutosh`, `priya`, `neha`, `rahul`, `pooja`, `rohan`, `simran`, `kavya`, `amit`, `dev`, `ishita`, `shreya`, `ratan`, `varun`, `manan`, `sumit`, `roopa`, `kabir`, `aayan`, `shubh`, `advait`, `anand`, `tanya`, `tarun`, `sunny`, `mani`, `gokul`, `vijay`, `shruti`, `suhani`, `mohit`, `kavitha`, `rehan`, `soham`, `rupali`

Legacy Voices for `bulbul:v2`:

- `shubh`, `arvind`, `amartya`, `priya`, `meera`, `pavithra`

Domain-Specialized Voices for `bulbul:v4-flash`:

- Conversational / Assistant: `aayan_hi_conversational`, `amit_hi_conversational`, `kavya_hi_conversational`, `simran_hi_conversation`, `sanchita_hi_assistant`, `dev_en_conversational`, `simran_en_conversation`
- Hinglish Bilingual: `ishita_enhi_companion`, `shubh_enhi_companion`, `shubh_enhi_banking`, `simran_enhi_customer`
- Customer Support / Banking: `shubh_hi_customer`, `sanchita_hi_banking`, `ishita_hi_banking`, `aditya_hi_sales`, `jaspal_pa_banking`
- Regional Narrators: `bappa_bn_conversation` (Bengali), `pooja_gu_conversational` (Gujarati), `chaitra_kn_conversation` (Kannada), `mrunal_mr_narration` (Marathi), `anand_pa_conversation` (Punjabi), `gokul_ta_narration` (Tamil), `kavitha_te_conversation` (Telugu)

Environment variable override: `SARVAM_TTS_MODEL_ID`

## Bhashini National Language Translation Mission

Bhashini (backed by AI4Bharat, Bodhan.AI, and the Government of India) uses pipeline `serviceId` values to route tasks. Set `BHASHINI_API_KEY` to enable.

### Translation Service IDs

| Service ID                                   | Capability  | Description                                                                                   |
| -------------------------------------------- | ----------- | --------------------------------------------------------------------------------------------- |
| `ai4bharat/indictrans-v2-all-gpu--t4`        | Translation | IndicTrans2 universal model supporting all 22 Eighth Schedule languages and English (Default) |
| `ai4bharat/indictrans-v2-indo_aryan-gpu--t4` | Translation | IndicTrans2 specialized Indo-Aryan language branch                                            |
| `ai4bharat/indictrans-v2-dravidian-gpu--t4`  | Translation | IndicTrans2 specialized Dravidian language branch                                             |

Environment variable override: `BHASHINI_TRANSLATION_SERVICE_ID`

### Speech to Text Service IDs

| Service ID                             | Provider / Architecture | Language         | Description                                                            |
| -------------------------------------- | ----------------------- | ---------------- | ---------------------------------------------------------------------- |
| `ai4bharat/conformer-hi-gpu--t4`       | AI4Bharat Conformer     | Hindi (`hi`)     | AI4Bharat Hindi Conformer ASR (Default for Hindi)                      |
| `bhashini/bodhan/asr-transcribe-flex`  | Bodhan.AI               | Multilingual     | Flexible ASR model covering 22+ languages and regional Indian dialects |
| `bhashini/bodhan/asr-transcribe-core`  | Bodhan.AI               | Multilingual     | Core high-accuracy multilingual ASR transcription pipeline             |
| `ai4bharat/conformer-ta-gpu--t4`       | AI4Bharat Conformer     | Tamil (`ta`)     | AI4Bharat Tamil Conformer ASR                                          |
| `ai4bharat/conformer-te-gpu--t4`       | AI4Bharat Conformer     | Telugu (`te`)    | AI4Bharat Telugu Conformer ASR                                         |
| `ai4bharat/conformer-bn-gpu--t4`       | AI4Bharat Conformer     | Bengali (`bn`)   | AI4Bharat Bengali Conformer ASR                                        |
| `ai4bharat/conformer-mr-gpu--t4`       | AI4Bharat Conformer     | Marathi (`mr`)   | AI4Bharat Marathi Conformer ASR                                        |
| `ai4bharat/conformer-gu-gpu--t4`       | AI4Bharat Conformer     | Gujarati (`gu`)  | AI4Bharat Gujarati Conformer ASR                                       |
| `ai4bharat/conformer-kn-gpu--t4`       | AI4Bharat Conformer     | Kannada (`kn`)   | AI4Bharat Kannada Conformer ASR                                        |
| `ai4bharat/conformer-ml-gpu--t4`       | AI4Bharat Conformer     | Malayalam (`ml`) | AI4Bharat Malayalam Conformer ASR                                      |
| `ai4bharat/conformer-pa-gpu--t4`       | AI4Bharat Conformer     | Punjabi (`pa`)   | AI4Bharat Punjabi Conformer ASR                                        |
| `ai4bharat/conformer-or-gpu--t4`       | AI4Bharat Conformer     | Odia (`or`)      | AI4Bharat Odia Conformer ASR                                           |
| `ai4bharat/whisper-medium-en--gpu--t4` | AI4Bharat IndicWhisper  | English (`en`)   | AI4Bharat IndicWhisper English medium model                            |
| `ai4bharat/whisper-all-gpu--t4`        | AI4Bharat IndicWhisper  | Multilingual     | AI4Bharat IndicWhisper multilingual model                              |

Environment variable override: `BHASHINI_STT_MODEL_ID`

### Text to Speech Service IDs

| Service ID                                     | Provider / Architecture | Description                                  | Supported Parameters                |
| ---------------------------------------------- | ----------------------- | -------------------------------------------- | ----------------------------------- |
| `ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4` | AI4Bharat Indic-TTS     | Indic-TTS for Indo-Aryan languages (Default) | `gender`, `voiceId`, `samplingRate` |
| `ai4bharat/indic-tts-coqui-dravidian-gpu--t4`  | AI4Bharat Indic-TTS     | Indic-TTS for Dravidian languages            | `gender`, `voiceId`, `samplingRate` |
| `ai4bharat/indic-tts-coqui-misc-gpu--t4`       | AI4Bharat Indic-TTS     | Indic-TTS for other scheduled languages      | `gender`, `voiceId`, `samplingRate` |

Environment variable override: `BHASHINI_TTS_MODEL_ID`

### Transliteration and Detection Service IDs

| Service ID                     | Capability         | Description                                                        |
| ------------------------------ | ------------------ | ------------------------------------------------------------------ |
| `ai4bharat/indicxlit--gpu--t4` | Transliteration    | AI4Bharat IndicXlit neural transliteration across 22 Indic scripts |
| `ai4bharat/tld--gpu--t4`       | Language Detection | Text Language Detection across 22 Indic languages                  |

Environment variable overrides: `BHASHINI_TRANSLITERATION_SERVICE_ID`, `BHASHINI_DETECTION_SERVICE_ID`

## Microsoft Edge TTS

Microsoft Edge TTS provides high-quality neural voice synthesis for Indian languages without requiring an API key. Install via `pip install 'indic-language-utils[tts-edge]'`.

### Neural Voice Identifiers

| Language        | Language Code  | Female Voice                  | Male Voice             |
| --------------- | -------------- | ----------------------------- | ---------------------- |
| Hindi           | `hi-IN` / `hi` | `hi-IN-SwaraNeural` (Default) | `hi-IN-MadhurNeural`   |
| English (India) | `en-IN` / `en` | `en-IN-NeerjaNeural`          | `en-IN-PrabhatNeural`  |
| Tamil           | `ta-IN` / `ta` | `ta-IN-PallaviNeural`         | `ta-IN-ValluvarNeural` |
| Telugu          | `te-IN` / `te` | `te-IN-ShrutiNeural`          | `te-IN-MohanNeural`    |
| Bengali         | `bn-IN` / `bn` | `bn-IN-TanishaaNeural`        | `bn-IN-BashkarNeural`  |
| Marathi         | `mr-IN` / `mr` | `mr-IN-AarohiNeural`          | `mr-IN-ManoharNeural`  |
| Gujarati        | `gu-IN` / `gu` | `gu-IN-DhwaniNeural`          | `gu-IN-NiranjanNeural` |
| Kannada         | `kn-IN` / `kn` | `kn-IN-SapnaNeural`           | `kn-IN-GaganNeural`    |
| Malayalam       | `ml-IN` / `ml` | `ml-IN-SobhanaNeural`         | `ml-IN-MidhunNeural`   |
| Urdu (India)    | `ur-IN` / `ur` | `ur-IN-GulNeural`             | `ur-IN-SalmanNeural`   |
| Nepali          | `ne-NP` / `ne` | `ne-NP-HemkalaNeural`         | `ne-NP-SagarNeural`    |

Supported Parameters:

- `voice`: Explicit voice identifier string (e.g. `hi-IN-MadhurNeural`).
- `gender`: `"female"` or `"male"` (automatically selects the default voice for the language).
- `rate`: Speed modifier string (e.g. `"+10%"`, `"-15%"`).
- `pitch`: Pitch modifier string (e.g. `"+2Hz"`, `"-2Hz"`).
- `volume`: Volume modifier string (e.g. `"+0%"`, `"-10%"`).

Environment variable override: `EDGE_TTS_VOICE`

## Local and Offline Models

### Faster-Whisper ASR

Faster-Whisper runs offline speech recognition locally on CPU or GPU. Install via `pip install 'indic-language-utils[stt-whisper]'`.

| Model Size             | Parameters | VRAM (Approx) | Relative Speed   |
| ---------------------- | ---------- | ------------- | ---------------- |
| `tiny` / `tiny.en`     | 39 M       | ~1 GB         | Fastest          |
| `base` / `base.en`     | 74 M       | ~1 GB         | Fast (Default)   |
| `small` / `small.en`   | 244 M      | ~2 GB         | Balanced         |
| `medium` / `medium.en` | 769 M      | ~5 GB         | High Accuracy    |
| `large-v3`             | 1550 M     | ~10 GB        | Best Accuracy    |
| `large-v3-turbo`       | 809 M      | ~6 GB         | Fast Large Model |

Environment variable overrides: `FASTER_WHISPER_MODEL`, `WHISPER_MODEL`

### Aksharamukha Transliteration

Pure Python deterministic script converter supporting 120+ scripts and Romanization standards:

- Indic Scripts: Devanagari, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Gurmukhi, Odia, Assamese, etc.
- Romanization Formats: IAST, ISO 15919, Harvard-Kyoto, Velthuis, SLP1, ITRANS, Titus, Roman (Colloquial).

Install via `pip install 'indic-language-utils[local-transliteration]'`.

### FastText Language Detection

Offline compact neural text language detection model:

- Model ID: `lid.176.ftz` (1 MB compressed) or `lid.176.bin` (126 MB full).
- Identifies 176 languages and returns ranked probabilities.

Install via `pip install 'indic-language-utils[local-tld]'`.
