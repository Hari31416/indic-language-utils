import React, { useEffect, useRef, useState } from 'react'
import {
  ChevronDown,
  Download,
  Loader2,
  Radio,
  Sliders,
  Sparkles,
  Square,
  Volume2,
  Zap,
} from 'lucide-react'
import { synthesizeSpeech } from '../api'
import { useLocalHistory } from '../history'
import { decodeBase64, pcmChunksToWav, PcmPlayer, providerConnectionSettings, speechSocket } from '../streaming'
import type { LanguageItem, ProviderInfo, TTSResponse, TTSStreamMessage } from '../types'
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
  sarvam: ['bulbul:v3', 'bulbul:v4-flash', 'bulbul:v3-beta', 'bulbul:v2'],
  bhashini: [
    'ai4bharat/indic-tts-coqui-indo_aryan-gpu--t4',
    'ai4bharat/indic-tts-coqui-dravidian-gpu--t4',
    'ai4bharat/indic-tts-coqui-misc-gpu--t4',
  ],
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
  navana: ['default_female', 'achu', 'ammu', 'ann', 'harleen', 'kannan', 'maria', 'murugan', 'shikha', 'zoya'],
}

const NAVANA_VOICES = [
  'default_female', 'achu', 'ammu', 'anirban', 'ann', 'arasi', 'ayesha', 'basava',
  'basheer', 'bhavana', 'bijay', 'bimla', 'champa', 'elango', 'faizal', 'falguni',
  'flavia', 'gurdeep', 'harleen', 'imran', 'ipsita', 'jayita', 'jessy', 'kannan',
  'kayal', 'kishan', 'mahadevi', 'malar', 'maria', 'merin', 'mukta', 'murugan',
  'nasrin', 'nayeema', 'netra', 'nila', 'ponni', 'porkavi', 'rukhiya', 'rukhsana',
  'savio', 'selvi', 'shabnam', 'sharon', 'shikha', 'shivanna', 'srinu', 'sulaiman',
  'tanaji', 'temjen', 'vanaja', 'vetri', 'xavier', 'yasmin', 'zoya',
]

type Fields = Record<string, string>
type ProviderFields = Record<string, Fields>

const initialFields: ProviderFields = {
  edge_tts: { gender: 'female', voice: '', rate: '', pitch: '', volume: '' },
  sarvam: { speaker: 'shubh', pace: '1.0' },
  bhashini: { gender: 'female', voiceId: '', samplingRate: '16000' },
  navana: { voice: 'default_female', speed: '', num_step: '', output_format: '24000:pcm16' },
}

function parseObject(value: string, label: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value || '{}')
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`${label} must be a JSON object`)
  }
  return parsed as Record<string, unknown>
}

interface Hist {
  lang: string
  text: string
}

export const TTSView: React.FC<TTSViewProps> = ({ languages, providers }) => {
  const [mode, setMode] = useState<'file' | 'live'>('file')
  const [text, setText] = useState('नमस्ते! भारतीय भाषा यूटिलिटीज वर्कबेंच में आपका स्वागत है।')
  const [language, setLanguage] = useState('hi')
  const [provider, setProvider] = useState('auto')
  const [modelId, setModelId] = useState('')
  const [showModelConfig, setShowModelConfig] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [fields, setFields] = useState<ProviderFields>(initialFields)
  const [advanced, setAdvanced] = useState('{}')
  const [result, setResult] = useState<TTSResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [liveState, setLiveState] = useState<'idle' | 'connecting' | 'streaming' | 'complete'>('idle')
  const [liveChunks, setLiveChunks] = useState(0)
  const [liveModel, setLiveModel] = useState('')
  const [liveAudioUrl, setLiveAudioUrl] = useState<string | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const playerRef = useRef<PcmPlayer | null>(null)
  const audioChunksRef = useRef<Uint8Array[]>([])
  const liveAudioUrlRef = useRef<string | null>(null)
  const completeRef = useRef(false)
  const { items: history, push, clear } = useLocalHistory<Hist>('ilu-hist-tts')

  useEffect(() => () => {
    socketRef.current?.close()
    if (playerRef.current) void playerRef.current.close()
    if (liveAudioUrlRef.current) URL.revokeObjectURL(liveAudioUrlRef.current)
  }, [])

  const stopLive = () => {
    completeRef.current = true
    socketRef.current?.close()
    socketRef.current = null
    if (playerRef.current) void playerRef.current.close()
    playerRef.current = null
    setLiveState('idle')
  }

  const startLive = async () => {
    if (!text.trim()) return
    if (!language) { setError('Choose a language for live speech.'); return }
    if (text.length > 2500) { setError('Live speech accepts up to 2,500 characters.'); return }
    setError(null)
    setResult(null)
    setLiveChunks(0)
    setLiveModel('')
    audioChunksRef.current = []
    if (liveAudioUrlRef.current) URL.revokeObjectURL(liveAudioUrlRef.current)
    liveAudioUrlRef.current = null
    setLiveAudioUrl(null)
    if (playerRef.current) void playerRef.current.close()
    playerRef.current = null
    completeRef.current = false
    try {
      const extra = parseObject(advanced, 'Extra options')
      let parameters: Record<string, unknown>
      if (provider === 'navana') {
        const steps = fields.navana.num_step ? Number(fields.navana.num_step) : undefined
        if (steps !== undefined && (!Number.isInteger(steps) || steps < 1 || steps > 100)) {
          throw new Error('Flow steps must be an integer between 1 and 100')
        }
        parameters = {
          voice: fields.navana.voice,
          output_format: '24000:pcm16',
          ...(steps !== undefined ? { num_step: steps } : {}),
          ...extra,
        }
        parameters.output_format = '24000:pcm16'
      } else {
        const pace = Number(fields.sarvam.pace)
        if (!Number.isFinite(pace) || pace < 0.5 || pace > 2) throw new Error('Pace must be between 0.5 and 2.0')
        parameters = {
          speaker: fields.sarvam.speaker,
          pace,
          ...extra,
          audio_format: 'linear16',
        }
      }
      const player = new PcmPlayer()
      playerRef.current = player
      await player.resume()
      const socket = speechSocket('/api/tts/stream')
      socketRef.current = socket
      setLiveState('connecting')
      socket.onopen = () => socket.send(JSON.stringify({
        type: 'start', provider, language, parameters,
        model_id: provider === 'navana'
          ? modelId.trim() || null
          : ['bulbul:v2', 'bulbul:v3'].includes(modelId.trim()) ? modelId.trim() : null,
        ...providerConnectionSettings(provider === 'navana' ? 'navana' : 'sarvam'),
      }))
      socket.onmessage = (message) => {
        let data: TTSStreamMessage
        try { data = JSON.parse(message.data as string) as TTSStreamMessage } catch { return }
        if (data.type === 'ready') {
          socket.send(JSON.stringify({ type: 'text', text }))
          socket.send(JSON.stringify({ type: 'flush' }))
          setLiveState('streaming')
        } else if (data.type === 'event' && data.kind === 'audio' && data.audio_base64) {
          const bytes = decodeBase64(data.audio_base64)
          audioChunksRef.current.push(bytes)
          player.play(bytes)
          setLiveChunks((count) => count + 1)
          if (data.model_id) setLiveModel(data.model_id)
        } else if (data.type === 'event' && data.kind === 'done') {
          if (audioChunksRef.current.length > 0) {
            const url = URL.createObjectURL(pcmChunksToWav(audioChunksRef.current))
            liveAudioUrlRef.current = url
            setLiveAudioUrl(url)
          }
          setLiveState('complete')
        } else if (data.type === 'done') {
          completeRef.current = true
          socket.close()
        } else if (data.type === 'error') {
          setError(data.message ?? 'Live speech failed')
          stopLive()
        }
      }
      socket.onerror = () => setError('Live speech connection failed')
      socket.onclose = () => {
        if (socketRef.current !== socket) return
        socketRef.current = null
        if (!completeRef.current) {
          setError((current) => current ?? 'Live speech disconnected')
          if (playerRef.current === player) {
            playerRef.current = null
            void player.close()
          }
          setLiveState('idle')
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start live speech')
      stopLive()
    }
  }

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
        if (provider === 'navana') {
          if (parameters.speed !== undefined) {
            const speed = Number(parameters.speed)
            if (!Number.isFinite(speed) || speed < 0.25 || speed > 4) {
              throw new Error('Speed must be between 0.25 and 4.0')
            }
            parameters.speed = speed
          }
          if (parameters.num_step !== undefined) {
            const steps = Number(parameters.num_step)
            if (!Number.isInteger(steps) || steps < 1 || steps > 100) {
              throw new Error('num_step must be an integer between 1 and 100')
            }
            parameters.num_step = steps
          }
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
      push({ lang: language, text })
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

  const activeModelPresets = mode === 'live' && provider === 'sarvam'
    ? ['bulbul:v3', 'bulbul:v2']
    : TTS_MODEL_PRESETS[provider] ?? []
  const charCount = text.length
  const streamProviders = providers.filter((item) => ['sarvam', 'navana'].includes(item.id) && item.available)
  const streamingReady = streamProviders.length > 0

  return (
    <div className="space-y-5">
      <ToolHeader
        icon={<Volume2 className="h-4 w-4" />}
        tileClass="border-rosewood-500/30 bg-rosewood-500/10 text-rosewood-300"
        title="Text to Speech"
        blurb="Generate a complete audio file or listen as speech arrives."
        glyph="उ"
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="panel space-y-5 p-5 sm:p-6 lg:col-span-7">
          <div className="flex gap-1 rounded-xl border border-ink-700 bg-ink-900/70 p-1 text-xs">
            <button type="button" onClick={() => { setMode('file'); stopLive() }}
              className={`flex-1 rounded-lg px-3 py-2 font-semibold transition ${mode === 'file' ? 'bg-ink-700 text-parchment-100' : 'text-parchment-500 hover:text-parchment-200'}`}>Audio file</button>
            <button type="button" disabled={!streamingReady}
              onClick={() => {
                const next = streamProviders.some((item) => item.id === provider)
                  ? provider
                  : streamProviders[0]?.id ?? 'sarvam'
                setProvider(next)
                setMode('live')
                setModelId('')
              }}
              className={`flex-1 rounded-lg px-3 py-2 font-semibold transition ${mode === 'live' ? 'bg-ink-700 text-parchment-100' : 'text-parchment-500 hover:text-parchment-200'}`}>Live playback</button>
          </div>
          <div className="flex items-center justify-between">
            <label className="eyebrow">Text to synthesize</label>
            <span className="font-mono text-[11px] text-parchment-500">{charCount} chars</span>
          </div>
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={5}
            placeholder="Type text in native script or English…"
            className="field -mt-3 min-h-[120px] resize-y !leading-relaxed"
          />

          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="flex items-center gap-1 font-medium text-parchment-500">
              <Sparkles className="h-3.5 w-3.5 text-rosewood-300" /> Samples:
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
                className="sample-btn"
              >
                {sample.title}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Language">
              <div className="relative">
                <select
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                  className="field !py-2.5 text-xs"
                >
                  <option value="">Unspecified</option>
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
              {mode === 'live' ? <div className="relative"><select value={provider} onChange={(event) => setProvider(event.target.value)} className="field !py-2.5 text-xs">
                {streamProviders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select><ChevronDown className="pointer-events-none absolute right-3 top-3 h-3.5 w-3.5 text-parchment-500" /></div> : <div className="relative">
                <select
                  value={provider}
                  onChange={(event) => {
                    setProvider(event.target.value)
                    setModelId('')
                    setAdvanced('{}')
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
          </div>

          <ModelDrawer
            open={showModelConfig}
            title="TTS Model / Voice ID Override"
            presets={activeModelPresets}
            modelId={modelId}
            onChange={setModelId}
            placeholder={
              provider === 'sarvam'
                ? 'Default: bulbul:v3 (or bulbul:v3-beta, bulbul:v2, bulbul:v1)'
                : provider === 'bhashini'
                  ? 'Default: configured Bhashini TTS model'
                  : provider === 'edge_tts'
                    ? 'Default: hi-IN-SwaraNeural (or hi-IN-MadhurNeural, en-IN-NeerjaNeural...)'
                    : 'Enter model ID or voice ID override...'
            }
          />

          {provider !== 'auto' && (
            <div className="panel-sunken animate-fade-in space-y-3.5 p-4">
              <div className="eyebrow !text-rosewood-300">Voice parameters</div>
              <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
                {provider === 'edge_tts' && (
                  <>
                    <Field label="Gender">
                      <select
                        value={fields.edge_tts.gender}
                        onChange={(event) => updateField('gender', event.target.value)}
                        className="field !bg-ink-850 !py-2 text-xs"
                      >
                        <option value="female">Female</option>
                        <option value="male">Male</option>
                      </select>
                    </Field>
                    <Field label="Voice name override">
                      <input
                        value={fields.edge_tts.voice}
                        onChange={(event) => updateField('voice', event.target.value)}
                        placeholder="e.g. hi-IN-SwaraNeural"
                        className="field field-mono !bg-ink-850 !py-2"
                      />
                    </Field>
                    <Field label="Rate">
                      <input
                        value={fields.edge_tts.rate}
                        onChange={(event) => updateField('rate', event.target.value)}
                        placeholder="+0% (e.g. +10%)"
                        className="field field-mono !bg-ink-850 !py-2"
                      />
                    </Field>
                    <Field label="Pitch">
                      <input
                        value={fields.edge_tts.pitch}
                        onChange={(event) => updateField('pitch', event.target.value)}
                        placeholder="+0Hz"
                        className="field field-mono !bg-ink-850 !py-2"
                      />
                    </Field>
                    <div className="sm:col-span-2">
                      <Field label="Volume">
                        <input
                          value={fields.edge_tts.volume}
                          onChange={(event) => updateField('volume', event.target.value)}
                          placeholder="+0% (e.g. -10%)"
                          className="field field-mono !bg-ink-850 !py-2"
                        />
                      </Field>
                    </div>
                  </>
                )}

                {provider === 'sarvam' && (
                  <>
                    <div className="sm:col-span-2">
                      <Field label="Speaker voice">
                        <select
                          value={fields.sarvam.speaker}
                          onChange={(event) => updateField('speaker', event.target.value)}
                          className="field !bg-ink-850 !py-2 text-xs"
                        >
                          <optgroup label="Bulbul v3 Verified Voices (37 Speakers)">
                            <option value="aditya">aditya (Male)</option>
                            <option value="ritu">ritu (Female)</option>
                            <option value="ashutosh">ashutosh (Male)</option>
                            <option value="priya">priya (Female)</option>
                            <option value="neha">neha (Female)</option>
                            <option value="rahul">rahul (Male)</option>
                            <option value="pooja">pooja (Female)</option>
                            <option value="rohan">rohan (Male)</option>
                            <option value="simran">simran (Female)</option>
                            <option value="kavya">kavya (Female)</option>
                            <option value="amit">amit (Male)</option>
                            <option value="dev">dev (Male)</option>
                            <option value="ishita">ishita (Female)</option>
                            <option value="shreya">shreya (Female)</option>
                            <option value="ratan">ratan (Male)</option>
                            <option value="varun">varun (Male)</option>
                            <option value="manan">manan (Male)</option>
                            <option value="sumit">sumit (Male)</option>
                            <option value="roopa">roopa (Female)</option>
                            <option value="kabir">kabir (Male)</option>
                            <option value="aayan">aayan (Male)</option>
                            <option value="shubh">shubh (Male)</option>
                            <option value="advait">advait (Male)</option>
                            <option value="anand">anand (Male)</option>
                            <option value="tanya">tanya (Female)</option>
                            <option value="tarun">tarun (Male)</option>
                            <option value="sunny">sunny (Male)</option>
                            <option value="mani">mani (Male)</option>
                            <option value="gokul">gokul (Male)</option>
                            <option value="vijay">vijay (Male)</option>
                            <option value="shruti">shruti (Female)</option>
                            <option value="suhani">suhani (Female)</option>
                            <option value="mohit">mohit (Male)</option>
                            <option value="kavitha">kavitha (Female)</option>
                            <option value="rehan">rehan (Male)</option>
                            <option value="soham">soham (Male)</option>
                            <option value="rupali">rupali (Female)</option>
                          </optgroup>
                          <optgroup label="Bulbul v2 Legacy Voices">
                            <option value="shubh">shubh (Male)</option>
                            <option value="arvind">arvind (Male)</option>
                            <option value="amartya">amartya (Male)</option>
                            <option value="priya">priya (Female)</option>
                            <option value="meera">meera (Female)</option>
                            <option value="pavithra">pavithra (Female)</option>
                          </optgroup>
                          <optgroup label="Bulbul v4-flash Conversational / Specialized">
                            <option value="aayan_hi_conversational">aayan_hi_conversational (Hindi)</option>
                            <option value="amit_hi_conversational">amit_hi_conversational (Hindi)</option>
                            <option value="kavya_hi_conversational">kavya_hi_conversational (Hindi)</option>
                            <option value="rahul_hi_conversational">rahul_hi_conversational (Hindi)</option>
                            <option value="simran_hi_conversation">simran_hi_conversation (Hindi)</option>
                            <option value="shubh_hi_customer">shubh_hi_customer (Hindi)</option>
                            <option value="sanchita_hi_assistant">sanchita_hi_assistant (Hindi)</option>
                            <option value="dev_en_conversational">dev_en_conversational (English)</option>
                            <option value="simran_en_conversation">simran_en_conversation (English)</option>
                            <option value="ishita_enhi_companion">ishita_enhi_companion (Hinglish)</option>
                            <option value="shubh_enhi_companion">shubh_enhi_companion (Hinglish)</option>
                            <option value="bappa_bn_conversation">bappa_bn_conversation (Bengali)</option>
                            <option value="pooja_gu_conversational">pooja_gu_conversational (Gujarati)</option>
                            <option value="chaitra_kn_conversation">chaitra_kn_conversation (Kannada)</option>
                            <option value="mrunal_mr_narration">mrunal_mr_narration (Marathi)</option>
                            <option value="anand_pa_conversation">anand_pa_conversation (Punjabi)</option>
                            <option value="gokul_ta_narration">gokul_ta_narration (Tamil)</option>
                            <option value="kavitha_te_conversation">kavitha_te_conversation (Telugu)</option>
                          </optgroup>
                        </select>
                      </Field>
                    </div>
                    <div className="sm:col-span-2">
                      <Field
                        label="Speech pace"
                        action={
                          <span className="font-mono text-[11px] text-marigold-300">
                            {Number(fields.sarvam.pace || 0).toFixed(1)}×
                          </span>
                        }
                      >
                        <input
                          type="range"
                          min="0.5"
                          max="2.0"
                          step="0.1"
                          value={fields.sarvam.pace || '1.0'}
                          onChange={(event) => updateField('pace', event.target.value)}
                          className="w-full"
                          aria-label="Speech pace"
                        />
                        <div className="flex justify-between font-mono text-[10px] text-parchment-600">
                          <span>0.5× slow</span>
                          <span>1.0×</span>
                          <span>2.0× brisk</span>
                        </div>
                      </Field>
                    </div>
                  </>
                )}

                {provider === 'bhashini' && (
                  <>
                    <Field label="Gender">
                      <select
                        value={fields.bhashini.gender}
                        onChange={(event) => updateField('gender', event.target.value)}
                        className="field !bg-ink-850 !py-2 text-xs"
                      >
                        <option value="female">Female</option>
                        <option value="male">Male</option>
                      </select>
                    </Field>
                    <Field label="Sample rate (Hz)">
                      <input
                        type="number"
                        min="8000"
                        step="1000"
                        value={fields.bhashini.samplingRate}
                        onChange={(event) => updateField('samplingRate', event.target.value)}
                        placeholder="16000"
                        className="field field-mono !bg-ink-850 !py-2"
                      />
                    </Field>
                  </>
                )}

                {provider === 'navana' && (
                  <>
                    <Field label="Voice">
                      <select
                        value={fields.navana.voice}
                        onChange={(event) => updateField('voice', event.target.value)}
                        className="field !bg-ink-850 !py-2 text-xs"
                      >
                        {NAVANA_VOICES.map((voice) => <option key={voice} value={voice}>{voice}</option>)}
                      </select>
                    </Field>
                    {mode === 'file' && <Field label="Speed (0.25–4.0)">
                      <input
                        type="number"
                        min="0.25"
                        max="4"
                        step="0.05"
                        value={fields.navana.speed}
                        onChange={(event) => updateField('speed', event.target.value)}
                        placeholder="Voice default"
                        className="field field-mono !bg-ink-850 !py-2"
                      />
                    </Field>}
                    <Field label="Flow steps (1–100)">
                      <input
                        type="number"
                        min="1"
                        max="100"
                        step="1"
                        value={fields.navana.num_step}
                        onChange={(event) => updateField('num_step', event.target.value)}
                        placeholder="Voice default"
                        className="field field-mono !bg-ink-850 !py-2"
                      />
                    </Field>
                    {mode === 'file' && <Field label="Audio output">
                      <select
                        value={fields.navana.output_format}
                        onChange={(event) => updateField('output_format', event.target.value)}
                        className="field !bg-ink-850 !py-2 text-xs"
                      >
                        <option value="24000:pcm16">24 kHz PCM 16-bit</option>
                        <option value="16000:pcm16">16 kHz PCM 16-bit</option>
                        <option value="8000:pcm16">8 kHz PCM 16-bit</option>
                        <option value="24000:float32">24 kHz Float 32-bit</option>
                      </select>
                    </Field>}
                    {mode === 'live' && <p className="sm:col-span-2 text-[11px] text-parchment-500">Live playback uses 24 kHz PCM. Navana streaming does not accept a speed setting.</p>}
                  </>
                )}
              </div>
            </div>
          )}

          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="link-accent"
            >
              <Sliders className="h-3 w-3" />
              {showAdvanced ? 'Hide advanced JSON' : 'Advanced JSON options'}
            </button>
            {showAdvanced && (
              <div className="drawer mt-2 animate-fade-in">
                <p className="text-[11px] leading-relaxed text-parchment-500">
                  {provider === 'auto'
                    ? 'Per-provider settings object, e.g. {"sarvam": {"speaker": "priya"}}.'
                    : 'Extra options merged into this provider\u2019s parameters.'}
                </p>
                <textarea
                  value={advanced}
                  onChange={(event) => setAdvanced(event.target.value)}
                  rows={3}
                  spellCheck={false}
                  placeholder='{}'
                  className="field field-mono !bg-ink-850"
                />
              </div>
            )}
          </div>

          {mode === 'live' ? <button type="button" className="btn-primary w-full !py-3"
            disabled={!text.trim() || liveState === 'connecting'}
            onClick={() => liveState === 'streaming' ? stopLive() : void startLive()}>
            {liveState === 'streaming'
              ? <><Square className="h-4 w-4" /> Stop playback</>
              : liveState === 'connecting'
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Connecting…</>
                : <><Radio className="h-4 w-4" /> {liveState === 'complete' ? 'Generate again' : 'Play live speech'}</>}
          </button> : <button
            type="button"
            disabled={!text.trim() || loading}
            onClick={() => void handleSynthesize()}
            className="btn-primary w-full !py-3"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Synthesizing speech…
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" /> Generate speech
              </>
            )}
          </button>
          }

          {error && <ErrorBox message={error} />}

          <HistoryStrip
            items={history}
            onClear={clear}
            onRestore={(h) => {
              setLanguage(h.lang)
              setText(h.text)
              setResult(null)
            }}
            renderLabel={(h) => `${h.lang || 'auto'}: ${h.text.slice(0, 36)}${h.text.length > 36 ? '…' : ''}`}
            renderSub={(h) => h.text}
          />
        </div>

        <div className="lg:col-span-5">
          <ResultPanel
            title="Generated audio"
            badge={
              mode === 'live' ? (
                <span className="rounded bg-ink-700/70 px-1.5 py-0.5 font-mono text-[10px] uppercase text-parchment-300">PCM</span>
              ) : result ? (
                <span className="rounded bg-ink-700/70 px-1.5 py-0.5 font-mono text-[10px] uppercase text-parchment-300">
                  {format}
                </span>
              ) : undefined
            }
          >
            {mode === 'live' ? (
              liveChunks > 0 ? <div className="panel-sunken flex min-h-[180px] flex-col items-center justify-center gap-3 p-5 text-center">
                <Volume2 className={`h-7 w-7 text-rosewood-300 ${liveState === 'streaming' ? 'animate-pulse' : ''}`} />
                <p className="font-display text-lg text-parchment-100">{liveState === 'complete' ? 'Speech ready' : 'Playing as audio arrives'}</p>
                <p className="font-mono text-xs text-parchment-500">{liveChunks} audio chunks received</p>
                  {liveAudioUrl && <div className="mt-2 w-full space-y-3">
                  <audio controls src={liveAudioUrl} className="w-full" aria-label="Replay live speech" />
                  <a href={liveAudioUrl} download={`${provider}-live-speech.wav`} className="btn-ghost w-full justify-center !py-2.5 !text-[13px]">
                    <Download className="h-4 w-4 text-marigold-300" /> Download WAV
                  </a>
                </div>}
              </div> : <EmptyState icon={<Volume2 className="h-8 w-8 opacity-60" />}
                title="Live playback is ready" hint="Press Play live speech to hear chunks as they arrive" />
            ) : result && audioUrl ? (
              <div className="space-y-4">
                <div className="panel-sunken p-4">
                  <audio controls src={audioUrl} className="w-full" aria-label="Generated speech" />
                </div>
                <a
                  href={audioUrl}
                  download={`${result.provider}-speech.${format}`}
                  className="btn-ghost w-full justify-center !py-2.5 !text-[13px]"
                >
                  <Download className="h-4 w-4 text-marigold-300" /> Download audio file
                </a>
              </div>
            ) : (
              <EmptyState
                icon={<Volume2 className="h-8 w-8 opacity-60" />}
                title="No audio generated yet"
                hint="Enter text and press Generate speech"
              />
            )}
            {mode === 'file' && result && (
              <MetaTable
                rows={[
                  ['Provider', result.provider],
                  ['Language', result.language ?? 'Auto'],
                  ...(result.model_id ? [['Model ID', result.model_id] as [string, string]] : []),
                  ['Route fallbacks', String(result.fallback_count)],
                  [
                    'Cache',
                    result.cached
                      ? `Hit · ${result.cache_backend}`
                      : result.cache_backend === 'none' ? 'Off' : 'Miss',
                  ],
                ]}
              />
            )}
            {mode === 'live' && liveModel && <MetaTable rows={[
              ['Provider', provider === 'navana' ? 'Navana AI' : 'Sarvam AI'], ['Language', language], ['Engine', liveModel],
            ]} />}
          </ResultPanel>
        </div>
      </div>
    </div>
  )
}
export default TTSView
