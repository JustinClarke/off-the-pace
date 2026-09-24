# Phase B — guards run, pass/fail, coverage (2026-09-24)

Warehouse: data/dev.duckdb (built 2026-09-22 23:23), read_only for every probe.
dbt test was run against a byte-copy (`scratchpad/transform_audit/dbcopy/dev.duckdb`) via a
scratch profiles.yml, with --target-path/--log-path in scratchpad, so transform/target/ (which
audit_forward_window reads) and data/dev.duckdb were never opened read-write.
A first run with the copy named dev_copy.duckdb produced 20 spurious "Catalog dev does not exist"
errors (views hard-qualify catalog "dev") -- log kept as phaseB_dbt_test_run1_catalogname_artefact.log;
rerun with copy named dev.duckdb.

## Results
| Guard | Command | Result |
|---|---|---|
| dbt tests (673) | dbt test (profile -> copy) | PASS 672, FAIL 1: assert_stint_geometry_2018_compound_code_null rule 2 -- 24,680 2025 slick stint-laps have NULL compound_code (stg_tyre_allocations/tyre_allocations seed covers 2019-2024 only) |
| features --check | scratch replica `phaseB_features_check_nowrite.py` (persist_encoders=False) | forward-window CLEAN; aggregation-scope CLEAN; 0 known_leak; 36 off-lineage survey items; leakage guard CLEAN (32 features for p50); split train=2018..2025 holdout=2026 rows holdout=0; encoders identical to ml/models/encoders.json |
| data-profile-check | make data-profile-check | FAIL, 197 drift lines. Baseline last committed 2026-09-07 (c7de693), predates 12a-1 (2025 ingest) and v13 substrate changes. Gate is red for expected reasons -> currently gates nothing |
| lint-oracle-check | make lint-oracle-check | FAIL: 6 of 7 fct_* hashes drifted vs transform/tests/model_hashes.baseline.json (committed 2026-09-11). Runs on data/ci.duckdb (fixtures, built 09-20), so says nothing about dev regardless |

## Guard defect found while running it
`python -m ml.src.features --check` (the charter-permitted "read-only" audit, Makefile `ml-features`)
calls `load_features(..., persist_encoders=True)` (features.py:705) which WRITES
ml/models/encoders.json, a tracked shipped artefact. Not run as-is for that reason.

## Structural checks (§6)
1. Name-set intersection: confirmed, test_features.py:46 `set(X.columns) & S.EXCLUDED_LEAKAGE_COLUMNS`
   and features.py:706. An unlisted leaky column passes.
2. Identity tautology: int_lap_residual_decomposed.sql:306-315 defines driver_skill_residual_s AS
   pace_delta_s minus the six components; assert_lap_7term_identity.sql tests pace_delta = sum + residual.
   Closes by construction. Additionally pace_delta_s itself is `lap_time_s - COALESCE(base_track_pace_s,
   lap_time_s)` (line 294) -> 0 when the field curve is missing (5-11% of laps/season, see Phase D).
3. Test/model duplicated constants (drift surface): assert_no_future_leakage (EWMA weights 0.717.. /0.819..,
   min_observations >=1, frame 7 PRECEDING vs model 8 PRECEDING -- cosmetic because LAG ignores frames);
   assert_cliff_class_horizon_partition (1.0 s threshold, bucket bounds 2/5 = label definition);
   assert_cliff_seed_severity_bounded (1.6 cap vs fitter 1.5 winsorise, MIN_STINTS 8);
   assert_stint_boundary_integrity (0.600/0.2500 air-state ratio); assert_field_pace_honest_range (0.990/1.055).
4. Coverage boundary of audit_forward_window / audit_aggregation_scope:
   - forward-window follows only bare column passthroughs/renames (features.py:388-390). Stops at the first
     computed expression. Anything reached via arithmetic/COALESCE is unchecked.
   - forward-window flags LEAD and FOLLOWING frames only. A window with PARTITION BY and no ORDER BY
     (whole-partition, i.e. future-inclusive) is not flagged by either audit.
   - aggregation-scope reads GROUP BY only (not windows).
   - neither reads: seeds (compound_cliff_params -- in lineage via dim_compounds_season), python fits
     (fit_compound_cliff.py), parquet fits (data/fits/*), app SQL, ml-side synthesis (features.py
     stint-life target), or models off the mart lineage.
   - `_declared_known_leaks`: 0 entries -- nothing stale to report.
