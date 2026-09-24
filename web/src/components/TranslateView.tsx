import React, { useState } from 'react'
import {
  ArrowLeftRight,
  Check,
  ChevronDown,
  Copy,
  Cpu,
  FileCode,
  FileText,
  Loader2,
  Sliders,
  Sparkles,
  Zap,
} from 'lucide-react'
import { translateText } from '../api'
import type { LanguageItem, ProviderInfo, TranslateResponse } from '../types'

interface TranslateViewProps {
  languages: LanguageItem[]
  providers: ProviderInfo[]
}

const POPULAR_LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'hi', name: 'Hindi' },
  { code: 'ta', name: 'Tamil' },
  { code: 'te', name: 'Telugu' },
  { code: 'bn', name: 'Bengali' },
  { code: 'mr', name: 'Marathi' },
  { code: 'gu', name: 'Gujarati' },
  { code: 'kn', name: 'Kannada' },
  { code: 'ml', name: 'Malayalam' },
  { code: 'pa', name: 'Punjabi' },
]

const SAMPLE_TEXTS = [
  {
    title: 'Basic Greeting',
    source: 'en',
    target: 'hi',
    format: 'plain' as const,
    text: 'Good morning! Welcome to India. How can I help you today?',
  },
  {
    title: 'Markdown Notice',
    source: 'en',
    target: 'ta',
    format: 'markdown' as const,
    text: '# System Alert\n\nPlease run `git pull origin main` to update your repository.\nVisit [Documentation](https://example.com/docs) for technical assistance.',
  },
  {
    title: 'Administrative Circular',
    source: 'en',
    target: 'te',
    format: 'plain' as const,
    text: 'All citizens are requested to carry their official identity card during the verification process at the regional center.',
  },
]

const MODEL_PRESETS: Record<string, string[]> = {
  sarvam: ['sarvam-translate:v1', 'mayura:v1'],
  bhashini: ['ai4bharat/indictrans-v2-all-gpu--t4'],
}

export const TranslateView: React.FC<TranslateViewProps> = ({
  languages,
  providers,
}) => {
  const [source, setSource] = useState('en')
  const [target, setTarget] = useState('hi')
  const [provider, setProvider] = useState('auto')
  const [modelId, setModelId] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [textFormat, setTextFormat] = useState<'plain' | 'markdown'>('plain')
  const [inputText, setInputText] = useState('Good morning! Welcome to India.')
  const [result, setResult] = useState<TranslateResponse | null>(null)
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

  const handleProviderChange = (newProvider: string) => {
    setProvider(newProvider)
    setModelId('')
  }

  const handleTranslate = async () => {
    if (!inputText.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await translateText({
        text: inputText,
        source,
        target,
        provider: provider === 'auto' ? null : provider,
        model_id: modelId.trim() || null,
        text_format: textFormat,
      })
      setResult(response)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Translation failed'
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
      void handleTranslate()
    }
  }

  const wordCount = inputText.trim() ? inputText.trim().split(/\s+/).length : 0
  const resultWordCount = result?.text.trim() ? result.text.trim().split(/\s+/).length : 0
  const activeModelPresets = MODEL_PRESETS[provider] ?? []

  return (
    <div className="space-y-5">
      {/* Control Card */}
      <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 sm:p-5 backdrop-blur-sm shadow-xl space-y-4">
        {/* Main Controls Header */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
          {/* Source Language */}
          <div className="md:col-span-4 space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Source Language
            </label>
            <div className="relative">
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-100 focus:outline-none focus:border-indigo-500 transition"
              >
                {languages.map((lang) => (
                  <option key={`src-${lang.code}`} value={lang.code}>
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

          {/* Target Language */}
          <div className="md:col-span-4 space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Target Language
            </label>
            <div className="relative">
              <select
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-100 focus:outline-none focus:border-indigo-500 transition"
              >
                {languages.map((lang) => (
                  <option key={`tgt-${lang.code}`} value={lang.code}>
                    {lang.name} ({lang.code})
                  </option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-3.5 pointer-events-none" />
            </div>
          </div>

          {/* Provider */}
          <div className="md:col-span-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
                Engine
              </label>
              <button
                type="button"
                onClick={() => setShowModelConfig(!showModelConfig)}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-400 hover:text-indigo-300"
              >
                <Sliders className="w-3 h-3" />
                {showModelConfig ? 'Hide Model ID' : 'Custom Model'}
              </button>
            </div>
            <div className="relative">
              <select
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value)}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-100 focus:outline-none focus:border-indigo-500 transition"
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

        {/* Optional Custom Model ID bar */}
        {showModelConfig && (
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2.5 animate-in fade-in duration-150">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <Cpu className="w-4 h-4 text-indigo-400" />
                <span>Provider Model ID / Service ID Override</span>
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
                          ? 'bg-indigo-600 text-white'
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
              placeholder={
                provider === 'sarvam'
                  ? 'Default: sarvam-translate:v1 (or mayura:v1, etc.)'
                  : provider === 'bhashini'
                    ? 'Default: ai4bharat/indictrans-v2-all-gpu--t4'
                    : 'Enter custom model ID or service ID...'
              }
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
            />
          </div>
        )}

        {/* Quick Language Chips */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/60">
          <div className="flex items-center gap-1.5 flex-wrap text-xs">
            <span className="text-slate-500 font-medium mr-1 hidden sm:inline">Quick Target:</span>
            {POPULAR_LANGUAGES.map((lang) => (
              <button
                key={`quick-${lang.code}`}
                type="button"
                onClick={() => setTarget(lang.code)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                  target === lang.code
                    ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40'
                    : 'bg-slate-950/60 text-slate-400 hover:text-slate-200 border border-slate-800/60 hover:border-slate-700'
                }`}
              >
                {lang.name}
              </button>
            ))}
          </div>

          {/* Format Toggle */}
          <div className="flex rounded-lg bg-slate-950 p-0.5 border border-slate-800">
            <button
              type="button"
              onClick={() => setTextFormat('plain')}
              className={`flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md transition ${
                textFormat === 'plain'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              Plain
            </button>
            <button
              type="button"
              onClick={() => setTextFormat('markdown')}
              className={`flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md transition ${
                textFormat === 'markdown'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileCode className="w-3.5 h-3.5" />
              Markdown
            </button>
          </div>
        </div>

        {/* Sample Presets */}
        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-slate-500 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> Samples:
          </span>
          {SAMPLE_TEXTS.map((sample) => (
            <button
              key={sample.title}
              type="button"
              onClick={() => {
                setSource(sample.source)
                setTarget(sample.target)
                setTextFormat(sample.format)
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
              <span>Source Text</span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-indigo-300">
                {source}
              </span>
            </div>
            <div className="flex items-center gap-3 text-slate-400">
              <span>{wordCount} words</span>
              <span>&bull;</span>
              <span>{inputText.length} chars</span>
            </div>
          </div>

          <textarea
            rows={10}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type or paste text to translate... (Cmd+Enter to run)"
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
              onClick={() => void handleTranslate()}
              disabled={loading || !inputText.trim()}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/20 transition active:scale-95"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Translating...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Translate
                </>
              )}
            </button>
          </div>
        </div>

        {/* Output Panel */}
        <div className="flex flex-col bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 sm:p-5 shadow-xl min-h-[340px]">
          <div className="flex justify-between items-center pb-3 text-xs text-slate-400 border-b border-slate-800/80">
            <div className="flex items-center gap-2 font-semibold uppercase tracking-wider text-slate-300">
              <span>Translation</span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-emerald-300">
                {target}
              </span>
            </div>

            {result && (
              <div className="flex items-center gap-3">
                <span className="text-slate-400">{resultWordCount} words</span>
                <button
                  type="button"
                  onClick={() => void handleCopy()}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-300 border border-indigo-500/20 text-xs font-medium transition"
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
              </div>
            )}
          </div>

          <textarea
            rows={10}
            readOnly
            value={result ? result.text : ''}
            placeholder={
              loading
                ? 'Processing translation request...'
                : 'Translation output will appear here...'
            }
            className="w-full flex-1 mt-3 bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none resize-none font-sans text-sm leading-relaxed"
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
                  : 'Live API'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
export default TranslateView
