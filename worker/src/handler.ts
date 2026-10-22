import {
  MAX_BODY_BYTES, MAX_MESSAGES, MAX_MESSAGE_CHARS, MAX_OUTPUT_TOKENS, MODEL, NEURONS_PER_M_INPUT,
  NEURONS_PER_M_OUTPUT, PAUSED_MESSAGE, REASONING, SYSTEM_PROMPT, TOOLS,
} from "./config";
import { dayKey, type Ledger } from "./ledger";

export interface Env {
  AI: { run(model: string, input: unknown): Promise<any> };
  LEDGER: DurableObjectNamespace;
  AI_PAUSED?: string;
  ALLOWED_ORIGINS?: string;
  DAILY_NEURON_CAP?: string;
  VISITOR_DAILY_LIMIT?: string;
  TURNSTILE_ENABLED?: string;
  TURNSTILE_SECRET?: string;
  ADMIN_TOKEN?: string;
}
export interface Deps {
  ledger: Ledger;
  fetch: typeof fetch;
  now: () => Date;
  log: (msg: string) => void;
}

const SITEVERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

export function redact(text: string, env: Env): string {
  let out = text;
  for (const s of [env.TURNSTILE_SECRET, env.ADMIN_TOKEN]) if (s) out = out.split(s).join("[redacted]");
  return out;
}

function cors(req: Request, env: Env): Record<string, string> {
  const origin = req.headers.get("Origin") ?? "";
  const allowed = (env.ALLOWED_ORIGINS ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  const h: Record<string, string> = { Vary: "Origin" };
  if (allowed.includes(origin)) {
    h["Access-Control-Allow-Origin"] = origin;
    h["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS";
    h["Access-Control-Allow-Headers"] = "Content-Type, X-Turnstile-Token, Authorization";
  }
  return h;
}

const json = (body: unknown, status: number, extra: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...extra } });

function safeEqual(a: string, b: string) {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

async function hashVisitor(ip: string, day: string) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${day}|${ip}`));
  return [...new Uint8Array(buf)].slice(0, 12).map((b) => b.toString(16).padStart(2, "0")).join("");
}

type Msg = { role: "user" | "assistant" | "tool"; content: string; tool_calls?: unknown; tool_call_id?: string };

/** Message list only. Every other browser-sent field is dropped. */
export function parseMessages(raw: unknown): Msg[] | null {
  const list = (raw as any)?.messages;
  if (!Array.isArray(list) || list.length === 0 || list.length > MAX_MESSAGES) return null;
  const out: Msg[] = [];
  for (const m of list) {
    if (!m || typeof m !== "object") return null;
    if (!["user", "assistant", "tool"].includes(m.role)) return null; // no client "system"
    if (typeof m.content !== "string" || m.content.length > MAX_MESSAGE_CHARS) return null;
    const msg: Msg = { role: m.role, content: m.content };
    if (m.role === "assistant" && Array.isArray(m.tool_calls)) msg.tool_calls = m.tool_calls;
    if (m.role === "tool" && typeof m.tool_call_id === "string") msg.tool_call_id = m.tool_call_id;
    out.push(msg);
  }
  return out[out.length - 1].role === "assistant" ? null : out;
}

export function neuronsFor(usage: any): number {
  const i = Number(usage?.prompt_tokens ?? 0), o = Number(usage?.completion_tokens ?? 0);
  return Math.ceil((i * NEURONS_PER_M_INPUT + o * NEURONS_PER_M_OUTPUT) / 1e6);
}

const isOverLimit = (e: unknown) => /4006|daily free allocation|neurons|exceeded.*(limit|allocation)/i.test(String((e as any)?.message ?? e));

async function admin(req: Request, env: Env, deps: Deps, path: string, day: string, c: Record<string, string>) {
  const tok = (req.headers.get("Authorization") ?? "").replace(/^Bearer /, "");
  if (!env.ADMIN_TOKEN || !safeEqual(tok, env.ADMIN_TOKEN)) return json({ error: "forbidden" }, 403, c);
  if (path === "/admin/usage" && req.method === "GET") return json(await deps.ledger.state(day), 200, c);
  if (path === "/admin/pause" && req.method === "POST") {
    const body = (await req.json().catch(() => ({}))) as any;
    await deps.ledger.setPaused(body?.paused === true);
    return json({ paused: body?.paused === true }, 200, c);
  }
  return json({ error: "not_found" }, 404, c);
}

export async function handle(req: Request, env: Env, deps: Deps): Promise<Response> {
  const c = cors(req, env);
  const url = new URL(req.url);
  const day = dayKey(deps.now());
  try {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: c });
    if (url.pathname.startsWith("/admin/")) return await admin(req, env, deps, url.pathname, day, c);
    if (url.pathname !== "/v1/chat" || req.method !== "POST") return json({ error: "not_found" }, 404, c);

    const origin = req.headers.get("Origin") ?? "";
    if (!c["Access-Control-Allow-Origin"]) return json({ error: "origin_not_allowed", origin }, 403, c);

    // 1. Pause switch (config value, or the stored flag set by /admin/pause). Checked before the
    //    single-use Turnstile token is spent.
    const st = await deps.ledger.state(day);
    const cap = Number(env.DAILY_NEURON_CAP ?? 90909);
    if (env.AI_PAUSED === "true" || st.paused || st.exhausted || st.neurons >= cap)
      return json({ error: "paused", message: PAUSED_MESSAGE }, 503, c);

    // 2. Body size.
    const declared = Number(req.headers.get("Content-Length") ?? 0);
    if (declared > MAX_BODY_BYTES) return json({ error: "too_large" }, 413, c);
    const text = await req.text();
    if (new TextEncoder().encode(text).length > MAX_BODY_BYTES) return json({ error: "too_large" }, 413, c);
    let parsed: unknown;
    try { parsed = JSON.parse(text); } catch { return json({ error: "bad_request" }, 400, c); }
    const messages = parseMessages(parsed);
    if (!messages) return json({ error: "bad_request" }, 400, c);

    // 3. Turnstile.
    if (env.TURNSTILE_ENABLED !== "false") {
      const token = req.headers.get("X-Turnstile-Token") ?? "";
      const ip = req.headers.get("CF-Connecting-IP") ?? "";
      let ok = false;
      if (token && env.TURNSTILE_SECRET) {
        const form = new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: token });
        if (ip) form.set("remoteip", ip);
        const r = await deps.fetch(SITEVERIFY, { method: "POST", body: form });
        ok = r.ok && ((await r.json()) as any).success === true;
      }
      if (!ok) return json({ error: "abuse_check_failed" }, 403, c);
    }

    // 4. Per-visitor daily limit.
    const visitor = await hashVisitor(req.headers.get("CF-Connecting-IP") ?? "unknown", day);
    const limit = Number(env.VISITOR_DAILY_LIMIT ?? 10);
    if (!(await deps.ledger.takeVisitorSlot(day, visitor, limit)))
      return json({ error: "visitor_limit", message: "daily question limit reached" }, 429, c);

    // 5. Model call: everything but the messages is fixed here.
    let result: any;
    try {
      result = await env.AI.run(MODEL, {
        messages: [{ role: "system", content: SYSTEM_PROMPT }, ...messages],
        ...(TOOLS.length ? { tools: TOOLS } : {}),
        max_tokens: MAX_OUTPUT_TOKENS,
        reasoning: REASONING,
      });
    } catch (e) {
      deps.log(redact(`ai_error: ${String((e as any)?.message ?? e)}`, env));
      if (isOverLimit(e)) {
        await deps.ledger.markExhausted(day);
        return json({ error: "paused", message: PAUSED_MESSAGE }, 503, c);
      }
      return json({ error: "upstream_error" }, 502, c);
    }

    const message = result?.choices?.[0]?.message ?? (typeof result?.response === "string" ? { role: "assistant", content: result.response } : null);
    const neurons = neuronsFor(result?.usage);
    await deps.ledger.record(day, neurons);
    if (!message) return json({ error: "upstream_error" }, 502, c);
    // Tool calls are passed through untouched; the Worker never runs a query.
    return json({ message, usage: result?.usage ?? null }, 200, c);
  } catch (e) {
    deps.log(redact(`error: ${String((e as any)?.message ?? e)}`, env));
    return json({ error: "internal_error" }, 500, c);
  }
}
