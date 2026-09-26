import { loadApiKeys } from './storage'

export function speechSocket(path: '/api/stt/stream' | '/api/tts/stream'): WebSocket {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${scheme}//${window.location.host}${path}`)
}

export function providerConnectionSettings(provider: 'sarvam' | 'navana'): { api_key?: string; endpoint?: string } {
  const keys = loadApiKeys()
  const apiKey = provider === 'navana' ? keys.navanaApiKey : keys.sarvamApiKey
  const endpoint = provider === 'navana' ? keys.navanaEndpoint : keys.sarvamEndpoint
  return {
    ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
    ...(endpoint.trim() ? { endpoint: endpoint.trim() } : {}),
  }
}

export const sarvamConnectionSettings = () => providerConnectionSettings('sarvam')

export function decodeBase64(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return bytes
}

export interface PcmCapture {
  stop: () => Promise<void>
}

export async function startPcmCapture(
  onChunk: (pcm: ArrayBuffer) => void,
  onLevel?: (level: number) => void,
): Promise<PcmCapture> {
  if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
    throw new Error('Live microphone capture requires a secure browser context with AudioWorklet support.')
  }
  const media = await navigator.mediaDevices.getUserMedia({ audio: true })
  let context: AudioContext | null = null
  try {
    context = new AudioContext({ sampleRate: 16000 })
    if (context.sampleRate !== 16000) {
      throw new Error('This browser could not capture audio at 16 kHz.')
    }
    const worklet = `
      class PcmCaptureProcessor extends AudioWorkletProcessor {
        process(inputs) {
          const channel = inputs[0] && inputs[0][0];
          if (channel) this.port.postMessage(channel.slice());
          return true;
        }
      }
      registerProcessor('pcm-capture', PcmCaptureProcessor);
    `
    const url = URL.createObjectURL(new Blob([worklet], { type: 'application/javascript' }))
    try {
      await context.audioWorklet.addModule(url)
    } finally {
      URL.revokeObjectURL(url)
    }
    const source = context.createMediaStreamSource(media)
    const node = new AudioWorkletNode(context, 'pcm-capture')
    const samples: number[] = []
    let stopped = false
    let lastLevelAt = 0

    function flush() {
      if (!samples.length) return
      const bytes = new ArrayBuffer(samples.length * 2)
      const view = new DataView(bytes)
      samples.forEach((sample, index) => {
        const clipped = Math.max(-1, Math.min(1, sample))
        view.setInt16(index * 2, clipped < 0 ? clipped * 32768 : clipped * 32767, true)
      })
      samples.length = 0
      onChunk(bytes)
    }

    node.port.onmessage = (event: MessageEvent<Float32Array>) => {
      if (stopped) return
      const now = performance.now()
      if (onLevel && now - lastLevelAt >= 80) {
        let power = 0
        for (const sample of event.data) power += sample * sample
        onLevel(Math.min(1, Math.sqrt(power / event.data.length) * 5))
        lastLevelAt = now
      }
      for (const sample of event.data) {
        samples.push(sample)
        if (samples.length === 1600) flush()
      }
    }
    source.connect(node)
    node.connect(context.destination)
    await context.resume()
    const activeContext = context
    return {
      stop: async () => {
        if (stopped) return
        stopped = true
        onLevel?.(0)
        flush()
        node.port.onmessage = null
        source.disconnect()
        node.disconnect()
        media.getTracks().forEach((track) => track.stop())
        await activeContext.close()
      },
    }
  } catch (error) {
    media.getTracks().forEach((track) => track.stop())
    if (context) await context.close()
    throw error
  }
}

export function pcmChunksToWav(chunks: Uint8Array[], sampleRate = 24000): Blob {
  const dataLength = chunks.reduce((total, chunk) => total + chunk.byteLength, 0)
  const wav = new ArrayBuffer(44 + dataLength)
  const view = new DataView(wav)
  const writeText = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index))
  }
  writeText(0, 'RIFF')
  view.setUint32(4, 36 + dataLength, true)
  writeText(8, 'WAVE')
  writeText(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeText(36, 'data')
  view.setUint32(40, dataLength, true)
  const bytes = new Uint8Array(wav)
  let offset = 44
  for (const chunk of chunks) {
    bytes.set(chunk, offset)
    offset += chunk.byteLength
  }
  return new Blob([wav], { type: 'audio/wav' })
}

export class PcmPlayer {
  private context: AudioContext
  private nextTime = 0
  private sources = new Set<AudioBufferSourceNode>()

  constructor(sampleRate = 24000) {
    this.context = new AudioContext({ sampleRate })
  }

  async resume(): Promise<void> {
    await this.context.resume()
  }

  play(bytes: Uint8Array): void {
    if (bytes.byteLength < 2 || bytes.byteLength % 2 !== 0) return
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    const buffer = this.context.createBuffer(1, bytes.byteLength / 2, this.context.sampleRate)
    const channel = buffer.getChannelData(0)
    for (let i = 0; i < channel.length; i += 1) {
      channel[i] = view.getInt16(i * 2, true) / 32768
    }
    const source = this.context.createBufferSource()
    source.buffer = buffer
    source.connect(this.context.destination)
    source.onended = () => this.sources.delete(source)
    const startAt = Math.max(this.context.currentTime + 0.03, this.nextTime)
    source.start(startAt)
    this.nextTime = startAt + buffer.duration
    this.sources.add(source)
  }

  async close(): Promise<void> {
    for (const source of this.sources) source.stop()
    this.sources.clear()
    await this.context.close()
  }
}
