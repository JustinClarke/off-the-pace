// AX-14: renders a checked answer. Render-time grounding (design 2.8): every number in the text is looked up in the
// cards and query results of THIS question (findUngroundedNumbers, the AX-10 function). A match becomes a NumberChip
// linking to the card's page; a miss is struck through with a note. Held and unavailable cards are listed with their
// reason (an unavailable value is a dash, never 0). Rule failures and loop notes are shown, not buried.
import { useMemo, useState, type ReactNode } from 'react'
import type { Card } from '../cards/card.types'
import { ChartCard } from './chartsLazy'
import type { Note } from '../core/loop'
import { cardLink } from '../../nav/routeParams'
import { collectSourceNumbers, extractAnswerNumbers, findUngroundedNumbers, numberMatches, sourceNumbersOfCard, type AnswerNumber } from '../grounding'
import NumberChip, { isHatched, MODELLED_NOTE, RESULT_NOTE, type ChipSource } from './NumberChip'

export const UNGROUNDED_NOTE = 'this number is not backed by a card or a query result'

export interface AnswerSources {
  cards: readonly Card[]
  results: readonly unknown[]
  texts: readonly string[]
}

interface Props {
  answer: string
  sources: AnswerSources
  notes?: readonly Note[]
  chartIds?: readonly string[]
  repairSkipped?: boolean
  /** Close the drawer when a chip link is followed (phone width). */
  onNavigate?(): void
}

type Piece = { kind: 'text'; text: string } | { kind: 'struck'; text: string } | { kind: 'chip'; key: string; text: string; source: ChipSource }

function sourceFor(n: AnswerNumber, answer: string, sources: AnswerSources): ChipSource | null {
  const abs: AnswerNumber = { ...n, value: Math.abs(n.value) }
  // Cards the answer names by id go first; the rest keep their order.
  const named = sources.cards.filter((c) => answer.includes(c.id))
  const ordered = [...named, ...sources.cards.filter((c) => !named.includes(c))]
  for (const c of ordered) {
    if (sourceNumbersOfCard(c).some((s) => numberMatches(abs, s))) return { kind: 'card', card: c, href: cardLink(c) }
  }
  if (collectSourceNumbers({ results: sources.results }).some((s) => numberMatches(abs, s))) return { kind: 'result' }
  return null // a number the question or an interval level grounds: plain text
}

export function pieces(answer: string, sources: AnswerSources): { parts: Piece[]; ungrounded: string[] } {
  const bad = findUngroundedNumbers(answer, { cards: sources.cards, results: sources.results, texts: sources.texts })
  const badAt = new Set(bad.map((b) => b.index))
  const parts: Piece[] = []
  let at = 0
  for (const n of extractAnswerNumbers(answer)) {
    if (n.index < at) continue
    if (n.index > at) parts.push({ kind: 'text', text: answer.slice(at, n.index) })
    at = n.index + n.text.length
    // AX-14 ruling 3: a leading minus (- or U+2212) belongs to the chip. Render only: matching still uses the bare number.
    let sign = ''
    const last = parts[parts.length - 1]
    if (last && last.kind === 'text' && !(parts.length > 1 && last.text.length === 1) && /(^|[^A-Za-z0-9)\].])[-\u2212]$/.test(last.text)) {
      sign = last.text.slice(-1)
      last.text = last.text.slice(0, -1)
      if (last.text === '') parts.pop()
    }
    if (badAt.has(n.index)) {
      parts.push({ kind: 'struck', text: sign + n.text })
      continue
    }
    const src = sourceFor(n, answer, sources)
    if (src) parts.push({ kind: 'chip', key: `${n.index}`, text: sign + n.text, source: src })
    else parts.push({ kind: 'text', text: sign + n.text })
  }
  if (at < answer.length) parts.push({ kind: 'text', text: answer.slice(at) })
  return { parts, ungrounded: bad.map((b) => b.text) }
}

function fmt(v: number | null): string {
  return v === null ? '-' : String(Math.round(v * 1e6) / 1e6)
}

function CardDetails({ card }: { card: Card }) {
  const iv = card.interval && card.interval.kind !== 'none' && card.interval.low !== null && card.interval.high !== null ? card.interval : null
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
      <dt className="text-muted">Card</dt>
      <dd className="break-all font-mono">{card.id}</dd>
      <dt className="text-muted">Value</dt>
      <dd>{card.display ?? `${card.value === null ? '-' : String(card.value)}${card.unit ? ` ${card.unit}` : ''}`}</dd>
      {iv ? (
        <>
          <dt className="text-muted">Interval</dt>
          <dd>{fmt(iv.low)} to {fmt(iv.high)} ({iv.kind}{iv.level !== null ? `, ${Math.round(iv.level * 100)}%` : ''})</dd>
        </>
      ) : null}
      <dt className="text-muted">Sample</dt>
      <dd>{card.n.count} {card.n.unit}</dd>
      <dt className="text-muted">Label</dt>
      <dd>{card.label}</dd>
      <dt className="text-muted">Versions</dt>
      <dd>label {card.versions.label_version ?? '-'}, model {card.versions.model_version ?? '-'}</dd>
    </dl>
  )
}

export default function AnswerView({ answer, sources, notes = [], chartIds = [], repairSkipped, onNavigate }: Props) {
  const { parts, ungrounded } = useMemo(() => pieces(answer, sources), [answer, sources])
  const [hover, setHover] = useState<string | null>(null)
  const [pinned, setPinned] = useState<string | null>(null)
  const activeKey = pinned ?? hover
  const active = parts.find((p) => p.kind === 'chip' && p.key === activeKey)

  const unusable = sources.cards.filter((c) => c.status === 'held' || c.label === 'unavailable')
  const ruleNotes = notes.filter((n) => n.kind !== 'ungrounded')

  const body: ReactNode[] = parts.map((p, i) => {
    if (p.kind === 'text') return <span key={i}>{p.text}</span>
    if (p.kind === 'struck') {
      return (
        <del key={i} className="text-red-400" data-testid="struck-number">
          {p.text}
          <span className="sr-only"> ({UNGROUNDED_NOTE})</span>
        </del>
      )
    }
    return (
      <NumberChip
        key={i}
        text={p.text}
        source={p.source}
        active={activeKey === p.key}
        onActivate={() => setHover(p.key)}
        onDeactivate={() => setHover(null)}
        onToggle={() => setPinned((k) => (k === p.key ? null : p.key))}
        onNavigate={onNavigate}
      />
    )
  })

  return (
    <div className="space-y-2 text-sm">
      <p className="whitespace-pre-wrap break-words leading-relaxed">{body}</p>

      {active && active.kind === 'chip' ? (
        <div role="group" aria-label={`Details for ${active.text}`} className="rounded border border-border p-2" data-testid="chip-details">
          {active.source.kind === 'card' ? (
            <>
              <CardDetails card={active.source.card} />
              {isHatched(active.source.card) ? <p className="mt-1 text-xs text-muted">{MODELLED_NOTE}</p> : null}
            </>
          ) : (
            <p className="text-xs text-muted">{RESULT_NOTE}</p>
          )}
        </div>
      ) : null}

      {ungrounded.length > 0 ? (
        <p role="note" className="rounded border border-red-400/50 p-2 text-xs text-red-300" data-testid="ungrounded-note">
          Struck through: {ungrounded.join(', ')}. For each, {UNGROUNDED_NOTE}.
        </p>
      ) : null}

      {ruleNotes.length > 0 || repairSkipped ? (
        <ul role="note" className="space-y-1 rounded border border-yellow-400/40 p-2 text-xs text-yellow-200" data-testid="rule-notes">
          {ruleNotes.map((n, i) => (
            <li key={i}>
              Check not met: <span className="font-mono">{n.code}</span>{n.detail ? ` (${n.detail})` : ''}
            </li>
          ))}
        </ul>
      ) : null}

      {chartIds.map((id) => (
        <ChartCard key={id} chartId={id} />
      ))}

      {unusable.length > 0 ? (
        <section aria-label="Cards without a value" className="space-y-1 text-xs">
          {unusable.map((c) => (
            <p key={c.id} data-testid="unusable-card">
              <span className="font-mono break-all">{c.id}</span>: <span aria-label="no value">&mdash;</span>{' '}
              {c.status === 'held' ? `held: ${c.held_reason ?? ''}` : `unavailable: ${c.unavailable_reason ?? ''}`}
            </p>
          ))}
        </section>
      ) : null}
    </div>
  )
}
