import { describe, it, expect, beforeEach } from 'vitest'
import entitiesJson from '../entities/__fixtures__/assistant_entities.json'
import { compareLapTimes } from './compareLapTimes'
import { catalogue, makeManifest, spyEngine } from '../queryBuilder/__fixtures__/fixtures'
import { clearResults } from '../queryBuilder/store'
import { clearCharts } from './chartStore'
import type { EntityRow } from '../listValues'

const entities = entitiesJson as unknown as EntityRow[]

function scan(v: unknown, path = ''): string[] {
  const bad: string[] = []
  if (Array.isArray(v)) {
    if (v.filter((x) => typeof x === 'number').length > 10) bad.push(`${path}: array of more than 10 numbers`)
    v.forEach((x, i) => bad.push(...scan(x, `${path}[${i}]`)))
  } else if (v && typeof v === 'object') {
    for (const [k, x] of Object.entries(v)) {
      if (k === 'rows') bad.push(`${path}.rows`)
      if (k === 'lap_number') bad.push(`${path}.lap_number`)
      bad.push(...scan(x, `${path}.${k}`))
    }
  }
  return bad
}

describe('context leak', () => {
  beforeEach(() => { clearCharts(); clearResults() })
  it('the model-facing context of a comparison run holds no lap rows, rows key or number arrays', async () => {
    const rows = ['LEC', 'SAI'].flatMap((d) => Array.from({ length: 57 }, (_, i) => ({ driver_id: d, lap_number: i + 1, value: 90 + i / 7, n: 1, total_groups: 114 })))
    const out = await compareLapTimes('LEC', 'SAI', '2024_8', { catalogue, manifest: makeManifest(), engine: spyEngine(rows), entities })
    const context = JSON.stringify([{ role: 'tool', content: out }])
    expect(scan(JSON.parse(context))).toEqual([])
    expect(context.length).toBeLessThan(200)
    expect(context).not.toMatch(/90\.\d/)
  })
})
