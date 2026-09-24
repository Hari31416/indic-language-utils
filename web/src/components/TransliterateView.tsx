import React, { useState } from 'react'
import {
  ArrowLeftRight,
  Check,
  ChevronDown,
  Copy,
  Cpu,
  Keyboard,
  Loader2,
  Sliders,
  Sparkles,
  Zap,
} from 'lucide-react'
import { transliterateText } from '../api'
import type { LanguageItem, ProviderInfo, TransliterateResponse } from '../types'

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

export const TransliterateView: React.FC<TransliterateViewProps> = ({
  languages,
  providers,
}) => {
  const [source, setSource] = useState('en')
  const [target, setTarget] = useState('hi')
  const [provider, setProvider] = useState('auto')
  const [modelId, setModelId] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [inputText, setInputText] = useState('namaste bharat aapka swagat hai')
  const [result, setResult] = useState<TransliterateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

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
    <div className="space-y-5">
      {/* Controls Card */}
      <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 sm:p-5 backdrop-blur-sm shadow-xl space-y-4">
        {/* Banner Title */}
        <div className="flex items-center gap-3 pb-3 border-b border-slate-800/70">
          <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
            <Keyboard className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100">
              Phonetic &amp; Script Transliteration
            </h2>
            <p className="text-xs text-slate-400">
              Convert phonetic Roman input to native Indic scripts, Romanize native texts, or convert directly between Indic scripts
            </p>
          </div>
        </div>

        {/* Form Inputs */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
          {/* Source Script */}
          <div className="md:col-span-4 space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Source Script / Language
            </label>
            <div className="relative">
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-100 focus:outline-none focus:border-teal-500 transition"
              >
                {languages.map((lang) => (
                  <option key={`xlit-src-${lang.code}`} value={lang.code}>
                    {lang.name} ({lang.code})
                  </option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-3.5 pointer-events-none" />
            </div>
          </div>

          {/* Swap Button */}
          <div className="md:col-span-1 flex justify-center pb-0.5">
            <button
              type="button"
              onClick={handleSwap}
              title="Swap source and target"
              className="p-2.5 rounded-xl bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/70 transition shadow-sm"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          {/* Target Script */}
          <div className="md:col-span-4 space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Target Script / Language
            </label>
            <div className="relative">
              <select
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-100 focus:outline-none focus:border-teal-500 transition"
              >
                {languages.map((lang) => (
                  <option key={`xlit-tgt-${lang.code}`} value={lang.code}>
                    {lang.name} ({lang.code})
                  </option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-3.5 pointer-events-none" />
            </div>
          </div>

          {/* Engine */}
          <div className="md:col-span-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
                Engine
              </label>
              <button
                type="button"
                onClick={() => setShowModelConfig(!showModelConfig)}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-teal-400 hover:text-teal-300"
              >
                <Sliders className="w-3 h-3" />
                {showModelConfig ? 'Hide Model' : 'Custom Model'}
              </button>
            </div>
            <div className="relative">
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value)
                  setModelId('')
                }}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-100 focus:outline-none focus:border-teal-500 transition"
              >
                <option value="auto">Auto (Default Route)</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id} disabled={!p.available}>
                    {p.name} {p.available ? '' : '(Unavailable)'}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-3.5 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Model ID Config Drawer */}
        {showModelConfig && (
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2.5 animate-in fade-in duration-150">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <Cpu className="w-4 h-4 text-teal-400" />
                <span>Transliteration Service / Model ID Override</span>
              </div>
              {activeModelPresets.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[11px] text-slate-500">Presets:</span>
                  {activeModelPresets.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setModelId(preset)}
                      className={`px-2 py-0.5 rounded text-[11px] font-mono transition ${
                        modelId === preset
                          ? 'bg-teal-600 text-white'
                          : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      {preset}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <input
              type="text"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              placeholder="e.g. ai4bharat/indicxlit--gpu--t4 or custom service ID..."
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-teal-500 transition"
            />
          </div>
        )}

        {/* Sample Presets */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/60 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-slate-500 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-teal-400" /> Samples:
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
              className="px-2.5 py-1 rounded-lg bg-slate-950/60 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800/80 transition"
            >
              {sample.title}
            </button>
          ))}
        </div>
      </div>

      {/* Dual Pane Input / Output Workspace */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Input Panel */}
        <div className="flex flex-col bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 sm:p-5 shadow-xl min-h-[340px]">
          <div className="flex justify-between items-center pb-3 text-xs text-slate-400 border-b border-slate-800/80">
            <div className="flex items-center gap-2 font-semibold uppercase tracking-wider text-slate-300">
              <span>Input Text</span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-teal-300">
                {source}
              </span>
            </div>
            <span>{inputText.length} chars</span>
          </div>

          <textarea
            rows={10}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type phonetic Roman text (e.g. 'namaste duniya') or paste native script... (Cmd+Enter to run)"
            className="w-full flex-1 mt-3 bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none resize-none font-sans text-sm leading-relaxed"
          />

          <div className="pt-3 flex justify-between items-center border-t border-slate-800/80 mt-2">
            <button
              type="button"
              onClick={() => setInputText('')}
              className="text-xs text-slate-500 hover:text-slate-300 transition"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={() => void handleTransliterate()}
              disabled={loading || !inputText.trim()}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal-600 hover:bg-teal-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-xl shadow-lg shadow-teal-600/20 transition active:scale-95"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Transliterating...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Transliterate
                </>
              )}
            </button>
          </div>
        </div>

        {/* Output Panel */}
        <div className="flex flex-col bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 sm:p-5 shadow-xl min-h-[340px]">
          <div className="flex justify-between items-center pb-3 text-xs text-slate-400 border-b border-slate-800/80">
            <div className="flex items-center gap-2 font-semibold uppercase tracking-wider text-slate-300">
              <span>Transliterated Output</span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-emerald-300">
                {target}
              </span>
            </div>

            {result && (
              <button
                type="button"
                onClick={() => void handleCopy()}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-teal-600/10 hover:bg-teal-600/20 text-teal-300 border border-teal-500/20 text-xs font-medium transition"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    Copy
                  </>
                )}
              </button>
            )}
          </div>

          <textarea
            rows={10}
            readOnly
            value={result ? result.text : ''}
            placeholder={
              loading
                ? 'Processing transliteration...'
                : 'Transliteration output will appear here...'
            }
            className="w-full flex-1 mt-3 bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none resize-none font-sans text-base leading-relaxed"
          />

          {error && (
            <div className="mt-2 p-3 bg-rose-950/60 border border-rose-800/70 text-rose-300 text-xs rounded-xl">
              {error}
            </div>
          )}

          {result && (
            <div className="pt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400 border-t border-slate-800/80 mt-2">
              <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 font-medium">
                Provider: {result.provider}
              </span>
              {(result.model_id || result.service_id) && (
                <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 font-mono text-[11px]">
                  Model: {result.model_id || result.service_id}
                </span>
              )}
              <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 font-mono text-[11px]">
                {Math.round(result.elapsed_seconds * 1000)}ms
              </span>
              <span
                className={`px-2.5 py-1 rounded-lg font-medium border text-[11px] ${
                  result.cached
                    ? 'bg-emerald-950/50 text-emerald-300 border-emerald-800/50'
                    : 'bg-slate-950 text-slate-400 border-slate-800'
                }`}
              >
                {result.cached
                  ? `Cache HIT (${result.cache_backend ?? 'cache'})`
                  : 'Live Computation'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
export default TransliterateView
