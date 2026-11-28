import { describe, it, expect } from 'vitest'
import { downsampleFloat32ToInt16, pcm16BytesToFloat32 } from '../api/audio'
import { groupConversations } from '../hooks/useConversations'
import { Conversation } from '../types/chat'

describe('Audio PCM16 conversions', () => {
  it('downsamples 48kHz Float32 audio into exact 16kHz Int16 PCM bounds', () => {
    const src = new Float32Array(4800)
    for (let i = 0; i < src.length; i += 1) {
      src[i] = Math.sin((i / 48000) * 440 * Math.PI * 2) * 0.8
    }
    const downsampled = downsampleFloat32ToInt16(src, 48000, 16000)
    expect(downsampled.length).toBe(1600)
    for (let i = 0; i < downsampled.length; i += 1) {
      expect(downsampled[i]).toBeGreaterThanOrEqual(-32768)
      expect(downsampled[i]).toBeLessThanOrEqual(32767)
    }
  })

  it('decodes raw 24kHz PCM16 bytes into normalized Float32 samples', () => {
    const buf = new ArrayBuffer(4)
    const view = new DataView(buf)
    view.setInt16(0, 16384, true)
    view.setInt16(2, -32768, true)
    const float32 = pcm16BytesToFloat32(buf)
    expect(float32.length).toBe(2)
    expect(float32[0]).toBeCloseTo(0.5, 4)
    expect(float32[1]).toBeCloseTo(-1.0, 4)
  })
})

describe('Conversation chronological grouping', () => {
  it('groups threads into Pinned, Today, Yesterday, Previous 7 Days, and Older', () => {
    const now = new Date('2026-11-28T15:00:00Z').getTime()
    const makeConv = (id: string, updatedAt: number, pinned = false): Conversation => ({
      id,
      title: id,
      pinned,
      createdAt: updatedAt,
      updatedAt,
      messages: [],
    })

    const list: Conversation[] = [
      makeConv('older', now - 14 * 86_400_000),
      makeConv('week', now - 3 * 86_400_000),
      makeConv('yesterday', now - 86_400_000),
      makeConv('today', now - 3_600_000),
      makeConv('pinned_old', now - 20 * 86_400_000, true),
    ]

    const groups = groupConversations(list, now)
    expect(groups.map((g) => g.label)).toEqual([
      'Pinned',
      'Today',
      'Yesterday',
      'Previous 7 Days',
      'Older',
    ])
    expect(groups[0].items[0].id).toBe('pinned_old')
  })
})
