// @vitest-environment node
// AX-06 / AXW5: the builder must not use the Query Lab's unbounded paths.
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const dir = __dirname
const sources = readdirSync(dir).filter((f) => f.endsWith('.ts') && !f.endsWith('.test.ts'))

describe('query builder imports', () => {
  it('has source files to scan', () => expect(sources.length).toBeGreaterThanOrEqual(5))
  for (const f of sources) {
    it(`${f} uses none of runLabQuery, assertReadOnly, registerPartitionedParquet, queryLab`, () => {
      const text = readFileSync(join(dir, f), 'utf8')
      const code = text.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '')
      for (const banned of ['runLabQuery', 'assertReadOnly', 'registerPartitionedParquet', 'queryLab']) {
        expect(code.includes(banned), `${f} mentions ${banned}`).toBe(false)
      }
    })
  }
})
