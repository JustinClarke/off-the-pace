// AX-10 shared types for the assistant core: messages, tool calls, the model client seam.
// The wire shape follows the Worker v2 contract (worker/src/handler.ts): the client sends
// user | assistant | tool messages only (the Worker owns the system prompt, the tools and the output cap).

export interface ToolCall {
  id: string
  name: string
  /** Parsed arguments (the wire form is a JSON string; parseToolCalls handles both). */
  arguments: unknown
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'tool'
  content: string
  tool_calls?: unknown
  tool_call_id?: string
}

export interface ModelUsage {
  prompt_tokens?: number
  completion_tokens?: number
}

export interface ModelReply {
  content: string | null
  tool_calls: ToolCall[]
  usage?: ModelUsage | null
  /** AX-13: the endpoint's usage object as returned (reasoning-token fields, if any), for the eval record. */
  raw_usage?: unknown
}

export interface ModelRequest {
  messages: ChatMessage[]
  /** 1-based model round of this question. */
  round: number
}

/** The seam the loop talks to: a scripted stub in tests, an HTTP endpoint in the CLI, the Worker in the app. */
export interface ModelClient {
  chat(req: ModelRequest): Promise<ModelReply>
}

/** What a tool returns to the model. Always an object with a status; never thrown. */
export interface ToolResult {
  status: 'ok' | 'no_data' | 'error'
  reason?: string
  allowed?: unknown
  [k: string]: unknown
}

/** Parse tool calls in OpenAI form ({id, function:{name, arguments:string|object}}) or flat form. */
export function parseToolCalls(raw: unknown): ToolCall[] {
  if (!Array.isArray(raw)) return []
  const out: ToolCall[] = []
  raw.forEach((c, i) => {
    if (!c || typeof c !== 'object') return
    const o = c as Record<string, unknown>
    const fn = (o.function && typeof o.function === 'object' ? o.function : o) as Record<string, unknown>
    const name = typeof fn.name === 'string' ? fn.name : ''
    let args: unknown = fn.arguments ?? fn.parameters ?? {}
    if (typeof args === 'string') {
      try {
        args = args.trim() === '' ? {} : JSON.parse(args)
      } catch {
        args = { __unparsable: true }
      }
    }
    out.push({ id: typeof o.id === 'string' && o.id ? o.id : `call_${i + 1}`, name, arguments: args })
  })
  return out
}
