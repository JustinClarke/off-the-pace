// Presentation of compound-cliff cells that are not measured.
//
// dim_compounds_season carries a source tag per parameter (onset_source, gradient_source,
// severity_source). A cell tagged class_default had no stints to fit, so its number is the
// compound-class placeholder from COMPOUND_DEFAULTS (fit_compound_cliff.py), not a value for
// this track. Those cells are shown as an estimate labelled "no data for this track", and the
// cliff lap is shown as a range instead of a single number.
//
// The range is the interquartile range of the measured onsets for the compound, computed in
// DuckDB from the published dim_compounds_season (a straight lift of the live
// compound_cliff_params seed), so it follows the seed on every re-fit. Measured means
// onset_source fitted or cross_season_fallback. A compound with fewer than
// MIN_MEASURED_ONSET_CELLS measured cells (INTERMEDIATE, WET, HYPERSOFT at the 2026-10-15 fit)
// gets no range, only the label. At that fit the ranges were HARD 15-26.5, MEDIUM 14-23,
// SOFT 15-23 laps.

/** Visible label for a class_default cell. */
export const CLIFF_ESTIMATE_LABEL = 'estimate, no data for this track'

/** onset_source values that count as a measured onset for the range. */
export const MEASURED_ONSET_SOURCES = ['fitted', 'cross_season_fallback'] as const

/** Below this many measured onsets for a compound, the range is too thin to show. */
export const MIN_MEASURED_ONSET_CELLS = 5

/**
 * CTE `onset_iqr(compound_code, onset_iqr_low, onset_iqr_high)` over every circuit and season
 * of dim_compounds_season. Needs dim_compounds_season registered. Use after WITH.
 */
export const ONSET_IQR_CTE = `onset_iqr AS (
        SELECT
          compound_code,
          quantile_cont(compound_cliff_onset_laps, 0.25) AS onset_iqr_low,
          quantile_cont(compound_cliff_onset_laps, 0.75) AS onset_iqr_high
        FROM dim_compounds_season
        WHERE onset_source IN (${MEASURED_ONSET_SOURCES.map(s => `'${s}'`).join(', ')})
          AND compound_cliff_onset_laps IS NOT NULL
        GROUP BY compound_code
        HAVING count(*) >= ${MIN_MEASURED_ONSET_CELLS}
      )`

/** True when a parameter's source tag says it is the compound-class placeholder. */
export function isClassDefault(source: string | null | undefined): boolean {
  return source === 'class_default'
}

/** How to show a cliff onset: one lap when measured, a range (or label only) when it is a default. */
export type CliffOnsetDisplay =
  | { kind: 'measured'; lap: number }
  | { kind: 'estimate'; range: [number, number] | null }

export function cliffOnsetDisplay(
  onsetLap: number | null | undefined,
  onsetSource: string | null | undefined,
  iqrLow: number | null | undefined,
  iqrHigh: number | null | undefined,
): CliffOnsetDisplay | null {
  if (isClassDefault(onsetSource)) {
    const range: [number, number] | null =
      iqrLow != null && iqrHigh != null ? [Math.round(iqrLow), Math.round(iqrHigh)] : null
    return { kind: 'estimate', range }
  }
  if (onsetLap == null) return null
  return { kind: 'measured', lap: onsetLap }
}

/** "laps 15-27" (en dash). */
export function formatOnsetRange([lo, hi]: [number, number]): string {
  return `laps ${lo}–${hi}`
}
