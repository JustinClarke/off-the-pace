# Performance, E2E & Coverage (Phase 5)

Phase 5 of [`SYSTEM_DESIGN_AUDIT.md`](../SYSTEM_DESIGN_AUDIT.md) (F9) closes the testing/perf gap for
a heavily client-side app: end-to-end browser coverage of the wasm subsystems, a hard bundle-size
budget, advisory Core Web Vitals, and coverage-threshold ratchets across the JS and Python suites.

Nothing here touches analytics outputs it is envelope hardening that sits *on top of* the existing
unit tests, parity contract, identity invariant, and byte oracle.

---

## 1. Playwright E2E (`app-e2e.yml` · `make app-e2e`)

A real browser drives the **production bundle** and proves the three heavy client subsystems boot and
produce output. Specs live in [`app/e2e/`](../app/e2e); config in
[`app/playwright.config.ts`](../app/playwright.config.ts).

| Spec | Route | Proves |
|---|---|---|
| `duckdb-query.e2e.ts` | `/data-quality` | DuckDB-wasm instantiates (`duckdb_init`) and a real parquet query resolves (`first_query`) and renders a table |
| `onnx-inference.e2e.ts` | `/ml/simulator` | onnxruntime-web creates a session from the live CDN model and serves an inference (`onnx_warmup`), no runtime fault |
| `identity.e2e.ts` | `/lap-decomposition/waterfall` | The additive-identity ("seven-term") UI boots end-to-end and draws |
| `smoke.e2e.ts` | `/`, `/data-quality` | SPA shell mounts with no uncaught error; client-side routing works |

**The signal.** The observability layer keeps an always-on, in-memory ring of timing marks
(`duckdb_init` / `first_query` / `onnx_warmup` / web-vitals), recorded *regardless of whether a RUM
backend is configured*, and mirrors it read-only to `window.__OTP_PERF__`. The E2E waits on those
marks (`app/e2e/_helpers.ts`) rather than scraping fragile DOM, so a green run means the subsystem
actually executed with a finite result. It's also a handy devtools probe (`__OTP_PERF__` in the console).

**Run modes.**

- **Local / CI (default):** no `E2E_BASE_URL`, so Playwright builds-then-serves the bundle via
  `vite preview` on `:4173` (cross-origin-isolated see the `preview.headers` block in
  `vite.config.ts`) and the app fetches data + models from the **live prod GCS CDN**. Self-contained;
  needs no warehouse. `make app-e2e` builds first; in CI the workflow builds then runs.
- **Against a deploy:** `E2E_BASE_URL=https://<channel>.web.app pnpm exec playwright test` skips the
  local server and smokes a real deploy point it at a Firebase **preview channel** (from
  `preview.yml`) to test the PR's actual artefact.

One-time browser install: `make app-e2e-install` (or `pnpm exec playwright install --with-deps chromium`).
Chromium only DuckDB-wasm + onnxruntime-web rely on cross-origin isolation + wasm threads, and
Chromium is the reference engine prod is verified against.

---

## 2. Bundle-size budget (`app-perf.yml`, **blocking** · `make app-bundle`)

[`app/scripts/check_bundle_size.mjs`](../app/scripts/check_bundle_size.mjs) sums the **JavaScript**
bytes in `dist/` (raw + gzip + largest single chunk; `.wasm` binaries excluded "pre-wasm" per the
audit) and fails if any metric exceeds [`app/perf-budget.json`](../app/perf-budget.json). Deterministic
and offline it reads the built artefact only.

Current baseline: **~3.0 MB raw / ~0.9 MB gzip** of JS across ~70 assets; the largest single chunk is
the self-hosted DuckDB worker (~0.75 MB). The committed budget carries **8 % headroom** so ordinary
churn doesn't flake the gate.

> The wasm binaries (onnxruntime-web, DuckDB) are large but version-pinned, immutable-cached deps; a
> bump is caught by Dependabot and would move the JS-worker bytes the budget tracks. The budget
> deliberately governs the JS payload, which is where app-code regressions show up.

**Regenerate after an intentional size change:** `make app-bundle-budget-update` (rewrites the budget
from the current build + headroom). Never widen it to paper over an unexplained regression lazy-load
the offender instead.

## 3. Lighthouse CI (`app-perf.yml`, **advisory** · `make app-lighthouse`)

[`app/lighthouserc.json`](../app/lighthouserc.json) collects Lighthouse on the data-engine-free shell
routes (`/`, `/roadmap`) so scores reflect bundle/shell health rather than wasm-init variance (the
heavy routes are the E2E's job). All assertions are **`warn`** and the CI step is `continue-on-error`,
so a wasm-heavy SPA can't flake the build red it surfaces CWV/a11y regressions for review, while the
bundle-size script is the hard byte gate.

---

## 4. Coverage thresholds (ratchets)

Floors set just below the current baseline they guard against *losing* coverage (deleting tests,
landing large untested modules), not as a high quality bar. Raise them when coverage rises; never
lower without cause.

| Suite | Where enforced | Floor | Baseline |
|---|---|---|---|
| **vitest** (app) | `vitest.config.ts` `thresholds`, run via `--coverage` in `app-ci.yml` / `make app-coverage` | stmts/lines 32 · fns 33 · branches 78 | 33 / 34 / 79 % |
| **ingestion** (py) | `make cov-python` | `--cov-fail-under=55` | 60 % |
| **transform coefficients** (py) | `dbt-ci.yml` pytest step + `make cov-python` | `--cov-fail-under=60` | 68 % |
| **ml** (py) | `make cov-python` | `--cov-fail-under=25` | 28 % |

The included vitest globs span whole feature dirs; the pure transform/lib logic is well covered by
`*.test.ts`, while React rendering is exercised by the Playwright E2E rather than unit tests hence
the global floor reads low. `pytest-cov` is pinned in `requirements.txt` + `ml/requirements.txt`.

The ml full-suite coverage (28 %) reflects only the warehouse-free tests that always run; the
data-dependent paths (`train`/`predict`/`evaluate`/`export_onnx`) need a populated mart, so the ml floor
is enforced locally (`make cov-python`), not in `ml-ci.yml`'s fixture-gated subset.

---

## 5. Operator checklist

- [ ] **Required status checks.** Add **App E2E** and **App Performance → `perf`** to branch protection
      once they've run green on a PR (alongside the existing App CI gate). Documented in `SECURITY.md`.
- [ ] **Preview-deploy E2E (optional).** To smoke the actual deployed artefact instead of a local
      `vite preview`, wire `E2E_BASE_URL` to the `preview.yml` channel URL (requires the Phase 2 WIF
      provisioning). The current default already gives full functional coverage against live CDN data.
- [ ] **Budget upkeep.** After a deliberate bundle change, run `make app-bundle-budget-update` and
      commit the new `perf-budget.json` in the same PR.

## 6. Local quick reference

```bash
make app-e2e-install   # one-time: download the Playwright Chromium
make app-e2e           # build + Playwright smoke vs live CDN
make app-build && make app-bundle   # bundle-size budget gate
make app-lighthouse    # advisory Lighthouse (after a build)
make app-coverage      # vitest coverage-threshold gate
make cov-python        # Python coverage ratchets (ingestion + coefficients + ml)
```
