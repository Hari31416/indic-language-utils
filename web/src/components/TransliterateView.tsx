import React, { useState } from 'react'
import {
  ArrowLeftRight,
  Check,
  Copy,
  Languages,
  Loader2,
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
    title: 'Gujarati (Roman to Gujarati)',
    source: 'en',
    target: 'gu',
    text: 'kem chho tame maja ma chho',
  },
  {
    title: 'Romanization (Devanagari to Roman)',
    source: 'hi',
    target: 'en',
    text: 'नमस्ते भारत आपका स्वागत है',
  },
]

export const TransliterateView: React.FC<TransliterateViewProps> = ({
  languages,
  providers,
}) => {
  const [source, setSource] = useState('en')
  const [target, setTarget] = useState('hi')
  const [provider, setProvider] = useState('auto')
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
      })
      setResult(response)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Transliteration failed'
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

  return (
    <div className="space-y-6">
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 sm:p-6 backdrop-blur-sm">
        {/* Header summary */}
        <div className="flex items-center gap-2 pb-4 mb-4 border-b border-slate-800/80">
          <div className="p-1.5 rounded-lg bg-teal-500/20 text-teal-400 border border-teal-500/30">
            <Languages className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100">
              Phonetic &amp; Script Transliteration
            </h2>
            <p className="text-xs text-slate-400">
              Convert phonetic Roman inputs to native Indic scripts or Romanize
              native texts using Bhashini and AI4Bharat IndicXlit.
            </p>
          </div>
        </div>

        {/* Controls Bar */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center pb-4 border-b border-slate-800">
          <div className="md:col-span-5 flex items-center gap-2">
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Source Script / Language
              </label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
              >
                {languages.map((lang) => (
                  <option key={`xlit-src-${lang.code}`} value={lang.code}>
                    {lang.name} ({lang.code})
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={handleSwap}
              title="Swap source and target"
              className="mt-5 p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          <div className="md:col-span-4">
            <label className="block text-xs font-medium text-slate-400 mb-1">
              Target Script / Language
            </label>
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
            >
              {languages.map((lang) => (
                <option key={`xlit-tgt-${lang.code}`} value={lang.code}>
                  {lang.name} ({lang.code})
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-slate-400 mb-1">
              Engine / Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
            >
              <option value="auto">Auto (Default Route)</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id} disabled={!p.available}>
                  {p.name} {p.available ? '' : '(Unavailable)'}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Sample Presets */}
        <div className="flex flex-wrap items-center gap-2 pt-3 pb-1 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-slate-500">
            <Sparkles className="w-3.5 h-3.5" /> Samples:
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
              className="px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition"
            >
              {sample.title}
            </button>
          ))}
        </div>

        {/* Text Input and Output Panels */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          {/* Input Panel */}
          <div className="flex flex-col bg-slate-950/80 border border-slate-800 rounded-lg p-3">
            <div className="flex justify-between items-center pb-2 text-xs text-slate-400 border-b border-slate-800/80">
              <span className="font-semibold tracking-wide uppercase text-slate-400">
                Input Text
              </span>
              <span>{inputText.length} characters</span>
            </div>
            <textarea
              rows={8}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type phonetic Roman text (e.g. 'namaste duniya') or paste native script... (Press Cmd+Enter to run)"
              className="w-full flex-1 mt-2 bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none resize-none font-mono text-sm leading-relaxed"
            />
            <div className="pt-2 flex justify-between items-center border-t border-slate-800/80 mt-2">
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
                className="inline-flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-lg shadow-sm transition"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Transliterating...
                  </>
                ) : (
                  <>
                    <Zap className="w-3.5 h-3.5" />
                    Transliterate
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Output Panel */}
          <div className="flex flex-col bg-slate-950/80 border border-slate-800 rounded-lg p-3">
            <div className="flex justify-between items-center pb-2 text-xs text-slate-400 border-b border-slate-800/80">
              <span className="font-semibold tracking-wide uppercase text-slate-400">
                Transliteration Output
              </span>
              {result && (
                <button
                  type="button"
                  onClick={() => void handleCopy()}
                  className="inline-flex items-center gap-1 text-xs text-teal-400 hover:text-teal-300 transition"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      Copy
                    </>
                  )}
                </button>
              )}
            </div>

            <textarea
              rows={8}
              readOnly
              value={result ? result.text : ''}
              placeholder={
                loading
                  ? 'Requesting transliteration from engine...'
                  : 'Transliterated text will appear here...'
              }
              className="w-full flex-1 mt-2 bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none resize-none font-sans text-base leading-relaxed"
            />

            {error && (
              <div className="mt-2 p-2 bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs rounded-md">
                {error}
              </div>
            )}

            {result && (
              <div className="pt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400 border-t border-slate-800/80 mt-2">
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
                  Provider: {result.provider}
                </span>
                {result.service_id && (
                  <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-400">
                    Service: {result.service_id}
                  </span>
                )}
                {result.model_id && (
                  <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-400">
                    Model: {result.model_id}
                  </span>
                )}
                <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-400">
                  {Math.round(result.elapsed_seconds * 1000)}ms
                </span>
                <span
                  className={`px-2 py-0.5 rounded font-medium ${
                    result.cached
                      ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/50'
                      : 'bg-slate-800/60 text-slate-400'
                  }`}
                >
                  {result.cached
                    ? `Cache HIT (${result.cache_backend ?? 'cache'})`
                    : 'Live API'}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
export default TransliterateView
