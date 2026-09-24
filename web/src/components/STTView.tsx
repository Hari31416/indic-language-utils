import React, { useEffect, useState } from 'react'
import {
  Check,
  ChevronDown,
  Copy,
  FileAudio2,
  Loader2,
  Mic,
  Sliders,
  UploadCloud,
  Zap,
} from 'lucide-react'
import { transcribeAudio } from '../api'
import { useLocalHistory } from '../history'
import type { LanguageItem, ProviderInfo, STTResponse } from '../types'
import {
  EmptyState,
  ErrorBox,
  Field,
  HistoryStrip,
  MetaTable,
  ModelDrawer,
  ResultPanel,
  ToolHeader,
} from './ui'

interface STTViewProps {
  languages: LanguageItem[]
  providers: ProviderInfo[]
}

const MAX_AUDIO_BYTES = 10 * 1024 * 1024
const FORMATS = ['wav', 'flac', 'mp3', 'ogg']

const STT_MODEL_PRESETS: Record<string, string[]> = {
  sarvam: ['saarika:v1', 'saarika:v2', 'saarika:flash'],
  bhashini: [
    'ai4bharat/conformer-hi-gpu--t4',
    'bhashini/bodhan/asr-transcribe-flex',
    'bhashini/bodhan/asr-transcribe-core',
    'ai4bharat/whisper-medium-en--gpu--t4',
  ],
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

interface Hist {
  name: string
  out: string
  provider: string
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
  const { items: history, push, clear } = useLocalHistory<Hist>('ilu-hist-stt')

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
      push({ name: file.name, out: response.text, provider: response.provider })
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
    <div className="space-y-5">
      <ToolHeader
        icon={<Mic className="h-4 w-4" />}
        tileClass="border-clay-500/30 bg-clay-500/10 text-clay-300"
        title="Speech to Text"
        blurb="Upload speech audio and transcribe it with Sarvam Saarika, Bhashini, Faster-Whisper, or Google STT."
        glyph="ई"
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="panel space-y-5 p-5 sm:p-6 lg:col-span-7">
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
            className={`relative rounded-2xl border-2 border-dashed p-6 text-center transition cursor-pointer ${
              isDragOver
                ? 'border-marigold-400 bg-marigold-500/10'
                : file
                  ? 'border-moss-500/50 bg-ink-900/80'
                  : 'border-ink-600 bg-ink-900/50 hover:border-parchment-600/60'
            }`}
          >
            <input
              type="file"
              accept=".wav,.flac,.mp3,.ogg,audio/*"
              className="sr-only"
              id="audio-upload-input"
              onChange={(event) => void handleFile(event.target.files?.[0])}
            />
            <label htmlFor="audio-upload-input" className="block cursor-pointer">
              <div
                className={`mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full border shadow-card ${
                  file
                    ? 'border-moss-500/40 bg-moss-500/10 text-moss-300'
                    : 'border-ink-600 bg-ink-800 text-marigold-300'
                }`}
              >
                {file ? <FileAudio2 className="h-6 w-6" /> : <UploadCloud className="h-6 w-6" />}
              </div>
              <div className="truncate text-sm font-semibold text-parchment-100">
                {file ? file.name : 'Choose an audio file or drag & drop'}
              </div>
              <p className="mt-1 text-xs text-parchment-500">
                WAV, FLAC, MP3, or OGG up to 10 MiB
              </p>
              {file && (
                <div className="mt-3 flex items-center justify-center gap-2 font-mono text-xs text-parchment-400">
                  <span className="meta-chip">{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
                  <span className="meta-chip uppercase">{audioFormat}</span>
                  {samplingRate && <span className="meta-chip">{samplingRate} Hz</span>}
                </div>
              )}
            </label>
          </div>

          {previewUrl && (
            <div className="panel-sunken p-3">
              <audio controls src={previewUrl} className="h-10 w-full" aria-label="Audio preview" />
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Spoken language">
              <div className="relative">
                <select
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                  className="field !py-2.5 text-xs"
                >
                  <option value="">Unspecified (Auto Detect)</option>
                  {languages.map((item) => (
                    <option key={item.tag} value={item.code}>
                      {item.name} ({item.code})
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3 h-3.5 w-3.5 text-parchment-500" />
              </div>
            </Field>

            <Field
              label="Engine"
              action={
                <button
                  type="button"
                  onClick={() => setShowModelConfig(!showModelConfig)}
                  className="link-accent"
                >
                  <Sliders className="h-3 w-3" />
                  {showModelConfig ? 'Hide Model' : 'Custom Model'}
                </button>
              }
            >
              <div className="relative">
                <select
                  value={provider}
                  onChange={(event) => {
                    setProvider(event.target.value)
                    setModelId('')
                  }}
                  className="field !py-2.5 text-xs"
                >
                  <option value="auto">Auto (Default Route)</option>
                  {providers.map((item) => (
                    <option key={item.id} value={item.id} disabled={!item.available}>
                      {item.name} {item.available ? '' : '(Unavailable)'}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3 h-3.5 w-3.5 text-parchment-500" />
              </div>
            </Field>

            <Field label="Audio format">
              <div className="relative">
                <select
                  value={audioFormat}
                  onChange={(event) => setAudioFormat(event.target.value)}
                  className="field uppercase !py-2.5 text-xs"
                >
                  {FORMATS.map((format) => (
                    <option key={format} value={format}>
                      {format.toUpperCase()}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3 h-3.5 w-3.5 text-parchment-500" />
              </div>
            </Field>

            <Field label="Sample rate (Hz)">
              <input
                type="number"
                min={1}
                step={1}
                value={samplingRate}
                onChange={(event) =>
                  setSamplingRate(event.target.value ? Number(event.target.value) : '')
                }
                placeholder="e.g. 16000"
                className="field field-mono !py-2.5"
              />
            </Field>
          </div>

          <ModelDrawer
            open={showModelConfig}
            title="STT Model ID Override"
            presets={activeModelPresets}
            modelId={modelId}
            onChange={setModelId}
            placeholder={
              provider === 'sarvam'
                ? 'Default: saarika:v1 (or saarika:v2, saarika:flash)'
                : provider === 'bhashini'
                  ? 'Default: configured Bhashini model ID'
                  : provider === 'faster_whisper'
                    ? 'Default: base (or tiny, small, medium, large-v3)'
                    : 'Enter model ID override...'
            }
          />

          <button
            type="button"
            disabled={!file || loading || !samplingRate || samplingRate <= 0}
            onClick={() => void handleTranscribe()}
            className="btn-primary w-full !py-3"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Transcribing audio…
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" /> Transcribe audio
              </>
            )}
          </button>

          {error && <ErrorBox message={error} />}

          <HistoryStrip
            items={history}
            onClear={clear}
            onRestore={(h) => void navigator.clipboard.writeText(h.out)}
            renderLabel={(h) => `${h.name.slice(0, 26)} → ${h.out.slice(0, 30)}${h.out.length > 30 ? '…' : ''}`}
            renderSub={(h) => h.out}
          />
        </div>

        <div className="lg:col-span-5">
          <ResultPanel
            title="Transcription"
            actions={
              result ? (
                <div className="flex items-center gap-3 text-xs text-parchment-500">
                  <span>{wordCount} words</span>
                  <button type="button" onClick={() => void handleCopy()} className="btn-ghost">
                    {copied ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-moss-300" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" /> Copy
                      </>
                    )}
                  </button>
                </div>
              ) : undefined
            }
          >
            {result ? (
              <p className="whitespace-pre-wrap font-display text-[17px] leading-relaxed text-parchment-100">
                {result.text || 'No speech detected in audio stream.'}
              </p>
            ) : (
              <EmptyState
                icon={<FileAudio2 className="h-8 w-8 opacity-60" />}
                title="No audio transcribed yet"
                hint="Upload a clip and press Transcribe"
              />
            )}
            {result && (
              <MetaTable
                rows={[
                  ['Provider', result.provider],
                  ['Language', result.language ?? 'Auto'],
                  ...(result.model_id ? [['Model ID', result.model_id] as [string, string]] : []),
                  ['Route fallbacks', String(result.fallback_count)],
                ]}
              />
            )}
          </ResultPanel>
        </div>
      </div>
    </div>
  )
}
export default STTView
