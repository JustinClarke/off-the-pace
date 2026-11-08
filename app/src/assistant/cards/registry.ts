// AX-04 card registry: every card kind, the classes that are live, and the registry hash.
//
// classesLive is ['T'] from AX-07 (rule 4 of BUILD-ORDER): the lineage table is saved
// (_evidence/ax-07-lineage/lineage.json) and filter-only air-state use is T with the
// AIR_STATE_FILTER caveat (HD13). DA, TRAFFIC and ML kinds stay held (HD2 = C).
import { sha256Hex } from './sha256'
import type { AnySpec, CardClass } from './kinds'
import { cardKinds as eraKinds } from '../../features/era-ratings-timeline/cards'
import { cardKinds as raceLostKinds } from '../../features/race-lost/cards'
import { cardKinds as pitKinds } from '../../features/pit-strategy/cards'
import { cardKinds as raceKinds } from './sql/raceKinds'
import { stubKinds } from './sql/heldStubs'
import { cardKinds as seasonKinds } from './sql/seasonKinds'

export type { CardKindSpec, CardClass, CardIndex, QueryRunner, ValueOutcome } from './kinds'

/**
 * Classes whose cards may be published with a value. AX-07: only 'T'. Filter-only kinds are
 * registered as 'T' with the AIR_STATE_FILTER caveat; 'T-F' is never used as a kind class.
 */
export const classesLive: readonly CardClass[] = ['T']

/** Sources no card may read (AD5: the chance line has no card kind). */
export const FORBIDDEN_SOURCES = [/flag_chance_lookup/i]

export function forbiddenSourceOf(spec: Pick<AnySpec, 'source'>): string | null {
  const fields = [spec.source.mart, spec.source.query, ...spec.source.columns].filter((x): x is string => !!x)
  for (const f of fields) if (FORBIDDEN_SOURCES.some((rx) => rx.test(f))) return f
  return null
}

/** Throws on a duplicate kind or a forbidden source. Run on the registry at import time. */
export function assertSpecs(specs: AnySpec[]): AnySpec[] {
  const seen = new Set<string>()
  for (const s of specs) {
    if (seen.has(s.kind)) throw new Error(`duplicate card kind ${s.kind}`)
    seen.add(s.kind)
    const bad = forbiddenSourceOf(s)
    if (bad) throw new Error(`card kind ${s.kind} reads a forbidden source (${bad}); the chance line has no card (AD5)`)
  }
  return specs
}

export const registry: readonly AnySpec[] = assertSpecs([...eraKinds, ...raceLostKinds, ...pitKinds, ...raceKinds, ...seasonKinds, ...stubKinds])

/**
 * The declarative part of a spec, serialised in a fixed key order. Function bodies are left out
 * on purpose: Vite SSR, vitest and the browser bundle rewrite imports inside them differently, so
 * hashing them would make the hash depend on the loader. Logic changes bump `rev` instead.
 */
export function serialiseSpec(s: AnySpec): string {
  return JSON.stringify({
    kind: s.kind,
    class: s.class,
    metric: s.metric,
    label: s.label,
    unit: s.unit,
    intervalKind: s.intervalKind,
    intervalLevel: s.intervalLevel,
    nUnit: s.nUnit,
    source: s.source,
    route: s.route,
    docsSlug: s.docsSlug,
    held: s.held ?? null,
    rev: s.rev,
    caveats: s.caveatRules.map((r) => r.code),
  })
}

export function computeRegistryHash(specs: readonly AnySpec[], live: readonly CardClass[] = classesLive): string {
  const body = [...specs].sort((a, b) => a.kind.localeCompare(b.kind)).map(serialiseSpec)
  return sha256Hex(JSON.stringify({ classesLive: [...live].sort(), specs: body }))
}

/** sha256 of the serialised specs; goes in every card's versions.registry. */
export const registryHash: string = computeRegistryHash(registry)

/** Why a kind's cards are published held, or null when they may carry a value. */
export function heldReasonFor(spec: AnySpec, live: readonly CardClass[] = classesLive): string | null {
  if (spec.held) return spec.held
  if (!live.includes(spec.class)) {
    return `CLASS_NOT_LIVE: class ${spec.class} is not live yet (BUILD-ORDER rule 4; transform class goes live at AX-07)`
  }
  return null
}
