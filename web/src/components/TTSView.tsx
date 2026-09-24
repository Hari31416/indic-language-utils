import React, { useState } from 'react'
import { Download, Loader2, Volume2 } from 'lucide-react'
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

type Fields = Record<string, string>
type ProviderFields = Record<string, Fields>

const initialFields: ProviderFields = {
  edge_tts: { gender: 'female', voice: '', rate: '', pitch: '', volume: '' },
  sarvam: { speaker: '', pace: '' },
  bhashini: { gender: 'female', voiceId: '', samplingRate: '' },
}

function parseObject(value: string, label: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value || '{}')
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`${label} must be a JSON object`)
  }
  return parsed as Record<string, unknown>
}

export const TTSView: React.FC<TTSViewProps> = ({ languages, providers }) => {
  const [text, setText] = useState('नमस्ते, आपका स्वागत है।')
  const [language, setLanguage] = useState('hi')
  const [provider, setProvider] = useState('auto')
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
      setError('Sarvam TTS requires a language.')
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
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Speech synthesis failed')
    } finally {
      setLoading(false)
    }
  }

  const format = result?.audio_format?.toLowerCase() ?? ''
  const audioUrl = result
    ? `data:${AUDIO_MIME[format] ?? 'application/octet-stream'};base64,${result.audio_base64}`
    : null
  const inputClass = 'block w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500'
  const labelClass = 'block text-xs font-medium text-slate-400'

  return (
    <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-3 bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Text to speech</h2>
          <p className="text-sm text-slate-400 mt-1">Try a voice, adjust its settings, then listen or download.</p>
        </div>
        <label className={labelClass}>
          Text
          <textarea value={text} onChange={(event) => setText(event.target.value)} rows={6}
            className={`${inputClass} py-3 leading-6 resize-y`} />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className={labelClass}>
            Language
            <select value={language} onChange={(event) => setLanguage(event.target.value)} className={inputClass}>
              <option value="">Unspecified</option>
              {languages.map((item) => (
                <option key={item.tag} value={item.code}>{item.name} ({item.code})</option>
              ))}
            </select>
          </label>
          <label className={labelClass}>
            Provider
            <select value={provider} onChange={(event) => { setProvider(event.target.value); setAdvanced('{}') }} className={inputClass}>
              <option value="auto">Auto route</option>
              {providers.map((item) => (
                <option key={item.id} value={item.id} disabled={!item.available}>
                  {item.name}{item.available ? '' : ' (Unavailable)'}
                </option>
              ))}
            </select>
          </label>
        </div>

        {provider === 'auto' ? (
          <p className="text-xs text-slate-400 border-l-2 border-indigo-500 pl-3">
            Auto route uses each provider's defaults. Select a provider to adjust its voice. To set options for fallback providers, enter a JSON object keyed by provider ID below.
          </p>
        ) : (
          <fieldset className="border border-slate-800 rounded-lg p-4">
            <legend className="px-2 text-xs font-semibold uppercase tracking-wider text-indigo-300">Voice controls</legend>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {provider === 'edge_tts' && <>
                <label className={labelClass}>Gender
                  <select value={fields.edge_tts.gender} onChange={(event) => updateField('gender', event.target.value)} className={inputClass}>
                    <option value="female">Female</option><option value="male">Male</option>
                  </select>
                </label>
                <label className={labelClass}>Voice ID override
                  <input value={fields.edge_tts.voice} onChange={(event) => updateField('voice', event.target.value)} placeholder="hi-IN-SwaraNeural" className={inputClass} />
                </label>
                <label className={labelClass}>Rate
                  <input value={fields.edge_tts.rate} onChange={(event) => updateField('rate', event.target.value)} placeholder="+10%" className={inputClass} />
                </label>
                <label className={labelClass}>Pitch
                  <input value={fields.edge_tts.pitch} onChange={(event) => updateField('pitch', event.target.value)} placeholder="+2Hz" className={inputClass} />
                </label>
                <label className={labelClass}>Volume
                  <input value={fields.edge_tts.volume} onChange={(event) => updateField('volume', event.target.value)} placeholder="+0%" className={inputClass} />
                </label>
              </>}
              {provider === 'sarvam' && <>
                <label className={labelClass}>Speaker
                  <input value={fields.sarvam.speaker} onChange={(event) => updateField('speaker', event.target.value)} placeholder="shubh" className={inputClass} />
                </label>
                <label className={labelClass}>Pace
                  <input type="number" min="0.1" step="0.1" value={fields.sarvam.pace} onChange={(event) => updateField('pace', event.target.value)} placeholder="1.0" className={inputClass} />
                </label>
              </>}
              {provider === 'bhashini' && <>
                <label className={labelClass}>Gender
                  <select value={fields.bhashini.gender} onChange={(event) => updateField('gender', event.target.value)} className={inputClass}>
                    <option value="female">Female</option><option value="male">Male</option>
                  </select>
                </label>
                <label className={labelClass}>Voice ID
                  <input value={fields.bhashini.voiceId} onChange={(event) => updateField('voiceId', event.target.value)} placeholder="Model-specific" className={inputClass} />
                </label>
                <label className={labelClass}>Sample rate (Hz)
                  <input type="number" min="1" step="1" value={fields.bhashini.samplingRate} onChange={(event) => updateField('samplingRate', event.target.value)} placeholder="16000" className={inputClass} />
                </label>
              </>}
            </div>
            {provider === 'bhashini' && <p className="text-xs text-slate-500 mt-3">Available voices and sample rates depend on the configured Bhashini model.</p>}
          </fieldset>
        )}

        <details className="border border-slate-800 rounded-lg p-4">
          <summary className="text-xs font-medium text-slate-300 cursor-pointer">Advanced settings (JSON)</summary>
          <label className={`${labelClass} mt-3`}>
            {provider === 'auto' ? 'Options by provider ID' : 'Extra model options'}
            <textarea value={advanced} onChange={(event) => setAdvanced(event.target.value)} rows={3} spellCheck={false}
              placeholder={provider === 'auto' ? '{"edge_tts":{"rate":"+10%"}}' : '{}'}
              className={`${inputClass} py-3 font-mono resize-y`} />
          </label>
          <p className="text-xs text-slate-500 mt-2">Extra options override the visible controls for the selected provider.</p>
        </details>
        <button type="button" disabled={!text.trim() || loading} onClick={() => void handleSynthesize()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium text-white transition">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Volume2 className="w-4 h-4" />}
          {loading ? 'Generating...' : 'Generate speech'}
        </button>
        {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
      </div>

      <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 min-h-56">
        <h3 className="text-sm font-semibold text-slate-200 pb-3 border-b border-slate-800">Generated audio</h3>
        {result && audioUrl ? (
          <div className="pt-4 space-y-5">
            {format in AUDIO_MIME ? (
              <audio controls src={audioUrl} className="w-full" aria-label="Generated speech" />
            ) : (
              <p className="text-sm text-slate-400">This audio format may not play in the browser. Download the file instead.</p>
            )}
            <a href={audioUrl} download={`${result.provider}-speech.${format || 'bin'}`}
              className="inline-flex items-center gap-2 text-sm text-indigo-300 hover:text-indigo-200">
              <Download className="w-4 h-4" /> Download audio
            </a>
            <dl className="text-xs text-slate-400 space-y-1 border-t border-slate-800 pt-3">
              <div className="flex justify-between gap-4"><dt>Provider</dt><dd>{result.provider}</dd></div>
              <div className="flex justify-between gap-4"><dt>Language</dt><dd>{result.language ?? 'Unspecified'}</dd></div>
              {result.model_id && <div className="flex justify-between gap-4"><dt>Model</dt><dd className="break-all text-right">{result.model_id}</dd></div>}
              <div className="flex justify-between gap-4"><dt>Route fallback</dt><dd>{result.fallback_count}</dd></div>
            </dl>
          </div>
        ) : (
          <p className="text-sm text-slate-500 pt-4">Generated speech will appear here.</p>
        )}
      </div>
    </section>
  )
}
