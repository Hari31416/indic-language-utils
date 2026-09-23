export interface LanguageItem {
  tag: string
  code: string
  name: string
  script?: string | null
  region?: string | null
}

export interface LanguagesResponse {
  languages: LanguageItem[]
}

export interface ProviderInfo {
  id: string
  name: string
  available: boolean
  details: string
}

export interface ProvidersResponse {
  translation: ProviderInfo[]
  detection: ProviderInfo[]
  transliteration: ProviderInfo[]
  speech_to_text: ProviderInfo[]
}

export interface STTRequest {
  audio_base64: string
  language: string
  audio_format: string
  sampling_rate: number
  provider?: string | null
}

export interface STTResponse {
  text: string
  language: string
  provider: string
  model_id?: string | null
  request_id: string
  provider_request_id?: string | null
  fallback_count: number
  cached: boolean
  cache_backend: string
}

export interface TranslateRequest {
  text: string
  source: string
  target: string
  provider?: string | null
  text_format?: 'plain' | 'markdown'
}

export interface TranslateResponse {
  text: string
  source: string
  target: string
  provider: string
  service_id?: string | null
  model_id?: string | null
  unofficial: boolean
  elapsed_seconds: number
  cached: boolean
  cache_backend?: string | null
  warnings: string[]
}

export interface DetectRequest {
  text: string
  provider?: string | null
}

export interface DetectCandidate {
  language: string
  name?: string | null
  confidence: number
  script?: string | null
}

export interface DetectResponse {
  language?: string | null
  language_name?: string | null
  script?: string | null
  candidates: DetectCandidate[]
  provider: string
  model_id?: string | null
  unofficial: boolean
  elapsed_seconds: number
  cached: boolean
}

export interface ScriptDetectResponse {
  script?: string | null
}

export interface TransliterateRequest {
  text: string
  source: string
  target: string
  provider?: string | null
}

export interface TransliterateResponse {
  text: string
  source: string
  target: string
  provider: string
  service_id?: string | null
  model_id?: string | null
  unofficial: boolean
  elapsed_seconds: number
  cached: boolean
  cache_backend?: string | null
  warnings: string[]
}
