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
  text_to_speech: ProviderInfo[]
}

export interface ApiKeysConfig {
  sarvamApiKey: string
  sarvamEndpoint: string
  bhashiniApiKey: string
  bhashiniEndpoint: string
  navanaApiKey: string
  navanaEndpoint: string
}

export interface TTSRequest {
  text: string
  language?: string | null
  model_id?: string | null
  api_key?: string | null
  parameters: Record<string, unknown>
  provider_parameters?: Record<string, Record<string, unknown>>
  provider?: string | null
}

export interface TTSResponse {
  audio_base64: string
  audio_format?: string | null
  language?: string | null
  provider: string
  model_id?: string | null
  request_id: string
  provider_request_id?: string | null
  fallback_count: number
  cached: boolean
  cache_backend: string
}

export interface STTRequest {
  audio_base64: string
  language?: string | null
  model_id?: string | null
  api_key?: string | null
  audio_format: string
  sampling_rate: number
  provider?: string | null
}

export interface STTResponse {
  text: string
  language?: string | null
  provider: string
  model_id?: string | null
  request_id: string
  provider_request_id?: string | null
  fallback_count: number
  cached: boolean
  cache_backend: string
}

export interface STTStreamMessage {
  type: 'ready' | 'event' | 'done' | 'error'
  kind?: 'speech_start' | 'speech_end' | 'partial' | 'final'
  text?: string | null
  language?: string | null
  provider?: string
  model_id?: string
  request_id?: string
  message?: string
}

export interface TTSStreamMessage {
  type: 'ready' | 'event' | 'done' | 'error'
  kind?: 'audio' | 'done'
  audio_base64?: string | null
  audio_format?: string
  language?: string
  provider?: string
  model_id?: string
  request_id?: string
  message?: string
}

export interface TranslateRequest {
  text: string
  source: string
  target: string
  model_id?: string | null
  api_key?: string | null
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
  model_id?: string | null
  api_key?: string | null
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
  model_id?: string | null
  api_key?: string | null
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
