// AX-14: one number in an answer that a card backs. The number is a link to the page that explains it (the
// card's page.route and params through routeParams/navigate v2: the model never writes a URL). An info button
// (and hover and focus) shows the details panel the AnswerView renders under the paragraph.
// Label rendering: measured/computed plain; modelled/experimental hatched with the word; a number that came from
// a query result is tagged "plain count/average".
import { Link } from 'react-router-dom'
import type { Card } from '../cards/card.types'

export type ChipSource = { kind: 'card'; card: Card; href: string | null } | { kind: 'result' }

export const MODELLED_NOTE = 'Modelled: an estimate from a model, not a direct measurement. The page shows how it is built.'
export const RESULT_NOTE = 'Plain count/average computed from published data. It is not a fact card, a rating or a model output.'

const HATCH = 'repeating-linear-gradient(135deg, rgba(148,163,184,0.28) 0 4px, transparent 4px 8px)'

export function labelWord(card: Card): string {
  return card.label
}

export function isHatched(card: Card): boolean {
  return card.label === 'modelled' || card.label === 'experimental'
}

interface Props {
  text: string
  source: ChipSource
  active: boolean
  onActivate(): void
  onDeactivate(): void
  onToggle(): void
  onNavigate?(): void
}

export default function NumberChip({ text, source, active, onActivate, onDeactivate, onToggle, onNavigate }: Props) {
  const card = source.kind === 'card' ? source.card : null
  const hatched = card ? isHatched(card) : false
  const style = hatched ? { backgroundImage: HATCH } : undefined
  const tag = card ? (hatched ? card.label : null) : 'plain count/average'
  const base = 'inline-flex items-baseline gap-1 rounded border border-border px-1 font-mono text-[0.95em] align-baseline'
  const body = (
    <>
      {text}
      {tag ? <span className="font-sans text-[0.7em] uppercase tracking-wide text-muted">{tag}</span> : null}
    </>
  )
  return (
    <span className="inline-flex items-baseline" onMouseEnter={onActivate} onMouseLeave={onDeactivate}>
      {source.kind === 'card' && source.href ? (
        <Link
          to={source.href}
          className={`${base} text-accent underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2`}
          style={style}
          onFocus={onActivate}
          onBlur={onDeactivate}
          onClick={onNavigate}
          aria-label={`${text}, ${card ? card.label : ''}, open the page that explains it`}
        >
          {body}
        </Link>
      ) : (
        <span className={base} style={style} tabIndex={0} onFocus={onActivate} onBlur={onDeactivate}>
          {body}
        </span>
      )}
      <button
        type="button"
        className="ml-0.5 min-h-6 min-w-6 rounded text-xs text-muted hover:text-accent focus-visible:outline focus-visible:outline-2"
        aria-label={`Details for ${text}`}
        aria-expanded={active}
        onClick={onToggle}
      >
        i
      </button>
    </span>
  )
}
