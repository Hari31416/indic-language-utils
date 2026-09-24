import React, { useEffect, useState } from 'react'
import {
  Activity,
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
import type {
  ApiKeysConfig,
  LanguageItem,
  ProviderInfo,
  ProvidersResponse,
} from './types'

type ActiveTab = 'translate' | 'transliterate' | 'detect' | 'stt' | 'tts' | 'providers'

interface TabDef {
  id: ActiveTab
  label: string
  blurb: string
  icon: React.ReactNode
  tile: string
  bar: string
}

const TABS: TabDef[] = [
  {
    id: 'translate',
    label: 'Translation',
    blurb: 'Full-sentence MT',
    icon: <Languages className="h-4 w-4" />,
    tile: 'border-marigold-500/30 bg-marigold-500/10 text-marigold-300',
    bar: 'bg-marigold-400',
  },
  {
    id: 'transliterate',
    label: 'Transliteration',
    blurb: 'Roman ↔ native script',
    icon: <Keyboard className="h-4 w-4" />,
    tile: 'border-peacock-500/30 bg-peacock-500/10 text-peacock-300',
    bar: 'bg-peacock-400',
  },
  {
    id: 'detect',
    label: 'Detection & Script',
    blurb: 'Identify language',
    icon: <FileSearch className="h-4 w-4" />,
    tile: 'border-orchid-500/30 bg-orchid-500/10 text-orchid-300',
    bar: 'bg-orchid-400',
  },
  {
    id: 'stt',
    label: 'Speech to Text',
    blurb: 'Transcribe audio',
    icon: <Mic className="h-4 w-4" />,
    tile: 'border-clay-500/30 bg-clay-500/10 text-clay-300',
    bar: 'bg-clay-400',
  },
  {
    id: 'tts',
    label: 'Text to Speech',
    blurb: 'Synthesize voice',
    icon: <Volume2 className="h-4 w-4" />,
    tile: 'border-rosewood-500/30 bg-rosewood-500/10 text-rosewood-300',
    bar: 'bg-rosewood-400',
  },
  {
    id: 'providers',
    label: 'Engines & Registry',
    blurb: 'Status & languages',
    icon: <Layers className="h-4 w-4" />,
    tile: 'border-moss-500/30 bg-moss-500/10 text-moss-300',
    bar: 'bg-moss-400',
  },
]

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

  const allProviders: ProviderInfo[] = providersData
    ? [
        ...providersData.translation,
        ...providersData.transliteration,
        ...providersData.detection,
        ...providersData.speech_to_text,
        ...providersData.text_to_speech,
      ]
    : []
  const totalReady = allProviders.filter((p) => p.available).length

  const activeDef = TABS.find((t) => t.id === activeTab) ?? TABS[0]

  return (
    <div className="flex min-h-screen flex-col bg-ink-950 font-sans text-parchment-100">
      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 border-b divider bg-ink-950/85 backdrop-blur-md lg:hidden">
        <div className="flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-marigold-500 p-1.5 text-ink-950 shadow-pop">
              <Languages className="h-4 w-4" />
            </div>
            <span className="font-display text-base font-semibold tracking-tight">
              indic-language-utils
            </span>
            <span className="rounded border border-ink-600 bg-ink-800 px-1.5 py-0.5 font-mono text-[10px] text-marigold-300">
              v0.5.0
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsKeysModalOpen(true)}
              className="icon-btn !p-2"
              title="Configure API keys"
            >
              <KeyRound className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={loading}
              className="icon-btn !p-2"
              title="Reload engine configuration"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
        <nav className="flex gap-1.5 overflow-x-auto px-4 pb-3">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                activeTab === tab.id
                  ? 'border-marigold-500/60 bg-marigold-500/15 text-marigold-200'
                  : 'border-ink-700/70 bg-ink-900 text-parchment-400'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="flex flex-1 items-stretch">
        {/* Studio sidebar (desktop) */}
        <aside className="sticky top-0 hidden h-screen w-[296px] shrink-0 flex-col border-r divider bg-ink-900/50 lg:flex">
          <div className="flex items-center gap-3 px-5 pb-5 pt-6">
            <div className="rounded-xl bg-marigold-500 p-2 text-ink-950 shadow-pop">
              <Languages className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate font-display text-[17px] font-semibold tracking-tight">
                  indic-language-utils
                </span>
              </div>
              <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-parchment-500">
                Indian Language AI Workbench
                <span className="rounded border border-ink-600 bg-ink-800 px-1 py-px font-mono text-[10px] text-marigold-300">
                  v0.5.0
                </span>
              </p>
            </div>
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-3">
            <p className="eyebrow px-2 pb-1.5">Tools</p>
            {TABS.map((tab) => {
              const active = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`group relative flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${
                    active
                      ? 'border-ink-600 bg-ink-800 shadow-card'
                      : 'border-transparent hover:border-ink-700/60 hover:bg-ink-850'
                  }`}
                >
                  <span
                    className={`absolute left-0 top-2.5 h-[calc(100%-20px)] w-[3px] rounded-full transition ${
                      active ? tab.bar : 'bg-transparent'
                    }`}
                  />
                  <span className={`rounded-lg border p-2 ${tab.tile}`}>
                    {tab.icon}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span
                      className={`block truncate text-[13px] font-semibold ${
                        active ? 'text-parchment-100' : 'text-parchment-300'
                      }`}
                    >
                      {tab.label}
                    </span>
                    <span className="block truncate text-[11px] text-parchment-500">
                      {tab.blurb}
                    </span>
                  </span>
                </button>
              )
            })}
          </nav>

          <div className="space-y-3 border-t divider p-4">
            <div className="panel-sunken flex items-center gap-2.5 p-3">
              <Activity className="h-4 w-4 shrink-0 text-moss-300" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-parchment-200">
                  {allProviders.length === 0
                    ? 'Engines unknown'
                    : `${totalReady} of ${allProviders.length} engines ready`}
                </p>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-700">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-moss-500 to-peacock-400 transition-all duration-700"
                    style={{
                      width: `${
                        allProviders.length === 0
                          ? 0
                          : Math.round((totalReady / allProviders.length) * 100)
                      }%`,
                    }}
                  />
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setIsKeysModalOpen(true)}
              className="flex w-full items-center gap-2 rounded-xl border border-ink-600 bg-ink-800 px-3 py-2.5 text-xs font-semibold text-parchment-200 transition hover:border-marigold-500/50 hover:text-marigold-200"
            >
              <KeyRound className="h-3.5 w-3.5 text-marigold-300" />
              <span className="flex-1 text-left">API Keys</span>
              {configuredKeyCount > 0 ? (
                <span className="h-2 w-2 animate-pulse rounded-full bg-moss-400" />
              ) : (
                <span className="rounded bg-ink-700 px-1.5 py-0.5 text-[10px] text-parchment-400">
                  Config
                </span>
              )}
            </button>
            <div className="flex items-center gap-2">
              <a
                href="/docs"
                target="_blank"
                rel="noreferrer"
                className="btn-ghost flex-1 justify-center"
              >
                <Terminal className="h-3.5 w-3.5" /> API Docs
              </a>
              <a
                href="https://github.com/hari31416/indic-language-utils"
                target="_blank"
                rel="noreferrer"
                className="btn-ghost flex-1 justify-center"
              >
                <BookOpen className="h-3.5 w-3.5" /> Source
              </a>
            </div>
          </div>
        </aside>

        {/* Main column */}
        <div className="min-w-0 flex-1">
          <div className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-8 lg:py-8">
            {/* Desktop toolbar */}
            <div className="hidden items-end justify-between lg:flex">
              <div>
                <p className="eyebrow !text-marigold-300/90">
                  {activeDef.blurb}
                </p>
                <h1 className="mt-1 font-display text-[28px] font-semibold leading-tight tracking-tight">
                  {activeDef.label}
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <span className="mr-1 hidden items-center gap-1.5 text-[11px] text-parchment-500 xl:flex">
                  Press <span className="kbd">⌘</span> +{' '}
                  <span className="kbd">↵</span> to run
                </span>
                <button
                  type="button"
                  onClick={() => void loadData()}
                  disabled={loading}
                  title="Reload engine configuration"
                  className="icon-btn"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${loading ? 'animate-spin text-marigold-300' : ''}`}
                  />
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center justify-between gap-3 rounded-2xl border border-clay-500/40 bg-clay-500/10 p-4 text-xs text-clay-300 shadow-card">
                <span>
                  Could not communicate with backend:{' '}
                  <strong className="font-semibold">{error}</strong> Make sure
                  the server is running on port 8000.
                </span>
                <button
                  type="button"
                  onClick={() => void loadData()}
                  className="shrink-0 rounded-lg bg-clay-500/20 px-3 py-1.5 font-semibold text-clay-200 transition hover:bg-clay-500/30"
                >
                  Retry
                </button>
              </div>
            )}

            {loading && languages.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 py-28 text-parchment-500">
                <Loader2 className="h-8 w-8 animate-spin text-marigold-400" />
                <span className="font-display text-lg italic text-parchment-300">
                  Setting up the atelier…
                </span>
                <span className="text-xs">
                  Loading language models, routes, and providers
                </span>
              </div>
            ) : (
              <div key={activeTab} className="animate-rise">
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
                    onOpenTool={(tool) => setActiveTab(tool)}
                  />
                )}
              </div>
            )}

            <footer className="flex flex-col items-center gap-1 border-t divider pt-5 text-center text-[11px] text-parchment-600 sm:flex-row sm:justify-between sm:text-left">
              <p className="font-display italic">
                indic-language-utils · provider-neutral foundations for Indian
                language applications
              </p>
              <p className="font-mono">
                {languages.length} languages · {allProviders.length} engines
              </p>
            </footer>
          </div>
        </div>
      </div>

      <ApiKeysModal
        isOpen={isKeysModalOpen}
        onClose={() => setIsKeysModalOpen(false)}
        apiKeys={apiKeys}
        onSave={handleKeysSaved}
      />
    </div>
  )
}
export default App
