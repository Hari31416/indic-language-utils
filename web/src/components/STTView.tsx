import React, { useEffect, useState } from 'react'
import { FileAudio2, Loader2 } from 'lucide-react'
import { transcribeAudio } from '../api'
import type { LanguageItem, ProviderInfo, STTResponse } from '../types'

interface STTViewProps {
  languages: LanguageItem[]
  providers: ProviderInfo[]
}

const MAX_AUDIO_BYTES = 10 * 1024 * 1024
const FORMATS = ['wav', 'flac', 'mp3', 'ogg']

async function wavSampleRate(file: File): Promise<number | null> {
  const header = await file.slice(0, 65536).arrayBuffer()
  if (header.byteLength < 28) return null
  const bytes = new Uint8Array(header)
  const signature = (start: number) => String.fromCharCode(...bytes.slice(start, start + 4))
  if (signature(0) !== 'RIFF' || signature(8) !== 'WAVE') return null
  const view = new DataView(header)
  let offset = 12
  while (offset + 8 <= header.byteLength) {
    const size = view.getUint32(offset + 4, true)
    if (signature(offset) === 'fmt ' && size >= 16 && offset + 20 <= header.byteLength) {
      return view.getUint32(offset + 12, true)
    }
    offset += 8 + size + (size % 2)
  }
  return null
}

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Could not read the audio file'))
    reader.onload = () => {
      const value = reader.result
      if (typeof value !== 'string') {
        reject(new Error('Could not read the audio file'))
        return
      }
      resolve(value.split(',', 2)[1] ?? '')
    }
    reader.readAsDataURL(file)
  })
}

export const STTView: React.FC<STTViewProps> = ({ languages, providers }) => {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [language, setLanguage] = useState('hi')
  const [audioFormat, setAudioFormat] = useState('wav')
  const [samplingRate, setSamplingRate] = useState<number | ''>('')
  const [provider, setProvider] = useState('auto')
  const [result, setResult] = useState<STTResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  const handleFile = async (selected: File | undefined) => {
    setResult(null)
    setError(null)
    if (!selected) {
      setFile(null)
      setSamplingRate('')
      return
    }
    if (selected.size === 0 || selected.size > MAX_AUDIO_BYTES) {
      setFile(null)
      setSamplingRate('')
      setError('Choose an audio file between 1 byte and 10 MiB.')
      return
    }
    const extension = selected.name.split('.').pop()?.toLowerCase()
    if (!extension || !FORMATS.includes(extension)) {
      setFile(null)
      setSamplingRate('')
      setError('Choose a WAV, FLAC, MP3, or OGG file.')
      return
    }
    setAudioFormat(extension)
    setFile(selected)
    setSamplingRate(extension === 'wav' ? (await wavSampleRate(selected)) || '' : '')
  }

  const handleTranscribe = async () => {
    if (!file || !samplingRate) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const audioBase64 = await readBase64(file)
      const response = await transcribeAudio({
        audio_base64: audioBase64,
        language: language || null,
        audio_format: audioFormat,
        sampling_rate: samplingRate,
        provider: provider === 'auto' ? null : provider,
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transcription failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-3 bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 space-y-5">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Speech to text</h2>
          <p className="text-sm text-slate-400 mt-1">Upload a clip and select the language spoken in it.</p>
        </div>

        <label className="block border border-dashed border-slate-600 hover:border-indigo-400 rounded-xl p-6 text-center cursor-pointer transition bg-slate-950/50">
          <FileAudio2 className="w-7 h-7 text-indigo-400 mx-auto mb-2" />
          <span className="block text-sm text-slate-200">{file?.name ?? 'Choose an audio file'}</span>
          <span className="block text-xs text-slate-500 mt-1">WAV, FLAC, MP3, or OGG, up to 10 MiB</span>
          <input
            type="file"
            accept=".wav,.flac,.mp3,.ogg,audio/*"
            className="sr-only"
            onChange={(event) => void handleFile(event.target.files?.[0])}
          />
        </label>

        {previewUrl && (
          <audio controls src={previewUrl} className="w-full" aria-label="Selected audio preview" />
        )}

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
          <label className="text-xs font-medium text-slate-400">
            Provider
            <select value={provider} onChange={(event) => setProvider(event.target.value)}
              className="block w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100">
              <option value="auto">Auto</option>
              {providers.map((item) => (
                <option key={item.id} value={item.id} disabled={!item.available}>
                  {item.name}{item.available ? '' : ' (Unavailable)'}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs font-medium text-slate-400">
            Audio format
            <select value={audioFormat} onChange={(event) => setAudioFormat(event.target.value)}
              className="block w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100">
              {FORMATS.map((format) => <option key={format} value={format}>{format.toUpperCase()}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-slate-400">
            Sample rate (Hz)
            <input type="number" min={1} step={1} value={samplingRate}
              onChange={(event) => setSamplingRate(event.target.value ? Number(event.target.value) : '')}
              placeholder="Enter the file's sample rate"
              className="block w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100" />
          </label>
        </div>
        <p className="text-xs text-slate-500">WAV sample rate is read from the file. For other formats, enter the actual rate. The server does not convert audio.</p>
        <button type="button" disabled={!file || loading || !samplingRate || samplingRate <= 0}
          onClick={() => void handleTranscribe()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium text-white transition">
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          {loading ? 'Transcribing...' : 'Transcribe audio'}
        </button>
        {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
      </div>

      <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-xl p-5 sm:p-6 min-h-56">
        <h3 className="text-sm font-semibold text-slate-200 pb-3 border-b border-slate-800">Transcript</h3>
        {result ? (
          <div className="pt-4 space-y-4">
            <p className="text-base leading-7 text-slate-100 whitespace-pre-wrap">{result.text || 'No speech detected.'}</p>
            <p className="text-xs text-slate-400">
              {result.cache_backend === 'none'
                ? 'No cache · Sent to provider'
                : result.cached
                  ? `Cache hit (${result.cache_backend})`
                  : `Fresh result (${result.cache_backend})`}
            </p>
            <dl className="text-xs text-slate-400 space-y-1 border-t border-slate-800 pt-3">
              <div className="flex justify-between gap-4"><dt>Provider</dt><dd>{result.provider}</dd></div>
              <div className="flex justify-between gap-4"><dt>Language</dt><dd>{result.language ?? 'Unspecified'}</dd></div>
              {result.model_id && <div className="flex justify-between gap-4"><dt>Model</dt><dd className="break-all text-right">{result.model_id}</dd></div>}
            </dl>
          </div>
        ) : (
          <p className="text-sm text-slate-500 pt-4">Your transcript will appear here.</p>
        )}
      </div>
    </section>
  )
}
