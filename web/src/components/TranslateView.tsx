import React, { useState } from 'react'
import {
  ArrowLeftRight,
  Check,
  Copy,
  FileCode,
  FileText,
  Loader2,
  Sparkles,
  Zap,
} from 'lucide-react'
import { translateText } from '../api'
import type { LanguageItem, ProviderInfo, TranslateResponse } from '../types'

interface TranslateViewProps {
  languages: LanguageItem[]
  providers: ProviderInfo[]
}

const SAMPLE_TEXTS = [
  {
    title: 'Basic Greeting',
    source: 'en',
    target: 'hi',
    format: 'plain' as const,
    text: 'Good morning! Welcome to India. How can I help you today?',
  },
  {
    title: 'Markdown with Code',
    source: 'en',
    target: 'ta',
    format: 'markdown' as const,
    text: '# System Alert\n\nPlease run `git pull origin main` to update your local repository.\nVisit [Documentation](https://example.com/docs) for assistance.',
  },
  {
    title: 'Administrative Notice',
    source: 'en',
    target: 'te',
    format: 'plain' as const,
    text: 'All citizens are requested to carry their official identity card during the verification process.',
  },
]

export const TranslateView: React.FC<TranslateViewProps> = ({
  languages,
  providers,
}) => {
  const [source, setSource] = useState('en')
  const [target, setTarget] = useState('hi')
  const [provider, setProvider] = useState('auto')
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

  return (
    <div className="space-y-6">
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 sm:p-6 backdrop-blur-sm">
        {/* Controls Bar */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center pb-4 border-b border-slate-800">
          <div className="md:col-span-4 flex items-center gap-2">
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Source Language
              </label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
              >
                {languages.map((lang) => (
                  <option key={`src-${lang.code}`} value={lang.code}>
                    {lang.name} ({lang.code})
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={handleSwap}
              title="Swap languages"
              className="mt-5 p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-slate-400 mb-1">
              Target Language
            </label>
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
            >
              {languages.map((lang) => (
                <option key={`tgt-${lang.code}`} value={lang.code}>
                  {lang.name} ({lang.code})
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-slate-400 mb-1">
              Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition"
            >
              <option value="auto">Auto (Default Route)</option>
              {providers.map((p) => (
                <option
                  key={p.id}
                  value={p.id}
                  disabled={!p.available}
                >
                  {p.name} {p.available ? '' : '(Unavailable)'}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-slate-400 mb-1">
              Format
            </label>
            <div className="flex rounded-lg bg-slate-950 p-0.5 border border-slate-700">
              <button
                type="button"
                onClick={() => setTextFormat('plain')}
                className={`flex-1 flex items-center justify-center gap-1 py-1.5 text-xs font-medium rounded-md transition ${
                  textFormat === 'plain'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                Plain
              </button>
              <button
                type="button"
                onClick={() => setTextFormat('markdown')}
                className={`flex-1 flex items-center justify-center gap-1 py-1.5 text-xs font-medium rounded-md transition ${
                  textFormat === 'markdown'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <FileCode className="w-3.5 h-3.5" />
                MD
              </button>
            </div>
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
                setTextFormat(sample.format)
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
                Source Text
              </span>
              <span>{inputText.length} characters</span>
            </div>
            <textarea
              rows={8}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type or paste text to translate... (Press Cmd+Enter to run)"
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
                onClick={() => void handleTranslate()}
                disabled={loading || !inputText.trim()}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-lg shadow-sm transition"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Translating...
                  </>
                ) : (
                  <>
                    <Zap className="w-3.5 h-3.5" />
                    Translate
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Output Panel */}
          <div className="flex flex-col bg-slate-950/80 border border-slate-800 rounded-lg p-3">
            <div className="flex justify-between items-center pb-2 text-xs text-slate-400 border-b border-slate-800/80">
              <span className="font-semibold tracking-wide uppercase text-slate-400">
                Translation Result
              </span>
              {result && (
                <button
                  type="button"
                  onClick={() => void handleCopy()}
                  className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition"
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
                  ? 'Requesting translation from engine...'
                  : 'Translation will appear here...'
              }
              className="w-full flex-1 mt-2 bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none resize-none font-mono text-sm leading-relaxed"
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
                    Model: {result.service_id}
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
