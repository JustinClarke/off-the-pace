import { describe, expect, it, vi } from "vitest";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { handle, type Env, type Deps } from "../src/handler";
import { MemoryLedger } from "../src/ledger";
import { CATALOGUE_VERSION, MAX_OUTPUT_TOKENS, MODEL, PAUSED_MESSAGE, TOOLS } from "../src/config";

const SECRET = "ts-secret-VALUE-123456";
const ADMIN = "admin-token-VALUE-987654";
const ORIGIN = "https://off-the-pace.web.app";

function setup(over: Partial<Env> = {}, ai?: (m: string, i: any) => Promise<any>, turnstileOk = true) {
  const ledger = new MemoryLedger();
  const calls: any[] = [];
  const logs: string[] = [];
  const env = {
    AI: { run: vi.fn(ai ?? (async (_m: string, i: any) => { calls.push(i); return { choices: [{ message: { role: "assistant", content: "hi" } }], usage: { prompt_tokens: 1000, completion_tokens: 200 } }; })) },
    ALLOWED_ORIGINS: ORIGIN, DAILY_NEURON_CAP: "90909", VISITOR_DAILY_LIMIT: "2", TURNSTILE_ENABLED: "true",
    TURNSTILE_SECRET: SECRET, ADMIN_TOKEN: ADMIN, TICKET_SECRET: "ticket-secret-VALUE-abcdef", AI_PAUSED: "false", ...over,
  } as unknown as Env;
  const fetchMock = vi.fn(async () => Response.json({ success: turnstileOk }));
  const deps: Deps = { ledger, fetch: fetchMock as any, now: () => new Date("2026-10-23T10:00:00Z"), log: (m) => logs.push(m) };
  const chat = (body: unknown = { messages: [{ role: "user", content: "q" }] }, h: Record<string, string> = {}) =>
    handle(new Request("https://w/v1/chat", { method: "POST", body: typeof body === "string" ? body : JSON.stringify(body),
      headers: { Origin: ORIGIN, "X-Turnstile-Token": "tok", "X-Catalogue-Version": CATALOGUE_VERSION, "CF-Connecting-IP": "1.2.3.4", ...h } }), env, deps);
  return { env, deps, ledger, calls, logs, chat, fetchMock };
}

describe("fixed server-side settings", () => {
  it("ignores browser-sent tools, max_tokens, reasoning, system and model", async () => {
    const t = setup();
    const r = await t.chat({ messages: [{ role: "user", content: "q" }], tools: [{ x: 1 }], max_tokens: 99999, reasoning: { effort: "high" }, model: "other", system: "evil" });
    expect(r.status).toBe(200);
    const [model, input] = (t.env.AI.run as any).mock.calls[0];
    expect(model).toBe(MODEL);
    expect(input.max_tokens).toBe(MAX_OUTPUT_TOKENS);
    expect(input.reasoning).toEqual({ effort: "low" });
    expect(input.tools).toEqual(TOOLS); // generated tools (AX-08), never the browser's
    expect(JSON.stringify(input.tools)).not.toContain('"x":1');
    expect(input.messages[0].role).toBe("system");
    expect(JSON.stringify(input)).not.toContain("evil");
  });
  it("rejects client system messages, oversize bodies, bad JSON", async () => {
    const t = setup();
    expect((await t.chat({ messages: [{ role: "system", content: "x" }] })).status).toBe(400);
    expect((await t.chat("{nope")).status).toBe(400);
    expect((await t.chat({ messages: [{ role: "user", content: "a".repeat(40000) }] })).status).toBe(413);
    expect(t.env.AI.run).not.toHaveBeenCalled();
  });
  it("passes tool calls through without running anything", async () => {
    const tc = [{ id: "1", type: "function", function: { name: "q", arguments: "{}" } }];
    const t = setup({}, async () => ({ choices: [{ message: { role: "assistant", content: "", tool_calls: tc } }], usage: { prompt_tokens: 1, completion_tokens: 1 } }));
    const body: any = await (await t.chat()).json();
    expect(body.message.tool_calls).toEqual(tc);
  });
});

describe("abuse check", () => {
  it("refuses a failed Turnstile check and a missing token", async () => {
    const bad = setup({}, undefined, false);
    expect((await bad.chat()).status).toBe(403);
    expect(bad.env.AI.run).not.toHaveBeenCalled();
    const none = setup();
    expect((await none.chat(undefined, { "X-Turnstile-Token": "" })).status).toBe(403);
    expect(none.fetchMock).not.toHaveBeenCalled();
  });
  it("refuses a disallowed origin", async () => {
    const t = setup();
    expect((await t.chat(undefined, { Origin: "https://evil.example" })).status).toBe(403);
  });
});

describe("limits and pause", () => {
  it("per-visitor limit triggers, other visitors unaffected", async () => {
    const t = setup();
    expect((await t.chat()).status).toBe(200);
    expect((await t.chat()).status).toBe(200);
    expect((await t.chat()).status).toBe(429);
    expect((await t.chat(undefined, { "CF-Connecting-IP": "9.9.9.9" })).status).toBe(200);
  });
  it("daily cap: simulated exhaustion shows the paused message", async () => {
    const t = setup({ DAILY_NEURON_CAP: "100", VISITOR_DAILY_LIMIT: "50" });
    expect((await t.chat()).status).toBe(200); // 1000 in + 200 out ~ 23.7 neurons? below 100
    await t.ledger.record("2026-10-23", 100);
    const r = await t.chat();
    expect(r.status).toBe(503);
    expect(((await r.json()) as any).message).toBe(PAUSED_MESSAGE);
  });
  it("Workers AI over-limit error pauses for the rest of the day", async () => {
    const t = setup({ VISITOR_DAILY_LIMIT: "50" }, async () => { throw new Error("4006: you have used up your daily free allocation of 10,000 neurons"); });
    const r = await t.chat();
    expect(r.status).toBe(503);
    expect(((await r.json()) as any).message).toBe(PAUSED_MESSAGE);
    const again = await t.chat();
    expect(again.status).toBe(503);
    expect(t.env.AI.run).toHaveBeenCalledTimes(1);
  });
  it("exhaustion resets at 00:00 UTC", async () => {
    const t = setup({ DAILY_NEURON_CAP: "100" });
    await t.ledger.record("2026-10-23", 100);
    expect((await t.chat()).status).toBe(503);
    t.deps.now = () => new Date("2026-10-24T00:00:01Z");
    expect((await t.chat()).status).toBe(200);
  });
  it("pause config value, and the stored switch, pause without a deploy; no Turnstile token spent", async () => {
    const a = setup({ AI_PAUSED: "true" });
    expect((await a.chat()).status).toBe(503);
    expect(a.fetchMock).not.toHaveBeenCalled();
    const b = setup();
    const set = await handle(new Request("https://w/admin/pause", { method: "POST", body: '{"paused":true}', headers: { Authorization: `Bearer ${ADMIN}` } }), b.env, b.deps);
    expect(set.status).toBe(200);
    expect((await b.chat()).status).toBe(503);
  });
});

describe("usage counter", () => {
  it("increases per answer and is readable by the owner only", async () => {
    const t = setup({ VISITOR_DAILY_LIMIT: "50" });
    const read = (tok: string) => handle(new Request("https://w/admin/usage", { headers: { Authorization: `Bearer ${tok}` } }), t.env, t.deps);
    await t.chat();
    await t.chat();
    const u: any = await (await read(ADMIN)).json();
    expect(u.rounds).toBe(2);
    expect(u.questions).toBe(2);
    expect(u.neurons).toBe(2 * Math.ceil((1000 * 18182 + 200 * 27273) / 1e6));
    expect((await read("wrong")).status).toBe(403);
  });
});

describe("secrets never leak", () => {
  it("forced error: absent from response and logs", async () => {
    const t = setup({ VISITOR_DAILY_LIMIT: "50" }, async () => { throw new Error(`boom with ${SECRET} and ${ADMIN}`); });
    const r = await t.chat();
    const text = await r.text();
    expect(r.status).toBe(502);
    for (const s of [SECRET, ADMIN]) { expect(text).not.toContain(s); expect(t.logs.join("\n")).not.toContain(s); }
    expect(t.logs.length).toBeGreaterThan(0);
  });
  it("internal error path is also clean", async () => {
    const t = setup();
    t.deps.ledger.state = async () => { throw new Error(`db ${SECRET}`); };
    const r = await t.chat();
    expect(r.status).toBe(500);
    expect(await r.text()).not.toContain(SECRET);
    expect(t.logs.join()).not.toContain(SECRET);
  });
});

describe("bundle key scan", () => {
  const scan = (dir: string, env: Record<string, string> = {}) => {
    try {
      execFileSync("node", ["scripts/scan-bundle.mjs", dir], { env: { ...process.env, ...env }, stdio: "pipe" });
      return 0;
    } catch (e: any) { return e.status as number; }
  };
  const mk = (extra?: [string, string]) => {
    const d = mkdtempSync(join(tmpdir(), "bundle-"));
    mkdirSync(join(d, "assets"));
    writeFileSync(join(d, "assets/app.js"), "console.log('clean')");
    writeFileSync(join(d, "assets/app.js.map"), '{"sources":[]}');
    if (extra) writeFileSync(join(d, "assets", extra[0]), extra[1]);
    return d;
  };
  it("passes a clean bundle", () => expect(scan(mk())).toBe(0));
  it("fails on a planted fake key in js and in a source map", () => {
    expect(scan(mk(["leak.js", "const k='sk-" + "a".repeat(32) + "'"]))).toBe(1);
    expect(scan(mk(["leak.js.map", '{"sourcesContent":["cfut_' + "b".repeat(40) + '"]}']))).toBe(1);
  });
  it("fails on an exact secret value", () => {
    expect(scan(mk(["x.js", `var a="${SECRET}"`]), { OTP_SCAN_SECRETS: SECRET })).toBe(1);
  });
});

// ---- AX-12: question tickets, per-question limit, version skew, cap, tool-message size ----
describe("worker v2", () => {
  const MSGS = { messages: [{ role: "user", content: "q" }] };
  const round = async (t: ReturnType<typeof setup>, ticket?: string, h: Record<string, string> = {}) => {
    const r = await t.chat(MSGS, { ...(ticket ? { "X-Question-Ticket": ticket } : {}), ...h });
    return { status: r.status, body: (await r.json()) as any };
  };

  it("a 5-round question spends 1 Turnstile call and 1 visitor slot; round 6 is refused", async () => {
    const t = setup({ VISITOR_DAILY_LIMIT: "1" });
    let r = await round(t);
    expect(r.status).toBe(200);
    expect(typeof r.body.ticket).toBe("string");
    for (let i = 2; i <= 5; i++) {
      r = await round(t, r.body.ticket);
      expect(r.status).toBe(200);
    }
    const sixth = await round(t, r.body.ticket);
    expect(sixth.status).toBe(429);
    expect(sixth.body.error).toBe("round_limit");
    expect(t.fetchMock).toHaveBeenCalledTimes(1);
    const st = await t.ledger.state("2026-10-23");
    expect(st.questions).toBe(1);
    expect(st.rounds).toBe(5);
    // the visitor's single slot is used: a new question is refused
    expect((await round(t)).body.error).toBe("visitor_limit");
  });

  it("default limit is 3 questions a day; the fourth is refused", async () => {
    const t = setup({ VISITOR_DAILY_LIMIT: undefined as unknown as string });
    for (let i = 0; i < 3; i++) expect((await round(t)).status).toBe(200);
    const r = await round(t);
    expect(r.status).toBe(429);
    expect(r.body.error).toBe("visitor_limit");
  });

  it("forged, other-visitor, expired and malformed tickets are refused; no model call", async () => {
    const t = setup({ VISITOR_DAILY_LIMIT: "5" });
    const ok = await round(t);
    const ticket = ok.body.ticket as string;
    const calls = (t.env.AI.run as any).mock.calls.length;
    const [body, mac] = ticket.split(".");
    expect((await round(t, `${body}.${mac.slice(0, -2)}AA`)).status).toBe(403);
    expect((await round(t, "not-a-ticket")).status).toBe(403);
    expect((await round(t, ticket, { "CF-Connecting-IP": "8.8.8.8" })).status).toBe(403);
    const later = new Date("2026-10-23T10:05:00Z");
    t.deps.now = () => later;
    expect((await round(t, ticket)).status).toBe(403);
    expect((t.env.AI.run as any).mock.calls.length).toBe(calls);
  });

  it("a replayed ticket cannot exceed the 5 rounds of its question", async () => {
    const t = setup({ VISITOR_DAILY_LIMIT: "5" });
    const first = await round(t);
    let n = 1;
    for (; n < 8; n++) if ((await round(t, first.body.ticket)).status !== 200) break;
    expect(n).toBe(5);
  });

  it("a missing or different X-Catalogue-Version is 409 and spends no Turnstile token or slot", async () => {
    const t = setup();
    for (const h of [{ "X-Catalogue-Version": "other" }, { "X-Catalogue-Version": "" }]) {
      const r = await round(t, undefined, h);
      expect(r.status).toBe(409);
      expect(r.body.error).toBe("app_updated");
    }
    const bare = await handle(new Request("https://w/v1/chat", { method: "POST", body: JSON.stringify(MSGS), headers: { Origin: ORIGIN, "X-Turnstile-Token": "tok" } }), t.env, t.deps);
    expect(bare.status).toBe(409);
    expect(t.fetchMock).not.toHaveBeenCalled();
    expect((await t.ledger.state("2026-10-23")).questions).toBe(0);
  });

  it("default cap is 10,000 neurons, and a question in flight at the cap gets paused", async () => {
    const t = setup({ DAILY_NEURON_CAP: undefined as unknown as string, VISITOR_DAILY_LIMIT: "5" });
    const r1 = await round(t);
    expect(r1.status).toBe(200);
    await t.ledger.record("2026-10-23", 9990);
    const r2 = await round(t, r1.body.ticket);
    expect(r2.status).toBe(503);
    expect(r2.body.message).toBe(PAUSED_MESSAGE);
  });

  it("a tool message over 5,000 characters is a 400; a 5,000 one passes; other roles keep 8,000", async () => {
    const t = setup({ VISITOR_DAILY_LIMIT: "9" });
    const mk = (n: number, role = "tool") => ({ messages: [{ role: "user", content: "q" }, { role: "assistant", content: "", tool_calls: [{ id: "1" }] }, { role, content: "x".repeat(n), tool_call_id: "1" }] });
    expect((await t.chat(mk(5001))).status).toBe(400);
    expect((await t.chat(mk(5000))).status).toBe(200);
    expect((await t.chat({ messages: [{ role: "user", content: "x".repeat(7000) }] })).status).toBe(200);
  });

  it("the preview config: output cap 2,500, cap and limit defaults", () => {
    expect(MAX_OUTPUT_TOKENS).toBe(2500);
  });
});
