// AX-04 card kind specs: the contract each feature's cards.ts implements (design 2.4).
//
// A spec never computes a number itself. compute() calls the feature's OWN registered queries
// and transform() (P2), so a card cannot drift from its page; build() only maps that output to
// card fields. interval.kind, n.unit and the label come from the spec, never from the data.
import type { CardLabel, CardPolicyFields, CardScope, CardSource, IntervalKind, NUnit } from './card.types'

/**
 * Card class, assigned from dbt lineage (AX-07a lineage.md section 0; final in AX-07):
 * T transform-only, T-F transform-only with the air-state filter caveat (HD13), DA dirty-air
 * dependent, TRAFFIC exposure / WC, ML model output.
 */
export type CardClass = 'T' | 'T-F' | 'DA' | 'TRAFFIC' | 'ML'

/** Runs a registered query by name (the useQuery registry), memoised per build. */
export interface QueryRunner {
  run<T = unknown>(name: string, params?: unknown): Promise<T>
}

/** What a kind may enumerate over: built once per run from the published files. */
export interface CardIndex {
  dataVersion: string
  seasons: number[]
  races: { season: number; race_id: string }[]
}

/** One card candidate with a value, before the publish gate (held / class / validation). */
export interface ValueOutcome {
  /** Scope key and variant segments; the id is kind ':' key.join(':'). */
  key: (string | number)[]
  scope: Partial<CardScope>
  value: number | string | boolean | null
  display: string | null
  /** null or undefined: the row has no n, so it becomes no card (ungrounded). */
  n: number | null | undefined
  interval?: { low: number | null; high: number | null; level: number | null; source_columns: string[] } | null
  pageParams: Record<string, string | number>
  policy_fields?: CardPolicyFields
  /**
   * Set: the card is published with label 'unavailable', value null, n 0 and no interval, and this
   * reason (AX-07: a suppressed rating, an unrated race). Unavailable is a value with a reason, never 0.
   */
  unavailable_reason?: string | null
}

export interface CaveatRule<P> {
  /** An AI-02 policy rule code (policy.json). */
  code: string
  when: (o: ValueOutcome, params: P) => boolean
}

export interface CardKindSpec<P = unknown, C = unknown> {
  kind: string
  class: CardClass
  metric: string
  label: CardLabel
  /** Unit of the card value (s, lap, ...). */
  unit: string | null
  intervalKind: IntervalKind
  /** Interval level the source columns represent (0.95 for a 95% CI), or null. */
  intervalLevel: number | null
  nUnit: NUnit
  source: CardSource
  route: string | null
  docsSlug: string | null
  /** Set: every card of this kind is published held with this reason (no value). */
  held?: string
  /** Bump when compute/build logic changes; part of the registry hash (function bodies are not). */
  rev: number
  enumerate(index: CardIndex, q: QueryRunner): Promise<P[]>
  /** The feature's own query + transform call chain for one parameter set. */
  compute(params: P, q: QueryRunner): Promise<C>
  /** A reason every card for this parameter set is refused, or null. */
  refusal(computed: C, params: P): string | null
  /** Card ids a refusal covers (so each refused row is listed). */
  ids(params: P, computed: C): string[]
  build(params: P, computed: C): ValueOutcome[]
  pageParams(params: P): Record<string, string | number>
  caveatRules: CaveatRule<P>[]
  /** Card ids the page shows for these parameters (drawer pre-load). */
  onScreen(params: P): string[]
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnySpec = CardKindSpec<any, any>

/** Identity helper that keeps P and C inferred per spec. */
export function defineKind<P, C>(spec: CardKindSpec<P, C>): CardKindSpec<P, C> {
  return spec
}
