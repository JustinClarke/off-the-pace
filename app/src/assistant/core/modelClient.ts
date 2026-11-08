// AX-10 model clients: a scripted stub for tests and the CLI's stub mode (deterministic, no network),
// and two HTTP clients for the CLI's real mode (the Worker v2 contract, and an OpenAI-compatible
// endpoint such as a local Ollama). Tests inject `fetch`; nothing here calls a network on its own.
import { parseToolCalls, type ChatMessage, type ModelClient, type ModelReply, type ModelRequest } from './types'

export interface ScriptStep {
  content?: string | null
  tool_calls?: { name: string; arguments: unknown }[]
  usage?: { prompt_tokens: number; completion_tokens: number }
}
export type ScriptEntry = ScriptStep | ((req: ModelRequest, ctx: ScriptContext) => ScriptStep)

/** What a scripted step can read: the tool results so far (parsed), by tool name in call order. */
export interface ScriptContext {
  results(name?: string): Record<string, unknown>[]
  lastUser(): string
}

function contextOf(messages: ChatMessage[]): ScriptContext {
  const names = new Map<string, string>()
  const out: { name: string; body: Record<string, unknown> }[] = []
  for (const m of messages) {
    if (m.role === 'assistant' && Array.isArray(m.tool_calls)) {
      for (const c of m.tool_calls as { id?: string; function?: { name?: string } }[]) if (c.id && c.function?.name) names.set(c.id, c.function.name)
    }
    if (m.role === 'tool') {
      let body: Record<string, unknown> = {}
      try {
        body = JSON.parse(m.content) as Record<string, unknown>
      } catch {
        /* keep empty */
      }
      out.push({ name: names.get(m.tool_call_id ?? '') ?? '', body })
    }
  }
  return {
    results: (name) => out.filter((r) => !name || r.name === name).map((r) => r.body),
    lastUser: () => [...messages].reverse().find((m) => m.role === 'user')?.content ?? '',
  }
}

/** Replays `script` one entry per round; past the end it repeats `fallback` (default: a plain answer). */
export class ScriptedModel implements ModelClient {
  readonly requests: ModelRequest[] = []
  private i = 0
  constructor(
    private readonly script: ScriptEntry[],
    private readonly fallback: ScriptEntry = { content: 'No further scripted step.' },
  ) {}

  async chat(req: ModelRequest): Promise<ModelReply> {
    this.requests.push({ messages: req.messages.map((m) => ({ ...m })), round: req.round })
    const entry = this.i < this.script.length ? this.script[this.i] : this.fallback
    this.i++
    const step = typeof entry === 'function' ? entry(req, contextOf(req.messages)) : entry
    return {
      content: step.content ?? null,
      tool_calls: (step.tool_calls ?? []).map((c, k) => ({ id: `stub_${req.round}_${k + 1}`, name: c.name, arguments: c.arguments })),
      usage: step.usage ?? null,
    }
  }
}

/** A stub that asks for the same tool in every round (the loop-limit fixture). */
export function alwaysCalls(name: string, args: unknown): ScriptedModel {
  return new ScriptedModel([], { tool_calls: [{ name, arguments: args }] })
}

type FetchLike = (url: string, init: { method: string; headers: Record<string, string>; body: string }) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>

function replyFrom(message: unknown, usage: unknown): ModelReply {
  const m = (message ?? {}) as { content?: unknown; tool_calls?: unknown }
  const u = usage as { prompt_tokens?: number; completion_tokens?: number } | null | undefined
  return {
    content: typeof m.content === 'string' ? m.content : null,
    tool_calls: parseToolCalls(m.tool_calls),
    usage: u ? { prompt_tokens: u.prompt_tokens, completion_tokens: u.completion_tokens } : null,
    ...(u ? { raw_usage: u } : {}),
  }
}

export class EndpointError extends Error {
  /** AX-14: the Worker's error code from the JSON body (app_updated, paused, visitor_limit, abuse_check_failed ...), when it sent one. */
  constructor(readonly status: number, message: string, readonly code: string | null = null) {
    super(message)
  }
}

export interface WorkerClientOptions {
  /** e.g. http://127.0.0.1:8787/v1/chat (wrangler dev, or the AX-12 preview Worker). */
  endpoint: string
  catalogueVersion: string
  /** A token, or a function giving a fresh one for each new question (a Turnstile token is single-use). */
  turnstileToken?: string | (() => string | undefined | Promise<string | undefined>)
  /** AX-13: Origin header for a Node caller (the Worker answers 403 to an origin not in ALLOWED_ORIGINS; Node sends none). */
  origin?: string
  fetch?: FetchLike
}

/**
 * Worker v2 contract (worker/src/handler.ts): POST {messages}; headers X-Catalogue-Version, and on
 * rounds 2..5 the X-Question-Ticket from the previous response. Round 1 starts a new ticket.
 */
export function createWorkerClient(o: WorkerClientOptions): ModelClient {
  const doFetch: FetchLike = o.fetch ?? ((url, init) => fetch(url, init))
  let ticket: string | null = null
  return {
    async chat(req) {
      if (req.round === 1) ticket = null
      const headers: Record<string, string> = { 'Content-Type': 'application/json', 'X-Catalogue-Version': o.catalogueVersion }
      if (o.origin) headers.Origin = o.origin
      if (ticket) headers['X-Question-Ticket'] = ticket
      else {
        const t = typeof o.turnstileToken === 'function' ? await o.turnstileToken() : o.turnstileToken
        if (t) headers['X-Turnstile-Token'] = t
      }
      const res = await doFetch(o.endpoint, { method: 'POST', headers, body: JSON.stringify({ messages: req.messages }) })
      const body = (await res.json().catch(() => ({}))) as { message?: unknown; usage?: unknown; ticket?: string; error?: string }
      if (!res.ok) throw new EndpointError(res.status, `endpoint answered ${res.status} ${body.error ?? ''}`.trim(), typeof body.error === 'string' ? body.error : null)
      if (typeof body.ticket === 'string') ticket = body.ticket
      return replyFrom(body.message, body.usage)
    },
  }
}

export interface OpenAIClientOptions {
  /** e.g. http://127.0.0.1:11434/v1/chat/completions (Ollama). */
  endpoint: string
  model: string
  system: string
  tools: readonly unknown[]
  maxTokens?: number
  fetch?: FetchLike
}

/** An OpenAI-compatible endpoint: the CLI supplies the system prompt and tools the Worker would. */
export function createOpenAIClient(o: OpenAIClientOptions): ModelClient {
  const doFetch: FetchLike = o.fetch ?? ((url, init) => fetch(url, init))
  return {
    async chat(req) {
      const body = {
        model: o.model,
        messages: [{ role: 'system', content: o.system }, ...req.messages],
        tools: o.tools,
        max_tokens: o.maxTokens ?? 2500,
        stream: false,
      }
      const res = await doFetch(o.endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      const j = (await res.json().catch(() => ({}))) as { choices?: { message?: unknown }[]; usage?: unknown }
      if (!res.ok) throw new EndpointError(res.status, `endpoint answered ${res.status}`)
      return replyFrom(j.choices?.[0]?.message, j.usage)
    },
  }
}
