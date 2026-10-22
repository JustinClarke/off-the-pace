// Per-day counters. Interface so tests can use memory; production uses one Durable Object
// (single-threaded, so counters are atomic, which KV is not).
export interface LedgerState {
  day: string;
  neurons: number;
  answers: number;
  exhausted: boolean;
  paused: boolean;
}
export interface Ledger {
  state(day: string): Promise<LedgerState>;
  /** Atomically take one visitor slot. Returns false when the visitor is at the limit. */
  takeVisitorSlot(day: string, visitor: string, limit: number): Promise<boolean>;
  record(day: string, neurons: number): Promise<void>;
  markExhausted(day: string): Promise<void>;
  setPaused(paused: boolean): Promise<void>;
}

export const dayKey = (d = new Date()) => d.toISOString().slice(0, 10); // UTC, resets 00:00 UTC

export class MemoryLedger implements Ledger {
  days = new Map<string, { neurons: number; answers: number; exhausted: boolean; visitors: Map<string, number> }>();
  paused = false;
  private d(day: string) {
    let v = this.days.get(day);
    if (!v) this.days.set(day, (v = { neurons: 0, answers: 0, exhausted: false, visitors: new Map() }));
    return v;
  }
  async state(day: string) {
    const v = this.d(day);
    return { day, neurons: v.neurons, answers: v.answers, exhausted: v.exhausted, paused: this.paused };
  }
  async takeVisitorSlot(day: string, visitor: string, limit: number) {
    const v = this.d(day);
    const n = v.visitors.get(visitor) ?? 0;
    if (n >= limit) return false;
    v.visitors.set(visitor, n + 1);
    return true;
  }
  async record(day: string, neurons: number) {
    const v = this.d(day);
    v.neurons += neurons;
    v.answers += 1;
  }
  async markExhausted(day: string) { this.d(day).exhausted = true; }
  async setPaused(p: boolean) { this.paused = p; }
}

// Durable Object: SQLite-backed storage, one instance named "global".
export class Ledger_DO {
  constructor(private ctx: DurableObjectState) {}
  async fetch(req: Request): Promise<Response> {
    const { op, day, visitor, limit, neurons, paused } = (await req.json()) as Record<string, any>;
    const s = this.ctx.storage;
    const get = async <T>(k: string, def: T) => ((await s.get<T>(k)) ?? def);
    let out: unknown = { ok: true };
    if (op === "state") {
      out = {
        day,
        neurons: await get(`n:${day}`, 0),
        answers: await get(`a:${day}`, 0),
        exhausted: await get(`x:${day}`, false),
        paused: await get("paused", false),
      };
    } else if (op === "slot") {
      const k = `v:${day}:${visitor}`;
      const n = await get(k, 0);
      if (n >= limit) out = { ok: false };
      else await s.put(k, n + 1);
    } else if (op === "record") {
      await s.put(`n:${day}`, (await get(`n:${day}`, 0)) + neurons);
      await s.put(`a:${day}`, (await get(`a:${day}`, 0)) + 1);
    } else if (op === "exhausted") await s.put(`x:${day}`, true);
    else if (op === "paused") await s.put("paused", !!paused);
    return Response.json(out);
  }
}

export class StubLedger implements Ledger {
  constructor(private stub: DurableObjectStub) {}
  private async call<T>(body: object): Promise<T> {
    const r = await this.stub.fetch("https://ledger/", { method: "POST", body: JSON.stringify(body) });
    return (await r.json()) as T;
  }
  state(day: string) { return this.call<LedgerState>({ op: "state", day }); }
  async takeVisitorSlot(day: string, visitor: string, limit: number) {
    return (await this.call<{ ok: boolean }>({ op: "slot", day, visitor, limit })).ok;
  }
  async record(day: string, neurons: number) { await this.call({ op: "record", day, neurons }); }
  async markExhausted(day: string) { await this.call({ op: "exhausted", day }); }
  async setPaused(paused: boolean) { await this.call({ op: "paused", paused }); }
}
