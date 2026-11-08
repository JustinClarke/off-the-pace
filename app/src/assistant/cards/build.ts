// AX-04 buildCards: loop each kind's enumerate(), run its compute() (the feature's own query +
// transform), map to cards, pass every card through the publish gate and validateCard. A card
// validateCard rejects is never emitted; every refused row goes on the ungrounded list with a
// reason. Runs anywhere the query layer runs: headless (scripts/build-cards.mjs) or in tests.
import { getRegisteredQuery } from '../../data/hooks/useQuery'
import { loadManifest, getTablePath } from '../../data/manifest'
import { registerParquet } from '../../data/duckdb/register'
import { rawQuery } from '../../data/hooks/useQuery'
import { registry, registryHash, heldReasonFor, classesLive as defaultLive } from './registry'
import type { AnySpec, CardClass, CardIndex, QueryRunner, ValueOutcome } from './kinds'
import type { Card, CardScope } from './card.types'
import { validateCard } from './validate'

export interface UngroundedEntry {
  id: string
  kind: string
  reason: string
  params: unknown
}

export interface BuildReport {
  cards: Card[]
  ungrounded: UngroundedEntry[]
  counts: Record<string, { params: number; active: number; held: number; refused: number }>
  versions: Card['versions']
}

export interface BuildOptions {
  /** Only these kinds. */
  kinds?: string[]
  /** Cap on parameter sets per kind (smoke runs). */
  limitPerKind?: number
  /** Override the parameter sets per kind (parity tests). */
  params?: Record<string, unknown[]>
  /** Override classesLive (tests only; publishing uses the registry's). */
  classesLive?: readonly CardClass[]
  specs?: readonly AnySpec[]
  q?: QueryRunner
  index?: CardIndex
}

/** A QueryRunner over the useQuery registry, memoised on (name, params) for one build. */
export function registryQueryRunner(): QueryRunner {
  const memo = new Map<string, Promise<unknown>>()
  return {
    run<T>(name: string, params: unknown = {}): Promise<T> {
      const key = `${name}|${JSON.stringify(params)}`
      let p = memo.get(key)
      if (!p) {
        const fn = getRegisteredQuery(name)
        if (!fn) return Promise.reject(new Error(`No query registered for key: ${name}`))
        p = fn(params)
        memo.set(key, p)
      }
      return p as Promise<T>
    },
  }
}

/** Seasons from the manifest; races from the published fct_lap_residuals partitions. */
export async function buildIndex(): Promise<CardIndex> {
  const manifest = await loadManifest()
  const seasons = manifest.stats?.seasons_list ?? []
  const races: CardIndex['races'] = []
  for (const season of seasons) {
    const alias = `fct_lap_residuals_${season}`
    await registerParquet(alias, getTablePath(manifest, 'fct_lap_residuals', season))
    const rows = await rawQuery<{ race_id: string }>(
      `SELECT DISTINCT race_id FROM ${alias} WHERE race_year = ? ORDER BY race_id`,
      [season],
    )
    for (const r of rows) races.push({ season, race_id: r.race_id })
  }
  return { dataVersion: manifest.version, seasons, races }
}

const EMPTY_SCOPE: CardScope = {
  season: null, race_id: null, driver_id: null, constructor_id: null,
  circuit_id: null, compound: null, stint_id: null, lap: null,
}

/** Map one outcome to a card through the publish gate. Pure: exported for the registry tests. */
export function assembleCard(
  spec: AnySpec,
  params: unknown,
  o: ValueOutcome,
  versions: Card['versions'],
  live: readonly CardClass[],
): { card: Card } | { refused: string; id: string } {
  const id = `${spec.kind}:${o.key.join(':')}`
  const heldReason = heldReasonFor(spec, live)
  if (!heldReason && !o.unavailable_reason && (o.n === null || o.n === undefined)) return { refused: 'no n: a source row with no n becomes no card (AI-01)', id }
  const caveats = spec.caveatRules.filter((r) => r.when(o, params)).map((r) => r.code)
  const base = {
    id,
    kind: spec.kind,
    metric: spec.metric,
    label: spec.label,
    unit: spec.unit,
    unavailable_reason: null,
    scope: { ...EMPTY_SCOPE, ...o.scope },
    source: spec.source,
    versions,
    page: spec.route ? { route: spec.route, params: o.pageParams, docs_slug: spec.docsSlug } : null,
    caveats,
    sample: 'na' as const,
    grade: null,
    policy_fields: o.policy_fields ?? {},
  }
  if (heldReason) {
    return {
      card: {
        ...base,
        value: null,
        display: null,
        n: { count: 0, unit: spec.nUnit },
        interval: null,
        status: 'held',
        held_reason: heldReason,
      },
    }
  }
  if (o.unavailable_reason) {
    // AX-07: whatever the row carried, an unavailable card never shows it (a suppressed rating stays out).
    return {
      card: {
        ...base,
        label: 'unavailable',
        unavailable_reason: o.unavailable_reason,
        value: null,
        display: null,
        n: { count: 0, unit: spec.nUnit },
        interval: null,
        status: 'active',
        held_reason: null,
      },
    }
  }
  return {
    card: {
      ...base,
      value: o.value,
      display: o.display,
      n: { count: o.n as number, unit: spec.nUnit },
      interval: o.interval
        ? { ...o.interval, level: o.interval.level ?? spec.intervalLevel, kind: spec.intervalKind }
        : null,
      status: 'active',
      held_reason: null,
    },
  }
}

/**
 * label_version comes from TX-05's mart_build_provenance, which the export writes to the manifest's
 * provenance block (AX-07 finding 5). Never hard-coded; null when the manifest has no provenance.
 */
export function labelVersionOf(manifest: unknown): string | null {
  const m = manifest as { provenance?: { label_version?: unknown } | null; label_version?: unknown }
  const v = m.provenance?.label_version ?? m.label_version
  return typeof v === 'string' && v ? v : null
}

/**
 * AX-07c: race_id -> calibration flag of that race's circuit (dim_circuits.calibration_flag via race_to_track).
 * Empty when the published files do not have the column yet (an export from before TX-13) or the query is not
 * available: a card then carries no calibration_flag at all, never a guessed one.
 */
export async function loadCircuitFlags(q: QueryRunner): Promise<Map<string, string>> {
  const out = new Map<string, string>()
  try {
    const rows = await q.run<{ race_id: string; calibration_flag: string | null }[]>('cards.race-circuit-flags', {})
    for (const r of rows ?? []) if (r.calibration_flag) out.set(r.race_id, r.calibration_flag)
  } catch {
    /* no calibration data in this export */
  }
  return out
}

/** Set policy_fields.calibration_flag on a race-scoped outcome (a flag the kind already set wins). */
export function withCalibrationFlag(o: ValueOutcome, flags: ReadonlyMap<string, string>): ValueOutcome {
  const raceId = o.scope.race_id
  const flag = raceId ? flags.get(raceId) : undefined
  if (!flag || o.policy_fields?.calibration_flag !== undefined) return o
  return { ...o, policy_fields: { ...o.policy_fields, calibration_flag: flag } }
}

export async function buildCards(opts: BuildOptions = {}): Promise<BuildReport> {
  const specs = (opts.specs ?? registry).filter((s) => !opts.kinds || opts.kinds.includes(s.kind))
  const live = opts.classesLive ?? defaultLive
  const q = opts.q ?? registryQueryRunner()
  const manifest = await loadManifest()
  const versions: Card['versions'] = {
    data_version: manifest.version,
    label_version: labelVersionOf(manifest),
    model_version: null,
    card_schema: '1',
    registry: registryHash,
  }
  const needIndex = specs.some((s) => !opts.params?.[s.kind])
  const index = opts.index ?? (needIndex ? await buildIndex() : { dataVersion: manifest.version, seasons: [], races: [] })

  const circuitFlags = await loadCircuitFlags(q)

  const cards: Card[] = []
  const seenIds = new Set<string>()
  const ungrounded: UngroundedEntry[] = []
  const counts: BuildReport['counts'] = {}
  for (const spec of specs) {
    const c = (counts[spec.kind] = { params: 0, active: 0, held: 0, refused: 0 })
    let all = opts.params?.[spec.kind] ?? (await spec.enumerate(index, q))
    if (opts.limitPerKind !== undefined) all = all.slice(0, opts.limitPerKind)
    for (const params of all) {
      c.params++
      let computed: unknown
      try {
        computed = await spec.compute(params, q)
      } catch (err) {
        ungrounded.push({ id: `${spec.kind}:?`, kind: spec.kind, reason: `compute failed: ${String(err)}`, params })
        c.refused++
        continue
      }
      const reason = spec.refusal(computed, params)
      if (reason) {
        for (const id of spec.ids(params, computed)) {
          ungrounded.push({ id, kind: spec.kind, reason, params })
          c.refused++
        }
        continue
      }
      for (const built of spec.build(params, computed)) {
        const o = withCalibrationFlag(built, circuitFlags)
        const r = assembleCard(spec, params, o, versions, live)
        if ('refused' in r) {
          ungrounded.push({ id: r.id, kind: spec.kind, reason: r.refused, params })
          c.refused++
          continue
        }
        const v = validateCard(r.card, { expectedIntervalKind: spec.intervalKind })
        if (!v.ok) {
          ungrounded.push({ id: r.card.id, kind: spec.kind, reason: `invalid card: ${v.errors.join('; ')}`, params })
          c.refused++
          continue
        }
        if (seenIds.has(r.card.id)) {
          ungrounded.push({ id: r.card.id, kind: spec.kind, reason: 'duplicate card id', params })
          c.refused++
          continue
        }
        seenIds.add(r.card.id)
        cards.push(r.card)
        if (r.card.status === 'held') c.held++
        else c.active++
      }
    }
  }
  return { cards, ungrounded, counts, versions }
}
