#!/usr/bin/env node
// Fails (exit 1) if the built bundle or its source maps contain something that looks like a key.
// Usage: node scripts/scan-bundle.mjs <dir>   (exact secret values: OTP_SCAN_SECRETS=a,b)
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const PATTERNS = [
  ["openai-style key", /\bsk-[A-Za-z0-9_-]{20,}/],
  ["cloudflare api token", /\bcf(?:ut|at)_[A-Za-z0-9_-]{30,}/],
  ["turnstile/admin secret name", /\b(?:TURNSTILE_SECRET|ADMIN_TOKEN)\b/],
  ["bearer credential", /Bearer\s+[A-Za-z0-9._-]{24,}/],
  ["private key block", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
];
const TEXT = /\.(js|mjs|cjs|map|html|css|json|txt)$/;

export function scanDir(dir, exact = []) {
  const hits = [];
  const walk = (d) => {
    for (const name of readdirSync(d)) {
      const p = join(d, name);
      const s = statSync(p);
      if (s.isDirectory()) walk(p);
      else if (TEXT.test(name) && s.size < 64 * 1024 * 1024) {
        const body = readFileSync(p, "utf8");
        for (const [label, re] of PATTERNS) if (re.test(body)) hits.push({ file: p, label });
        for (const x of exact) if (x && body.includes(x)) hits.push({ file: p, label: "exact secret value" });
      }
    }
  };
  walk(dir);
  return hits;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const dir = process.argv[2];
  if (!dir) { console.error("usage: scan-bundle.mjs <dir>"); process.exit(2); }
  const hits = scanDir(dir, (process.env.OTP_SCAN_SECRETS ?? "").split(",").filter(Boolean));
  for (const h of hits) console.error(`KEY-LIKE: ${h.label} in ${h.file}`);
  console.log(hits.length ? `FAIL: ${hits.length} hit(s)` : `OK: no key-like strings in ${dir}`);
  process.exit(hits.length ? 1 : 0);
}
