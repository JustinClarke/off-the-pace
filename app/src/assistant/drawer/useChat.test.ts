import { describe, it, expect } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useChat, classifyError, ERROR_TEXT, TurnstileFailure } from './useChat'
import { EndpointError } from '../core/modelClient'
import { answer, cannedFetch, fakeRuntime } from './testKit'

function setup(replies: Parameters<typeof cannedFetch>[0], extra: Partial<Parameters<typeof useChat>[0]> = {}) {
  const f = cannedFetch(replies)
  const hook = renderHook(() =>
    useChat({ endpoint: 'http://worker.test/v1/chat', loadRuntime: async () => fakeRuntime('cat-9'), fetchImpl: f.fetch, ...extra }),
  )
  return { ...hook, f }
}

async function ask(h: ReturnType<typeof setup>, q = 'who was faster?') {
  await act(async () => {
    await h.result.current.send(q)
  })
  await waitFor(() => expect(h.result.current.busy).toBe(false))
  return h.result.current.turns.at(-1)!
}

describe('useChat', () => {
  it('200: a checked answer, with the catalogue version header and no ticket on round 1', async () => {
    const h = setup([answer('The race had no caution laps.')])
    const t = await ask(h)
    expect(t.status).toBe('done')
    expect(t.result?.answer).toBe('The race had no caution laps.')
    expect(h.f.calls[0].headers['X-Catalogue-Version']).toBe('cat-9')
    expect(h.f.calls[0].headers['X-Question-Ticket']).toBeUndefined()
    expect(t.steps.length).toBeGreaterThan(1)
  })

  it('a tool round carries the ticket from the first response into the next request', async () => {
    const toolReply = { body: { message: { role: 'assistant', content: null, tool_calls: [{ id: 'c1', type: 'function', function: { name: 'list_values', arguments: JSON.stringify({ domain: 'driver', query: 'Checo' }) } }] }, ticket: 'TK1' } }
    const h = setup([toolReply, answer('That is PER.', 'TK2')])
    const t = await ask(h)
    expect(t.status).toBe('done')
    expect(h.f.calls).toHaveLength(2)
    expect(h.f.calls[1].headers['X-Question-Ticket']).toBe('TK1')
    expect(t.steps.some((s) => s.startsWith('Looking up names'))).toBe(true)
  })

  it('sends the Turnstile token on round 1 only', async () => {
    const toolReply = { body: { message: { role: 'assistant', content: null, tool_calls: [{ id: 'c1', type: 'function', function: { name: 'list_values', arguments: JSON.stringify({ domain: 'driver', query: 'x' }) } }] }, ticket: 'TK1' } }
    const h = setup([toolReply, answer('ok')], { getTurnstileToken: async () => 'tok-1' })
    await ask(h)
    expect(h.f.calls[0].headers['X-Turnstile-Token']).toBe('tok-1')
    expect(h.f.calls[1].headers['X-Turnstile-Token']).toBeUndefined()
  })

  it.each([
    [409, { error: 'app_updated' }, 'updated'],
    [429, { error: 'visitor_limit', message: 'daily question limit reached' }, 'limit'],
    [429, { error: 'round_limit' }, 'rounds'],
    [503, { error: 'paused', message: 'x' }, 'paused'],
    [403, { error: 'abuse_check_failed' }, 'abuse'],
    [502, { error: 'upstream_error' }, 'upstream'],
  ])('HTTP %i %j -> %s', async (status, body, kind) => {
    const h = setup([{ status, body }])
    const t = await ask(h)
    expect(t.status).toBe('error')
    expect(t.error?.kind).toBe(kind)
    expect(t.error?.text).toBe(ERROR_TEXT[kind as keyof typeof ERROR_TEXT])
  })

  it('network error -> network message; a later question still works', async () => {
    const h = setup([() => { throw new TypeError('Failed to fetch') }, answer('fine')])
    const t1 = await ask(h)
    expect(t1.error?.kind).toBe('network')
    const t2 = await ask(h, 'again')
    expect(t2.status).toBe('done')
  })

  it('a runtime that cannot load -> data message; no Worker call is made', async () => {
    const f = cannedFetch([answer('x')])
    const h = renderHook(() => useChat({ endpoint: 'http://worker.test/v1/chat', loadRuntime: async () => { throw new Error('boom') }, fetchImpl: f.fetch }))
    await act(async () => { await h.result.current.send('q') })
    expect(h.result.current.turns[0].error?.kind).toBe('data')
    expect(f.calls).toHaveLength(0)
  })

  it('no endpoint configured -> unconfigured, nothing loaded or fetched', async () => {
    let loaded = false
    const f = cannedFetch([answer('x')])
    const h = renderHook(() => useChat({ endpoint: '', loadRuntime: async () => { loaded = true; return fakeRuntime() }, fetchImpl: f.fetch }))
    await act(async () => { await h.result.current.send('q') })
    expect(h.result.current.turns[0].error?.kind).toBe('unconfigured')
    expect(loaded).toBe(false)
    expect(f.calls).toHaveLength(0)
  })

  it('classifyError maps Turnstile failure to abuse', () => {
    expect(classifyError(new TurnstileFailure('x'))).toBe('abuse')
    expect(classifyError(new EndpointError(500, 'x'))).toBe('upstream')
  })
})
