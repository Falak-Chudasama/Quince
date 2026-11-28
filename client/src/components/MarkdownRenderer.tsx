import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { Check, Copy } from 'lucide-react'

interface MarkdownRendererProps {
  content: string
  className?: string
  isStreaming?: boolean
}

function safeUrlTransform(url: string): string {
  const sanitized = url.trim()
  if (!sanitized) return ''
  const lower = sanitized.toLowerCase()
  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('vbscript:') ||
    lower.startsWith('data:')
  ) {
    return '#unsafe-link-blocked'
  }
  return sanitized
}

interface CodeBlockProps {
  className?: string
  children?: React.ReactNode
}

const CodeBlock: React.FC<CodeBlockProps> = ({ className, children }) => {
  const [copied, setCopied] = useState(false)
  const match = /language-([\w-]+)/.exec(className || '')
  const codeText = String(children).replace(/\n$/, '')
  const isInline = !className && !codeText.includes('\n')

  if (isInline) {
    return (
      <code className="px-1.5 py-0.5 rounded-md font-mono text-[12px] bg-stone-200/65 dark:bg-stone-800/90 text-stone-900 dark:text-stone-100 border border-black/[0.06] dark:border-white/[0.08]">
        {children}
      </code>
    )
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeText)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      // Clipboard unavailable
    }
  }

  return (
    <div className="relative my-3 rounded-2xl border border-black/[0.08] dark:border-white/[0.09] bg-stone-950 text-stone-100 overflow-hidden shadow-2xs">
      <div className="flex items-center justify-between px-3.5 py-2 bg-stone-900/95 border-b border-white/[0.08] text-stone-400 text-[11px] font-mono select-none">
        <span className="uppercase tracking-wider">{match ? match[1] : 'code'}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="btn-interactive inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] text-stone-300 hover:text-white hover:bg-white/[0.08] focus-ring"
          aria-label="Copy code block"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-quince-leaf" />
              <span className="text-quince-leaf">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-[12.5px] leading-relaxed font-mono text-stone-100">
        <code>{codeText}</code>
      </pre>
    </div>
  )
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className = '',
  isStreaming = false,
}) => {
  if (!content) return null

  return (
    <div
      className={`text-[15px] leading-[1.68] text-stone-900 dark:text-[#F3F4F1] break-words ${className}`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        urlTransform={safeUrlTransform}
        components={{
          code: ({ className: codeClass, children }) => (
            <CodeBlock className={codeClass}>{children}</CodeBlock>
          ),
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          h1: ({ children }) => (
            <h1 className="font-display text-lg font-semibold mt-4 mb-2 first:mt-0 text-stone-950 dark:text-white">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="font-display text-base font-semibold mt-4 mb-2 first:mt-0 text-stone-950 dark:text-white">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold mt-3 mb-1.5 first:mt-0 text-stone-950 dark:text-white">
              {children}
            </h3>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 mb-3 last:mb-0 space-y-1.5 marker:text-stone-400 dark:marker:text-stone-500">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 mb-3 last:mb-0 space-y-1.5 marker:text-stone-500">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-2 border-quince-400 pl-3.5 py-0.5 text-stone-600 dark:text-stone-300 italic">
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-quince-600 dark:text-quince-400 underline underline-offset-2 decoration-quince-400/50 hover:decoration-quince-400 transition"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-xl border border-black/[0.08] dark:border-white/[0.08]">
              <table className="w-full text-left text-xs border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-stone-100/90 dark:bg-stone-850/90 border-b border-black/[0.06] dark:border-white/[0.08]">
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 font-semibold text-stone-700 dark:text-stone-200">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 border-t border-black/[0.05] dark:border-white/[0.06] text-stone-700 dark:text-stone-300">
              {children}
            </td>
          ),
          hr: () => <hr className="my-4 border-black/[0.06] dark:border-white/[0.08]" />,
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && (
        <span
          className="inline-block w-2 h-4 ml-1 align-middle rounded-sm bg-quince-400 animate-pulse"
          aria-hidden="true"
        />
      )}
    </div>
  )
}
