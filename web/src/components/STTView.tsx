import React, { useEffect, useRef, useState } from 'react'
import {
  Check,
  ChevronDown,
  Copy,
  FileAudio2,
  Loader2,
  Mic,
  Radio,
  Sliders,
  Square,
  UploadCloud,
  Zap,
} from 'lucide-react'
import { transcribeAudio } from '../api'
import { useLocalHistory } from '../history'
import { sarvamConnectionSettings, speechSocket, startPcmCapture } from '../streaming'
import type { PcmCapture } from '../streaming'
import type { LanguageItem, ProviderInfo, STTResponse, STTStreamMessage } from '../types'
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
  sarvam: ['saaras:v4', 'saaras:v3'],
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
  const [mode, setMode] = useState<'file' | 'live'>('file')
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
  const [liveState, setLiveState] = useState<'idle' | 'connecting' | 'listening' | 'stopping'>('idle')
  const [liveFinal, setLiveFinal] = useState('')
  const [livePartial, setLivePartial] = useState('')
  const [liveModel, setLiveModel] = useState('')
  const [micLevel, setMicLevel] = useState(0)
  const socketRef = useRef<WebSocket | null>(null)
  const captureRef = useRef<PcmCapture | null>(null)
  const stoppingRef = useRef(false)
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

  useEffect(() => () => {
    socketRef.current?.close()
    if (captureRef.current) void captureRef.current.stop()
  }, [])

  const startLive = () => {
    if (socketRef.current) return
    setError(null)
    setResult(null)
    setLiveFinal('')
    setLivePartial('')
    setLiveModel('')
    setMicLevel(0)
    setLiveState('connecting')
    stoppingRef.current = false
    const socket = speechSocket('/api/stt/stream')
    socketRef.current = socket
    socket.onopen = () => socket.send(JSON.stringify({
      type: 'start', provider: 'sarvam', language: language || null,
      sampling_rate: 16000,
      model_id: ['saaras:v4', 'saaras:v3-realtime'].includes(modelId.trim())
        ? modelId.trim() : null,
      ...sarvamConnectionSettings(),
    }))
    socket.onmessage = (message) => {
      let data: STTStreamMessage
      try { data = JSON.parse(message.data as string) as STTStreamMessage } catch { return }
      if (data.type === 'ready') {
        void startPcmCapture((pcm) => {
          if (socket.readyState === WebSocket.OPEN && !stoppingRef.current) socket.send(pcm)
        }, setMicLevel).then((capture) => {
          if (socketRef.current !== socket) {
            void capture.stop()
            return
          }
          captureRef.current = capture
          setLiveState('listening')
        }).catch((err: unknown) => {
          setError(err instanceof Error ? err.message : 'Could not start microphone')
          socket.close()
        })
      } else if (data.type === 'event') {
        if (data.kind === 'partial') setLivePartial(data.text ?? '')
        if (data.kind === 'final') {
          setLiveFinal((current) => [current, data.text].filter(Boolean).join(' '))
          setLivePartial('')
          if (data.model_id) setLiveModel(data.model_id)
        }
      } else if (data.type === 'error') {
        setError(data.message ?? 'Live transcription failed')
        socket.close()
      } else if (data.type === 'done') {
        stoppingRef.current = true
        socket.close()
      }
    }
    socket.onerror = () => setError('Live transcription connection failed')
    socket.onclose = () => {
      if (socketRef.current !== socket) return
      socketRef.current = null
      if (captureRef.current) {
        void captureRef.current.stop()
        captureRef.current = null
      }
      if (!stoppingRef.current) setError((current) => current ?? 'Live transcription disconnected')
      setMicLevel(0)
      setLiveState('idle')
    }
  }

  const stopLive = async () => {
    const socket = socketRef.current
    if (!socket || stoppingRef.current) return
    setLiveState('stopping')
    if (captureRef.current) {
      await captureRef.current.stop()
      captureRef.current = null
    }
    stoppingRef.current = true
    if (socket.readyState === WebSocket.OPEN) {
      socket.send('{"type":"finish"}')
    }
  }

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
    const text = mode === 'live' ? liveFinal : result?.text
    if (!text) return
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const activeModelPresets = mode === 'live'
    ? ['saaras:v4', 'saaras:v3-realtime'] : STT_MODEL_PRESETS[provider] ?? []
  const displayText = mode === 'live' ? [liveFinal, livePartial].filter(Boolean).join(' ') : result?.text ?? ''
  const wordCount = displayText.trim() ? displayText.trim().split(/\s+/).length : 0
  const sarvamReady = providers.some((item) => item.id === 'sarvam' && item.available)

  return (
    <div className="space-y-5">
      <ToolHeader
        icon={<Mic className="h-4 w-4" />}
        tileClass="border-clay-500/30 bg-clay-500/10 text-clay-300"
        title="Speech to Text"
        blurb="Transcribe a recording or speak live with Sarvam Realtime."
        glyph="ई"
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="panel space-y-5 p-5 sm:p-6 lg:col-span-7">
          <div className="flex gap-1 rounded-xl border border-ink-700 bg-ink-900/70 p-1 text-xs">
            <button type="button" onClick={() => setMode('file')} disabled={liveState !== 'idle'}
              className={`flex-1 rounded-lg px-3 py-2 font-semibold transition ${mode === 'file' ? 'bg-ink-700 text-parchment-100' : 'text-parchment-500 hover:text-parchment-200'}`}>Audio file</button>
            <button type="button" onClick={() => { setMode('live'); setProvider('sarvam'); setModelId('') }}
              disabled={!sarvamReady || liveState !== 'idle'}
              className={`flex-1 rounded-lg px-3 py-2 font-semibold transition ${mode === 'live' ? 'bg-ink-700 text-parchment-100' : 'text-parchment-500 hover:text-parchment-200'}`}>Live microphone</button>
          </div>
          {mode === 'live' && (
            <div className="relative flex min-h-[150px] flex-col items-center justify-center overflow-hidden rounded-xl border border-clay-500/25 bg-clay-500/5 px-4 py-5 text-center">
              <div className="relative mb-3 flex h-16 w-16 items-center justify-center">
                {liveState === 'listening' && <span className="absolute inset-0 rounded-full border border-clay-400/40 motion-safe:animate-ping" />}
                <span
                  className={`absolute inset-1 rounded-full border transition-transform duration-100 ${liveState === 'listening' ? 'border-clay-400/60 bg-clay-500/15' : 'border-ink-600 bg-ink-800'}`}
                  style={{ transform: liveState === 'listening' ? `scale(${1 + micLevel * 0.3})` : undefined }}
                />
                <Mic className={`relative h-6 w-6 ${liveState === 'listening' ? 'text-clay-300' : 'text-parchment-500'}`} />
              </div>
              <p className="text-sm font-semibold text-parchment-200" role="status">
                {liveState === 'listening' ? 'Listening to your microphone' : liveState === 'connecting' ? 'Connecting microphone…' : liveState === 'stopping' ? 'Finishing transcript…' : 'Microphone ready'}
              </p>
              <p className="mt-1 text-xs text-parchment-500">
                {liveState === 'listening' ? 'The ring responds to your voice' : 'Sarvam Realtime · 16 kHz audio'}
              </p>
            </div>
          )}
          {mode === 'file' && <>
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
          </>}

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
              {mode === 'live' ? <div className="field !py-2.5 text-xs">Sarvam AI Realtime</div> : <div className="relative">
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
              </div>}
            </Field>

            {mode === 'file' && <>
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
            </>}
          </div>

          <ModelDrawer
            open={showModelConfig}
            title="STT Model ID Override"
            presets={activeModelPresets}
            modelId={modelId}
            onChange={setModelId}
            placeholder={
              provider === 'sarvam'
                ? mode === 'live' ? 'Default: saaras:v4' : 'Default: configured Sarvam model'
                : provider === 'bhashini'
                  ? 'Default: configured Bhashini model ID'
                  : provider === 'faster_whisper'
                    ? 'Default: base (or tiny, small, medium, large-v3)'
                    : 'Enter model ID override...'
            }
          />

          {mode === 'live' ? <button type="button"
            disabled={liveState === 'connecting' || liveState === 'stopping'}
            onClick={() => liveState === 'listening' ? void stopLive() : startLive()}
            className="btn-primary w-full !py-3">
            {liveState === 'listening' ? <><Square className="h-4 w-4" /> Stop listening</>
              : liveState === 'connecting' || liveState === 'stopping' ? <><Loader2 className="h-4 w-4 animate-spin" /> {liveState === 'connecting' ? 'Connecting…' : 'Finishing…'}</>
              : <><Radio className="h-4 w-4" /> Start live transcription</>}
          </button> : <button
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
          }

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
              displayText ? (
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
            {displayText ? (
              <p className="whitespace-pre-wrap font-display text-[17px] leading-relaxed text-parchment-100">
                {mode === 'live' ? <>{liveFinal} <span className="text-parchment-500">{livePartial}</span></> : displayText}
              </p>
            ) : (
              <EmptyState
                icon={mode === 'live' ? <Mic className="h-8 w-8 opacity-60" /> : <FileAudio2 className="h-8 w-8 opacity-60" />}
                title="No audio transcribed yet"
                hint={mode === 'live' ? 'Start the microphone to see words appear' : 'Upload a clip and press Transcribe'}
              />
            )}
            {mode === 'file' && result && (
              <MetaTable
                rows={[
                  ['Provider', result.provider],
                  ['Language', result.language ?? 'Auto'],
                  ...(result.model_id ? [['Model ID', result.model_id] as [string, string]] : []),
                  ['Route fallbacks', String(result.fallback_count)],
                ]}
              />
            )}
            {mode === 'live' && liveModel && <MetaTable rows={[
              ['Provider', 'Sarvam AI'], ['Model ID', liveModel], ['Mode', 'Live microphone'],
            ]} />}
          </ResultPanel>
        </div>
      </div>
    </div>
  )
}
export default STTView
