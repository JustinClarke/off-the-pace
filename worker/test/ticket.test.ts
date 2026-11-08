import { describe, expect, it } from "vitest";
import { signTicket, verifyTicket } from "../src/ticket";

describe("ticket", () => {
  const now = Date.parse("2026-10-23T10:00:00Z");
  const p = { v: "abc", q: "q1", exp: now / 1000 + 120 };
  it("round-trips", async () => expect(await verifyTicket("s", await signTicket("s", p), now)).toEqual(p));
  it("rejects a wrong secret, a tampered body and an expired ticket", async () => {
    const t = await signTicket("s", p);
    expect(await verifyTicket("other", t, now)).toBeNull();
    const [b, m] = t.split(".");
    const forged = btoa(JSON.stringify({ ...p, v: "evil" })).replace(/=+$/, "");
    expect(await verifyTicket("s", `${forged}.${m}`, now)).toBeNull();
    expect(await verifyTicket("s", t, now + 121_000)).toBeNull();
    expect(b.length).toBeGreaterThan(0);
  });
  it("rejects junk", async () => {
    for (const j of ["", "a", "a.b.c", "!!.!!"]) expect(await verifyTicket("s", j, now)).toBeNull();
  });
});
