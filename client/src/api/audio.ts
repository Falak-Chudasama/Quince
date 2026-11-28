/**
 * Web Audio layer matching Basket's binary WS contract:
 * - Capture: downsamples microphone input to exact 16,000 Hz mono Int16 PCM chunks.
 * - Playback: gaplessly schedules raw 24,000 Hz mono Int16 PCM chunks from WS binary frames
 *   and supports immediate interrupt/flush for barge-in cancellation.
 */

export const CAPTURE_SAMPLE_RATE = 16000
export const PLAYBACK_SAMPLE_RATE = 24000

export function downsampleFloat32ToInt16(
  input: Float32Array,
  sourceSampleRate: number,
  targetSampleRate = CAPTURE_SAMPLE_RATE,
): Int16Array {
  if (sourceSampleRate === targetSampleRate) {
    const out = new Int16Array(input.length)
    for (let i = 0; i < input.length; i += 1) {
      const clamped = Math.max(-1, Math.min(1, input[i]))
      out[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff
    }
    return out
  }

  const ratio = sourceSampleRate / targetSampleRate
  const newLength = Math.max(1, Math.round(input.length / ratio))
  const out = new Int16Array(newLength)

  let offsetResult = 0
  let offsetBuffer = 0
  while (offsetResult < out.length) {
    const nextOffsetBuffer = Math.min(input.length, Math.round((offsetResult + 1) * ratio))
    let accum = 0
    let count = 0
    for (let i = offsetBuffer; i < nextOffsetBuffer; i += 1) {
      accum += input[i]
      count += 1
    }
    const sample = count > 0 ? accum / count : 0
    const clamped = Math.max(-1, Math.min(1, sample))
    out[offsetResult] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff
    offsetResult += 1
    offsetBuffer = nextOffsetBuffer
  }
  return out
}

export function pcm16BytesToFloat32(buffer: ArrayBuffer): Float32Array<ArrayBuffer> {
  const view = new DataView(buffer)
  const samples = Math.floor(buffer.byteLength / 2)
  const float32 = new Float32Array(new ArrayBuffer(samples * 4))
  for (let i = 0; i < samples; i += 1) {
    const int16 = view.getInt16(i * 2, true)
    float32[i] = int16 / 32768
  }
  return float32
}

export function computeRmsLevel(input: Float32Array): number {
  if (input.length === 0) return 0
  let sum = 0
  for (let i = 0; i < input.length; i += 1) {
    sum += input[i] * input[i]
  }
  return Math.min(1, Math.sqrt(sum / input.length) * 3.2)
}

export class PcmStreamPlayer {
  private ctx: AudioContext | null = null
  private nextStartTime = 0
  private activeSources = new Set<AudioBufferSourceNode>()
  private muted = false

  private ensureContext(): AudioContext | null {
    if (typeof window === 'undefined') return null
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) return null
    if (!this.ctx) {
      this.ctx = new AudioCtx({ sampleRate: PLAYBACK_SAMPLE_RATE })
    }
    if (this.ctx.state === 'suspended') {
      void this.ctx.resume().catch(() => {})
    }
    return this.ctx
  }

  public setMuted(muted: boolean): void {
    this.muted = muted
    if (muted) {
      this.stopAll()
    }
  }

  public enqueuePcm16(buffer: ArrayBuffer): void {
    if (this.muted || buffer.byteLength < 2) return
    const ctx = this.ensureContext()
    if (!ctx) return

    const float32 = pcm16BytesToFloat32(buffer)
    const audioBuffer = ctx.createBuffer(1, float32.length, PLAYBACK_SAMPLE_RATE)
    audioBuffer.copyToChannel(float32, 0)

    const source = ctx.createBufferSource()
    source.buffer = audioBuffer
    source.connect(ctx.destination)

    const now = ctx.currentTime
    if (this.nextStartTime < now) {
      this.nextStartTime = now + 0.015
    }
    source.start(this.nextStartTime)
    this.nextStartTime += audioBuffer.duration

    this.activeSources.add(source)
    source.onended = () => {
      this.activeSources.delete(source)
    }
  }

  public stopAll(): void {
    for (const source of this.activeSources) {
      try {
        source.stop()
      } catch {
        // ignore already stopped sources
      }
      source.disconnect()
    }
    this.activeSources.clear()
    this.nextStartTime = 0
  }

  public dispose(): void {
    this.stopAll()
    if (this.ctx) {
      void this.ctx.close().catch(() => {})
      this.ctx = null
    }
  }
}

export interface MicCaptureController {
  stop: () => void
}

export async function startMicCapture(
  onPcmChunk: (chunk: ArrayBuffer) => void,
  onLevel: (level: number) => void,
): Promise<MicCaptureController> {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error('Microphone access is unavailable in this browser context.')
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  })

  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
  const ctx = new AudioCtx()
  if (ctx.state === 'suspended') {
    await ctx.resume()
  }

  const source = ctx.createMediaStreamSource(stream)
  const processor = ctx.createScriptProcessor(4096, 1, 1)
  const silentGain = ctx.createGain()
  silentGain.gain.value = 0

  let stopped = false

  processor.onaudioprocess = (event: AudioProcessingEvent) => {
    if (stopped) return
    const input = event.inputBuffer.getChannelData(0)
    onLevel(computeRmsLevel(input))
    const pcm16 = downsampleFloat32ToInt16(input, ctx.sampleRate, CAPTURE_SAMPLE_RATE)
    const copy = new ArrayBuffer(pcm16.byteLength)
    new Int16Array(copy).set(pcm16)
    onPcmChunk(copy)
  }

  source.connect(processor)
  processor.connect(silentGain)
  silentGain.connect(ctx.destination)

  return {
    stop: () => {
      if (stopped) return
      stopped = true
      processor.onaudioprocess = null
      try {
        processor.disconnect()
        source.disconnect()
        silentGain.disconnect()
      } catch {
        // ignore disconnect errors
      }
      stream.getTracks().forEach((track) => track.stop())
      onLevel(0)
      void ctx.close().catch(() => {})
    },
  }
}
