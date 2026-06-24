# .github/workflows/-CI Pipeline Index

Fifteen GitHub Actions workflows run on the repository. The four code-layer gates each mirror
the `make` targets you can run locally if it passes locally, it passes here. Runbooks:
`.github/DEPLOYMENT.md` (release), `.github/OBSERVABILITY.md` (SLOs), `.github/DATA_PIPELINE.md`
(orchestration + data quality), `.github/PERFORMANCE.md` (E2E + perf budgets + coverage).

## Workflow index

| Workflow | File | Triggers on | What it gates |
|---|---|---|---|
| **dbt CI** | `dbt-ci.yml` | Changes to `transform/`, `ingestion/`, `requirements.txt` | Build all 60 models; run 443 tests including `assert_additive_identity`; confirm the seven-term identity holds on every lap |
| **Docs CI** | `docs-ci.yml` | Changes to `docs/`, `scripts/`, `transform/models/**`, `ingestion/schemas/**` | Validate Mintlify docs; run `python scripts/build_reference.py && git diff --exit-code`-fails if any generated MDX drifts from its source |
| **ML CI** | `ml-ci.yml` | Changes to `ml/`, `scripts/gen_ml_reference.py` | 28-test leakage spine (static guards always run; warehouse-dependent guards gate on bronze fixtures); ONNX parity; beats-baseline; no hardcoded holdout year in `ml/src`; model-card MDX drift check |
| **App CI** | `app-ci.yml` | Changes to `app/**` | pnpm typecheck, ESLint, the vitest suite **with the coverage-threshold ratchet** (`--coverage`), and a production build (defaults to the CDN data base, so no warehouse export is needed) |
| **App E2E** | `app-e2e.yml` | Changes to `app/**` | Playwright headless-Chromium smoke: serves the prod bundle (`vite preview`) against the live CDN and asserts DuckDB-wasm init + a real query, an ONNX inference, and the additive-identity UI all boot |
| **App Performance** | `app-perf.yml` | Changes to `app/**` | Bundle-size budget (**blocking**, `check_bundle_size.mjs` vs `perf-budget.json`) + Lighthouse CI (advisory CWV/a11y on the shell routes) |
| **CodeQL** | `codeql.yml` | Push/PR to `main`, weekly | SAST over Python and TS/JS with the `security-extended` query pack; results to the Security tab |
| **Security Scan** | `security-scan.yml` | Push/PR to `main`, weekly | gitleaks secret scan (**blocking**); `pip-audit` (root + `ml/`) and `pnpm audit` dependency CVE scans (non-blocking until the backlog is clean) |
| **OSV-Scanner** | `osv-scanner.yml` | Push/PR to `main`, weekly | Cross-ecosystem lockfile CVE scan (OSV database) → SARIF in the Security tab; PR runs flag only newly-introduced vulnerabilities |
| **SBOM** | `sbom.yml` | Release published, manual | CycloneDX SBOM (syft) of the Python + app lockfiles, attached to the release |
| **Release Please** | `release-please.yml` | Push to `main` | Maintain the release PR + `CHANGELOG.md` from conventional commits; tag + GitHub Release on merge |
| **Deploy** | `deploy.yml` | Release published, manual | Keyless (WIF): smoke staging → promote staging→prod → `firebase deploy` → smoke prod |
| **Preview Deploy** | `preview.yml` | App PRs | Keyless (WIF): build against staging data → Firebase preview channel `pr-<n>` + PR comment |
| **Synthetic Monitor** | `synthetic-monitor.yml` | Every 30 min + daily | Black-box probe of the live site/CDN: manifest + sample parquet + site 200, freshness, and a daily headless ONNX inference. Alerts on breach (guards the 2026-06-11 incident class) |
| **Data Pipeline** | `pipeline.yml` | Manual + weekly | Orchestrated DAG: ingest → dbt build + oracles → data-quality → ml → export → publish(staging) → verify (auto-rollback). Self-hosted runner + WIF; guards on `PIPELINE_ENABLED` |

## Local equivalents

```bash
make dbt-test          # mirrors dbt-ci.yml
make docs-reference    # mirrors the drift-check step in docs-ci.yml
make ml-test           # mirrors ml-ci.yml test steps
cd app && pnpm typecheck && pnpm lint && pnpm exec vitest run && pnpm build  # mirrors app-ci.yml
make app-coverage      # vitest coverage-threshold gate (mirrors app-ci.yml's --coverage step)
make app-e2e           # mirrors app-e2e.yml (one-time: make app-e2e-install)
make app-bundle        # mirrors app-perf.yml's bundle-size budget (after make app-build)
make cov-python        # Python coverage-threshold ratchets (ingestion + coefficients + ml)
make security          # mirrors security-scan.yml (audit + secret-scan; needs pip-audit, gitleaks)
make sbom              # mirrors sbom.yml (needs syft)
make app-publish-staging && make app-smoke ENV=staging && make app-promote  # mirrors deploy.yml's data path
make dq-test           # mirrors pipeline.yml Stage 3 (data-profile diff + freshness)
make verify-published  # mirrors pipeline.yml Stage 7 (post-publish gate; ENV=, ROLLBACK=1)
```

## Security & supply chain

`SECURITY.md` documents the vulnerability-disclosure flow, which CI gate covers what, and the
one-time GitHub repo settings (secret-scanning push protection, Dependabot alerts, CodeQL
advanced setup, required status checks) that live in settings rather than in code. Dependency
*updates* are automated by Dependabot (`.github/dependabot.yml`).

## Architecture decisions

`.github/adr/DECISIONS.md` records why key architectural choices were made-DuckDB over
Postgres, Hive partitioning, the additive identity as a CI gate, etc.
