// AX-01 card projections.
//
// toModelProjection: the compact form get_fact_cards puts into the model's context (design
//   2.2, about 45-60 tokens). It never carries the page route or params, interval source
//   columns or versions: the browser keeps the full card for links and hover.
// toCheckerCard: flattens a card into the loose FactCard the AI-02 honesty checker reads
//   (policy.json triggers read flat fields such as n, n_unit and source_page).
import type { FactCard } from '../honesty/checker'
import type { Card } from './card.types'

export interface ModelProjection {
  id: string
  m: string
  v: number | string | boolean | null
  u: string | null
  lbl: Card['label']
  n: string
  iv: [number, number, string] | null
  cav: string[]
  pg: string | null
  /** AX-07 ruling 4: rating_trust_label, only when the card carries it. */
  trust?: string
  /** rank_separated_from_next, only when present (boolean). */
  rank_sep?: boolean
  /** coverage_reason, only when present. */
  cov?: string
  /** The unavailable or held reason; present only when v is null. */
  why?: string
}

/** Longest why the projection carries; the full reason stays on the card for the drawer. */
export const WHY_MAX_CHARS = 64

function clip(text: string): string {
  if (text.length <= WHY_MAX_CHARS) return text
  const cut = text.slice(0, WHY_MAX_CHARS - 1)
  const sp = cut.lastIndexOf(' ')
  return `${(sp > WHY_MAX_CHARS / 2 ? cut.slice(0, sp) : cut).replace(/[\s,;:]+$/, '')}…`
}

/** Six significant digits: enough for any page's display precision, without float noise. */
function compactNumber(v: number): number {
  return Number(v.toPrecision(6))
}

export function toModelProjection(card: Card): ModelProjection {
  const iv =
    card.interval && card.interval.kind !== 'none' && card.interval.low !== null && card.interval.high !== null
      ? ([compactNumber(card.interval.low), compactNumber(card.interval.high), card.interval.kind] as [number, number, string])
      : null
  const out: ModelProjection = {
    id: card.id,
    m: card.metric.replace(/_/g, ' '),
    v: typeof card.value === 'number' ? compactNumber(card.value) : card.value,
    u: card.unit,
    lbl: card.label,
    n: `${card.n.count} ${card.n.unit}`,
    iv,
    cav: card.caveats,
    pg: card.page?.docs_slug ?? null,
  }
  const pf = card.policy_fields ?? {}
  if (typeof pf.rating_trust_label === 'string') out.trust = pf.rating_trust_label
  if (typeof pf.rank_separated_from_next === 'boolean') out.rank_sep = pf.rank_separated_from_next
  if (typeof pf.coverage_reason === 'string') out.cov = pf.coverage_reason
  if (out.v === null) {
    const why = card.status === 'held' ? card.held_reason : card.unavailable_reason
    out.why = clip(why ?? (card.status === 'held' ? 'held' : 'unavailable'))
  }
  return out
}

export function toCheckerCard(card: Card): FactCard {
  return {
    id: card.id,
    kind: card.kind,
    metric: card.metric,
    label: card.label,
    status: card.status,
    value: card.value,
    unit: card.unit ?? undefined,
    n: card.n.count,
    n_unit: card.n.unit,
    interval:
      card.interval && card.interval.low !== null && card.interval.high !== null
        ? { low: card.interval.low, high: card.interval.high, kind: card.interval.kind, ...(card.interval.level !== null ? { level: card.interval.level } : {}) }
        : null,
    scope: { ...card.scope },
    source_table: card.source.mart ?? undefined,
    source_page: card.page?.docs_slug ?? undefined,
    model_version: card.versions.model_version ?? undefined,
    caveats: card.caveats,
    sample: card.sample,
    grade: card.grade,
    // AX-10: the grounding check reads the numbers in these texts as card numbers.
    ...(card.display ? { display: card.display } : {}),
    ...(card.unavailable_reason ? { unavailable_reason: card.unavailable_reason } : {}),
    ...(card.held_reason ? { held_reason: card.held_reason } : {}),
    ...card.policy_fields,
  }
}
