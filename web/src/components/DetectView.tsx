import React, { useState } from 'react'
import {
  ChevronDown,
  Cpu,
  FileSearch,
  Globe,
  Loader2,
  Sliders,
  Sparkles,
  Type,
  Zap,
} from 'lucide-react'
import { detectLanguage } from '../api'
import type { DetectResponse, ProviderInfo } from '../types'

interface DetectViewProps {
  providers: ProviderInfo[]
}

const SAMPLE_DETECT_TEXTS = [
  {
    language: 'Hindi (Devanagari)',
    text: 'भारत सरकार ने राष्ट्रीय शिक्षा नीति की घोषणा की है।',
  },
  {
    language: 'Tamil',
    text: 'தமிழ்நாடு இந்தியக் குடியரசின் 28 மாநிலங்களுள் ஒன்றாகும்.',
  },
  {
    language: 'Bengali',
    text: 'পশ্চিমবঙ্গ ভারতের পূর্ব অঞ্চলের একটি রাজ্য।',
  },
  {
    language: 'Telugu',
    text: 'ఆంధ్ర ప్రదేశ్ భారతదేశంలోని దక్షిణ భాగంలో ఉన్న ఒక రాష్ట్రం.',
  },
  {
    language: 'Gujarati',
    text: 'ગુજરાત ભારતનું પશ્ચિમ કિનારે આવેલું રાજ્ય છે.',
  },
  {
    language: 'Malayalam',
    text: 'കേരളം ഇന്ത്യയുടെ തെക്കുപടിഞ്ഞാറൻ തീരത്തുള്ള ഒരു സംസ്ഥാനമാണ്.',
  },
  {
    language: 'Marathi',
    text: 'महाराष्ट्र हे भारताच्या पश्चिम भागातील एक राज्य आहे.',
  },
  {
    language: 'Kannada',
    text: 'ಕರ್ನಾಟಕ ಭಾರತದ ದಕ್ಷಿಣ ಭಾಗದಲ್ಲಿರುವ ಒಂದು ರಾಜ್ಯ.',
  },
]

export const DetectView: React.FC<DetectViewProps> = ({ providers }) => {
  const [provider, setProvider] = useState('auto')
  const [modelId, setModelId] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [text, setText] = useState(
    'भारत सरकार ने राष्ट्रीय शिक्षा नीति की घोषणा की है।'
  )
  const [result, setResult] = useState<DetectResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDetect = async () => {
    if (!text.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await detectLanguage({
        text,
        provider: provider === 'auto' ? null : provider,
        model_id: modelId.trim() || null,
      })
      setResult(response)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Detection failed'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      void handleDetect()
    }
  }

  return (
    <div className="space-y-5">
      {/* Control Card */}
      <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 sm:p-5 backdrop-blur-sm shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-3 border-b border-slate-800/70">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <FileSearch className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100">
                Language &amp; Script Identification
              </h2>
              <p className="text-xs text-slate-400">
                Detect natural language from text, analyze Unicode scripts, and view candidate probabilities
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              type="button"
              onClick={() => setShowModelConfig(!showModelConfig)}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-purple-400 hover:text-purple-300 px-2 py-1 rounded bg-slate-950 border border-slate-800"
            >
              <Sliders className="w-3 h-3" />
              {showModelConfig ? 'Hide Model' : 'Custom Model'}
            </button>
            <div className="relative flex-1 sm:w-48">
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value)
                  setModelId('')
                }}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 hover:border-slate-600 rounded-xl px-3 py-2 text-xs font-medium text-slate-100 focus:outline-none focus:border-purple-500 transition"
              >
                <option value="auto">Auto (Default Route)</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id} disabled={!p.available}>
                    {p.name} {p.available ? '' : '(Unavailable)'}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-2.5 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Model ID Config Drawer */}
        {showModelConfig && (
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2 animate-in fade-in duration-150">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
              <Cpu className="w-4 h-4 text-purple-400" />
              <span>Detection Model / Service ID Override</span>
            </div>
            <input
              type="text"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              placeholder="e.g. lid.176.ftz or Bhashini detection service ID..."
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-purple-500 transition"
            />
          </div>
        )}

        {/* Sample Texts */}
        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-slate-500 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" /> Samples:
          </span>
          {SAMPLE_DETECT_TEXTS.map((sample) => (
            <button
              key={sample.language}
              type="button"
              onClick={() => {
                setText(sample.text)
                setResult(null)
              }}
              className="px-2.5 py-1 rounded-lg bg-slate-950/60 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800/80 transition"
            >
              {sample.language}
            </button>
          ))}
        </div>
      </div>

      {/* Input Box */}
      <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 sm:p-5 shadow-xl space-y-3">
        <div className="flex justify-between items-center pb-2 text-xs text-slate-400 border-b border-slate-800/80">
          <span className="font-semibold uppercase tracking-wider text-slate-300">
            Input Text
          </span>
          <span>{text.length} characters</span>
        </div>

        <textarea
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type or paste text in any Indic language or English... (Cmd+Enter to analyze)"
          className="w-full bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none resize-none font-sans text-sm leading-relaxed"
        />

        <div className="pt-2 flex justify-between items-center border-t border-slate-800/80">
          <button
            type="button"
            onClick={() => setText('')}
            className="text-xs text-slate-500 hover:text-slate-300 transition"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={() => void handleDetect()}
            disabled={loading || !text.trim()}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-xl shadow-lg shadow-purple-600/20 transition active:scale-95"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                Identify Language &amp; Script
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-950/60 border border-rose-800/70 text-rose-300 text-xs rounded-xl">
          {error}
        </div>
      )}

      {/* Results Dashboard */}
      {result && (
        <div className="space-y-4 animate-in fade-in duration-200">
          {/* Top Result Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Primary Language */}
            <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 flex items-start gap-3.5 shadow-xl">
              <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                <Globe className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Primary Detected Language
                </div>
                <div className="text-xl font-bold text-slate-100 mt-1">
                  {result.language_name || result.language || 'Unknown'}
                </div>
                <div className="text-xs font-mono text-indigo-400 mt-1">
                  ISO Code: {result.language ?? 'N/A'}
                </div>
              </div>
            </div>

            {/* Unicode Script */}
            <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 flex items-start gap-3.5 shadow-xl">
              <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
                <Type className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Unicode Script Code
                </div>
                <div className="text-xl font-bold text-slate-100 mt-1">
                  {result.script || 'Unknown / Mixed'}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Deterministic code-point range analysis
                </div>
              </div>
            </div>
          </div>

          {/* Candidate Breakdown */}
          <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Candidate Confidence Breakdown
            </div>
            <div className="space-y-3">
              {result.candidates.map((cand, idx) => {
                const percentage = Math.round(cand.confidence * 100)
                return (
                  <div key={`${cand.language}-${idx}`} className="space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-slate-200">
                        {cand.name || cand.language}{' '}
                        <span className="text-slate-500 font-mono font-normal">
                          ({cand.language})
                        </span>
                        {cand.script && (
                          <span className="ml-2 text-[11px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
                            Script: {cand.script}
                          </span>
                        )}
                      </span>
                      <span className="font-mono text-slate-300">
                        {percentage}% ({cand.confidence.toFixed(4)})
                      </span>
                    </div>
                    <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${
                          idx === 0
                            ? 'bg-gradient-to-r from-purple-500 to-indigo-500'
                            : 'bg-slate-700'
                        }`}
                        style={{ width: `${Math.max(percentage, 2)}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Metadata Footer */}
            <div className="pt-3 mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-400 border-t border-slate-800/80">
              <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 font-medium">
                Provider: {result.provider}
              </span>
              {result.model_id && (
                <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 font-mono text-[11px]">
                  Model: {result.model_id}
                </span>
              )}
              <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 font-mono text-[11px]">
                {Math.round(result.elapsed_seconds * 1000)}ms
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 font-mono text-[11px]">
                {result.cached ? 'Cache HIT' : 'Computed Live'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
export default DetectView
