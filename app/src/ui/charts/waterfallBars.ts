import type { WaterfallBar } from './Waterfall'

/**
 * Build one waterfall bar from a possibly-NULL component (AP-01).
 *
 * A NULL value, or a value backed by zero laps, is `unavailable`: it has no height,
 * the running sum skips it, and it is never drawn as 0 s. `nUsed < nLaps` adds the
 * "based on k of n laps" note.
 *
 * `runningStart` is the cumulative sum before this bar; `advance` is false for
 * informational bars (track noise) that never enter the running sum.
 */
export function buildBar(
  label: string,
  value: number | null | undefined,
  nUsed: number,
  nLaps: number,
  color: string | undefined,
  runningStart: number,
  advance = true,
): { bar: WaterfallBar; nextStart: number } {
  if (value === null || value === undefined || nUsed <= 0) {
    return {
      bar: {
        label,
        value: null,
        start: advance ? runningStart : 0,
        sign: 'positive',
        color,
        unavailable: true,
        note: 'no measured laps',
      },
      nextStart: runningStart,
    }
  }
  const from = advance ? runningStart : 0
  return {
    bar: {
      label,
      value,
      start: value < 0 ? from + value : from,
      sign: value >= 0 ? 'positive' : 'negative',
      color,
      note: nUsed < nLaps ? `based on ${nUsed} of ${nLaps} laps` : undefined,
    },
    nextStart: advance ? runningStart + value : runningStart,
  }
}
