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

export const TTSView: React.FC<TTSViewProps> = ({ languages, providers }) => {
  const [text, setText] = useState('नमस्ते, आपका स्वागत है।')
  const [language, setLanguage] = useState('hi')
  const [provider, setProvider] = useState('auto')
  const [parameters, setParameters] = useState('{}')
  const [result, setResult] = useState<TTSResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSynthesize = async () => {
    if (!text.trim()) return
    if ((provider === 'sarvam' || (provider === 'auto' && providers.find((item) => item.available)?.id === 'sarvam')) && !language) {
      setError('Sarvam TTS requires a language.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const parsed: unknown = JSON.parse(parameters || '{}')
      if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('Model options must be a JSON object')
      }
      const response = await synthesizeSpeech({
        text,
        language: language || null,
        parameters: parsed as Record<string, unknown>,
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

  return (
    <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-3 bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Text to speech</h2>
          <p className="text-sm text-slate-400 mt-1">Create speech with a configured voice model.</p>
        </div>

        <label className="block text-xs font-medium text-slate-400">
          Text
          <textarea value={text} onChange={(event) => setText(event.target.value)} rows={6}
            className="block w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-3 text-sm leading-6 text-slate-100 focus:outline-none focus:border-indigo-500 resize-y" />
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="text-xs font-medium text-slate-400">
            Language
            <select value={language} onChange={(event) => setLanguage(event.target.value)}
              className="block w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100">
              <option value="">Unspecified (model decides)</option>
              {languages.map((item) => (
                <option key={item.tag} value={item.code}>{item.name} ({item.code})</option>
              ))}
            </select>
          </label>
          <label className='text-xs font-medium text-slate-400'>
            Provider
            <select value={provider} onChange={(event) => {
              const selected = event.target.value
              setProvider(selected)
              if (selected === 'sarvam') {
                setParameters('{"speaker":"shubh","pace":1}')
              } else if (selected === 'bhashini') {
                setParameters('{"gender":"female","samplingRate":16000}')
              } else if (selected === 'edge_tts') {
                setParameters('{"gender":"female","rate":"+0%","pitch":"+0Hz"}')
              } else {
                setParameters('{}')
              }
            }}
              className='block w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100'>
              <option value='auto'>Auto</option>
              {providers.map((item) => (
                <option key={item.id} value={item.id} disabled={!item.available}>
                  {item.name}{item.available ? '' : ' (Unavailable)'}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className='block text-xs font-medium text-slate-400'>
          Model options (JSON)
          <textarea value={parameters} onChange={(event) => setParameters(event.target.value)} rows={3}
            spellCheck={false}
            className='block w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-3 font-mono text-xs leading-5 text-slate-100 focus:outline-none focus:border-indigo-500 resize-y' />
        </label>
        <p className='text-xs text-slate-500'>
          Passed to the selected model. Edge TTS supports gender, voice, rate, pitch, and volume; Bhashini accepts model-specific keys; Sarvam accepts speaker and pace.
        </p>
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
            </dl>
            <p className="text-xs text-slate-500">
              {result.cache_backend === 'none'
                ? 'No cache · Sent to provider'
                : result.cached
                  ? `Cache hit (${result.cache_backend})`
                  : `Fresh result (${result.cache_backend})`}
            </p>
          </div>
        ) : (
          <p className="text-sm text-slate-500 pt-4">Generated speech will appear here.</p>
        )}
      </div>
    </section>
  )
}
