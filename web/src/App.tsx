import React, { useEffect, useState } from 'react'
import {
  BookOpen,
  FileSearch,
  Languages,
  Layers,
  Loader2,
  RefreshCw,
  Terminal,
} from 'lucide-react'
import { fetchLanguages, fetchProviders } from './api'
import { DetectView } from './components/DetectView'
import { ProvidersView } from './components/ProvidersView'
import { TranslateView } from './components/TranslateView'
import type { LanguageItem, ProvidersResponse } from './types'

type ActiveTab = 'translate' | 'detect' | 'providers'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('translate')
  const [languages, setLanguages] = useState<LanguageItem[]>([])
  const [providersData, setProvidersData] = useState<ProvidersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [langRes, provRes] = await Promise.all([
        fetchLanguages(),
        fetchProviders(),
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

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Top Navigation */}
      <header className="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
              <Languages className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-100 tracking-tight text-base sm:text-lg">
                  indic-language-utils
                </span>
                <span className="text-[11px] px-1.5 py-0.5 rounded font-mono bg-slate-800 text-slate-400">
                  v0.1.1
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                Testing & Evaluation Workbench for Indian Languages
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <a
              href="/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700 hover:text-white transition"
            >
              <Terminal className="w-3.5 h-3.5" />
              API Docs
            </a>
            <a
              href="https://github.com/indic-language-utils/indic-language-utils"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700 hover:text-white transition"
            >
              <BookOpen className="w-3.5 h-3.5" />
              Source
            </a>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <nav className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
            <button
              type="button"
              onClick={() => setActiveTab('translate')}
              className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'translate'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Languages className="w-4 h-4" />
              Translation
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('detect')}
              className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'detect'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileSearch className="w-4 h-4" />
              Detection & Script
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('providers')}
              className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'providers'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-4 h-4" />
              Engines & Registry
            </button>
          </nav>

          <button
            type="button"
            onClick={() => void loadData()}
            disabled={loading}
            title="Reload engine configuration"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800 transition"
          >
            <RefreshCw
              className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`}
            />
          </button>
        </div>

        {/* Global Error Banner */}
        {error && (
          <div className="p-4 bg-rose-950/60 border border-rose-800/80 rounded-xl text-rose-300 text-xs flex items-center justify-between">
            <span>
              Could not communicate with backend: <strong>{error}</strong>. Make
              sure the server is running on port 8000.
            </span>
            <button
              type="button"
              onClick={() => void loadData()}
              className="px-3 py-1 bg-rose-900/80 hover:bg-rose-800 text-rose-100 rounded-md font-medium"
            >
              Retry
            </button>
          </div>
        )}

        {/* Content Views */}
        {loading && languages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-slate-500 gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
            <span className="text-sm font-medium">
              Initializing language models and routes...
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
            {activeTab === 'detect' && (
              <DetectView providers={providersData?.detection ?? []} />
            )}
            {activeTab === 'providers' && (
              <ProvidersView
                languages={languages}
                providersData={providersData}
              />
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        <p>
          indic-language-utils &bull; Provider-neutral foundations for Indian
          language applications
        </p>
      </footer>
    </div>
  )
}
export default App
