import type { DirtyAirCostRow } from './queries'

/**
 * DD-WC2 disclaimer, word for word (_roadmap/_wake-calibration/status/build-log.json; reworded by the owner 2026-10-31).
 * Shown with every modelled value; the warehouse rows carry the same text.
 */
export const DD_WC2_DISCLAIMER =
  "Modelled: an assumed typical loss for this circuit, season, tyre and car, applied to the measured time spent close behind another car. Not calibrated on this driver's own stints."

/** Second line, placeholder-specific (WC-11; kept by the owner 2026-10-30; reworded by DD-WC30 2026-11-01 so it no longer repeats DD-WC2). */
export const PLACEHOLDER_LINE =
  'Placeholder = an interim value set by a fixed rule, not a measurement of this lap.'

/**
 * WC-16: the assumed tyre factors, for the Assumptions disclosure. 2019-2025: by the lap's Pirelli C-number
 * against the race's medium (seeds/wake_placeholder_c_number_factor.csv); 2018: the WC-13 relative class
 * (seeds/wake_placeholder_compound_factor.csv).
 */
export const TYRE_FACTOR_SUMMARY =
  "by the lap's Pirelli C-number against the race's medium compound: one step softer x1.10, two or more x1.17, "
  + 'one step harder x0.96, two or more x0.93, medium x1.00; '
  + '2018 races: softest x1.10, middle x1.00, hardest x0.96; intermediate and wet x1.00 (neutral)'

/**
 * The "How It's Calculated" badge text. Built from TYRE_FACTOR_SUMMARY so the badge, the
 * Assumptions disclosure and the seeds cannot drift apart (review R1, WC-16).
 */
export const HOW_CALCULATED =
  'Each race has an assumed loss for a full lap within 1 s of the car ahead, set by a fixed rule: the layout\'s corner mix (fast corners count most, slow corners and flat-out kinks least) times an assumed factor for the car generation (2022 ground-effect cars are assumed to follow more easily). Nothing is fitted to lap times; the race\'s basis is printed under the disclaimer. '
  + `Each lap then gets a small assumed tyre factor, set ${TYRE_FACTOR_SUMMARY}, and a car factor (1.00 for every team), held to 0.15-0.55 s. `
  + 'A lap is charged that loss times the measured share of the lap within 1 s, plus half the share between 1 and 2 s; nothing beyond 2 s. Laps with no measured gap and safety car, VSC or red flag laps have no value (—), never 0.'

/** Shown wherever a value is unavailable. Never 0. */
export const UNAVAILABLE = '—'

export interface DirtyAirResult {
  rank: number
  driver_id: string
  total_placeholder_cost_s: number | null
  avg_placeholder_cost_s: number | null
  laps_modelled: number
  laps_unavailable: number
  total_laps: number
  unavailable_reasons: string | null
  constructor_id: string | null
  /** WC-13: car factor with its basis, e.g. '1.00 (neutral default)'. */
  car_factor: string
  /** WC-13: tyre factors on the driver's modelled laps, with the C-number since WC-16 (e.g. 'SOFT (C4) x1.10'); '—' when none. */
  tyre_factors: string
  /** WC-13: factor fallback flags for the driver's laps; NULL when every factor resolved. */
  factor_flags: string | null
  /** Always 'modelled' or 'unavailable': nothing on this page is measured. */
  value_label: 'modelled' | 'unavailable'
}

export interface DirtyAirTotals {
  /** Field total over every lap with a value; NULL when no lap has one. */
  total_s: number | null
  /** Share of the total that is modelled (placeholder): 1 whenever total_s is set. */
  modelled_share: number | null
  laps_modelled: number
  laps_unavailable: number
  corner_class: string | null
  /** The race's assumed loss for a full lap within 1 s, before tyre and car factors (one value per race). */
  race_loss_s_per_lap_within_1s: number | null
  /** WC-13: true when every driver's car factor is the seed's neutral default. */
  car_factors_all_neutral: boolean
  /** WC-13: modelled laps on a neutral tyre factor (wet / intermediate or missing compound). */
  laps_tyre_neutral: number
  /** WC-13: laps whose race x tyre x car value was held to the bounds. */
  laps_lap_loss_bounded: number
  era: string | null
  era_factor: number | null
  loss_source: string | null
  /** True when the race used the circuit-class fallback, not the rule. */
  is_fallback: boolean
  loss_basis: string | null
}

/** WC-13: the car factor and its basis; the neutral default is always said to be one. */
export function formatCarFactor(r: Pick<DirtyAirCostRow, 'constructor_factor' | 'constructor_factor_source' | 'constructor_basis'>): string {
  const f = r.constructor_factor == null ? UNAVAILABLE : r.constructor_factor.toFixed(2)
  switch (r.constructor_factor_source) {
    case 'neutral_default': return `${f} (neutral default, no public evidence used)`
    case 'public_concept': return `${f} (public concept: ${r.constructor_basis})`
    default: return `${f} (neutral fallback: ${r.constructor_basis})`
  }
}

export function transform(rows: DirtyAirCostRow[]): DirtyAirResult[] {
  return rows
    .slice()
    .sort((a, b) => (b.total_placeholder_cost_s ?? -Infinity) - (a.total_placeholder_cost_s ?? -Infinity))
    .map((r, i) => ({
      rank: i + 1,
      driver_id: r.driver_id,
      total_placeholder_cost_s: r.total_placeholder_cost_s,
      avg_placeholder_cost_s: r.avg_placeholder_cost_s,
      laps_modelled: r.laps_modelled,
      laps_unavailable: r.laps_unavailable,
      total_laps: r.total_laps,
      unavailable_reasons: r.unavailable_reasons,
      constructor_id: r.constructor_id,
      car_factor: formatCarFactor(r),
      tyre_factors: r.tyre_factors ?? UNAVAILABLE,
      factor_flags: r.factor_flags,
      value_label: r.total_placeholder_cost_s == null ? 'unavailable' : 'modelled',
    }))
}

export function totals(rows: DirtyAirCostRow[]): DirtyAirTotals {
  const withValue = rows.filter(r => r.total_placeholder_cost_s != null)
  const total = withValue.length
    ? withValue.reduce((s, r) => s + (r.total_placeholder_cost_s as number), 0)
    : null
  // Every value on this page is a placeholder, so the modelled share of the total
  // is all of it. Printed anyway (BUILD-ORDER rule 7) so the page never reads as measured.
  return {
    total_s: total,
    modelled_share: total == null ? null : 1,
    laps_modelled: rows.reduce((s, r) => s + r.laps_modelled, 0),
    laps_unavailable: rows.reduce((s, r) => s + r.laps_unavailable, 0),
    corner_class: rows[0]?.corner_class ?? null,
    race_loss_s_per_lap_within_1s: rows[0]?.race_loss_s_per_lap_within_1s ?? null,
    car_factors_all_neutral: rows.every(r => r.constructor_factor_source !== 'public_concept'),
    laps_tyre_neutral: rows.reduce((s, r) => s + (r.laps_tyre_neutral ?? 0), 0),
    laps_lap_loss_bounded: rows.reduce((s, r) => s + (r.laps_lap_loss_bounded ?? 0), 0),
    era: rows[0]?.era ?? null,
    era_factor: rows[0]?.era_factor ?? null,
    loss_source: rows[0]?.loss_source ?? null,
    is_fallback: rows[0]?.loss_source === 'class_fallback',
    loss_basis: rows[0]?.loss_basis ?? null,
  }
}

/** Seconds for display: '—' for unavailable, never 0. */
export function formatSeconds(v: number | null | undefined, digits = 2): string {
  return v == null || Number.isNaN(v) ? UNAVAILABLE : `${v.toFixed(digits)}s`
}

export function toCsvRows(rows: DirtyAirCostRow[]): Record<string, unknown>[] {
  return rows.map(r => ({
    driver_id: r.driver_id,
    total_placeholder_cost_s: r.total_placeholder_cost_s == null ? UNAVAILABLE : r.total_placeholder_cost_s.toFixed(3),
    avg_placeholder_cost_s: r.avg_placeholder_cost_s == null ? UNAVAILABLE : r.avg_placeholder_cost_s.toFixed(3),
    value_label: r.total_placeholder_cost_s == null ? 'unavailable' : 'modelled',
    value_kind: r.value_kind,
    laps_modelled: r.laps_modelled,
    laps_unavailable: r.laps_unavailable,
    unavailable_reasons: r.unavailable_reasons ?? '',
    total_laps: r.total_laps,
    corner_class: r.corner_class,
    race_loss_s_per_lap_within_1s: r.race_loss_s_per_lap_within_1s,
    avg_lap_loss_s: r.avg_lap_loss_s == null ? UNAVAILABLE : r.avg_lap_loss_s.toFixed(4),
    tyre_factors: r.tyre_factors ?? UNAVAILABLE,
    laps_tyre_neutral: r.laps_tyre_neutral,
    constructor_id: r.constructor_id ?? UNAVAILABLE,
    constructor_factor: r.constructor_factor,
    constructor_factor_source: r.constructor_factor_source,
    constructor_basis: r.constructor_basis,
    laps_lap_loss_bounded: r.laps_lap_loss_bounded,
    factor_flags: r.factor_flags ?? '',
    era: r.era,
    era_factor: r.era_factor,
    loss_source: r.loss_source,
    loss_bounded: r.loss_bounded,
    loss_basis: r.loss_basis,
    disclaimer: r.disclaimer,
    disclaimer_placeholder: r.disclaimer_placeholder,
  }))
}

/** Car factor sentence for the assumptions disclosure. */
export function carFactorNote(allNeutral: boolean): string {
  return allNeutral
    ? 'neutral default 1.00 for every team (no public evidence used; no team is assumed to suffer more or less in the wake)'
    : 'neutral default 1.00 except where a team row cites a public source (see the Car factor in each driver\'s detail)'
}

export interface AssumptionNotes {
  /** One line, always visible beside the disclosure toggle. */
  summary: string
  /** Detail lines shown when the disclosure is open. */
  rule: string | null
  tyre: string
  car: string
}

/** The assumption detail that used to be a dense block above the chart. Pure text, built from the same constants. */
export function assumptionNotes(sum: DirtyAirTotals): AssumptionNotes {
  const loss = sum.race_loss_s_per_lap_within_1s
  return {
    summary: loss != null
      ? `Assumed ${loss.toFixed(2)}s per full lap within 1 s for this race (placeholder), before tyre and car factors.`
      : `No assumed loss for this race ${UNAVAILABLE}.`,
    rule: sum.loss_basis ? `${sum.is_fallback ? 'FALLBACK · ' : ''}${sum.loss_basis}` : null,
    tyre: `Tyre factor (assumed, not tyre wear): ${TYRE_FACTOR_SUMMARY}`
      + (sum.laps_tyre_neutral > 0 ? ` · ${sum.laps_tyre_neutral} modelled laps on a neutral tyre factor` : '')
      + (sum.laps_lap_loss_bounded > 0 ? ` · ${sum.laps_lap_loss_bounded} laps held to the 0.15-0.55 s bounds` : ''),
    car: `Car factor: ${carFactorNote(sum.car_factors_all_neutral)}`,
  }
}

/** Field total line: always visible, never collapsed. */
export function fieldTotalLine(sum: DirtyAirTotals): string {
  return `Field total ${formatSeconds(sum.total_s, 1)} · modelled share ${
    sum.modelled_share == null ? UNAVAILABLE : `${Math.round(sum.modelled_share * 100)}%`} (placeholder) · ${
    sum.laps_modelled} laps with a value, ${sum.laps_unavailable} unavailable`
}
