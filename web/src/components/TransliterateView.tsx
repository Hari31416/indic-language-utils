import React, { useState } from 'react'
import {
  ArrowLeftRight,
  Check,
  ChevronDown,
  Copy,
  Loader2,
  Sliders,
  Sparkles,
  Zap,
} from 'lucide-react'
import { transliterateText } from '../api'
import { useLocalHistory } from '../history'
import type { LanguageItem, ProviderInfo, TransliterateResponse } from '../types'
import {
  ErrorBox,
  Field,
  HistoryStrip,
  MetaBar,
  ModelDrawer,
} from './ui'

interface TransliterateViewProps {
  languages: LanguageItem[]
  providers: ProviderInfo[]
}

const SAMPLE_TEXTS = [
  {
    title: 'Hindi (Roman to Devanagari)',
    source: 'en',
    target: 'hi',
    text: 'namaste bharat aapka swagat hai',
  },
  {
    title: 'Tamil to Devanagari (Script)',
    source: 'ta',
    target: 'hi',
    text: 'வணக்கம், நீங்கள் நலமா?',
  },
  {
    title: 'Devanagari to Bengali (Script)',
    source: 'hi',
    target: 'bn',
    text: 'नमस्ते भारत आपका स्वागत है',
  },
  {
    title: 'Tamil (Roman to Tamil)',
    source: 'en',
    target: 'ta',
    text: 'vanakkam ungalai santhithathil magizhchi',
  },
  {
    title: 'Telugu (Roman to Telugu)',
    source: 'en',
    target: 'te',
    text: 'namaskaram meeru ela unnaru',
  },
  {
    title: 'Bengali (Roman to Bengali)',
    source: 'en',
    target: 'bn',
    text: 'nomoshkar kemon achhen',
  },
  {
    title: 'Romanization (Devanagari to Roman)',
    source: 'hi',
    target: 'en',
    text: 'नमस्ते भारत आपका स्वागत है',
  },
]

const MODEL_PRESETS: Record<string, string[]> = {
  bhashini: ['ai4bharat/indicxlit--gpu--t4'],
}

interface Hist {
  source: string
  target: string
  text: string
  out: string
}

export const TransliterateView: React.FC<TransliterateViewProps> = ({
  languages,
  providers,
}) => {
  const [source, setSource] = useState('en')
  const [target, setTarget] = useState('hi')
  const [provider, setProvider] = useState('auto')
  const [modelId, setModelId] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [showOptions, setShowOptions] = useState(false)
  const [inputText, setInputText] = useState('namaste bharat aapka swagat hai')
  const [result, setResult] = useState<TransliterateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const { items: history, push, clear } = useLocalHistory<Hist>('ilu-hist-xliterate')

  const handleSwap = () => {
    setSource(target)
    setTarget(source)
    if (result) {
      setInputText(result.text)
      setResult(null)
    }
  }

  const handleTransliterate = async () => {
    if (!inputText.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await transliterateText({
        text: inputText,
        source,
        target,
        provider: provider === 'auto' ? null : provider,
        model_id: modelId.trim() || null,
      })
      setResult(response)
      push({ source, target, text: inputText, out: response.text })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Transliteration failed'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    if (!result?.text) return
    await navigator.clipboard.writeText(result.text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      void handleTransliterate()
    }
  }

  const activeModelPresets = MODEL_PRESETS[provider] ?? []

  return (
    <div className="space-y-4">
      {/* Compact command bar: route + engine + submit in one row */}
      <div className="panel p-3.5 sm:p-4">
        <div className="flex flex-col gap-2.5 lg:flex-row lg:items-end">
          <div className="min-w-0 flex-1">
            <Field label="From script / language">
              <div className="relative">
                <select value={source} onChange={(e) => setSource(e.target.value)} className="field">
                  {languages.map((lang) => (
                    <option key={`xlit-src-${lang.code}`} value={lang.code}>
                      {lang.name} ({lang.code})
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-parchment-500" />
              </div>
            </Field>
          </div>
          <button
            type="button"
            onClick={handleSwap}
            title="Swap source and target"
            className="icon-btn hidden !rounded-full lg:mb-0.5 lg:block"
          >
            <ArrowLeftRight className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <Field label="To script / language">
              <div className="relative">
                <select value={target} onChange={(e) => setTarget(e.target.value)} className="field">
                  {languages.map((lang) => (
                    <option key={`xlit-tgt-${lang.code}`} value={lang.code}>
                      {lang.name} ({lang.code})
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-parchment-500" />
              </div>
            </Field>
          </div>
          <div className="lg:w-56 lg:shrink-0">
            <Field
              label="Engine"
              action={
                <button
                  type="button"
                  onClick={() => setShowModelConfig(!showModelConfig)}
                  className="link-accent"
                  title="Custom model ID override"
                >
                  <Sliders className="h-3 w-3" />
                  {showModelConfig ? 'Hide' : 'Model'}
                </button>
              }
            >
              <div className="relative">
                <select
                  value={provider}
                  onChange={(e) => {
                    setProvider(e.target.value)
                    setModelId('')
                  }}
                  className="field"
                >
                  <option value="auto">Auto (Default Route)</option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id} disabled={!p.available}>
                      {p.name} {p.available ? '' : '(Unavailable)'}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-parchment-500" />
              </div>
            </Field>
          </div>
          <button
            type="button"
            onClick={() => void handleTransliterate()}
            disabled={loading || !inputText.trim()}
            className="btn-primary shrink-0 lg:w-auto"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Transliterating…
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" /> Transliterate
              </>
            )}
          </button>
        </div>

        <ModelDrawer
          open={showModelConfig}
          title="Transliteration Service / Model ID Override"
          presets={activeModelPresets}
          modelId={modelId}
          onChange={setModelId}
          placeholder="e.g. ai4bharat/indicxlit--gpu--t4 or custom service ID..."
        />

        <div className="mt-2.5 border-t divider pt-2">
          <button
            type="button"
            onClick={() => setShowOptions(!showOptions)}
            className="btn-quiet flex items-center gap-1.5 !text-xs"
          >
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform ${showOptions ? 'rotate-180' : ''}`}
            />
            {showOptions ? 'Hide samples & history' : 'Samples & history'}
          </button>
          {showOptions && (
            <div className="animate-fade-in space-y-3 pt-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="flex items-center gap-1 font-medium text-parchment-500">
                  <Sparkles className="h-3.5 w-3.5 text-peacock-300" /> Samples:
                </span>
                {SAMPLE_TEXTS.map((sample) => (
                  <button
                    key={sample.title}
                    type="button"
                    onClick={() => {
                      setSource(sample.source)
                      setTarget(sample.target)
                      setInputText(sample.text)
                      setResult(null)
                    }}
                    className="sample-btn"
                  >
                    {sample.title}
                  </button>
                ))}
              </div>
              <HistoryStrip
                items={history}
                onClear={clear}
                onRestore={(h) => {
                  setSource(h.source)
                  setTarget(h.target)
                  setInputText(h.text)
                  setResult(null)
                }}
                renderLabel={(h) => `${h.source}→${h.target}: ${h.text.slice(0, 32)}${h.text.length > 32 ? '…' : ''}`}
                renderSub={(h) => h.out}
              />
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="panel flex min-h-[300px] flex-col p-4 sm:p-5">
          <div className="flex items-center justify-between border-b divider pb-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-[0.14em] text-parchment-300">
                Input
              </span>
              <span className="rounded bg-ink-700/70 px-2 py-0.5 font-mono text-[11px] text-peacock-300">
                {source}
              </span>
              <button
                type="button"
                onClick={handleSwap}
                title="Swap source and target"
                className="btn-quiet flex items-center gap-1 lg:hidden"
              >
                <ArrowLeftRight className="h-3 w-3" /> Swap
              </button>
            </div>
            <span className="text-parchment-500">{inputText.length} chars</span>
          </div>
          <textarea
            rows={9}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type phonetic Roman text (e.g. “namaste duniya”) or paste native script…"
            className="mt-3 w-full flex-1 resize-none bg-transparent text-[15px] leading-relaxed text-parchment-100 placeholder:text-parchment-600 focus:outline-none"
          />
          <div className="mt-2 flex items-center justify-between border-t divider pt-3">
            <button type="button" onClick={() => setInputText('')} className="btn-quiet">
              Clear
            </button>
            <span className="hidden items-center gap-1 text-[11px] text-parchment-600 sm:flex">
              <span className="kbd">⌘</span>+<span className="kbd">↵</span> to run
            </span>
          </div>
        </div>

        <div className="panel flex min-h-[300px] flex-col p-4 sm:p-5">
          <div className="flex items-center justify-between border-b divider pb-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-[0.14em] text-parchment-300">
                Output
              </span>
              <span className="rounded bg-ink-700/70 px-2 py-0.5 font-mono text-[11px] text-moss-300">
                {target}
              </span>
            </div>
            {result && (
              <button type="button" onClick={() => void handleCopy()} className="btn-ghost">
                {copied ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-moss-300" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" /> Copy
                  </>
                )}
              </button>
            )}
          </div>
          <textarea
            rows={9}
            readOnly
            value={result ? result.text : ''}
            placeholder={loading ? 'Processing transliteration…' : 'Transliterated output will appear here…'}
            className="mt-3 w-full flex-1 resize-none bg-transparent text-[15px] leading-relaxed text-parchment-100 placeholder:text-parchment-600 focus:outline-none"
          />
          {error && (
            <div className="mt-2">
              <ErrorBox message={error} />
            </div>
          )}
          {result && (
            <MetaBar
              items={[
                { label: 'Provider', value: result.provider },
                ...(result.model_id || result.service_id
                  ? [{ label: 'Model', value: result.model_id || result.service_id || '' }]
                  : []),
                { label: 'Time', value: `${Math.round(result.elapsed_seconds * 1000)}ms` },
                result.cached
                  ? { label: 'Cache', value: `HIT · ${result.cache_backend ?? 'cache'}`, tone: 'hit' as const }
                  : { label: 'Cache', value: 'Live' },
              ]}
            />
          )}
        </div>
      </div>
    </div>
  )
}
export default TransliterateView
