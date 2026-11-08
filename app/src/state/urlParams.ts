// AX-03: URL value parsing shared by FilterContext and its tests.

/** A URL value as an integer, or null when it is missing or not a plain integer (never NaN). */
export function intParam(raw: string | null): number | null {
  return raw !== null && /^-?\d+$/.test(raw) ? Number(raw) : null
}
