# AI-06 — Cloudflare Worker proxy to Workers AI

**Group:** 3 delivery and launch · **Depends on:** none · **Blocker:** none. `AD1` ruled 2026-10-15: Cloudflare Workers AI on the account's free allowance (about 10,000 neurons a day) for now.

**Sources:** `firebase.json`, `docs/platform/architecture-decisions.mdx`, `_roadmap/_wip/AI_PLAN.md`.

**Decided, and nothing beyond it:** the proxy is a Cloudflare Worker that calls Workers AI, model gpt-oss-20b (`AD2`, 2026-10-22; the earlier Llama candidate is superseded). Launch cost and access are `AD4`, deferred: until it is ruled the Worker carries a low placeholder daily cap (about 1 USD of usage) and a per-visitor limit (watch W1). The model access lives in the Worker, never in the browser bundle. Firebase Hosting stays as it is; the Worker is the only thing that touches the model API. No paid tier and no bring-your-own-key path are decided.

---

## What exists today

The old AI plan (`_roadmap/_wip/AI_PLAN.md`) sketches a Firebase Cloud Function proxy, a secret store and Firebase App Check. None of it is built and there is no functions folder; read those parts as superseded by the Worker. `firebase.json` sets a Content-Security-Policy (report-only) whose `connect-src` allows only `'self'` and `https://storage.googleapis.com`, so a browser call to the Worker host would be blocked once the policy is enforced.

## First steps (before any code)

1. **Confirm the model and the limit from the Cloudflare docs.** Check that gpt-oss-20b is available on Workers AI with tool calls, and read its current price and the free-tier limit. Checked 2026-10-15: free allowance 10,000 neurons a day, resetting at 00:00 UTC, errors past it (https://developers.cloudflare.com/workers-ai/platform/pricing/). The prototype measured about 460 neurons per answer (not yet measured on the production endpoint). Recheck on the day, as pricing pages change.
2. Convert AI-07's tokens per answer into answers per day against the allowance, and record it.

## Method

1. The Worker takes a message list only. It fixes the model, the system prompt, the tool set and the output cap server-side, ignores browser-sent tools, `max_tokens` and reasoning settings, and rejects bodies over a fixed size.
2. Add a per-visitor daily limit, the placeholder daily cap until `AD4` is ruled, and Turnstile as the abuse check (App Check is Firebase-only; the old plan is superseded).
3. **Usage counter.** The Worker counts neurons (or tokens) used per day in Worker-side storage, readable by the owner, so we can see how fast the allowance is used.
4. **Allowance guard.** When the daily allowance is spent (counter at the limit, or Workers AI returns its over-limit error), the Worker returns a fixed "paused" response and the drawer shows "answers are paused for today". It resets at 00:00 UTC.
5. One config value pauses the Worker without a deploy; the drawer shows the same paused state.
6. Add the Worker host to `connect-src` in `firebase.json` and nothing broader. Keep Firebase hosting.
7. The Worker passes tool calls through but never runs a query. Data stays client-side.

## Acceptance

- Step 1 is written down with the source and date before code starts.
- A scan of the built bundle and its source maps finds no key, run in CI. A planted fake key makes it fail.
- The key is absent from responses, logs and error messages (tested with a forced error).
- Requests failing the abuse check are refused.
- The per-visitor limit, the allowance guard (simulated exhaustion shows "answers are paused for today") and the pause switch each trigger in a test.
- The usage counter increases per answer and can be read.

## Definition of done

The Worker runs on a preview environment and every acceptance check passes there. CSP lists the single new host. Deploying to production is the user's call.
