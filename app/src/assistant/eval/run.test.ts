// AX-13 real-run path without a network: the Worker v2 client with an injected fetch that speaks the Worker
// contract. Checks what the owner's real run will record: Origin header, ticket carry, endpoint usage
// (prompt/completion/reasoning tokens, neurons from usage, not estimated), and an endpoint error recorded
// as an errored run (never graded as a pass).
import { describe, it, expect } from 'vitest'
import { createWorkerClient } from '../core/modelClient'
import { createDispatcher } from '../core/dispatcher'
import { demoStore, testDeps, system, toolsJson, demoCards } from '../core/testKit'
import { neuronsFor } from '../core/budget'
import { runOnce } from './run'
import { createCardTable, grade } from './grade'
import { QUESTIONS } from './questions'
import { summarize } from './report'

type Reply = { status?: number; body: unknown }
function fakeWorker(replies: Reply[]) {
  const calls: { headers: Record<string, string>; body: { messages: unknown[] } }[] = []
  let i = 0
  const f = async (_url: string, init: { headers: Record<string, string>; body: string }) => {
    calls.push({ headers: init.headers, body: JSON.parse(init.body) })
    const r = replies[Math.min(i++, replies.length - 1)]
    return { ok: (r.status ?? 200) < 400, status: r.status ?? 200, json: async () => r.body }
  }
  return { f, calls }
}

const q = QUESTIONS.find((x) => x.id === 'lv-checo')!
const store = demoStore()
const deps = { store, loopDeps: (model: Parameters<typeof runOnce>[2]) => ({ model, dispatcher: createDispatcher(testDeps()), store, system, toolsJson }) }

describe('AX-13 real-run path (Worker contract, injected fetch)', () => {
  it('records endpoint usage per round, reasoning tokens when reported, and grades the answer', async () => {
    const { f, calls } = fakeWorker([
      { body: { message: { role: 'assistant', content: null, tool_calls: [{ id: 't1', type: 'function', function: { name: 'list_values', arguments: '{"domain":"driver","query":"Checo"}' } }] }, usage: { prompt_tokens: 2100, completion_tokens: 160, completion_tokens_details: { reasoning_tokens: 141 } }, ticket: 'T1' } },
      { body: { message: { role: 'assistant', content: 'That is Sergio Perez; the data uses the code PER.' }, usage: { prompt_tokens: 2200, completion_tokens: 30 }, ticket: 'T2' } },
    ])
    const client = createWorkerClient({ endpoint: 'http://worker.test/v1/chat', catalogueVersion: 'cv1', origin: 'http://localhost:5173', fetch: f })
    const obs = await runOnce(q, 1, client, deps, 'endpoint:worker')
    expect(obs.status).toBe('answered')
    expect(calls[0].headers.Origin).toBe('http://localhost:5173')
    expect(calls[0].headers['X-Question-Ticket']).toBeUndefined()
    expect(calls[1].headers['X-Question-Ticket']).toBe('T1')
    expect(obs.usage_rounds.map((u) => [u.prompt_tokens, u.completion_tokens, u.reasoning_tokens])).toEqual([[2100, 160, 141], [2200, 30, undefined]])
    expect(obs.budget.estimated).toBe(false)
    expect(obs.budget.total).toBe(2100 + 160 + 2200 + 30)
    expect(obs.budget.neurons).toBe(neuronsFor({ prompt_tokens: 4300, completion_tokens: 190 }))
    expect(grade(q, obs, createCardTable(demoCards)).failures).toEqual([])
    const s = summarize([q], [obs], [grade(q, obs, createCardTable(demoCards))], { status: 'pending' }, 'endpoint:worker')
    expect(s.reasoning.rounds_reporting_reasoning).toBe(1)
    expect(s.reasoning.reasoning_tokens_total).toBe(141)
    expect(s.neurons.from_usage).toBe(true)
    expect(s.reasoning.completion_tokens_reported).toBe(190)
    expect(s.reasoning.rounds_hidden_output).toBe(1) // round 1: 160 tokens billed for an 82-character tool call
  })

  it('an endpoint error (409 app_updated) is recorded as an errored run, not graded as a pass', async () => {
    const { f } = fakeWorker([{ status: 409, body: { error: 'app_updated' } }])
    const client = createWorkerClient({ endpoint: 'http://worker.test/v1/chat', catalogueVersion: 'stale', fetch: f })
    const obs = await runOnce(q, 1, client, deps, 'endpoint:worker')
    expect(obs.status).toBe('error')
    expect(obs.error).toMatch(/409/)
    const g = grade(q, obs, createCardTable(demoCards))
    expect(g.all_pass).toBe(false)
    const s = summarize([q], [obs], [g], { status: 'pending' }, 'endpoint:worker')
    expect(s.errored_runs).toBe(1)
    expect(s.verdict).not.toBe('PASS')
  })
})
