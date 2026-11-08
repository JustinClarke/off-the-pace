import { describe, it, expect, vi } from 'vitest'
import { EndpointError, ScriptedModel, createOpenAIClient, createWorkerClient } from './modelClient'
import { parseToolCalls } from './types'

type Init = { method: string; headers: Record<string, string>; body: string }
const fakeFetch = (replies: { ok?: boolean; status?: number; body: unknown }[]) => {
  const calls: { url: string; init: Init }[] = []
  let i = 0
  const f = vi.fn(async (url: string, init: Init) => {
    calls.push({ url, init })
    const r = replies[Math.min(i++, replies.length - 1)]
    return { ok: r.ok ?? true, status: r.status ?? 200, json: async () => r.body }
  })
  return { f, calls }
}

describe('parseToolCalls', () => {
  it('reads OpenAI form (JSON-string arguments), flat form, bad JSON and junk', () => {
    const calls = parseToolCalls([
      { id: 'a', type: 'function', function: { name: 'navigate', arguments: '{"route":"/ml"}' } },
      { name: 'list_values', arguments: { domain: 'driver' } },
      { id: 'c', function: { name: 'x', arguments: '{oops' } },
      null,
    ])
    expect(calls[0]).toEqual({ id: 'a', name: 'navigate', arguments: { route: '/ml' } })
    expect(calls[1]).toMatchObject({ id: 'call_2', name: 'list_values', arguments: { domain: 'driver' } })
    expect(calls[2].arguments).toEqual({ __unparsable: true })
    expect(calls).toHaveLength(3)
    expect(parseToolCalls(undefined)).toEqual([])
  })
})

describe('worker client (Worker v2 contract, fetch injected)', () => {
  it('sends only {messages}, the catalogue version, and carries the ticket on rounds 2+', async () => {
    const { f, calls } = fakeFetch([
      { body: { message: { role: 'assistant', content: null, tool_calls: [{ id: 't1', function: { name: 'list_values', arguments: '{"domain":"driver"}' } }] }, usage: { prompt_tokens: 100, completion_tokens: 9 }, ticket: 'TICKET1' } },
      { body: { message: { role: 'assistant', content: 'done' }, usage: { prompt_tokens: 150, completion_tokens: 5 }, ticket: 'TICKET2' } },
      { body: { message: { role: 'assistant', content: 'next question' }, ticket: 'T3' } },
    ])
    const c = createWorkerClient({ endpoint: 'http://127.0.0.1:8787/v1/chat', catalogueVersion: 'abc', turnstileToken: 'tok', fetch: f })
    const r1 = await c.chat({ round: 1, messages: [{ role: 'user', content: 'hi' }] })
    expect(r1.tool_calls[0]).toMatchObject({ name: 'list_values', arguments: { domain: 'driver' } })
    expect(r1.usage).toEqual({ prompt_tokens: 100, completion_tokens: 9 })
    expect(calls[0].init.headers).toMatchObject({ 'X-Catalogue-Version': 'abc', 'X-Turnstile-Token': 'tok' })
    expect(calls[0].init.headers['X-Question-Ticket']).toBeUndefined()
    expect(Object.keys(JSON.parse(calls[0].init.body))).toEqual(['messages'])
    await c.chat({ round: 2, messages: [{ role: 'user', content: 'hi' }] })
    expect(calls[1].init.headers['X-Question-Ticket']).toBe('TICKET1')
    expect(calls[1].init.headers['X-Turnstile-Token']).toBeUndefined()
    // a new question starts a new ticket
    await c.chat({ round: 1, messages: [{ role: 'user', content: 'again' }] })
    expect(calls[2].init.headers['X-Question-Ticket']).toBeUndefined()
  })

  it('a non-2xx reply is an EndpointError carrying the status (409 app_updated, 429 round_limit ...)', async () => {
    const { f } = fakeFetch([{ ok: false, status: 409, body: { error: 'app_updated' } }])
    const c = createWorkerClient({ endpoint: 'http://x/v1/chat', catalogueVersion: 'old', fetch: f })
    await expect(c.chat({ round: 1, messages: [] })).rejects.toMatchObject({ status: 409 })
    await expect(c.chat({ round: 1, messages: [] })).rejects.toBeInstanceOf(EndpointError)
  })
})

describe('openai-compatible client (local Ollama; fetch injected)', () => {
  it('prepends the system prompt, sends tools, reads choices[0].message', async () => {
    const { f, calls } = fakeFetch([{ body: { choices: [{ message: { role: 'assistant', content: 'hello' } }], usage: { prompt_tokens: 10, completion_tokens: 2 } } }])
    const c = createOpenAIClient({ endpoint: 'http://127.0.0.1:11434/v1/chat/completions', model: 'gpt-oss:20b', system: 'SYS', tools: [{ type: 'function' }], fetch: f })
    const r = await c.chat({ round: 1, messages: [{ role: 'user', content: 'q' }] })
    expect(r.content).toBe('hello')
    const sent = JSON.parse(calls[0].init.body)
    expect(sent.messages[0]).toEqual({ role: 'system', content: 'SYS' })
    expect(sent.tools).toHaveLength(1)
    expect(sent.max_tokens).toBe(2500)
  })
})

describe('scripted model', () => {
  it('replays steps, records requests, lets a step read earlier tool results, repeats the fallback', async () => {
    const m = new ScriptedModel([{ tool_calls: [{ name: 'x', arguments: {} }] }, (_req, ctx) => ({ content: `saw ${ctx.results('x').length}` })], { content: 'tail' })
    const r1 = await m.chat({ round: 1, messages: [{ role: 'user', content: 'q' }] })
    expect(r1.tool_calls[0].id).toBe('stub_1_1')
    const msgs = [
      { role: 'user' as const, content: 'q' },
      { role: 'assistant' as const, content: '', tool_calls: [{ id: 'stub_1_1', type: 'function', function: { name: 'x', arguments: '{}' } }] },
      { role: 'tool' as const, content: '{"status":"ok"}', tool_call_id: 'stub_1_1' },
    ]
    expect((await m.chat({ round: 2, messages: msgs })).content).toBe('saw 1')
    expect((await m.chat({ round: 3, messages: msgs })).content).toBe('tail')
    expect(m.requests).toHaveLength(3)
  })
})
