// AX-01: the checked-in generated types match what the generator writes from the schema today.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
// @ts-expect-error plain .mjs script without a declaration file
import { generate, TS_FILE, PY_FILE } from '../../../scripts/gen-card-types.mjs'

describe('AX-01 generated card types', () => {
  it('card.types.ts and card_types.py are not stale (run node scripts/gen-card-types.mjs)', () => {
    const { ts, py } = generate() as { ts: string; py: string }
    expect(readFileSync(TS_FILE, 'utf8')).toBe(ts)
    expect(readFileSync(PY_FILE, 'utf8')).toBe(py)
  })
})
