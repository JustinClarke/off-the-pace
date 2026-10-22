import { describe, expect, it, vi } from "vitest";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { handle, type Env, type Deps } from "../src/handler";
import { MemoryLedger } from "../src/ledger";
import { MAX_OUTPUT_TOKENS, MODEL, PAUSED_MESSAGE } from "../src/config";

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
    TURNSTILE_SECRET: SECRET, ADMIN_TOKEN: ADMIN, AI_PAUSED: "false", ...over,
  } as unknown as Env;
  const fetchMock = vi.fn(async () => Response.json({ success: turnstileOk }));
  const deps: Deps = { ledger, fetch: fetchMock as any, now: () => new Date("2026-10-23T10:00:00Z"), log: (m) => logs.push(m) };
  const chat = (body: unknown = { messages: [{ role: "user", content: "q" }] }, h: Record<string, string> = {}) =>
    handle(new Request("https://w/v1/chat", { method: "POST", body: typeof body === "string" ? body : JSON.stringify(body),
      headers: { Origin: ORIGIN, "X-Turnstile-Token": "tok", "CF-Connecting-IP": "1.2.3.4", ...h } }), env, deps);
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
    expect(input.tools).toBeUndefined();
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
    expect(u.answers).toBe(2);
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
