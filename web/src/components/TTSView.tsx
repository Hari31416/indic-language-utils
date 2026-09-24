import React, { useState } from 'react'
import {
  ChevronDown,
  Cpu,
  Download,
  Loader2,
  Sliders,
  Sparkles,
  Volume2,
  Zap,
} from 'lucide-react'
import { synthesizeSpeech } from '../api'
import type { LanguageItem, ProviderInfo, TTSResponse } from '../types'

interface TTSViewProps {
  languages: LanguageItem[]
  providers: ProviderInfo[]
}

const AUDIO_MIME: Record<string, string> = {
  wav: 'audio/wav',
  mp3: 'audio/mpeg',
  ogg: 'audio/ogg',
  flac: 'audio/flac',
}

const TTS_SAMPLE_TEXTS = [
  {
    lang: 'hi',
    title: 'Hindi Greeting',
    text: 'नमस्ते! भारतीय भाषा यूटिलिटीज वर्कबेंच में आपका स्वागत है।',
  },
  {
    lang: 'ta',
    title: 'Tamil Greeting',
    text: 'வணக்கம்! இந்திய மொழி கருவிகள் தளத்திற்கு தங்களை அன்புடன் வரவேற்கிறோம்.',
  },
  {
    lang: 'te',
    title: 'Telugu Greeting',
    text: 'నమస్కారం! భారతీయ భాషా యుటిలిటీస్ వర్క్‌బెంచ్‌కు స్వాగతం.',
  },
  {
    lang: 'bn',
    title: 'Bengali Greeting',
    text: 'নমস্কার! ভারতীয় ভাষা ইউটিলিটিস ওয়ার্কবেঞ্চে আপনাকে স্বাগতম।',
  },
  {
    lang: 'en',
    title: 'English Announcement',
    text: 'Welcome to Indic Language Utils workbench. High-performance voice synthesis is active.',
  },
]

const TTS_MODEL_PRESETS: Record<string, string[]> = {
  sarvam: ['bulbul:v1', 'bulbul:v2'],
  bhashini: ['ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4'],
  edge_tts: [
    'hi-IN-SwaraNeural',
    'hi-IN-MadhurNeural',
    'en-IN-NeerjaNeural',
    'en-IN-PrabhatNeural',
    'ta-IN-PallaviNeural',
    'te-IN-MohanNeural',
    'bn-IN-TanishaaNeural',
    'mr-IN-AarohiNeural',
    'gu-IN-DhwaniNeural',
  ],
}

type Fields = Record<string, string>
type ProviderFields = Record<string, Fields>

const initialFields: ProviderFields = {
  edge_tts: { gender: 'female', voice: '', rate: '', pitch: '', volume: '' },
  sarvam: { speaker: 'shubh', pace: '1.0' },
  bhashini: { gender: 'female', voiceId: '', samplingRate: '16000' },
}

function parseObject(value: string, label: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value || '{}')
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`${label} must be a JSON object`)
  }
  return parsed as Record<string, unknown>
}

export const TTSView: React.FC<TTSViewProps> = ({ languages, providers }) => {
  const [text, setText] = useState('नमस्ते! भारतीय भाषा यूटिलिटीज वर्कबेंच में आपका स्वागत है।')
  const [language, setLanguage] = useState('hi')
  const [provider, setProvider] = useState('auto')
  const [modelId, setModelId] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [fields, setFields] = useState<ProviderFields>(initialFields)
  const [advanced, setAdvanced] = useState('{}')
  const [result, setResult] = useState<TTSResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const updateField = (key: string, value: string) => {
    setFields((current) => ({
      ...current,
      [provider]: { ...current[provider], [key]: value },
    }))
  }

  const handleSynthesize = async () => {
    if (!text.trim()) return
    if (provider === 'sarvam' && !language) {
      setError('Sarvam TTS requires a language to be specified.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const extra = parseObject(advanced, provider === 'auto' ? 'Provider settings' : 'Extra options')
      let parameters: Record<string, unknown> = {}
      let providerParameters: Record<string, Record<string, unknown>> = {}

      if (provider === 'auto') {
        for (const [name, value] of Object.entries(extra)) {
          if (value === null || Array.isArray(value) || typeof value !== 'object') {
            throw new Error(`Settings for ${name} must be a JSON object`)
          }
          providerParameters[name] = value as Record<string, unknown>
        }
      } else {
        const selectedFields = fields[provider] ?? {}
        parameters = Object.fromEntries(
          Object.entries(selectedFields).filter(([, value]) => value.trim() !== '')
        )
        if (provider === 'sarvam' && parameters.pace !== undefined) {
          const pace = Number(parameters.pace)
          if (!Number.isFinite(pace) || pace <= 0) throw new Error('Pace must be positive')
          parameters.pace = pace
        }
        if (provider === 'bhashini' && parameters.samplingRate !== undefined) {
          const rate = Number(parameters.samplingRate)
          if (!Number.isInteger(rate) || rate <= 0) throw new Error('Sample rate must be positive')
          parameters.samplingRate = rate
        }
        parameters = { ...parameters, ...extra }
      }

      const response = await synthesizeSpeech({
        text,
        language: language || null,
        parameters,
        provider_parameters: providerParameters,
        provider: provider === 'auto' ? null : provider,
        model_id: modelId.trim() || null,
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Speech synthesis failed')
    } finally {
      setLoading(false)
    }
  }

  const format = result?.audio_format?.toLowerCase() ?? 'wav'
  const audioUrl = result
    ? `data:${AUDIO_MIME[format] ?? 'application/octet-stream'};base64,${result.audio_base64}`
    : null

  const activeModelPresets = TTS_MODEL_PRESETS[provider] ?? []

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Left Column: Voice Synthesis Controls */}
      <div className="lg:col-span-7 bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 sm:p-6 backdrop-blur-sm shadow-xl space-y-5">
        <div className="flex items-center gap-3 pb-3 border-b border-slate-800/70">
          <div className="p-2 rounded-xl bg-violet-500/10 text-violet-400 border border-violet-500/20">
            <Volume2 className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Text to Speech (TTS)</h2>
            <p className="text-xs text-slate-400">
              Synthesize natural Indian speech using Edge TTS, Sarvam Bulbul, or Bhashini Indic-TTS
            </p>
          </div>
        </div>

        {/* Text Input */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
            Text to Synthesize
          </label>
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={5}
            placeholder="Type text in native script or English..."
            className="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-3 text-sm text-slate-100 focus:outline-none focus:border-violet-500 resize-y leading-relaxed"
          />
        </div>

        {/* Sample Texts */}
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-slate-500 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-violet-400" /> Samples:
          </span>
          {TTS_SAMPLE_TEXTS.map((sample) => (
            <button
              key={sample.title}
              type="button"
              onClick={() => {
                setLanguage(sample.lang)
                setText(sample.text)
                setResult(null)
              }}
              className="px-2.5 py-1 rounded-lg bg-slate-950/60 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800/80 transition"
            >
              {sample.title}
            </button>
          ))}
        </div>

        {/* Language & Provider Selection */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Language
            </label>
            <div className="relative">
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs font-medium text-slate-100 focus:outline-none focus:border-violet-500"
              >
                <option value="">Unspecified</option>
                {languages.map((item) => (
                  <option key={item.tag} value={item.code}>
                    {item.name} ({item.code})
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-3 pointer-events-none" />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
                Engine
              </label>
              <button
                type="button"
                onClick={() => setShowModelConfig(!showModelConfig)}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-violet-400 hover:text-violet-300"
              >
                <Sliders className="w-3 h-3" />
                {showModelConfig ? 'Hide Model' : 'Custom Model'}
              </button>
            </div>
            <div className="relative">
              <select
                value={provider}
                onChange={(event) => {
                  setProvider(event.target.value)
                  setModelId('')
                  setAdvanced('{}')
                }}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs font-medium text-slate-100 focus:outline-none focus:border-violet-500"
              >
                <option value="auto">Auto (Default Route)</option>
                {providers.map((item) => (
                  <option key={item.id} value={item.id} disabled={!item.available}>
                    {item.name} {item.available ? '' : '(Unavailable)'}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-3 pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Model ID Config Drawer */}
        {showModelConfig && (
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2.5 animate-in fade-in duration-150">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <Cpu className="w-4 h-4 text-violet-400" />
                <span>TTS Model / Voice ID Override</span>
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
                          ? 'bg-violet-600 text-white'
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
                  ? 'Default: bulbul:v1 (or bulbul:v2)'
                  : provider === 'bhashini'
                    ? 'Default: configured Bhashini TTS model'
                    : provider === 'edge_tts'
                      ? 'Default: hi-IN-SwaraNeural (or hi-IN-MadhurNeural, en-IN-NeerjaNeural...)'
                      : 'Enter model ID or voice ID override...'
              }
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-violet-500 transition"
            />
          </div>
        )}

        {/* Provider-Specific Voice Controls */}
        {provider !== 'auto' && (
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-violet-300">
              Voice Parameters
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {provider === 'edge_tts' && (
                <>
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-400">Gender</label>
                    <select
                      value={fields.edge_tts.gender}
                      onChange={(event) => updateField('gender', event.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100"
                    >
                      <option value="female">Female</option>
                      <option value="male">Male</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-400">Voice Name Override</label>
                    <input
                      value={fields.edge_tts.voice}
                      onChange={(event) => updateField('voice', event.target.value)}
                      placeholder="e.g. hi-IN-SwaraNeural"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-400">Rate</label>
                    <input
                      value={fields.edge_tts.rate}
                      onChange={(event) => updateField('rate', event.target.value)}
                      placeholder="+0% (e.g. +10%)"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-400">Pitch</label>
                    <input
                      value={fields.edge_tts.pitch}
                      onChange={(event) => updateField('pitch', event.target.value)}
                      placeholder="+0Hz"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100"
                    />
                  </div>
                </>
              )}

              {provider === 'sarvam' && (
                <>
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-400">Speaker Name</label>
                    <select
                      value={fields.sarvam.speaker}
                      onChange={(event) => updateField('speaker', event.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100"
                    >
                      <option value="shubh">shubh (Male)</option>
                      <option value="arvind">arvind (Male)</option>
                      <option value="amartya">amartya (Male)</option>
                      <option value="priya">priya (Female)</option>
                      <option value="meera">meera (Female)</option>
                      <option value="pavithra">pavithra (Female)</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-400">Speech Pace (Pace)</label>
                    <input
                      type="number"
                      min="0.5"
                      max="2.0"
                      step="0.1"
                      value={fields.sarvam.pace}
                      onChange={(event) => updateField('pace', event.target.value)}
                      placeholder="1.0"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100"
                    />
                  </div>
                </>
              )}

              {provider === 'bhashini' && (
                <>
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-400">Gender</label>
                    <select
                      value={fields.bhashini.gender}
                      onChange={(event) => updateField('gender', event.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100"
                    >
                      <option value="female">Female</option>
                      <option value="male">Male</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-400">Sample Rate (Hz)</label>
                    <input
                      type="number"
                      min="8000"
                      step="1000"
                      value={fields.bhashini.samplingRate}
                      onChange={(event) => updateField('samplingRate', event.target.value)}
                      placeholder="16000"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100"
                    />
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        <button
          type="button"
          disabled={!text.trim() || loading}
          onClick={() => void handleSynthesize()}
          className="w-full inline-flex items-center justify-center gap-2 px-5 py-3 bg-violet-600 hover:bg-violet-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-xl shadow-lg shadow-violet-600/20 transition active:scale-95"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Synthesizing Speech...
            </>
          ) : (
            <>
              <Zap className="w-4 h-4" />
              Generate Speech
            </>
          )}
        </button>

        {error && (
          <div className="p-3 bg-rose-950/60 border border-rose-800/70 text-rose-300 text-xs rounded-xl">
            {error}
          </div>
        )}
      </div>

      {/* Right Column: Audio Output */}
      <div className="lg:col-span-5 bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 sm:p-6 backdrop-blur-sm shadow-xl flex flex-col min-h-[380px]">
        <div className="flex justify-between items-center pb-3 text-xs text-slate-400 border-b border-slate-800/80">
          <span className="font-semibold uppercase tracking-wider text-slate-300">
            Generated Speech Audio
          </span>
          {result && (
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px] uppercase">
              {format}
            </span>
          )}
        </div>

        <div className="flex-1 mt-4 flex flex-col justify-between">
          {result && audioUrl ? (
            <div className="space-y-5">
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
                <audio controls src={audioUrl} className="w-full" aria-label="Generated speech" />
              </div>

              <a
                href={audioUrl}
                download={`${result.provider}-speech.${format}`}
                className="inline-flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white border border-slate-700/80 text-xs font-semibold transition"
              >
                <Download className="w-4 h-4 text-violet-400" /> Download Audio File
              </a>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-48 text-center text-slate-500">
              <Volume2 className="w-10 h-10 mb-2 opacity-40" />
              <span className="text-sm font-medium">No audio generated yet</span>
              <span className="text-xs mt-1">Enter text and click Generate Speech</span>
            </div>
          )}

          {result && (
            <div className="pt-4 border-t border-slate-800/80 space-y-2 text-xs text-slate-400">
              <div className="flex justify-between">
                <span>Provider:</span>
                <span className="text-slate-200 font-medium">{result.provider}</span>
              </div>
              <div className="flex justify-between">
                <span>Language:</span>
                <span className="text-slate-200">{result.language ?? 'Auto'}</span>
              </div>
              {result.model_id && (
                <div className="flex justify-between">
                  <span>Model ID:</span>
                  <span className="text-slate-200 font-mono text-[11px] break-all">
                    {result.model_id}
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Route Fallbacks:</span>
                <span className="text-slate-200">{result.fallback_count}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
export default TTSView
