import React, { useState } from 'react'
import {
  FileSearch,
  Globe,
  Loader2,
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
]

export const DetectView: React.FC<DetectViewProps> = ({ providers }) => {
  const [provider, setProvider] = useState('auto')
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
      })
      setResult(response)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Detection failed'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 sm:p-6 backdrop-blur-sm">
        {/* Controls Bar */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-4 border-b border-slate-800">
          <div>
            <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <FileSearch className="w-4 h-4 text-indigo-400" />
              Language & Script Identification
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Identify natural language, Unicode script, and candidate probabilities
            </p>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <label className="text-xs font-medium text-slate-400 whitespace-nowrap">
              Engine:
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 transition w-full sm:w-48"
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

        {/* Sample Texts */}
        <div className="flex flex-wrap items-center gap-2 pt-3 pb-1 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-slate-500">
            <Sparkles className="w-3.5 h-3.5" /> Samples:
          </span>
          {SAMPLE_DETECT_TEXTS.map((sample) => (
            <button
              key={sample.language}
              type="button"
              onClick={() => {
                setText(sample.text)
                setResult(null)
              }}
              className="px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition"
            >
              {sample.language}
            </button>
          ))}
        </div>

        {/* Input Text Area */}
        <div className="mt-4 bg-slate-950/80 border border-slate-800 rounded-lg p-3">
          <div className="flex justify-between items-center pb-2 text-xs text-slate-400 border-b border-slate-800/80">
            <span className="font-semibold tracking-wide uppercase text-slate-400">
              Input Text
            </span>
            <span>{text.length} characters</span>
          </div>
          <textarea
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type or paste text in any Indic language or English..."
            className="w-full mt-2 bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none resize-none font-mono text-sm leading-relaxed"
          />
          <div className="pt-2 flex justify-between items-center border-t border-slate-800/80 mt-2">
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
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-lg shadow-sm transition"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Zap className="w-3.5 h-3.5" />
                  Detect Language
                </>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs rounded-lg">
            {error}
          </div>
        )}

        {/* Detection Results */}
        {result && (
          <div className="mt-6 space-y-4">
            {/* Top Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Primary Language Card */}
              <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4 flex items-start gap-3">
                <div className="p-2.5 rounded-lg bg-indigo-950/50 border border-indigo-800/40 text-indigo-400">
                  <Globe className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-400">
                    Primary Detected Language
                  </div>
                  <div className="text-lg font-bold text-slate-100 mt-0.5">
                    {result.language_name || result.language || 'Unknown'}
                  </div>
                  <div className="text-xs font-mono text-indigo-400 mt-0.5">
                    Tag: {result.language ?? 'N/A'}
                  </div>
                </div>
              </div>

              {/* Script Card */}
              <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4 flex items-start gap-3">
                <div className="p-2.5 rounded-lg bg-purple-950/50 border border-purple-800/40 text-purple-400">
                  <Type className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-400">
                    Unicode Script
                  </div>
                  <div className="text-lg font-bold text-slate-100 mt-0.5">
                    {result.script || 'Unknown / Mixed'}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">
                    Deterministic Unicode code-point analysis
                  </div>
                </div>
              </div>
            </div>

            {/* Candidates Table */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                Candidate Probabilities
              </div>
              <div className="space-y-3">
                {result.candidates.map((cand, idx) => {
                  const percentage = Math.round(cand.confidence * 100)
                  return (
                    <div key={`${cand.language}-${idx}`} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium text-slate-200">
                          {cand.name || cand.language}{' '}
                          <span className="text-slate-500 font-mono">
                            ({cand.language})
                          </span>
                        </span>
                        <span className="font-mono text-slate-300">
                          {percentage}% ({cand.confidence.toFixed(4)})
                        </span>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            idx === 0 ? 'bg-indigo-500' : 'bg-slate-600'
                          }`}
                          style={{ width: `${Math.max(percentage, 2)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Metadata Footer */}
              <div className="pt-4 mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-400 border-t border-slate-800/80">
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  Provider: {result.provider}
                </span>
                {result.model_id && (
                  <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-400">
                    Model: {result.model_id}
                  </span>
                )}
                <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-400">
                  {Math.round(result.elapsed_seconds * 1000)}ms
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-400">
                  {result.cached ? 'Cache HIT' : 'Computed Live'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
