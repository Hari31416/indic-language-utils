import React, { useState } from 'react'
import {
  Check,
  ChevronDown,
  Copy,
  FileSearch,
  Globe,
  Loader2,
  Sliders,
  Sparkles,
  Type,
  Zap,
} from 'lucide-react'
import { detectLanguage } from '../api'
import { useLocalHistory } from '../history'
import type { DetectResponse, ProviderInfo } from '../types'
import {
  ErrorBox,
  Field,
  HistoryStrip,
  MetaBar,
  ModelDrawer,
  ToolHeader,
} from './ui'

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

interface Hist {
  text: string
  lang: string
  script: string
}

export const DetectView: React.FC<DetectViewProps> = ({ providers }) => {
  const [provider, setProvider] = useState('auto')
  const [modelId, setModelId] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [text, setText] = useState(
    'भारत सरकार ने राष्ट्रीय शिक्षा नीति की घोषणा की है।',
  )
  const [result, setResult] = useState<DetectResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const { items: history, push, clear } = useLocalHistory<Hist>('ilu-hist-detect')

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
      push({
        text,
        lang: response.language_name || response.language || 'Unknown',
        script: response.script || '—',
      })
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

  const handleCopySummary = async () => {
    if (!result) return
    const top = result.candidates[0]
    await navigator.clipboard.writeText(
      `Language: ${result.language_name || result.language || 'Unknown'} (${result.language ?? 'n/a'}), Script: ${result.script || 'unknown'}${top ? `, confidence: ${(top.confidence * 100).toFixed(2)}%` : ''}`,
    )
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-5">
      <ToolHeader
        icon={<FileSearch className="h-4 w-4" />}
        tileClass="border-orchid-500/30 bg-orchid-500/10 text-orchid-300"
        title="Detection & Script"
        blurb="Detect the natural language behind any text, analyze its Unicode script, and inspect candidate probabilities."
        glyph="इ"
      />

      <div className="panel space-y-4 p-4 sm:p-5">
        <div className="grid grid-cols-1 items-end gap-3 md:grid-cols-[1fr_240px]">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="flex items-center gap-1 font-medium text-parchment-500">
              <Sparkles className="h-3.5 w-3.5 text-orchid-300" /> Samples:
            </span>
            {SAMPLE_DETECT_TEXTS.map((sample) => (
              <button
                key={sample.language}
                type="button"
                onClick={() => {
                  setText(sample.text)
                  setResult(null)
                }}
                className="sample-btn"
              >
                {sample.language}
              </button>
            ))}
          </div>
          <Field
            label="Engine"
            action={
              <button
                type="button"
                onClick={() => setShowModelConfig(!showModelConfig)}
                className="link-accent"
              >
                <Sliders className="h-3 w-3" />
                {showModelConfig ? 'Hide' : 'Custom'}
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
                className="field !py-2 text-xs"
              >
                <option value="auto">Auto (Default Route)</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id} disabled={!p.available}>
                    {p.name} {p.available ? '' : '(Unavailable)'}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-3 h-3.5 w-3.5 text-parchment-500" />
            </div>
          </Field>
        </div>

        <ModelDrawer
          open={showModelConfig}
          title="Detection Model / Service ID Override"
          presets={[]}
          modelId={modelId}
          onChange={setModelId}
          placeholder="e.g. lid.176.ftz or Bhashini detection service ID..."
        />

        <HistoryStrip
          items={history}
          onClear={clear}
          onRestore={(h) => {
            setText(h.text)
            setResult(null)
          }}
          renderLabel={(h) => `${h.lang} · ${h.text.slice(0, 28)}${h.text.length > 28 ? '…' : ''}`}
          renderSub={(h) => h.text}
        />
      </div>

      <div className="panel flex flex-col p-4 sm:p-5">
        <div className="flex items-center justify-between border-b divider pb-2.5">
          <span className="text-xs font-bold uppercase tracking-[0.14em] text-parchment-300">
            Input text
          </span>
          <span className="text-xs text-parchment-500">{text.length} characters</span>
        </div>
        <textarea
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type or paste text in any Indic language or English…"
          className="mt-3 w-full resize-none bg-transparent text-[15px] leading-relaxed text-parchment-100 placeholder:text-parchment-600 focus:outline-none"
        />
        <div className="mt-2 flex items-center justify-between border-t divider pt-3">
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setText('')} className="btn-quiet">
              Clear
            </button>
            <span className="hidden items-center gap-1 text-[11px] text-parchment-600 sm:flex">
              <span className="kbd">⌘</span>+<span className="kbd">↵</span> to run
            </span>
          </div>
          <button
            type="button"
            onClick={() => void handleDetect()}
            disabled={loading || !text.trim()}
            className="btn-primary"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Analyzing…
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" /> Identify language & script
              </>
            )}
          </button>
        </div>
      </div>

      {error && <ErrorBox message={error} />}

      {result && (
        <div className="animate-fade-in space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="panel relative overflow-hidden p-5">
              <span aria-hidden className="glyph-mark absolute -right-1 -top-6 text-[88px]">
                {result.language_name?.charAt(0) ?? 'अ'}
              </span>
              <div className="relative flex items-start gap-3.5">
                <div className="rounded-xl border border-marigold-500/30 bg-marigold-500/10 p-3 text-marigold-300">
                  <Globe className="h-6 w-6" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="eyebrow">Detected language</div>
                  <div className="mt-1 truncate font-display text-2xl font-semibold tracking-tight">
                    {result.language_name || result.language || 'Unknown'}
                  </div>
                  <div className="mt-1 font-mono text-xs text-marigold-300">
                    ISO · {result.language ?? 'n/a'}
                  </div>
                </div>
              </div>
            </div>

            <div className="panel relative overflow-hidden p-5">
              <span aria-hidden className="glyph-mark absolute -right-1 -top-6 text-[88px]">
                {result.script?.charAt(0) ?? '§'}
              </span>
              <div className="relative flex items-start gap-3.5">
                <div className="rounded-xl border border-orchid-500/30 bg-orchid-500/10 p-3 text-orchid-300">
                  <Type className="h-6 w-6" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="eyebrow">Unicode script</div>
                  <div className="mt-1 truncate font-display text-2xl font-semibold tracking-tight">
                    {result.script || 'Unknown / Mixed'}
                  </div>
                  <div className="mt-1 text-xs text-parchment-500">
                    Deterministic code-point range analysis
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="panel space-y-4 p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-[0.14em] text-parchment-300">
                Candidate confidence
              </span>
              <button type="button" onClick={() => void handleCopySummary()} className="btn-ghost">
                {copied ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-moss-300" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" /> Copy summary
                  </>
                )}
              </button>
            </div>
            <div className="space-y-3.5">
              {result.candidates.map((cand, idx) => {
                const percentage = Math.round(cand.confidence * 100)
                return (
                  <div key={`${cand.language}-${idx}`} className="space-y-1.5">
                    <div className="flex items-baseline justify-between gap-2 text-xs">
                      <span className="min-w-0 truncate font-semibold text-parchment-100">
                        {cand.name || cand.language}{' '}
                        <span className="font-mono font-normal text-parchment-500">
                          ({cand.language})
                        </span>
                        {cand.script && (
                          <span className="ml-2 rounded bg-ink-700/70 px-1.5 py-px text-[11px] text-parchment-400">
                            {cand.script}
                          </span>
                        )}
                      </span>
                      <span className="shrink-0 font-mono text-parchment-300">
                        {percentage}% · {cand.confidence.toFixed(4)}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full border border-ink-700 bg-ink-900">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${
                          idx === 0
                            ? 'bg-gradient-to-r from-orchid-500 via-marigold-400 to-marigold-300'
                            : 'bg-ink-600'
                        }`}
                        style={{ width: `${Math.max(percentage, 2)}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
            <MetaBar
              items={[
                { label: 'Provider', value: result.provider },
                ...(result.model_id ? [{ label: 'Model', value: result.model_id }] : []),
                { label: 'Time', value: `${Math.round(result.elapsed_seconds * 1000)}ms` },
                result.cached
                  ? { label: 'Cache', value: 'HIT', tone: 'hit' as const }
                  : { label: 'Cache', value: 'Computed live' },
              ]}
            />
          </div>
        </div>
      )}
    </div>
  )
}
export default DetectView
