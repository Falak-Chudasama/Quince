// @vitest-environment jsdom
import React, { act } from 'react'
import { createRoot, Root } from 'react-dom/client'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MarkdownRenderer } from '../components/MarkdownRenderer'
import { AwaitUserCard } from '../components/AwaitUserCard'
import { RtsiTimelineCard } from '../components/RtsiTimelineCard'
import { WelcomeEmptyState } from '../components/WelcomeEmptyState'
import { Navbar } from '../components/Navbar'
import { ThemeProvider } from '../context/ThemeContext'
import { useBasketSocket } from '../hooks/useBasketSocket'

function mount(element: React.ReactElement): { container: HTMLDivElement; unmount: () => void } {
  const container = document.createElement('div')
  document.body.appendChild(container)
  let root: Root
  act(() => {
    root = createRoot(container)
    root.render(element)
  })
  return {
    container,
    unmount: () => {
      act(() => {
        root.unmount()
      })
      container.remove()
    },
  }
}

describe('Quince UI component smoke tests', () => {
  beforeEach(() => {
    ;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders streaming markdown with headings, links, and fenced code copy button', () => {
    const md = [
      '## Results',
      '',
      '```python',
      'print("quince")',
      '```',
      '',
      'Safe [link](https://example.com) and blocked [xss](javascript:alert(1)).',
    ].join('\n')

    const { container, unmount } = mount(
      React.createElement(MarkdownRenderer, { content: md, isStreaming: true }),
    )

    expect(container.textContent).toContain('Results')
    expect(container.textContent).toContain('print("quince")')
    expect(container.querySelector('button[aria-label="Copy code block"]')).not.toBeNull()
    const links = Array.from(container.querySelectorAll('a'))
    expect(links.some((a) => a.getAttribute('href') === 'https://example.com')).toBe(true)
    expect(links.some((a) => a.getAttribute('href')?.includes('javascript:'))).toBe(false)
    unmount()
  })

  it('renders interactive AwaitUserCard confirmation buttons and inline reply', () => {
    const onAnswer = vi.fn()
    const { container, unmount } = mount(
      React.createElement(AwaitUserCard, {
        prompt: {
          id: 'aw_1',
          kind: 'confirmation',
          question: 'Confirm checkout on Amazon?',
          status: 'pending',
        },
        isRecording: false,
        onAnswer,
        onStartVoiceReply: vi.fn(),
        onStopVoiceReply: vi.fn(),
      }),
    )

    expect(container.textContent).toContain('Confirm checkout on Amazon?')
    const buttons = Array.from(container.querySelectorAll('button'))
    const approveBtn = buttons.find((b) => b.textContent?.includes('Approve (Yes)'))
    const declineBtn = buttons.find((b) => b.textContent?.includes('Decline (No)'))
    expect(approveBtn).toBeDefined()
    expect(declineBtn).toBeDefined()

    act(() => {
      approveBtn?.click()
    })
    expect(onAnswer).toHaveBeenCalledWith('yes')
    unmount()
  })

  it('renders collapsible RtsiTimelineCard and WelcomeEmptyState starter chips', () => {
    const onSelectPrompt = vi.fn()
    const { container: timelineEl, unmount: unmountTimeline } = mount(
      React.createElement(RtsiTimelineCard, {
        isLive: true,
        steps: [
          {
            id: 's1',
            timestamp: Date.now(),
            kind: 'speak',
            label: 'Voice status',
            detail: 'Navigating to store',
            status: 'completed',
          },
        ],
      }),
    )
    expect(timelineEl.textContent).toContain('RTSI')
    expect(timelineEl.textContent).toContain('Navigating to store')
    unmountTimeline()

    const { container: emptyEl, unmount: unmountEmpty } = mount(
      React.createElement(WelcomeEmptyState, {
        connectionState: 'disconnected',
        activeModel: 'qwen3-4b',
        onSelectPrompt,
      }),
    )
    expect(emptyEl.textContent).toContain('Quince')
    expect(emptyEl.textContent).toContain('Offline mode')
    const firstSuggestion = emptyEl.querySelector('button')
    expect(firstSuggestion).not.toBeNull()
    act(() => {
      firstSuggestion?.click()
    })
    expect(onSelectPrompt).toHaveBeenCalledTimes(1)
    unmountEmpty()
  })

  it('keeps WebSocket stable across parent re-renders and shows Sun icon in dark mode with hover rotation', () => {
    const wsCreated: Array<{ close: ReturnType<typeof vi.fn>; readyState: number }> = []
    class MockWebSocket {
      static CONNECTING = 0
      static OPEN = 1
      static CLOSING = 2
      static CLOSED = 3
      readyState = MockWebSocket.OPEN
      binaryType = 'arraybuffer'
      onopen: (() => void) | null = null
      onmessage: ((e: MessageEvent) => void) | null = null
      onerror: (() => void) | null = null
      onclose: (() => void) | null = null
      close = vi.fn()
      send = vi.fn()
      constructor() {
        wsCreated.push(this)
      }
    }

    const origWs = globalThis.WebSocket
    ;(globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket =
      MockWebSocket as unknown as typeof WebSocket

    try {
      const Harness: React.FC<{ tick: number }> = ({ tick }) => {
        useBasketSocket({
          onAppendMessage: () => void tick,
          onUpdateMessage: () => {},
          onNotifyError: () => {},
        })
        return React.createElement(Navbar, {
          title: `Chat ${tick}`,
          canRenameTitle: true,
          sidebarOpen: true,
          connectionState: 'connected',
          turnPhase: 'idle',
          onToggleSidebar: () => {},
          onRenameTitle: () => {},
          onOpenSettings: () => {},
          onReconnect: () => {},
        })
      }

      window.localStorage.setItem('quince_theme_preference', 'dark')
      const container = document.createElement('div')
      document.body.appendChild(container)
      let root: Root
      act(() => {
        root = createRoot(container)
        root.render(
          React.createElement(ThemeProvider, null, React.createElement(Harness, { tick: 1 })),
        )
      })

      expect(wsCreated.length).toBe(1)

      // Re-render with fresh inline callbacks
      act(() => {
        root.render(
          React.createElement(ThemeProvider, null, React.createElement(Harness, { tick: 2 })),
        )
      })
      expect(wsCreated.length).toBe(1)
      expect(wsCreated[0].close).not.toHaveBeenCalled()

      // In dark mode, theme toggle shows Sun ("Switch to light mode") with hover:rotate-45
      const switchBtn = container.querySelector('button[aria-label="Switch to light mode"]')
      expect(switchBtn).not.toBeNull()
      expect(switchBtn?.innerHTML).toContain('hover:rotate-45')

      act(() => {
        root.unmount()
      })
      container.remove()
    } finally {
      ;(globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket = origWs
      window.localStorage.removeItem('quince_theme_preference')
    }
  })
})
