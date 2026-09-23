import type {
  DetectRequest,
  DetectResponse,
  LanguagesResponse,
  ProvidersResponse,
  ScriptDetectResponse,
  TranslateRequest,
  TranslateResponse,
  TransliterateRequest,
  TransliterateResponse,
} from './types'

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
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

export async function fetchLanguages(): Promise<LanguagesResponse> {
  return requestJson<LanguagesResponse>('/api/languages')
}

export async function fetchProviders(): Promise<ProvidersResponse> {
  return requestJson<ProvidersResponse>('/api/providers')
}

export async function translateText(req: TranslateRequest): Promise<TranslateResponse> {
  return requestJson<TranslateResponse>('/api/translate', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function detectLanguage(req: DetectRequest): Promise<DetectResponse> {
  return requestJson<DetectResponse>('/api/detect', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function detectScript(text: string): Promise<ScriptDetectResponse> {
  return requestJson<ScriptDetectResponse>('/api/detect-script', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}

export async function transliterateText(
  req: TransliterateRequest
): Promise<TransliterateResponse> {
  return requestJson<TransliterateResponse>('/api/transliterate', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}
