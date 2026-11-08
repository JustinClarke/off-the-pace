// Question ticket: proves that round 1 of a question passed Turnstile and took a visitor slot.
// Stateless (HMAC-SHA256), so it cannot stop replay by itself; the ledger counts rounds per question id.
const enc = new TextEncoder();
const b64u = (b: ArrayBuffer | Uint8Array) =>
  btoa(String.fromCharCode(...new Uint8Array(b as ArrayBuffer))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64u = (s: string) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

export interface TicketPayload { v: string; q: string; exp: number }

async function key(secret: string) {
  return crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

export async function signTicket(secret: string, p: TicketPayload): Promise<string> {
  const body = b64u(enc.encode(JSON.stringify(p)));
  const mac = await crypto.subtle.sign("HMAC", await key(secret), enc.encode(body));
  return `${body}.${b64u(mac)}`;
}

/** The payload when the MAC is valid and the ticket is unexpired; null otherwise. Visitor match is the caller's check. */
export async function verifyTicket(secret: string, ticket: string, nowMs: number): Promise<TicketPayload | null> {
  const [body, mac, extra] = ticket.split(".");
  if (!body || !mac || extra !== undefined) return null;
  try {
    const ok = await crypto.subtle.verify("HMAC", await key(secret), unb64u(mac), enc.encode(body));
    if (!ok) return null;
    const p = JSON.parse(new TextDecoder().decode(unb64u(body))) as TicketPayload;
    if (typeof p.v !== "string" || typeof p.q !== "string" || typeof p.exp !== "number" || p.exp * 1000 < nowMs) return null;
    return p;
  } catch {
    return null;
  }
}
