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
// onset_source fitted (an own-history fit), the same rule as dim_compounds_season.is_measured;
// cross_season_fallback, pooled_compound_fallback and carried_forward onsets are borrowed numbers
// and are drawn as one lap with a "from other seasons" note, not counted as measured. A compound with fewer than
// MIN_MEASURED_ONSET_CELLS measured cells (INTERMEDIATE, WET, HYPERSOFT at the 2026-10-15 fit)
// gets no range, only the label. At that fit the ranges were HARD 15-26.5, MEDIUM 14-23,
// SOFT 15-23 laps.

/** Visible label for a class_default cell. */
export const CLIFF_ESTIMATE_LABEL = 'estimate, no data for this track'

/** onset_source values that count as a measured onset for the range (own-history fits only). */
export const MEASURED_ONSET_SOURCES = ['fitted'] as const

/** Note shown beside a borrowed (non-own-history, non-default) parameter. */
export const BORROWED_ESTIMATE_LABEL = 'from other seasons or tracks'

/** Note shown beside a parameter whose source column is null or missing: not known to be fitted. */
export const UNKNOWN_SOURCE_LABEL = 'source unknown'

/** What a single parameter's own source column says about it. null = fitted, no note needed. */
export type ParamSourceNote = 'estimate' | 'borrowed' | 'unknown' | null

/** Per-parameter provenance from that parameter's OWN source column (onset_source,
 *  gradient_source, severity_source), never from the cell's overall provenance class.
 *  fitted -> null; class_default -> 'estimate'; null/missing/empty -> 'unknown' (kept distinct,
 *  never treated as fitted); any other value (cross_season_fallback, pooled_compound_fallback,
 *  carried_forward, ...) -> 'borrowed'. */
export function paramSourceNote(source: string | null | undefined): ParamSourceNote {
  if (source == null || source === '') return 'unknown'
  if (source === 'fitted') return null
  if (source === 'class_default') return 'estimate'
  return 'borrowed'
}

/** Visible note text for a parameter source note, or null when none is shown. */
export function paramNoteLabel(note: ParamSourceNote): string | null {
  if (note === 'estimate') return CLIFF_ESTIMATE_LABEL
  if (note === 'borrowed') return BORROWED_ESTIMATE_LABEL
  if (note === 'unknown') return UNKNOWN_SOURCE_LABEL
  return null
}

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

/** How to show a cliff onset: one lap when measured (flagged borrowed if not own-history), a range (or label only) when it is a default. */
export type CliffOnsetDisplay =
  | { kind: 'measured'; lap: number; borrowed?: true; unknown?: true }
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
  // A pooled, cross-season or carried-forward onset is a real number but not this cell's own fit;
  // a null source is kept distinct (unknown), never labelled fitted.
  const note = paramSourceNote(onsetSource)
  if (note === 'borrowed') return { kind: 'measured', lap: onsetLap, borrowed: true }
  if (note === 'unknown') return { kind: 'measured', lap: onsetLap, unknown: true }
  return { kind: 'measured', lap: onsetLap }
}

/** "laps 15-27" (en dash). */
export function formatOnsetRange([lo, hi]: [number, number]): string {
  return `laps ${lo}–${hi}`
}
