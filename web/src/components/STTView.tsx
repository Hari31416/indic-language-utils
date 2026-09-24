import React, { useEffect, useState } from 'react'
import {
  Check,
  ChevronDown,
  Copy,
  Cpu,
  FileAudio2,
  Loader2,
  Mic,
  Sliders,
  UploadCloud,
  Zap,
} from 'lucide-react'
import { transcribeAudio } from '../api'
import type { LanguageItem, ProviderInfo, STTResponse } from '../types'

interface STTViewProps {
  languages: LanguageItem[]
  providers: ProviderInfo[]
}

const MAX_AUDIO_BYTES = 10 * 1024 * 1024
const FORMATS = ['wav', 'flac', 'mp3', 'ogg']

const STT_MODEL_PRESETS: Record<string, string[]> = {
  sarvam: ['saarika:v1', 'saarika:v2', 'saarika:flash'],
  bhashini: ['ai4bharat/conformer-hi-gpu--t4', 'ai4bharat/whisper-medium-en--gpu--t4'],
  faster_whisper: ['base', 'tiny', 'small', 'medium', 'large-v3'],
}

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
    reader.onerror = () => reject(new Error('Could not read audio file'))
    reader.onload = () => {
      const value = reader.result
      if (typeof value !== 'string') {
        reject(new Error('Could not read audio file'))
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
  const [samplingRate, setSamplingRate] = useState<number | ''>(16000)
  const [provider, setProvider] = useState('auto')
  const [modelId, setModelId] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [result, setResult] = useState<STTResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)

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
      return
    }
    if (selected.size === 0 || selected.size > MAX_AUDIO_BYTES) {
      setFile(null)
      setError('Choose an audio file between 1 byte and 10 MiB.')
      return
    }
    const extension = selected.name.split('.').pop()?.toLowerCase()
    if (!extension || !FORMATS.includes(extension)) {
      setFile(null)
      setError('Choose a WAV, FLAC, MP3, or OGG file.')
      return
    }
    setAudioFormat(extension)
    setFile(selected)
    if (extension === 'wav') {
      const detectedRate = await wavSampleRate(selected)
      if (detectedRate) setSamplingRate(detectedRate)
    }
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
        sampling_rate: Number(samplingRate),
        provider: provider === 'auto' ? null : provider,
        model_id: modelId.trim() || null,
      })
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transcription failed')
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

  const activeModelPresets = STT_MODEL_PRESETS[provider] ?? []
  const wordCount = result?.text.trim() ? result.text.trim().split(/\s+/).length : 0

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Left Column: Upload & Parameters */}
      <div className="lg:col-span-7 bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 sm:p-6 backdrop-blur-sm shadow-xl space-y-5">
        <div className="flex items-center gap-3 pb-3 border-b border-slate-800/70">
          <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Mic className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Speech to Text (ASR)</h2>
            <p className="text-xs text-slate-400">
              Upload speech audio to transcribe with Sarvam, Bhashini, Faster-Whisper, or Google STT
            </p>
          </div>
        </div>

        {/* Audio Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragOver(true)
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setIsDragOver(false)
            void handleFile(e.dataTransfer.files[0])
          }}
          className={`relative border-2 border-dashed rounded-2xl p-6 text-center transition cursor-pointer ${
            isDragOver
              ? 'border-indigo-500 bg-indigo-950/20'
              : file
                ? 'border-indigo-500/60 bg-slate-950/70'
                : 'border-slate-700/80 hover:border-slate-600 bg-slate-950/40'
          }`}
        >
          <input
            type="file"
            accept=".wav,.flac,.mp3,.ogg,audio/*"
            className="sr-only"
            id="audio-upload-input"
            onChange={(event) => void handleFile(event.target.files?.[0])}
          />
          <label htmlFor="audio-upload-input" className="cursor-pointer block">
            <div className="p-3 rounded-full bg-slate-900 border border-slate-800 w-12 h-12 mx-auto mb-3 flex items-center justify-center text-indigo-400 shadow-md">
              {file ? <FileAudio2 className="w-6 h-6" /> : <UploadCloud className="w-6 h-6" />}
            </div>
            <div className="text-sm font-semibold text-slate-100">
              {file ? file.name : 'Choose an audio file or drag & drop'}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              WAV, FLAC, MP3, or OGG up to 10 MiB
            </p>
            {file && (
              <div className="flex items-center justify-center gap-2 mt-3 text-xs font-mono text-slate-400">
                <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 uppercase">
                  {audioFormat}
                </span>
                {samplingRate && (
                  <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">
                    {samplingRate} Hz
                  </span>
                )}
              </div>
            )}
          </label>
        </div>

        {/* Audio Player Preview */}
        {previewUrl && (
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <audio controls src={previewUrl} className="w-full h-10" aria-label="Audio preview" />
          </div>
        )}

        {/* Configuration Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Spoken Language
            </label>
            <div className="relative">
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs font-medium text-slate-100 focus:outline-none focus:border-indigo-500"
              >
                <option value="">Unspecified (Auto Detect)</option>
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
                className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-400 hover:text-indigo-300"
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
                }}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs font-medium text-slate-100 focus:outline-none focus:border-indigo-500"
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

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Audio Format
            </label>
            <div className="relative">
              <select
                value={audioFormat}
                onChange={(event) => setAudioFormat(event.target.value)}
                className="w-full appearance-none bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs font-medium text-slate-100 focus:outline-none focus:border-indigo-500 uppercase"
              >
                {FORMATS.map((format) => (
                  <option key={format} value={format}>
                    {format.toUpperCase()}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-3 pointer-events-none" />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
              Sample Rate (Hz)
            </label>
            <input
              type="number"
              min={1}
              step={1}
              value={samplingRate}
              onChange={(event) =>
                setSamplingRate(event.target.value ? Number(event.target.value) : '')
              }
              placeholder="e.g. 16000"
              className="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs font-mono text-slate-100 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {/* Model ID Config Drawer */}
        {showModelConfig && (
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2.5 animate-in fade-in duration-150">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                <Cpu className="w-4 h-4 text-indigo-400" />
                <span>STT Model ID Override</span>
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
                  ? 'Default: saarika:v1 (or saarika:v2, saarika:flash)'
                  : provider === 'bhashini'
                    ? 'Default: configured Bhashini model ID'
                    : provider === 'faster_whisper'
                      ? 'Default: base (or tiny, small, medium, large-v3)'
                      : 'Enter model ID override...'
              }
              className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
            />
          </div>
        )}

        <button
          type="button"
          disabled={!file || loading || !samplingRate || samplingRate <= 0}
          onClick={() => void handleTranscribe()}
          className="w-full inline-flex items-center justify-center gap-2 px-5 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/20 transition active:scale-95"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Transcribing Audio...
            </>
          ) : (
            <>
              <Zap className="w-4 h-4" />
              Transcribe Audio
            </>
          )}
        </button>

        {error && (
          <div className="p-3 bg-rose-950/60 border border-rose-800/70 text-rose-300 text-xs rounded-xl">
            {error}
          </div>
        )}
      </div>

      {/* Right Column: Transcript Result */}
      <div className="lg:col-span-5 bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 sm:p-6 backdrop-blur-sm shadow-xl flex flex-col min-h-[380px]">
        <div className="flex justify-between items-center pb-3 text-xs text-slate-400 border-b border-slate-800/80">
          <span className="font-semibold uppercase tracking-wider text-slate-300">
            Transcription
          </span>
          {result && (
            <div className="flex items-center gap-3">
              <span>{wordCount} words</span>
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

        <div className="flex-1 mt-4 flex flex-col justify-between">
          {result ? (
            <div className="space-y-4">
              <p className="text-base leading-relaxed text-slate-100 whitespace-pre-wrap font-sans">
                {result.text || 'No speech detected in audio stream.'}
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-48 text-center text-slate-500">
              <FileAudio2 className="w-10 h-10 mb-2 opacity-40" />
              <span className="text-sm font-medium">No audio transcribed yet</span>
              <span className="text-xs mt-1">Upload a clip and click Transcribe</span>
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
export default STTView
