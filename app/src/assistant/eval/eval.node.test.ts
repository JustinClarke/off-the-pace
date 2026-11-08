// @vitest-environment node
// AX-13 STUB baseline over real published files (the AX-04 Node adapter, wasm DuckDB): every question once,
// through the real loop, graded. Skipped unless AX06_DATA_DIR (data root with assistant/qv, the catalogue and
// assistant_entities) and AX10_CARDS (a build-cards cards.json) are set. The evidence run (5 repeats, files) is
// `node scripts/assistant-eval.mjs --stub ...`; this test keeps the harness from regressing.
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { registry, heldReasonFor } from '../cards/registry'
import { createNodeRuntime, type NodeRuntime } from '../core/nodeDeps'
import { generateTools } from '../core/nodeTools'
import { ScriptedModel } from '../core/modelClient'
import type { Card } from '../cards/card.types'
import { createCardTable, type GradeResult, type RunObservation } from './grade'
import { runEval } from './run'
import { QUESTIONS } from './questions'
import { stubScript } from './stubModel'
import { summarize, type Summary } from './report'

const DATA = process.env.AX06_DATA_DIR
const CARDS = process.env.AX10_CARDS
const enabled = !!DATA && !!CARDS && existsSync(join(DATA, 'assistant', 'catalogue.json')) && existsSync(CARDS)

describe.skipIf(!enabled)('AX-13 STUB run over published files (1 repeat)', () => {
  let rt: NodeRuntime
  let obs: RunObservation[]
  let grades: GradeResult[]
  let s: Summary
  beforeAll(async () => {
    const kinds = registry.map((x) => ({ kind: x.kind, held_reason: heldReasonFor(x) }))
    const gen = await generateTools({ catalogueJson: join(DATA!, 'assistant/catalogue.json'), kinds: kinds.map((k) => k.kind), appDir: resolve(__dirname, '../../..') })
    const cards = JSON.parse(readFileSync(CARDS!, 'utf8')) as Card[]
    rt = await createNodeRuntime({ dataDir: DATA!, cards, tools: gen.tools, system: gen.system, kinds, specs: registry })
    const out = await runEval(QUESTIONS, {
      repeats: 1,
      mode: 'STUB',
      modelFor: (q) => new ScriptedModel(stubScript(q)),
      deps: { loopDeps: (m) => rt.loopDeps(m), store: rt.store },
      table: createCardTable(cards),
    })
    obs = out.observations
    grades = out.grades
    s = summarize(QUESTIONS, obs, grades, { status: 'not_applicable' }, 'STUB')
  }, 300_000)
  afterAll(() => rt?.close())

  it('the four numeric bar items hold for the harness (grounded, refusals, right tool, tokens)', () => {
    expect(s.errored_runs).toBe(0)
    expect(s.bar.grounded.pass).toBe(true)
    expect(s.bar.refusal.pass).toBe(true)
    expect(s.bar.right_tool.pass).toBe(true)
    expect(s.bar.tokens.pass).toBe(true)
  })

  it('no STUB answer needs a repair turn (system.md wording suffices), teammate_race included', () => {
    expect(obs.filter((o) => o.repaired).map((o) => o.question_id)).toEqual([])
    expect(obs.filter((o) => o.question_id.startsWith('tr-')).every((o) => o.status === 'answered' && !o.repaired)).toBe(true)
  })

  it('the only failures are the two "wins" questions no tool can answer (finding, not a harness bug)', () => {
    expect([...new Set(s.failures.map((f) => f.question_id))].sort()).toEqual(['ch-wins-2023', 'oc-wins-VER-2023'])
    expect(s.no_tool_could_answer.questions).toEqual(['oc-wins-VER-2023', 'ch-wins-2023', 'h-ml-band-2024_1-VER'])
  })
})
