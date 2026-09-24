 # Issue Register

Single consolidated register for Off The Pace. Replaces the per-subsystem `_issue_logs/` tree.
State as of **2026-07-06**.

**Severity:** P0 blocking · P1 high · P2 medium · P3 low.
**Status:** Open · Accepted-by-design · Resolved.
**ID prefixes:** `TR` transform · `ML` ml/pipeline · `APP`/`INF` app & infrastructure · `DOC` docs ·
`GATE` validation-gate conditions.

---

## Open

| ID | Comp | Sev | Summary | Root cause / next step |
|---|---|---|---|---|
| GATE-1 | ml+transform | P1 | §4 gate **condition 1** — finish-confidence overconfident (calibration slope 0.717) | Recalibrate by sourcing finish-position SE from the Monte Carlo core (favour the MC route — the k≈2.77 inflation recipe broke on the full-data rebuild). Evidence comes from ML §4.2 in [PROJECT_PLAN.md](./PROJECT_PLAN.md#watch-along-plan--historical-race-replay--strategy-product); this condition gates the live phases in [STREAMING_PLAN.md](./STREAMING_PLAN.md). |
| GATE-2 | transform+app | P2 | §4 gate **condition 2** — aggregate reorderings at full-race granularity | Suppress per-stint deg-driven swaps; reorder at full-race grain. ML §4.1 distributions feed it. Both gate conditions must clear before any live watch-along phase. |
| DOC-001 | docs | P2 | `learn-dbt/master.md` — 12 dead in-page anchors (`#part-0`…`#part-11`) | TOC links to `#part-N` but headings slugify to `#part-N-title`. Fix: explicit `{#part-N}` heading ids. `onBrokenAnchors:'warn'` so the build still passes; stricter link-check could flag. |
| APP-002 | app | P3 | Ghost-car scatter plots team-changers twice (grain is driver × constructor) | **Decision locked (accepted):** keep the driver × constructor grain. Disambiguation UI (label by constructor, e.g. `BOT · ALFA`) not yet built — current index-suffix key is a stopgap. |
| TR-001 | transform+export | P3 | `stg_pits` absent from export → Feature 9 (pit gantt) on partial data | Staging model reads Bronze parquet that wasn't present. Ingestion v0.2 has since backfilled Bronze + Jolpica pit stops, so this likely just needs `materialized: table` + a rebuild to confirm. |
| TR-019 | transform | P2 | TR-014 (`assert_stint_boundaries_correct`) was vacuously true for an unknown period before being caught — unknown whether any other `transform/tests/assert_*.sql` (35 total) has a similarly inverted/tautological condition | Audit each singular test by deliberately corrupting a copy of the relevant model's data (or flipping the condition) and confirming the test actually fails — not done this session, scope there was fixing the 4 known failures only. |

---

## Accepted-by-design

| ID | Comp | Sev | Summary | Rationale |
|---|---|---|---|---|
| TR-002 | transform+export | P3 | `fct_ghost_car_pace` 35 MB total (partitioned by year × race) | Within limits; the app registers only the active-season partition (~5 MB), not all 35 MB. Move to CDN only if the total approaches ~150 MB. |

---

## Resolved

### Transform & ML pipeline

| ID | Comp | Sev | Summary | Fix |
|---|---|---|---|---|
| ML-001 | ml+transform | P1 | Predictions mart stale: 8 features dropped → `KeyError: 'n_gear_changes'`, 17 ml tests red, parity badge would fail | Cliff-features mart had dropped the powertrain/air-density joins after training. Re-synced at **v3** (137,447 laps, ONNX parity maxAbs 7.6e-6); full 53-model rebuild ran green 2026-06-12. |
| ML-002 | ml | P2 | ZipMap classifier-export concern (ort-web `ai.onnx.ml` support) | Didn't materialize — export uses `TreeEnsembleClassifier` with a plain float prob tensor, no ZipMap; NaN inputs preserved. No re-export needed. |
| ML-003 | ml | P2 | Degradation target bounded `[0,30]` — silently clipped real recovery laps | Corrected to `[-10,10]` with negatives allowed. |
| ML-004 | ml | P1 | Stint-life target leakage → near-oracle baseline (unfair eval) | Switched to a fair cohort-mean baseline; 28/28 ml tests green. |
| ML-005 | ml | P3 | `dim_corners` seed broken (~6% circuit coverage) | Telemetry features computed lap-internally (speed-minima) instead. Seed won't be revived. |
| ML-006 | ml+transform | P2 | Telemetry forward-fill double-counting channels | Filter `source_channel='car'`. |
| ML-007 | ml | P3 | `lift_and_coast` boolean degenerate (98% true) | Replaced with continuous `lift_coast_share`. |
| TR-003 | transform | P1 | Constructor pace conflation — driver skill leaks into car-pace metric (Verstappen makes Red Bull look artificially dominant) | `MEDIAN(pace_delta)` → omitted-variable bias. Refit `int_constructor_structural_pace` as an HDFE panel regression (`pyfixest`, constructor/driver/race/lap-bucket FE, clustered SE) + coefficient-sign assertion test. |
| TR-004 | transform | P1 | dbt-expectations `mostly` kwarg → compilation error (exit 2, whole build blocked) | `mostly` is dbt-core-only, not dbt-expectations. Removed it (use `row_condition` for NULL tolerance); purged ghost `schema.yml` patches. |
| TR-005 | transform | P2 | Dirty-air tax unstable / overconfident SE | Pooled SQL OLS → two-way FE (`driver^race`) panel + continuous `n/(n+500)` shrinkage. |
| TR-006 | transform | P2 | `stg_laps.race_id` is NUMERIC, not the slug | Gotcha surfaced during §5; joins corrected. |
| TR-007 | transform | P2 | TrackStatus codes mislabelled in `stg_laps` | Correct mapping: 4=SC / 5=Red / 6=VSC / 7=VSC-end. |
| TR-008 | transform | P2 | DuckDB has no `erf()` for SE propagation | Wrote a custom `normal_cdf` macro. |
| TR-009 | transform | P1 | Field cliff model assumed quadratic (squared formula) → ±72s error | It's **linear**; implemented linear `cliff_interaction_s`. |
| TR-010 | transform+export | P3 | `int_dirty_air_tax_component` / `int_coast_tax_component` lack `race_year` (can't partition) | Enrichment join via `fct_lap_residuals.lap_id` → year in `export_app_data.py`. |
| TR-011 | docs/meta | P3 | dbt model count reported 46 (plan said 58) | Auto-derived from the manifest; the count is now 53, hardcoded in `scripts/docs_facts.py`. |
| TR-012 | transform | P2 | `int_driver_circuit_era_affinity` returned `shrunk_affinity_s`/SE/CI for `n_obs<2` (should be NULL below the shrinkage threshold); the schema `not_null` test on `shrunk_affinity_s` was also unconditional, so fixing the model broke the test in turn | Wrapped the estimate/SE/CI columns in `CASE WHEN n_obs >= 2 THEN ... ELSE NULL END`; scoped the `not_null` test `where: "n_obs > 1"` to match the SE/CI columns already scoped that way. `assert_affinity_min_races` green. |
| TR-013 | transform | P3 | `assert_thermal_variance_positive` queried `int_lap_thermal_proxy` for `track_temp_c`, a column that model never had (a Binder Error surfacing as a test failure, not a real invariant violation) | Re-pointed the test at `int_track_evolution` (carries `track_temp_c` from `stg_weather`). |
| TR-014 | transform | P2 | `assert_stint_boundaries_correct`'s comparison operator was flipped (`>=` instead of `<=`) — trivially true for ~130k of the table's rows, so the test gave false assurance for an unknown period before being caught | Flipped to the correct `<=` direction. **Follow-up not done — see TR-019.** |
| TR-015 | transform+ml | P1 | `fit_compound_cliff.py` resolved circuit names via `season*100 + round`, which only matches double-digit rounds; every single-digit round (1-9 — most early-season races, every year 2018-2024) silently mis-keyed under a fake `"season_round"` circuit key instead of the real slug, orphaning 174 fitted rows and quietly corrupting a large share of the compound-cliff coefficients for an unknown number of releases | Fixed the join to `CAST(REPLACE(l.race_id,'_','') AS INTEGER) = rtt.race_id` (matches the dbt model's own join style, see TR-016 for the one seed gap this then exposed). Re-fit dropped mis-keyed rows 174→2, reviewed the full keyed diff, promoted (403 rows). P1 because the corrupted params feed `fct_cliff_prediction_features` — see ML-008. |
| ML-008 | ml | P1 | All 5 production ML targets (`degradation_regressor_{p10,p50,p90}`, `cliff_classifier`, `stint_life_regressor`) share the `fct_cliff_prediction_features` mart, so all 5 had been trained/evaluated on the data corrupted by TR-015 for an unknown number of releases | Retrained all 5 v4 targets on the corrected mart using existing tuned hyperparameters (`ml/models/<target>_best_params.json`) rather than a full Optuna re-search, since only ~172/403 seed keys changed, not the feature space. All 5 beat baseline; metrics moved in the expected direction (cliff classifier macro-F1 eval 0.328→0.333, stint-life RMSE eval 8.09→7.69, underperforming cohort cells 15→10, adversarial-probe accuracy 0.987→0.999). ONNX re-exported + parity-verified (28/28 ml tests), model card/reference/doc-facts snippets regenerated. |
| TR-016 | transform | P3 | `race_to_track.csv` seed was missing 2018 round 14 (Italian GP/Monza) — every other season 2019-2024 has its `italian_grand_prix` row; 2018 alone skipped straight from round 13 to 15, leaving 2 rows unresolved after the TR-015 fix | Added `2018_14,italian_grand_prix`. The 2 previously-orphaned cliff rows now resolve to the real circuit instead of falling through to a fake key. |
| TR-017 | transform | P2 | Promoting a coefficient seed (`seed_writer.py promote`) only writes the CSV under `transform/seeds/` — it never touches `data/dev.duckdb`, and `make dbt-dev`/`dbt-dev-full`/`dbt-prod` never ran `dbt seed`. A promoted seed was silently invisible to the warehouse until someone remembered to run `dbt seed` manually (this bit the TR-015 fix: `make dbt-dev && make dbt-test` kept "failing" post-promotion on the *old* 401-row seed) | Added a `dbt-seed` Makefile target; `dbt-dev`/`dbt-dev-full`/`dbt-prod` now depend on it, so seeds always load before models build. `coefficients-promote` also prints a reminder. CI's `test-all` was unaffected — `dbt build` already seeds+runs+tests together. |
| TR-018 | transform | P3 | `seed_writer.py`'s `ARCHIVE_DIR` (`seeds/_archive/`) lived inside dbt's `seed-paths: ["seeds"]` scan path, so every `dbt seed` after a promotion created a spurious extra table (e.g. `compound_cliff_params_2026-07-06`) — one more phantom table per future promotion, forever | Moved `ARCHIVE_DIR` to `transform/seeds_archive/` (sibling of `seeds/`, outside dbt's scan path); relocated the existing archive file; dropped the stray table from `data/dev.duckdb`. |
| ML-009 | ml | P2 | `export_onnx.py --version` silently defaulted to `"v1"` while every other ML CLI (`evaluate.py`, `predict.py`, `tune.py`, `card.py`) defaults to `S.MODEL_VERSION_DEFAULT` (currently `v4`) — an omitted `--version` loads a stale model, and if its feature count happened to match the current contract, would produce a silently-wrong ONNX export with no parity failure to catch it (this session hit the lucky case: `expected 38, got 42`, a loud crash — but a same-feature-count stale version would not have errored) | Changed the default to `S.MODEL_VERSION_DEFAULT` for consistency with the rest of the pipeline. |

### App & infrastructure

| ID | Comp | Sev | Summary | Fix |
|---|---|---|---|---|
| INF-009 | infra | P0 | iCloud + git index corruption — all files shown deleted/untracked | `index.lock` sync race vs git's atomic rename. Recover with `rm .git/index.lock` + `git reset HEAD`. **Root fix: repo moved to `/Users/justin/github`** (out of iCloud). |
| INF-010 | infra | P0 | venv shebang pointed at dead iCloud path + duplicate `dbt_utils 2/` → dbt CLI unusable | Rebuilt venv in place (correct shebangs) + removed the duplicate package dir. dbt CLI now operational — full 53-model rebuild green 2026-06-12. |
| INF-001 | app | P0 | Feature #14 worker blob hang under COEP — every data feature stuck on "Initialising query engine" | `blob:` + `importScripts()` blocked by COEP `require-corp`. Load the same-origin worker directly + 30s init timeout so any future hang surfaces as an error. |
| INF-003 | app | P0 | Feature #14 COI bundle vs parquet shared-memory `LinkError` — all parquet reads fail | `selectBundle()` picks the threaded COI bundle under cross-origin isolation; parquet ext can't link shared memory. Pin the EH (non-threaded) bundle. |
| INF-002 | app | P1 | Feature #14 named query never registered (type-only import erased) | Add a side-effect `import './queries'` alongside the `import type`. |
| INF-004 | app | P1 | Feature #14 server-absolute parquet path 404s in the DuckDB VFS | `registerFileURL` over HTTP under a virtual name, then `parquet_scan` that name. |
| INF-005 | app | P1 | onnxruntime-web breaks in Vite dev (mjs `?import` 500 / CORP) + "Session already started" on re-score | Dev-only Vite middleware serves `/ort/*.mjs` raw with CORP/COEP headers; global `runSerial()` queue serialises runs through the one shared proxy worker — Feature #16. |
| INF-007 | app | P2 | Stale-v1 fingerprint on simulator + blind-test (app v1/38-feat vs ML default v3/41-feat) | Bumped fingerprints (3aff4559 → b8a37b7c); faithful v3 real-row scoring. |
| INF-006 | app | P2 | DuckDB bigint → JS Number coercion (Feature #16) | Coerce in the shared ml layer. |
| APP-001 | app | P2 | Waterfall: `fct_lap_residuals` closure gap (~12.6s) from omitting `dirty_air_tax_s` | **Identity is 7-term** (`fuel + compound + rubber + ambient + constructor + dirty_air_tax + driver_skill`; verified 1.4e-14). The gap was from missing `dirty_air_tax_s` (the 6th env term inside `total_explained_s`), NOT a missing 8th term. Reconstruct `pace_delta_s` (not exported) from the 7 terms. `track_unexplained_s` is a **non-closing** field-level diagnostic — show it as a separate "Track noise" bar; do NOT add it to the closure (over-counts ≤2.5s). COALESCE its NULLs. See `reference_lap_residuals_identity.md`. |
| INF-011 | infra | P2 | Numbered-prefix paths survived a dir rename (`03_data` → `data`) → silent empty warehouse | Repo-wide substitution + a grep CI gate on `0[1-4]_` + startup path assertions (DuckDB silently creates an empty DB on a missing path). |
| INF-008 | infra | P3 | `tsconfig` `ignoreDeprecations:"6.0"` rejected by TS 5.9 → build breaks | Dropped `baseUrl` + `ignoreDeprecations`; anchored `paths` `@/*` → `./src/*`. |

### Docs

| ID | Comp | Sev | Summary | Fix |
|---|---|---|---|---|
| DOC-002 | docs | P3 | Core READMEs had broken relative links + stale `05_ML` references | Documentation cleanup sweep across `ingestion/`, `transform/`, marts READMEs. |
| DOC-003 | docs | P3 | `reference/glossary.md` hand-edited → would fail the reference-drift CI gate | Resolved at source; no longer in `git status`. Never hand-edit `docs/reference/` (auto-generated). |
