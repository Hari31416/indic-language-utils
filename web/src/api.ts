import { getApiKeyHeaders } from './storage'
import type {
  ApiKeysConfig,
  DetectRequest,
  DetectResponse,
  LanguagesResponse,
  ProvidersResponse,
  ScriptDetectResponse,
  STTRequest,
  STTResponse,
  TTSRequest,
  TTSResponse,
  TranslateRequest,
  TranslateResponse,
  TransliterateRequest,
  TransliterateResponse,
} from './types'

async function requestJson<T>(url: string, init?: RequestInit, customKeys?: ApiKeysConfig): Promise<T> {
  const authHeaders = getApiKeyHeaders(customKeys)
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...init?.headers,
    },
    ...init,
  })

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status} ${response.statusText}`
    try {
      const data = (await response.json()) as { detail?: string }
      if (data.detail) {
        errorMessage = data.detail
      }
    } catch {
      // Keep default HTTP status message
    }
    throw new Error(errorMessage)
  }

  return (await response.json()) as T
}

export async function fetchLanguages(customKeys?: ApiKeysConfig): Promise<LanguagesResponse> {
  return requestJson<LanguagesResponse>('/api/languages', undefined, customKeys)
}

export async function fetchProviders(customKeys?: ApiKeysConfig): Promise<ProvidersResponse> {
  return requestJson<ProvidersResponse>('/api/providers', undefined, customKeys)
}

export async function translateText(
  req: TranslateRequest,
  customKeys?: ApiKeysConfig
): Promise<TranslateResponse> {
  return requestJson<TranslateResponse>(
    '/api/translate',
    {
      method: 'POST',
      body: JSON.stringify(req),
    },
    customKeys
  )
}

export async function detectLanguage(
  req: DetectRequest,
  customKeys?: ApiKeysConfig
): Promise<DetectResponse> {
  return requestJson<DetectResponse>(
    '/api/detect',
    {
      method: 'POST',
      body: JSON.stringify(req),
    },
    customKeys
  )
}

export async function detectScript(
  text: string,
  customKeys?: ApiKeysConfig
): Promise<ScriptDetectResponse> {
  return requestJson<ScriptDetectResponse>(
    '/api/detect-script',
    {
      method: 'POST',
      body: JSON.stringify({ text }),
    },
    customKeys
  )
}

export async function transliterateText(
  req: TransliterateRequest,
  customKeys?: ApiKeysConfig
): Promise<TransliterateResponse> {
  return requestJson<TransliterateResponse>(
    '/api/transliterate',
    {
      method: 'POST',
      body: JSON.stringify(req),
    },
    customKeys
  )
}

export async function transcribeAudio(
  req: STTRequest,
  customKeys?: ApiKeysConfig
): Promise<STTResponse> {
  return requestJson<STTResponse>(
    '/api/stt',
    {
      method: 'POST',
      body: JSON.stringify(req),
    },
    customKeys
  )
}

export async function synthesizeSpeech(
  req: TTSRequest,
  customKeys?: ApiKeysConfig
): Promise<TTSResponse> {
  return requestJson<TTSResponse>(
    '/api/tts',
    {
      method: 'POST',
      body: JSON.stringify(req),
    },
    customKeys
  )
}
