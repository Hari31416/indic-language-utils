import React, { useEffect, useState } from 'react'
import {
  BookOpen,
  FileSearch,
  KeyRound,
  Keyboard,
  Languages,
  Layers,
  Loader2,
  Mic,
  RefreshCw,
  Terminal,
  Volume2,
} from 'lucide-react'
import { fetchLanguages, fetchProviders } from './api'
import { ApiKeysModal } from './components/ApiKeysModal'
import { DetectView } from './components/DetectView'
import { ProvidersView } from './components/ProvidersView'
import { STTView } from './components/STTView'
import { TTSView } from './components/TTSView'
import { TranslateView } from './components/TranslateView'
import { TransliterateView } from './components/TransliterateView'
import { loadApiKeys } from './storage'
import type { ApiKeysConfig, LanguageItem, ProvidersResponse } from './types'

type ActiveTab = 'translate' | 'transliterate' | 'detect' | 'stt' | 'tts' | 'providers'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('translate')
  const [languages, setLanguages] = useState<LanguageItem[]>([])
  const [providersData, setProvidersData] = useState<ProvidersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isKeysModalOpen, setIsKeysModalOpen] = useState(false)
  const [apiKeys, setApiKeys] = useState<ApiKeysConfig>(loadApiKeys())

  const loadData = async (keysToUse?: ApiKeysConfig) => {
    setLoading(true)
    setError(null)
    const effectiveKeys = keysToUse ?? apiKeys
    try {
      const [langRes, provRes] = await Promise.all([
        fetchLanguages(effectiveKeys),
        fetchProviders(effectiveKeys),
      ])
      setLanguages(langRes.languages)
      setProvidersData(provRes)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to connect to backend server'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  const handleKeysSaved = (updatedKeys: ApiKeysConfig) => {
    setApiKeys(updatedKeys)
    void loadData(updatedKeys)
  }

  const configuredKeyCount =
    (apiKeys.sarvamApiKey.trim() ? 1 : 0) + (apiKeys.bhashiniApiKey.trim() ? 1 : 0)

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-indigo-500/30 selection:text-indigo-200 font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/75 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-500/20">
              <Languages className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-100 tracking-tight text-base sm:text-lg">
                  indic-language-utils
                </span>
                <span className="text-[11px] px-1.5 py-0.5 rounded font-mono bg-slate-800 text-indigo-300 border border-indigo-500/20">
                  v0.5.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                Unified Indian Language AI &amp; NLP Workbench
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* API Keys Configuration Button */}
            <button
              type="button"
              onClick={() => setIsKeysModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-200 bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 transition shadow-sm"
            >
              <KeyRound className="w-3.5 h-3.5 text-indigo-400" />
              <span>API Keys</span>
              {configuredKeyCount > 0 ? (
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block ml-0.5 animate-pulse" />
              ) : (
                <span className="text-[10px] px-1 py-0.2 rounded bg-slate-800 text-slate-400">
                  Config
                </span>
              )}
            </button>

            <a
              href="/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium text-slate-300 bg-slate-900/90 hover:bg-slate-800 hover:text-white border border-slate-800 transition"
            >
              <Terminal className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">API Docs</span>
            </a>
            <a
              href="https://github.com/hari31416/indic-language-utils"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium text-slate-300 bg-slate-900/90 hover:bg-slate-800 hover:text-white border border-slate-800 transition"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Source</span>
            </a>
          </div>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Navigation Tabs Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-800/80">
          <nav className="flex items-center gap-1.5 bg-slate-900/90 p-1.5 rounded-2xl border border-slate-800/90 shadow-lg overflow-x-auto max-w-full">
            <button
              type="button"
              onClick={() => setActiveTab('translate')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap ${
                activeTab === 'translate'
                  ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Languages className="w-4 h-4" />
              Translation
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('transliterate')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap ${
                activeTab === 'transliterate'
                  ? 'bg-gradient-to-r from-teal-600 to-teal-500 text-white shadow-md shadow-teal-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Keyboard className="w-4 h-4" />
              Transliteration
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('detect')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap ${
                activeTab === 'detect'
                  ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow-md shadow-purple-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <FileSearch className="w-4 h-4" />
              Detection &amp; Script
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('stt')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap ${
                activeTab === 'stt'
                  ? 'bg-gradient-to-r from-amber-600 to-amber-500 text-white shadow-md shadow-amber-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Mic className="w-4 h-4" />
              Speech to Text
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('tts')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap ${
                activeTab === 'tts'
                  ? 'bg-gradient-to-r from-violet-600 to-violet-500 text-white shadow-md shadow-violet-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Volume2 className="w-4 h-4" />
              Text to Speech
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('providers')}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition whitespace-nowrap ${
                activeTab === 'providers'
                  ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Layers className="w-4 h-4" />
              Engines &amp; Registry
            </button>
          </nav>

          <button
            type="button"
            onClick={() => void loadData()}
            disabled={loading}
            title="Reload engine configuration"
            className="p-2.5 rounded-xl text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800 shadow-sm transition"
          >
            <RefreshCw
              className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`}
            />
          </button>
        </div>

        {/* Global Error Banner */}
        {error && (
          <div className="p-4 bg-rose-950/70 border border-rose-800 rounded-2xl text-rose-300 text-xs flex items-center justify-between shadow-lg">
            <span>
              Could not communicate with backend: <strong>{error}</strong>. Make sure the server is running on port 8000.
            </span>
            <button
              type="button"
              onClick={() => void loadData()}
              className="px-3 py-1 bg-rose-900 hover:bg-rose-800 text-rose-100 rounded-lg font-medium transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* Content Views */}
        {loading && languages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-28 text-slate-500 gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
            <span className="text-sm font-medium text-slate-400">
              Initializing language models, routes, and providers...
            </span>
          </div>
        ) : (
          <>
            {activeTab === 'translate' && (
              <TranslateView
                languages={languages}
                providers={providersData?.translation ?? []}
              />
            )}
            {activeTab === 'transliterate' && (
              <TransliterateView
                languages={languages}
                providers={providersData?.transliteration ?? []}
              />
            )}
            {activeTab === 'detect' && (
              <DetectView providers={providersData?.detection ?? []} />
            )}
            {activeTab === 'stt' && (
              <STTView
                languages={languages}
                providers={providersData?.speech_to_text ?? []}
              />
            )}
            {activeTab === 'tts' && (
              <TTSView
                languages={languages}
                providers={providersData?.text_to_speech ?? []}
              />
            )}
            {activeTab === 'providers' && (
              <ProvidersView
                languages={languages}
                providersData={providersData}
                onOpenApiKeysModal={() => setIsKeysModalOpen(true)}
              />
            )}
          </>
        )}
      </main>

      {/* API Keys Configuration Modal */}
      <ApiKeysModal
        isOpen={isKeysModalOpen}
        onClose={() => setIsKeysModalOpen(false)}
        apiKeys={apiKeys}
        onSave={handleKeysSaved}
      />

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500 mt-auto">
        <p>
          indic-language-utils &bull; Provider-neutral foundations for Indian language applications
        </p>
      </footer>
    </div>
  )
}
export default App
