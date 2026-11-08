// AX-21: system.md fits AX-10's 1,200-token instruction slot, carries no data values, names every
// question type and skill measure, and AX-08's gen-tools builds with it and with the bundle enum.
// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { estimateTokens } from '../../nav/pageSummaries.mjs'
import { playbook, bundleTypes } from './bundles'

const HERE = import.meta.dirname
const system = readFileSync(join(HERE, 'system.md'), 'utf8').trim()

describe('AX-21 system prompt', () => {
  it('is at most 1,200 tokens by estimateTokens', () => {
    expect(estimateTokens(system)).toBeLessThanOrEqual(1200)
  })

  it('carries no data values (no decimals, percentages or seconds)', () => {
    expect(system).not.toMatch(/\d+\.\d+/)
    expect(system).not.toMatch(/\d\s?%/)
    expect(system).not.toMatch(/\d\s?s\b/)
  })

  it('names every question type and every skill measure', () => {
    for (const t of playbook.types) expect(system, t.type).toContain(t.type)
    for (const g of playbook.glossary) expect(system, g.skill_measure).toContain(g.skill_measure)
  })

  it('does not claim capabilities unverified on Workers AI', () => {
    expect(system).not.toMatch(/multi-?round|several rounds|reasoning tokens?/i)
  })

  it('keeps the order: scope, grounding, labels, method, chains, glossary, refusals, what-if, style', () => {
    const at = (s: string) => system.indexOf(s)
    const order = ['2018-2025', 'Grounding.', 'Labels.', 'Method.', 'Never make these chains', 'Skill measures', 'Refusals.', 'What-if', 'Style.']
    for (const s of order) expect(at(s), s).toBeGreaterThanOrEqual(0)
    expect(order.map(at)).toEqual([...order.map(at)].sort((a, b) => a - b))
  })

  it('gen-tools builds with this prompt and the playbook bundle enum', async () => {
    const worker = join(HERE, '../../../../worker')
    // @ts-expect-error plain .mjs outside the app project
    const { generate, LIMITS } = await import('../../../../worker/scripts/gen-tools.mjs')
    const r = generate({
      dataDir: join(worker, 'test/fixtures'),
      systemPath: join(HERE, 'system.md'),
      toolsPath: join(HERE, 'tools.template.json'),
      playbookPath: join(HERE, 'playbook.json'),
    })
    expect(r.tokens.system).toBeLessThanOrEqual(LIMITS.system)
    expect(r.tokens.tools).toBeLessThanOrEqual(LIMITS.tools)
    const tools = JSON.parse(r.src.split('export const TOOLS: unknown[] = ')[1].replace(/;\s*$/, ''))
    const get = tools.find((t: { function: { name: string } }) => t.function.name === 'get_fact_cards')
    expect(get.function.parameters.properties.bundle.enum).toEqual(bundleTypes())
  })
})
