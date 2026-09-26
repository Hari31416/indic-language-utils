import type { ApiKeysConfig } from './types'

const STORAGE_KEY = 'indic_language_utils_api_keys'

export const DEFAULT_API_KEYS: ApiKeysConfig = {
  sarvamApiKey: '',
  sarvamEndpoint: '',
  bhashiniApiKey: '',
  bhashiniEndpoint: '',
  navanaApiKey: '',
  navanaEndpoint: '',
}

export function loadApiKeys(): ApiKeysConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_API_KEYS }
    const parsed = JSON.parse(raw) as Partial<ApiKeysConfig>
    return {
      sarvamApiKey: typeof parsed.sarvamApiKey === 'string' ? parsed.sarvamApiKey : '',
      sarvamEndpoint: typeof parsed.sarvamEndpoint === 'string' ? parsed.sarvamEndpoint : '',
      bhashiniApiKey: typeof parsed.bhashiniApiKey === 'string' ? parsed.bhashiniApiKey : '',
      bhashiniEndpoint: typeof parsed.bhashiniEndpoint === 'string' ? parsed.bhashiniEndpoint : '',
      navanaApiKey: typeof parsed.navanaApiKey === 'string' ? parsed.navanaApiKey : '',
      navanaEndpoint: typeof parsed.navanaEndpoint === 'string' ? parsed.navanaEndpoint : '',
    }
  } catch {
    return { ...DEFAULT_API_KEYS }
  }
}

export function saveApiKeys(keys: ApiKeysConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(keys))
  } catch {
    // Ignore storage write errors
  }
}

export function clearApiKeys(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Ignore storage remove errors
  }
}

export function getApiKeyHeaders(keys?: ApiKeysConfig): Record<string, string> {
  const current = keys ?? loadApiKeys()
  const headers: Record<string, string> = {}

  if (current.sarvamApiKey.trim()) {
    headers['X-Sarvam-Api-Key'] = current.sarvamApiKey.trim()
  }
  if (current.sarvamEndpoint.trim()) {
    headers['X-Sarvam-Endpoint'] = current.sarvamEndpoint.trim()
  }
  if (current.bhashiniApiKey.trim()) {
    headers['X-Bhashini-Api-Key'] = current.bhashiniApiKey.trim()
  }
  if (current.bhashiniEndpoint.trim()) {
    headers['X-Bhashini-Endpoint'] = current.bhashiniEndpoint.trim()
  }
  if (current.navanaApiKey.trim()) {
    headers['X-Navana-Api-Key'] = current.navanaApiKey.trim()
  }
  if (current.navanaEndpoint.trim()) {
    headers['X-Navana-Endpoint'] = current.navanaEndpoint.trim()
  }

  return headers
}
