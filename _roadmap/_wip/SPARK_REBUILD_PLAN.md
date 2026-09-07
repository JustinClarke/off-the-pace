# Spark Rebuild Plan — Databricks Data Engineer Associate Study Project

> Separate repo. Reuses off-the-pace's already-ingested raw data (no re-ingestion).
> Rebuilds the transform layer in PySpark/Spark SQL + Delta Lake, in parallel with
> [PROJECT_PLAN.md](./PROJECT_PLAN.md), [AI_PLAN.md](./AI_PLAN.md), and
> [STREAMING_PLAN.md](./STREAMING_PLAN.md) — none of which this plan replaces yet.
> Issue register → [ISSUES.md](./ISSUES.md).

---

## Status

```
Discovery (this doc)     Build (not started)     Parity gate     Cutover
──────────────────────────────────────────────────────────────────────
✅ complete               ❌ not started           ❌ not started   ❌ not started
```

**Goal (locked 2026-06-30):** rebuild the off-the-pace transform layer in Spark —
both to study for the Databricks Certified Data Engineer Associate exam and to
revisit transform-layer design decisions documented in this repo's memory/incident
history ("where we went wrong"). **Eventual replacement**, not a permanent fork:
if the Spark output proves better, it becomes off-the-pace's data layer. Until the
parity gate (below) passes, the existing dbt-duckdb pipeline stays authoritative
and untouched.

**Non-goals:** re-ingestion (raw data is reused as-is), changing the app folder,
changing ML code (only retraining is in scope — see §3).

---

## 1. The contract that keeps the app and ML untouched

The app (DuckDB-wasm, browser) and ML (Python, `ml/`) never talk to dbt — they
consume parquet under four exported subdirectories, written by
[`scripts/publish_cdn.sh`](../../scripts/publish_cdn.sh) (lines 90–96):

```
data/dimensions/    ← dim_*           (4 reference models)
data/facts/         ← fct_*           (7 of the 10 marts models)
data/intermediates/ ← int_* (exported subset of the 34 intermediate models)
data/marts/         ← mart_*          (2 of the 10 marts models)
data/models/        ← ONNX artefacts  (ml/models/manifest.json, currently v4)
```

**Rule: as long as Spark writes parquet matching these paths, table names, and
column names/types, the app and ML need zero code changes.** This is the entire
reason a from-scratch rebuild is safe to attempt without touching two other
codebases.

Current dbt-duckdb model inventory (`transform/dbt_project.yml`) — this is the
shape the Spark rebuild targets, layer for layer:

| Layer | Materialization | Count | Spark equivalent |
|---|---|---|---|
| staging | VIEW | 12 | bronze→silver read/cast, no shuffle |
| reference | TABLE | 4 | small dimension tables, broadcast joins |
| intermediate | VIEW, tagged `[intermediate]` | 34 | silver transforms |
| marts | TABLE | 10 (7 `fct_` + 2 `mart_` + 1 `dim_events`) | gold, Delta tables |

**60 models total.** ML is on `manifest.json` v4 (42 features, 5 models:
`cliff_classifier_v4`, 3× `degradation_regressor_{p10,p50,p90}_v4`,
`stint_life_regressor_v4`, trained 2018–2024 holdout-2025).

---

## 2. Exam domain → project coverage map

Databricks Certified Data Engineer Associate: 45 MCQs, 90 min, SQL-primary.

```
Domain                              Weight    Coverage in Spark rebuild
─────────────────────────────────────────────────────────────────────
Transformation & Modeling            22% ███████████  ●●●●● direct hit
Data Ingestion & Loading             21% ██████████   ●●●○○ partial
Lakeflow Jobs                        16% ████████     ●●●●● direct hit
Governance & Security                15% ███████      ●●○○○ bolt-on
CI/CD                                10% █████        ●●●●● direct hit
Troubleshooting/Monitoring/Optim.    10% █████        ●●●●● direct hit
Platform basics                       6% ███          ●○○○○ incidental
                                     ────
                                     100%
```

```
 off-the-pace TODAY                  exam domain                Spark rebuild
 ───────────────────                 ───────────                ─────────────
 dbt-duckdb staging/                 Transformation              PySpark/Spark SQL
 intermediate/marts        ───────►  & Modeling (22%)  ◄───────  + Delta Lake
 (60 models)                                                     (MERGE, time travel,
                                                                   OPTIMIZE/ZORDER)

 raw ingestion (reused          ╲    Data Ingestion              Auto Loader replay
 as-is, no change)               ╲   & Loading (21%)   ◄───────  of bronze files as
                                  ╲                               a "landing zone"
                                   ╲  (no live source → partial)

 .github/workflows/pipeline.yml ───►  Lakeflow Jobs               Lakeflow Jobs
 (7-stage DAG, self-hosted)           (16%)             ◄───────  (same 7 stages,
                                                                    new orchestrator)

 (nothing today —                   Governance &                Unity Catalog
  no catalog/ACLs)          ───────► Security (15%)    ◄───────  (bolt-on: register
                                      (functionally optional)     gold tables, demo
                                                                   ACLs/row filters)

 setup_wif.sh + deploy.yml ───────►  CI/CD (10%)        ◄───────  Databricks Asset
 (keyless OIDC release eng)                                       Bundles

 snapshot_model_hashes.py  ───────►  Troubleshooting/    ◄───────  partition/shuffle
 thread-reorder float       drift    Monitoring/                  debugging, cluster
 fix (profiles.yml:11–18)            Optimization (10%)            sizing, query plans

 (n/a)                               Platform basics (6%)         incidental, skip
```

4 of 7 domains (69% of exam weight — Transformation & Modeling, Lakeflow Jobs,
CI/CD, Troubleshooting/Monitoring) map to a real existing off-the-pace artefact.
Ingestion and Governance (36% combined) are bolt-ons built *for* the cert rather
than *from* a project need — lower priority if time is tight.

---

## 3. Domain-by-domain build notes

### Transformation & Modeling (22%) — direct hit
Rebuild all 60 models as PySpark/Spark SQL + Delta Lake, preserving the
staging→reference/intermediate→marts layering. Use Delta `MERGE` for incremental
marts, Delta time travel in place of the current snapshot-hash parity workflow,
`OPTIMIZE`/`ZORDER` in place of DuckDB thread-pinning tricks (see §4 for why the
old fix doesn't translate directly).

### Data Ingestion and Loading (21%) — partial
No live source to ingest (raw data reused as-is per the non-goals above). Demo
this domain by replaying the existing bronze files through Databricks Auto
Loader / `COPY INTO`, treating the static raw files as a landing zone — gives
exam-relevant patterns (schema inference/evolution, incremental file detection)
without rebuilding real ingestion.

### Working with Lakeflow Jobs (16%) — direct hit
[`pipeline.yml`](../../.github/workflows/pipeline.yml) is a 7-stage DAG today:
Ingest → Transform+Tests → Data Quality → ML → Export → Publish (WIF) → Verify
(with auto-rollback on stage 7 mismatch). Rebuild the same 7 stages as Lakeflow
Jobs tasks with explicit dependencies/retries — same shape, new orchestrator.
Note the original runs on a **self-hosted runner** because the ~6GB bronze corpus
doesn't fit a fresh GitHub-hosted runner per `pipeline.yml` lines 8–12 — the
Databricks equivalent (persistent cluster/volume vs. ephemeral) is worth treating
as a deliberate design comparison, not just a lift-and-shift.

### Implementing CI/CD (10%) — direct hit
Mirrors existing release engineering: [`setup_wif.sh`](../../scripts/setup_wif.sh)
(keyless OIDC) + [`deploy.yml`](../../.github/workflows/deploy.yml) (smoke
staging → promote → deploy → smoke prod). Same pattern via Databricks Asset
Bundles + environment promotion instead of GCP WIF + Firebase.

### Troubleshooting, Monitoring, and Optimization (10%) — direct hit
Real prior incident to replay: [`snapshot_model_hashes.py`](../../transform/scripts/snapshot_model_hashes.py)
caught non-associative float aggregation reordering across DuckDB intra-query
threads, drifting `fct_*` output build-to-build with no logic change. Fixed by
pinning DuckDB's *intra-query* thread count (`transform/profiles/profiles.yml:18`,
`settings.threads: 1` — distinct from dbt's own `threads: 1` at line 16, which
only controls model concurrency). Translating "why did float aggregation drift"
into Spark's partition/shuffle terms (and whether Delta's deterministic write
path sidesteps this class of bug entirely) is genuinely useful exam material,
not just box-checking.

### Governance and Security (15%) — bolt-on
Unity Catalog is functionally unnecessary for a solo project (off-the-pace has
no catalog/ACL layer today). Cheap to demo anyway: register gold tables in
Unity Catalog, add a couple of ACLs/row filters as a pure learning exercise.

### Databricks Intelligence Platform (6%) — incidental
Workspace/cluster/notebook basics, picked up for free while doing the above.
Not worth designing project work around.

---

## 4. ML — retrain, don't rewrite

ML stays Python/`ml/`, untouched at the code level, **as long as the Spark
output matches the marts schema contract (§1)**. Two things change behavior,
not code:

- If the Spark rebuild fixes a data-layer issue (the goal — "find out where we
  went wrong, can be better"), feature distributions shift → existing training
  scripts need a **retrain**, same as the v1→v4 progression already in
  `ml/models/manifest.json`.
- If feature *names/count* change (currently 42), that's a model-version bump
  (v4→v5), following the existing versioning pattern — not an architecture
  change.

Validate before any cutover: diff Spark output against current dbt-duckdb
output per model, for any model not deliberately changed, before pointing the
app's CDN publish step at Spark-produced parquet. This is the same instinct
behind `snapshot_model_hashes.py` — reuse that pattern (committed baseline +
build-over-build diff) rather than inventing a new oracle.

---

## 5. Streaming tie-in (no contradiction with STREAMING_PLAN.md)

[STREAMING_PLAN.md](./STREAMING_PLAN.md) is ⛔ deferred/gated — live watch-along
phases are blocked on confidence recalibration (GATE-1 in ISSUES.md) and a
live-timing source/licensing decision (FastF1 live vs OpenF1), targeting a
GCS + Cloud Run + in-browser Monte Carlo architecture. **This plan does not
unblock or accelerate that gate.**

What Spark Structured Streaming *can* do here, scoped tightly: replay the
existing static historical data through a streaming read (Auto Loader's
incremental mode) as a study exercise for the exam's streaming-adjacent
ingestion content. It is explicitly **not** an attempt to build the live
relay service or pull in a live-timing feed — that decision stays gated where
STREAMING_PLAN.md left it. Microsoft Fabric (PROJECT_PLAN.md Phase 4,
enterprise streaming) is a separate, later, unrelated trigger.

---

## 6. Open questions before starting a build

- New repo name/location — not decided.
- Local Spark (single-node, `spark-submit`/Databricks Community Edition) vs.
  paid Databricks workspace for the Lakeflow Jobs/Unity Catalog domains — cost
  tradeoff not yet evaluated.
- Which models to port first for parity validation — recommend starting with
  the cheapest layer (staging, 12 models) to prove the harness before tackling
  the 34 intermediate models.
