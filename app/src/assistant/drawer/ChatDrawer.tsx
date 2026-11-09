// AX-14: the chat drawer. A modal dialog: focus moves in on open and returns to the opener on close, Tab is trapped
// while open, Escape closes. The log is aria-live="polite". The slide-in animation is off under prefers-reduced-motion.
// 16px gutters, no horizontal scroll at 320px. The Worker returns one reply per round, so a pending question shows step
// progress, then the checked answer.
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import EmptyState from '../../ui/feedback/EmptyState'
import { ErrorBoundary } from '../../ui/feedback/ErrorBoundary'
import { TechTooltip, TechTooltipProvider } from '../../ui/TechTooltip'
import AnswerView from './AnswerView'
import TurnstileGate from './TurnstileGate'
import { ERROR_TEXT, type Turn } from './useChat'

export interface ChatApi {
  turns: Turn[]
  busy: boolean
  send(question: string): void | Promise<void>
  clear(): void
}

interface Props {
  open: boolean
  onClose(): void
  chat: ChatApi
  /** Attach the Turnstile mount point (the launcher owns the token source). */
  turnstileRef?: React.Ref<HTMLDivElement>
}

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select, [tabindex]:not([tabindex="-1"])'

export default function ChatDrawer({ open, onClose, chat, turnstileRef }: Props) {
  const panel = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const [draft, setDraft] = useState('')

  // Focus in on open, back to the opener on close.
  useEffect(() => {
    if (!open) return
    const opener = document.activeElement as HTMLElement | null
    input.current?.focus()
    return () => {
      if (opener && typeof opener.focus === 'function') opener.focus()
    }
  }, [open])

  // Keep the newest turn in view.
  const logEnd = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (open) logEnd.current?.scrollIntoView?.({ block: 'end' })
  }, [open, chat.turns])

  if (!open) return null

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
      return
    }
    if (e.key !== 'Tab' || !panel.current) return
    const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null || el === document.activeElement)
    if (items.length === 0) return
    const first = items[0]
    const last = items[items.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const q = draft.trim()
    if (!q || chat.busy) return
    setDraft('')
    void chat.send(q)
  }

  return (
    <TechTooltipProvider>
      <div className="fixed inset-0 z-[60]" onKeyDown={onKeyDown}>
        <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-hidden />
        <div
          ref={panel}
          role="dialog"
          aria-modal="true"
          aria-label="Ask the assistant"
          className="absolute inset-y-0 right-0 flex w-full max-w-full flex-col border-l border-border bg-surface shadow-xl animate-slide-up motion-reduce:animate-none sm:w-[28rem]"
        >
          <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
            <h2 className="text-base font-semibold">Ask the assistant</h2>
            <div className="flex gap-2">
              {chat.turns.length > 0 ? (
                <button type="button" className="min-h-9 rounded px-2 text-xs text-muted hover:text-accent" onClick={chat.clear}>
                  New conversation
                </button>
              ) : null}
              <button type="button" className="min-h-9 min-w-9 rounded px-2 text-muted hover:text-accent" aria-label="Close the assistant" onClick={onClose}>
                &times;
              </button>
            </div>
          </header>

          <div role="log" aria-live="polite" aria-label="Conversation" className="min-h-0 flex-1 space-y-4 overflow-y-auto overflow-x-hidden px-4 py-3">
            {chat.turns.length === 0 ? (
              <>
                <EmptyState
                  icon="?"
                  title="Ask about the 2018-2025 seasons"
                  description="Every number in an answer links to the card and page behind it. A number with no source is struck through."
                />
                <p className="text-xs text-muted">
                  Labels:{' '}
                  <TechTooltip content="Measured or computed directly from the published laps and results.">
                    <button type="button" className="underline decoration-dotted">measured</button>
                  </TechTooltip>
                  ,{' '}
                  <TechTooltip content="An estimate from a model, shown hatched. The page shows how it is built.">
                    <button type="button" className="underline decoration-dotted">modelled</button>
                  </TechTooltip>
                  ,{' '}
                  <TechTooltip content="No value is published, so a dash is shown with the reason. Never a zero.">
                    <button type="button" className="underline decoration-dotted">unavailable</button>
                  </TechTooltip>
                  .
                </p>
              </>
            ) : null}

            {chat.turns.map((t) => (
              <article key={t.id} className="space-y-2" aria-label={`Question: ${t.question}`}>
                <p className="rounded bg-accent-subtle px-3 py-2 text-sm break-words">{t.question}</p>
                {t.status === 'pending' ? (
                  <p className="text-xs text-muted" data-testid="step-progress">
                    {t.steps.length ? t.steps[t.steps.length - 1] : 'Working...'}
                  </p>
                ) : null}
                {t.status === 'error' && t.error ? (
                  <div role="alert" className="space-y-2 rounded border border-red-500/30 bg-red-500/5 p-3 text-sm" data-testid={`error-${t.error.kind}`}>
                    <p>{t.error.text}</p>
                    {t.error.kind === 'updated' ? (
                      <button type="button" className="min-h-9 rounded border border-border px-3 text-xs" onClick={() => window.location.reload()}>
                        Reload
                      </button>
                    ) : null}
                    {t.error.kind === 'abuse' || t.error.kind === 'network' || t.error.kind === 'upstream' || t.error.kind === 'data' ? (
                      <button type="button" className="min-h-9 rounded border border-border px-3 text-xs" disabled={chat.busy} onClick={() => void chat.send(t.question)}>
                        Try again
                      </button>
                    ) : null}
                  </div>
                ) : null}
                {t.status === 'done' && t.result && t.sources ? (
                  <ErrorBoundary fallback={<p className="text-xs text-muted">{ERROR_TEXT.data}</p>}>
                    <AnswerView
                      answer={t.result.answer}
                      sources={t.sources}
                      notes={t.result.notes}
                      chartIds={t.result.chartIds}
                      links={t.result.links}
                      repairSkipped={t.result.repairSkipped}
                      onNavigate={onClose}
                    />
                  </ErrorBoundary>
                ) : null}
              </article>
            ))}
            <div ref={logEnd} />
          </div>

          <TurnstileGate ref={turnstileRef} />

          <form onSubmit={submit} className="border-t border-border px-4 py-3">
            <label htmlFor="assistant-question" className="mb-1 block text-xs text-muted">
              Your question
            </label>
            <div className="flex gap-2">
              <textarea
                id="assistant-question"
                ref={input}
                rows={2}
                value={draft}
                maxLength={600}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    submit(e)
                  }
                }}
                className="min-w-0 flex-1 resize-none rounded border border-border bg-transparent px-2 py-1 text-sm"
              />
              <button type="submit" disabled={chat.busy || !draft.trim()} className="min-h-9 rounded border border-border px-3 text-sm disabled:opacity-50">
                Send
              </button>
            </div>
          </form>
        </div>
      </div>
    </TechTooltipProvider>
  )
}
