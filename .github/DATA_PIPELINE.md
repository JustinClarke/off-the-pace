# Data Pipeline & Quality Runbook

Implements Phase 4 (Data orchestration & quality, F6/F7/F10) of `SYSTEM_DESIGN_AUDIT.md`. Turns
the hand-run Makefile pipeline into a scheduled, retried, quality-gated, verified DAG and bounds
the storage the no-delete publish would otherwise leak.

## The DAG

```
ingest → transform (+ identity & byte oracles) → data-quality → ml → export → publish(staging) → verify
```

[`pipeline.yml`](workflows/pipeline.yml) runs this as one job (each stage consumes the previous
stage's `data/` on disk). `workflow_dispatch` (with a `season` input) or weekly schedule.

**Runner constraint (read this):** the warehouse rebuild needs the ~6 GB bronze corpus, which does
not fit a fresh GitHub-hosted runner. Run on a **self-hosted runner with a persistent `data/`** 
set repo var `PIPELINE_RUNNER` to its label so ingest is incremental. On `ubuntu-latest` it would
re-ingest from scratch every run. The job guards on `vars.PIPELINE_ENABLED == 'true'`, so it never
fires before that's deliberately set. Publish stages additionally require WIF (see
[`DEPLOYMENT.md`](DEPLOYMENT.md)); they skip cleanly when unconfigured.

| Stage | Command | Gate |
|---|---|---|
| 1 Ingest | `make ingest-recent ingest-jolpica` (or `add-season SEASON=`) | retried 3× (network) |
| 2 Transform | `make dbt-dev-full dbt-test` + byte oracle `--check` | identity invariant + byte-stability |
| 3 Data quality | `make dq-test` | profile diff + freshness (non-fatal review) |
| 4 ML | `make ml-all` | leakage guards + ONNX↔booster parity |
| 5 Export | `make app-data app-models` | manifest + model copy |
| 6 Publish | `make app-publish-staging` (WIF) | staging only |
| 7 Verify | `scripts/verify_published.sh --env staging --rollback-on-fail` | version + stats + ONNX, **auto-rollback** |

Promotion staging→prod stays the deliberate step in [`DEPLOYMENT.md`](DEPLOYMENT.md) (`make app-promote`).

## Data quality (F7)

Three layers, on top of the additive-identity invariant and the byte-stability oracle:

1. **Build-over-build data-diff** `transform/scripts/snapshot_data_profile.py`. Profiles every
   `fct_*`/`mart_*`/`dim_*` table (row count, per-column null-rate, numeric means) into a committed
   baseline (`transform/tests/data_profile.baseline.json`) and `--check`s with tolerances. Catches
   **volume drift, null-rate spikes, and target-mean shift** the semantic drift the byte oracle
   (which only proves byte-identity) can't describe. Like the oracle, the baseline is an approval
   artefact: regenerate (`make data-profile-snapshot`) when the data *should* change.
2. **Source freshness** `transform/scripts/check_source_freshness.py`. Classic dbt
   `source freshness` keys on a per-row `loaded_at_field`; the bronze sources are file-based external
   parquet with **no ingestion timestamp**, so that doesn't apply. Instead this asserts season
   recency (`MAX(season) ≥ MIN_SEASON`). Non-fatal by default (data is seasonal); `--strict` in the
   DAG once a new season is expected.
3. **Post-publish verification** `scripts/verify_published.sh` (Stage 7): fetches the *just-
   published* manifest + sample parquet + model manifest + ONNX, asserts the live version/stats match
   the local export and a real inference returns finite output, and **auto-rolls-back the manifest**
   on mismatch (`rollback_cdn.sh`). Folds the manual 2026-06-11 debugging into one guard.

Run locally: `make dq-test` (diff + freshness) and `make verify-published ENV=prod`.

## Bucket GC (F10)

The no-delete publish + in-place overwrite accretes storage forever. `infra/gcs_lifecycle.json`
(applied by `make bucket-lifecycle` → `scripts/apply_bucket_lifecycle.sh`) enables object versioning
and:

- expires **noncurrent** versions 30 days after they're superseded, keeping the **3 newest** so a
  recent rollback can still restore real parquet bytes;
- reaps the ephemeral `staging/` prefix after 14 days;
- expires `data/manifest-archive/` rollback pointers after 180 days.

Codified in `infra/terraform/bucket.tf` (Phase 6, `make tf-validate`); the script is the no-Terraform interim.

## Operator setup

- [ ] Provide a runner with persistent `data/`; set `vars.PIPELINE_RUNNER` + `vars.PIPELINE_ENABLED=true`.
- [ ] WIF configured (Phase 2) for the publish/verify stages.
- [ ] `make bucket-lifecycle` once (enables versioning + GC).
- [ ] Optional `secrets.ALERT_WEBHOOK` for failure alerts.
- [ ] Bump `MIN_SEASON` / the freshness `--strict` flag when a new season should have landed.
