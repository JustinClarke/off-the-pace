// AX-21: resolveBundle(type, scope) -> the card ids of a question type's recipe, held stubs included,
// so one get_fact_cards({bundle}) call replaces up to five rounds (AX-10 wires it into the dispatcher).
//
// Ids follow AX-01's pattern (kind ':' scope key ...). A template ending in '*' is a prefix: with an
// `expand` callback (the card store) it is expanded here; without one it is returned as-is and the
// store expands it. A held link keeps ONE stub per kind (one stub carries the reason; more would
// spend the slot on repeats). A held link with no stub in the store comes back in `held` with the
// playbook's reason, so the model still sees why there is no number.
import playbookData from './playbook.json'

export interface RecipeStep {
  kind?: string
  tool?: string
  id?: string
  scope_from: string[]
  required: boolean
}
export interface HeldLink {
  kind: string
  id: string
  held_reason: string
}
export interface PlaybookType {
  type: string
  v1: string
  bundle: boolean
  examples: string[]
  recipe: RecipeStep[]
  allowed_conclusion: string
  forbidden_codes: string[]
  held_links: HeldLink[]
}
export interface GlossaryEntry {
  skill_measure: string
  column: string
  line: string
  status: 'live' | 'held'
  kinds: string[]
  no_card?: string[]
}
export interface Playbook {
  version: number
  classes_live: string[]
  pending_kinds: Record<string, { owner: string; expected: 'live' | 'held'; held_reason?: string }>
  glossary: GlossaryEntry[]
  types: PlaybookType[]
}

export const playbook = playbookData as unknown as Playbook

/** design 2.6: get_fact_cards returns at most 10 cards. */
export const BUNDLE_MAX_CARDS = 10

export interface BundleScope {
  season?: number
  race_id?: string
  driver_id?: string
  teammate_id?: string
  constructor_id?: string
  compound?: string
}

export interface ResolveOptions {
  /** Expand a prefix (template without its trailing '*') into the stored card ids, sorted. */
  expand?: (prefix: string) => string[]
  /** Whether an exact id is in the store. When given, absent ids are left out (held links fall back to `held`). */
  has?: (id: string) => boolean
  /** Fill teammate_id when the caller does not know it (the store reads it from the race mart). */
  teammateOf?: (race_id: string, driver_id: string) => string | null | undefined
}

export interface ResolvedBundle {
  type: string
  ids: string[]
  /** Held links with no stub in the store: the model gets the reason in place of a card. */
  held: { kind: string; held_reason: string }[]
  /** Recipe steps skipped because the scope lacks a key they need. */
  missing_scope: string[]
  /** Live recipe ids the store does not hold (only when `has` / `expand` is given). */
  absent: string[]
  /** Ids dropped by the 10-card cap (optional steps first). */
  dropped: string[]
}

/** Types whose recipe names cards: the enum of get_fact_cards' bundle argument. */
export function bundleTypes(pb: Playbook = playbook): string[] {
  return pb.types.filter((t) => t.bundle).map((t) => t.type).sort()
}

export function findType(type: string, pb: Playbook = playbook): PlaybookType | undefined {
  return pb.types.find((t) => t.type === type)
}

/** Fill {key} placeholders from the scope; null when a key is missing. */
export function fillTemplate(template: string, scope: BundleScope): string | null {
  let missing = false
  const out = template.replace(/\{([a-z_]+)\}/g, (_m, key: string) => {
    const v = (scope as Record<string, unknown>)[key]
    if (v === undefined || v === null || v === '') {
      missing = true
      return ''
    }
    return String(v)
  })
  return missing ? null : out
}

export function resolveBundle(type: string, scope: BundleScope, opts: ResolveOptions = {}): ResolvedBundle {
  const t = findType(type)
  if (!t || !t.bundle) throw new Error(`resolveBundle: ${type} has no card recipe`)
  const s: BundleScope = { ...scope }
  if (!s.teammate_id && s.race_id && s.driver_id && opts.teammateOf) {
    s.teammate_id = opts.teammateOf(s.race_id, s.driver_id) ?? undefined
  }

  const missing_scope: string[] = []
  const held: ResolvedBundle['held'] = []
  const absent: string[] = []
  // priority 0 = required live step, 1 = held link, 2 = optional step
  const picked: { id: string; prio: number }[] = []
  const seen = new Set<string>()
  const add = (id: string, prio: number) => {
    if (seen.has(id)) return
    seen.add(id)
    picked.push({ id, prio })
  }

  const resolve = (template: string, keepOne: boolean): string[] | null => {
    const id = fillTemplate(template, s)
    if (id === null) return null
    if (!id.endsWith('*')) return !opts.has || opts.has(id) ? [id] : []
    if (!opts.expand) return [id]
    const found = opts.expand(id.slice(0, -1))
    return keepOne ? found.slice(0, 1) : found
  }

  for (const step of t.recipe) {
    if (!step.kind || !step.id) continue
    const ids = resolve(step.id, false)
    if (ids === null) {
      if (step.required) missing_scope.push(step.id)
      continue
    }
    if (ids.length === 0) absent.push(fillTemplate(step.id, s) as string)
    for (const id of ids) add(id, step.required ? 0 : 2)
  }
  for (const link of t.held_links) {
    const ids = resolve(link.id, true)
    if (ids === null || ids.length === 0) {
      held.push({ kind: link.kind, held_reason: link.held_reason })
      continue
    }
    add(ids[0], 1)
  }

  const ordered = picked.map((p, i) => ({ ...p, i })).sort((a, b) => a.prio - b.prio || a.i - b.i)
  const kept = new Set(ordered.slice(0, BUNDLE_MAX_CARDS).map((p) => p.id))
  return {
    type,
    ids: picked.filter((p) => kept.has(p.id)).map((p) => p.id),
    held,
    missing_scope,
    absent,
    dropped: picked.filter((p) => !kept.has(p.id)).map((p) => p.id),
  }
}
