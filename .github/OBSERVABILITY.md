# Observability & SLOs

Implements Phase 3 (Observability & reliability, F3) of `SYSTEM_DESIGN_AUDIT.md`. The platform
is static + client-side, so "production" observability splits in two: **in-browser** telemetry
(errors + RUM from real users) and **black-box** synthetic monitoring of the serving plane.

Everything here is **off by default** and activates only when configured matching the
env-gated pattern of Phases 1–2.

## 1. Error tracking (Sentry, env-gated)

A vendor-neutral facade lives in [`app/src/observability/`](../app/src/observability/):

- `initObservability()` (called in `main.tsx`) initialises Sentry **only when `VITE_SENTRY_DSN`
  is set**. The Sentry SDK is dynamically imported, so the default telemetry-off build never
  downloads it.
- `ErrorBoundary.componentDidCatch` forwards caught render errors via `captureException()`.
- `sendDefaultPii: false` no IP / user identifiers.

**Source maps:** when a build sets `SENTRY_AUTH_TOKEN` + `SENTRY_ORG` + `SENTRY_PROJECT`,
`vite.config.ts` enables `@sentry/vite-plugin` to upload hidden source maps, then deletes them
from `dist/` (`filesToDeleteAfterUpload`) so they symbolicate Sentry stacks **without being
served publicly**. With those unset, no maps are generated or shipped.

> One-time: the deploy runner must allow `@sentry/cli` to run its install script (it fetches the
> upload binary). It's pre-approved in `app/pnpm-workspace.yaml` / `app/.npmrc`
> (`onlyBuiltDependencies` + `allowBuilds`).

## 2. RUM / Core Web Vitals

`reportWebVitals()` (in `main.tsx`) streams **LCP / INP / CLS / FCP / TTFB** plus app-specific
timings through `track()`:

| Metric | Where it's emitted |
|---|---|
| `duckdb_init` | `data/duckdb/client.ts` DuckDB-wasm boot duration |
| `first_query` | `data/duckdb/client.ts` latency of the first user query (cold path) |
| `onnx_warmup` | `ml/session.ts` `InferenceSession.create` per model |
| `web_vital.*` | `observability/webVitals.ts` |

`track()` routes to (a) a `VITE_RUM_ENDPOINT` beacon if set and (b) Sentry breadcrumbs. RUM is
active when **either** a DSN or a beacon endpoint exists; sampled by `VITE_RUM_SAMPLE_RATE`.

See [`app/.env.example`](../app/.env.example) for every variable.

## 3. Synthetic monitoring

[`synthetic-monitor.yml`](workflows/synthetic-monitor.yml) exercises the live serving plane the
same way a browser does this is the direct guard against the **2026-06-11 incident class**
(stale bundle / manifest pointing at parquet that 404s):

- **http-smoke** (every 30 min): `scripts/smoke_cdn.sh` manifest 200, a sample parquet 200, the
  live site 200, version present, freshness. Cheap (curl only).
- **onnx-liveness** (daily + on demand): `app/scripts/synthetic_check.mjs` loads the live ONNX in
  headless node and runs one real inference, asserting finite output.

Both are runnable locally: `make app-smoke ENV=prod` and `node app/scripts/synthetic_check.mjs`.

**Alerting:** a failed scheduled run emails repo admins (GitHub default). If `secrets.ALERT_WEBHOOK`
is set, failures also POST a Slack/Discord-compatible message. Set `vars.PROD_SITE_URL` to include
the live-site check.

> The ONNX check is a *serving-liveness + finite-output* assertion, not full booster parity (the
> booster ground truth exists only at build time full parity stays the `ml-ci` / `app-parity`
> CI gate). Committing a small golden `{input, expected, tol}` fixture would upgrade
> `synthetic_check.mjs` to an exact parity assertion; a worthwhile follow-up.

## 4. SLOs

| SLO | Target | Measured by | On breach |
|---|---|---|---|
| **CDN manifest availability** | 99.9% of probes return 200 | `http-smoke` every 30 min | Page (webhook + email) |
| **Sample parquet reachability** | 100% (manifest never points at a 404) | `http-smoke` | Page this *is* the 2026-06-11 guard |
| **Live site availability** | 99.9% | `http-smoke` (`--site`) | Page |
| **ONNX serving liveness** | Daily inference returns finite output | `onnx-liveness` | Page |
| **Data freshness lag** | Manifest `generatedAt` ≤ 90 days | `http-smoke` `--max-age-hours 2160` | Review (non-paging data is seasonal) |
| **Parity badge green** | ONNX↔booster parity holds | `ml-ci` / `app-parity` at build | Block release |

Freshness is intentionally non-paging: the dataset updates per F1 season, so an old manifest is
usually correct. It surfaces as a warning to review, not an alert.

## 5. Operator setup checklist

- [ ] Create a Sentry (or GlitchTip) project; set `VITE_SENTRY_DSN` (+ optionally
      `SENTRY_AUTH_TOKEN`/`SENTRY_ORG`/`SENTRY_PROJECT` as deploy env for source-map upload).
- [ ] (Optional) Stand up a RUM beacon endpoint; set `VITE_RUM_ENDPOINT`.
- [ ] Set `vars.PROD_SITE_URL` so the synthetic monitor checks the live site.
- [ ] (Optional) Set `secrets.ALERT_WEBHOOK` for push alerting on monitor failure.
