# Transform-layer audit: is it ready for an AI chat assistant to quote from?

Audited 2026-11-07. This was read-only. Queries ran against the scratch warehouse `scratchpad/dbt1/dev.duckdb` (full build: PASS=1491, WARN=0, ERROR=0; 79 tables, 18 views, 19 seeds, 1,373 data tests and 2 unit tests). I made no git operations and did not touch `data/dev.duckdb` or `data/ci.duckdb`.

## Verdict

**Not ready.** The build is green and the keys hold: every mart has a uniqueness test, and every one I sampled has no duplicates. The problem is honesty, not plumbing. Four things stand in the way:

1. **Race ratings can carry a false-tight interval or none at all.** The interval on the main AI-facing mart, `mart_race_driver_summary`, is built from a different statistic than the number it brackets. It is tightest exactly where the rating rests on one or two laps.
2. **Some dirty-air values are not what they claim.** "Unavailable" is turned into 0.0 s on 6,460 clean laps and in whole-race means. The standard error is a hardcoded 15% of the point estimate, but the docs call it "propagation". The method behind every dirty-air number has had no validation verdict since WC-03/04 closed.
3. **No mart says which build or label version a number came from**, and the three marts built "for an LLM" are not exported to the app.
4. **The data the app is currently serving predates the v16 label seal.** I confirmed this on the one file I could check.

Each of these is 0.25 to 2 days of work. The total is about 5 to 8 days of transform-side work before the AI layer (also parked by owner ruling PK1) can safely quote numbers.

---

## Cracks (ranked)

### C1. Race-rating interval does not belong to the rating (severity: P0 for AI)
- **Evidence:**
  - The point estimate is `rating_s = driver_skill_loro_s`, the **median of paired lap-time differences** to the teammate (`int_driver_race_skill_loro.sql` header, lines 6-12).
  - The interval is `rating_s ± 1.96 × SE(mean of driver_skill_residual_s)` (`mart_race_driver_summary.sql:28-30, 105-106`). That is the SE of a different, field-relative statistic over a different lap set.
  - `paired_lap_count` exists upstream (`int_driver_race_skill_loro.sql:204, 244, 297`) but the mart drops it.
- **Data:**
  - 128 of 3,138 race ratings rest on fewer than 5 paired laps, and 208 on fewer than 10.
  - Example: 2020_14 HAM rating −6.617 s from **1 paired lap**, reported CI [−6.89, −6.34]. Likewise BOT +6.617 s with CI [5.62, 7.61], and 2018_13 VET −5.40 s with CI [−5.64, −5.15].
  - On 350 rows the clean-lap n exceeds the paired-lap n by more than 10 laps.
- **What it breaks:** The assistant would quote a precise, wrong "±" on the very ratings that are noise. AI-01's rule "the interval kind is never relabelled" cannot be met, because the interval kind is wrong at the source.

### C2. Ratings published for races where every residual is NULL, with no reason column (P0)
- **Evidence:** `mart_race_driver_summary` has `rating_s` for every driver in 2018_1, 2018_2 and 2018_3, and also in 2025_6 (Miami, quarantined). In those races `driver_skill_residual_s` is NULL on 100% of laps.
  - 2018_1/2 have `base_track_pace_s` and `track_temp_c` NULL on every lap. This matches the known gap at `ingestion/src/bronze_checks.py:199-209`.
  - 2018_3 and 2025_6 are tyre-QA quarantined (`staging/schema.yml:569-570`).
  - Result: `ci_low`/`ci_high` are NULL on 66 of 368 rows in 2018 and 21 of 438 in 2025. In 2018_3 and 2025_6, `n_clean_laps`, `constructor_rank` and all component means are also NULL.
  - Example: 2025_6 HAD −1.206 s vs LAW, with no n, no CI and no flag.
- **Silent absences:** 2021_16 (Turkey) is in `fct_lap_residuals` but has no rows in either rating mart. 2021_12 (Spa) is absent from every lap mart, although README.md:23 counts "173 races".
- **What it breaks:** The assistant cannot tell "unavailable" from "fine". Nothing in the mart says why the CI is missing, and a missing race just looks like no race.

### C3. Dirty-air "unavailable" becomes 0.0 s in lap and race means (P0 for anything dirty-air)
- **Evidence:**
  - `int_lap_residual_decomposed.sql:285-290` sets `dirty_air_tax_s` and `dirty_air_tax_se_s` to `0.0` wherever `int_dirty_air_tax_component` has no row. The comment says the fill "never reaches driver_skill_residual_s".
  - But it does reach the aggregates. 6,460 `ml_eligible` laps have `pace_delta_s IS NULL` and `dirty_air_tax_s = 0`, including every lap of 2018_1 and 2018_2.
- **Data:** `mart_race_driver_summary.mean_dirty_air_tax_s = 0.0` for all 16 drivers in 2018_1 and all 18 in 2018_2. `mart_driver_season_summary` and the 2018 rows of `mart_metric_benchmark` average those zeros in.
- **What it breaks:** It breaks the project's own rule 7 ("unavailable is shown as '—' with a reason, never 0"; `_wake-calibration/status/BUILD-ORDER.md`). The assistant would say "no dirty-air cost at Melbourne 2018", which is false: it was never measured.

### C4. Dirty-air SE is a hardcoded 15%, and the method has no validation verdict (P1)
- **Evidence:**
  - `int_dirty_air_tax_component.sql:354-355` sets `dirty_air_tax_se_s = ABS(theta_air × share × 0.15)`. All 161,040 rows satisfy SE/tax = 0.15 exactly.
  - The schema says "Standard error of the tax estimate via propagation" (`intermediate/schema.yml:1577-1578`). That is false.
  - `tax_calibration_confidence` is one constant (0.99633) on every row. The schema itself says per-season θ "straddles zero" in 2021 and 2024 (`intermediate/schema.yml:1589-1591`).
  - θ = 0.331 s/lap is a declared constant fitted outside dbt (`dbt_project.yml:313-327`; procedure in `_roadmap/_fixes/THETA_AIR_LABEL_VALUE_PROCEDURE.md`). The `data/fits/*.parquet` inputs are not in git (only `.gitkeep` is tracked).
- **What it breaks:** Every dirty-air number and its interval is a modelling convention, not a validated measurement (see the next section). An assistant quoting "±" on dirty air is quoting the 0.15 constant.

### C5. No provenance or version column on any mart (P1)
- **Evidence:** I scanned the columns of all 19 marts. None carries `model_version`, `label_version`, a `theta_air` value or a build timestamp.
  - `tax_calibration_confidence` and `theta_air` live only in intermediates.
  - The label version (v16, sealed by CO-33 on 2026-10-26) is not recorded anywhere a query can see.
- **What it breaks:** AI-01's card field `model_version` "where it applies" cannot be filled from the transform layer. Nothing ties an answer to the build it came from.

### C6. The AI-intended marts are not exported, and app data is pre-seal (P1)
- **Evidence:**
  - `scripts/export_app_data.py:51-98` (TABLES) omits `mart_race_driver_summary`, `mart_driver_season_summary`, `mart_metric_benchmark`, all four `fct_driver_isolation_*` and `fct_power_law_training`.
  - `app/public/data/_manifest.json` is `generatedAt 2026-10-16`, with stats `dbt_models: 93`. That is before CO-30, CO-31 and CO-33 (the v16 seal, 2026-10-26).
  - Committed export `app/public/data/marts/mart_degradation_history_envelope.parquet` has 8,075 rows and a mean p50 deg of 0.1928 s. The warehouse has 8,115 rows and 0.1888 s. So it is stale.
  - `mart_corner_skill_driver` matches.
  - I could not check the 36 tables served from the CDN.
- **What it breaks:** The browser-side assistant (AI-04/AI-09 query in-browser DuckDB) would read pre-v16 numbers, or would not find the rating marts at all.

### C7. Season mart drops the uncertainty it has upstream (P2)
- **Evidence:** `mart_driver_season_summary.sql:50-57` keeps the CI but drops `era_adjusted_rating_se_s`, `rating_confidence` (min 0.167), `total_clean_laps_n`, `low_anchor_sample_flag` and `bridge_driver_anchor_flag` from `int_era_normalized_driver_rating`.
- **Rank and percentile:** These are computed with no uncertainty. Ranks 2-5 in 2024 differ by 0.035 s, inside CIs about 0.42 s wide (VER, ALB, ALO, NOR, HUL sample).
- **What it breaks:** The assistant would read `teammate_gap_rank` as an exact ordering.

### C8. `dim_events` is a 6-row hand-typed placeholder, exported to the app (P2)
- **Evidence:** `seeds/raw_dim_events.csv` holds 6 rows, all from 2021. `dim_events.sql:11` says "your brand-new dim_events.csv". It is exported (`export_app_data.py:57`, manifest `total_events: 6`) but no app code or dbt model reads it.
- **Content check:** These come from my own F1 knowledge; I did not verify them against data. "Verstappen mechanical DNF" at Monza 2021 was the VER/HAM collision. At Silverstone 2021 Hamilton got a 10 s time penalty, not a grid penalty.
- **Docs:** Eight of its 10 columns are undocumented.
- **What it breaks:** If the assistant can see it, it would quote fabricated events.

### C9. Test suite: range tests on the AI marts are vacuous, and one threshold was loosened after seeing data (P2)
- **Vacuous tests:** On the AI marts: `n_clean_laps >= 0`, `laps_completed >= 0`, `n_drivers >= 1`, `n_races >= 1` and `sample_size >= 1` (manifest).
- **Missing tests:** None checks:
  - that `ci_low <= rating_s <= ci_high`
  - a minimum paired-lap n
  - CI coverage for each race
  - that a mean is not zero-filled
  - that a race in `fct_lap_residuals` also appears in the rating mart
- **Loosened threshold:** `assert_driver_skill_residual_reasonable.sql:33` was raised 15→16→17→19 s across WI-01 and dev completion, each time after an observed lap crossed it (`git log -L`). The header (lines 2, 6) still says ±16 s. The current max is 13.82 s, so the test is now loose.
- **Weaker in CI:** Five singular tests change threshold or severity when the target is `ci`:
  - `assert_prior_season_labels_frozen` is warn-only on CI.
  - `assert_field_base_component_neutral` and `assert_isolation_sign_convention` use smaller row thresholds there. So does `assert_isolation_thin_cell_tax_matches_component`.
  - `assert_hardness_rank_2018_from_lap_name` is skipped on CI.
  - CI runs a 3-race fixture, so the real-data invariants run only locally (AI-13 is open).
- **Latest season not frozen:** The label-freeze test excludes the latest season (2025) by design, so 2025 labels can move without a failure.
- **Vacuity audit:** TR-019 (audit every singular test for vacuity) is still open in `_roadmap/_status/ISSUES.md`. That register was last updated 2026-07-06, so it is stale. I did not re-run the corruption audit.
- **Severity:** Two seed tests (`fit_date` within 365 days) are warn-only. No models are disabled.

### C10. External fit drifted from the mart it feeds (P2)
- **Evidence:** `data/fits/degradation_isotonic.parquet` is dated 2026-09-24 and has 8,074 rows. It predates WI-01, CO-09, CO-15 and CO-31.
  - The envelope now has 8,115 cells, and 44 have NULL `*_mono_s`. Those mono columns drive the app headline.
  - Mean |mono − raw p50| = 0.34 s, p95 1.35 s.
- **Fallback constants:** `mart_degradation_history_envelope.sql:151-153` hardcodes 1.0 / 8.0 / 0.010 as fallbacks, used on 2,261 rows.
- **Thin cells:** 709 cells have `n_observations < 5`, yet still report p10 and p90. The minimum n is 3 (filter at line 161).
- **Stale header:** Line 38 says post2022 = 2022-2024, but 2025 is included.

### C11. Documentation and count drift (P3)
- **Counts:** README.md:23/63/93/146/223 say 94 models / 1,320 tests. The build has 97 models, 1,373 data tests and 2 unit tests. The app manifest says 93.
- **Undocumented columns:**

| Mart | Undocumented columns |
|---|---|
| `fct_lap_residuals` | 30 of 49 |
| `fct_ghost_car_pace` | 18 of 38 |
| `fct_power_law_training` | 14 of 25 |
| `fct_ghost_race_finish` | 9 of 26 |
| `dim_events` | 8 of 10 |
| `mart_degradation_history_envelope` | 6 (including the mono columns) |
| `fct_stint_features` | 1 |

- **Undocumented flags:** In `fct_lap_residuals` these include `is_safety_car_lap`, `is_red_flag_lap`, `correction_class`, `total_explained_s`, `track_unexplained_s` and the constructor CI columns. Those are exactly what an assistant needs to read flags.
- **Leftover tables:** The scratch copy of dev has tables with no model (`circuit_reference_pending`, `int_driver_isolation_age_curve`, `int_lap_anomaly_flags_option_a` and `_option_b`). `seeds/_pending/dim_drivers_tactical_pending.csv` is still loaded as a table, although "tactical" was cancelled on 2026-09-28.

### C12. Stale roadmap pointers (P3, but they mislead whoever picks up AI work)
- **AI board:** `_roadmap/_ai-integration/status/build-log.json:5` has pointer `CO-32` (micro-sector dirty air). Its sources (line 983-984) point at `_roadmap/_dirty-air/`, which no longer exists: the plan was archived 2026-10-27 after DA-03 failed its registered checks. The board's own "Next" line runs `python3 _roadmap/_dirty-air/status/board.py`.
- **Archived models still built:** `int_microsector_crossings`, `int_microsector_proximity` and `int_microsector_corner_class` are still built (3 tables). No mart, export or app code references them (grep), so W2/W11 hold for now.
- **Fixes board:** `--check` fails ("BUILD-ORDER.md generated task list is stale").

### Other notes (not cracks for quoting)
- **Views need the repo:** All 18 views (every `stg_*`) read bronze through relative paths (`../data/bronze/...`). Opened from anywhere but `transform/`, they fail. An assistant must never query views; only tables are safe.
- **2026 data:** `holdout_season: 2026` (`dbt_project.yml:153-158`) and 2026 is not ingested (fixes W19, WC-09 SPEC). The marts end at 2025, so no 2026 row can leak in. The honesty policy has `NO_2026_DATA`. Fine, but `era_boundary` has no 2026 era, and θ was fitted on 2018-2025, so a 2026 answer has nothing to stand on.
- **Known data gaps, and where they show up:**
  - **2018_1/2 (no telemetry):** NULL residuals, a 0.0 dirty-air fill (C3), and a rating with no CI (C2).
  - **2018_3, 2025_6 (quarantined races):** All tyre-derived columns NULL, and a rating with no CI (C2).
  - **2022_7 / 2022_11 (Monaco / Austria):** These are the TyreLife exceptions. They are 2022, not 2018 (`bronze_checks.py:225-234`). About 10-20% NULLs, with nothing in the mart to show it.
  - **2025 Miami qualifying:** The empty Jolpica Q1 does not surface. The qualifying chain is lap-based: `int_qualifying_decomposed` has 99 rows for 2025_6, and `quali_push_laps_n` is non-null there.
- **Finish confidence:** GATE-1 (ghost finish confidence overconfident, calibration slope 0.717) has no resolution I could find. `fct_ghost_race_finish.finish_pos_se` / `p_beats_next` should be treated as uncalibrated.
- **Honesty policy gaps:** `app/src/assistant/honesty/policy.json` (updated 2026-10-22) has no rule for dirty-air values, quarantined or no-telemetry races, or thin teammate pairs.

---

## Wake-calibration / dirty-air status, and what depends on it

**State** (per `board.py`, log updated 2026-10-30):

| Item | State |
|---|---|
| WC-01 | LANDED |
| WC-02 | CLOSED |
| WC-03, WC-04 | CLOSED with **no verdict**: G3.4 digest mismatch, nothing fitted or scored (DD-WC15). Ruling: **"the flat penalty stays"**. |
| WC-10e (pointer) | BUILDING, blocked by DD-WC23. Amendment B2 is needed because NaN `tyre_life` blocks the fit. W15 says the pre-fix SG1-SG7 results are superseded. W14 says the real mode has no gate check. |
| WC-10f/g/h/j | BLOCKED (WC-10h is the owner gate DD-WC21; WC-10j is DD-WC19) |
| WC-05 (labels), WC-06 (app) | SPEC, waiting on WC-10i |
| DA-03 | Archived after a registered FAIL; none of its numbers may be used |

Nothing from WC-10 or `_artifacts` feeds dbt (grep of models, macros and `dbt_project.yml`).

**What is in the marts today** is the flat lap-grain label: `dirty_air_tax_s = clamp(0.331 × previous-lap dirty-air share, 0, 5)`.
- θ = `theta_air_label_value: 0.331` (W40, 2026-09-27; F2 fit 0.3313 [0.293, 0.370], n = 138,679, fitted outside dbt).
- It was sealed into label v16 (CO-33).
- The method that was meant to validate it or replace it (WC-03/04) produced no verdict. Its successor (WC-10) is still in discovery and has fitted nothing.

**Marts whose numbers move with θ or the flat method**, from the SQL and schema text:

| Mart / column | Dependence |
|---|---|
| `fct_lap_residuals`: `dirty_air_tax_s`, `dirty_air_tax_se_s`, `cumulative_dirty_air_tax_race_s` | direct |
| `fct_lap_residuals.driver_skill_residual_s`, and so `mart_metric_benchmark` (driver_skill and dirty_air rows) | the residual is net of the tax |
| `mart_race_driver_summary` / `mart_driver_season_summary`: `mean_dirty_air_tax_s`; the race-mart **CI** (SE of the residual) | direct / indirect |
| `fct_cliff_prediction_features` targets (`next_*_jump_s`) | "theta sits inside every dirty-air lap's label" (`assert_prior_season_labels_frozen.sql`) |
| `fct_ghost_car_pace.dirty_air_tax_s`, and so `fct_ghost_race_finish` | direct |
| `fct_driver_isolation_*` | the thin-cell tax is priced as θ × share (CO-30, `int_driver_isolation_lap_panel.sql:119-153`) |
| `fct_driver_skill_features` | built on the residual |
| `mart_degradation_history_envelope.dirty_air_deg_mult` | a separate dirty-air multiplier (1.0 or 1.15) from the external isotonic fit; not θ, and also unvalidated |

**Not dependent:**
- `rating_s` in both rating marts: the paired raw lap-time median, and the era rating built on it.
- `mart_corner_skill_driver`.
- `fct_telemetry_deltas`.
- `fct_stint_features` (except where it reads residuals; not traced in full).

**Rule for the AI:** Any dirty-air number may be quoted only as "modelled, flat 0.331 s/lap × share, method not validated". Never quote it as measured, never quote its ± as an estimate, and never read a 0.0 as "clean air" unless the lap was actually measured.

---

## Mart-by-mart quotability

Row counts and keys come from the scratch warehouse. "Uncertainty" means an interval, SE or n column is present.

| Mart | Grain / key (unique test passes) | Rows | Uncertainty / provenance | Exported / consumer | Verdict |
|---|---|---:|---|---|---|
| `mart_race_driver_summary` | driver × race | 3,138 (171 races) | CI is for the wrong statistic; no paired n; no version | not exported, no consumer | **Do not quote** the rating or CI until C1 and C2 are fixed. `positions_gained` and `has_dnf` are quotable. |
| `mart_driver_season_summary` | driver × season | 173 | CI present; SE, confidence and n laps dropped; no version | not exported, no consumer | **Quote with caveat**: rating with CI and n_races; rank only as "teammate-gap rank" with ties inside the CI; not the dirty-air mean |
| `mart_metric_benchmark` | metric × season | 48 | `sample_size` (laps) | not exported, no consumer | **Quote with caveat**: lap_time and fuel rows fine; the dirty_air rows (p50 = 0, include zero-fill) and driver_skill rows depend on θ |
| `fct_lap_residuals` | lap_id | 161,040 | constructor CI; dirty-air SE (fake); 30 columns undocumented | exported, 17 app files | **Quote with caveat**: lap time and flags; components only as modelled; dirty_air_tax / se **do not quote** as measured |
| `fct_driver_isolation_race` | driver × race | 3,102 | SE, confidence, trust_label; pure skill suppressed on 86% | not exported, no consumer | **Quote with caveat**: `relative_pace_*` only when trust_label is `solid`/`indicative`; **do not quote** `pure_skill_*` (policy VALIDATION_GRADE_BELOW_PASS) |
| `fct_driver_isolation_stint` / `_lap` / `_pair_lap` | stint-phase / lap / lap × peer | 26,325 / 127,476 / 557,814 | as above | not exported; stint has no consumer | Same as race; lap/pair grain: **do not quote** (single-lap noise) |
| `mart_corner_skill_driver` | driver × season | 161 | SE and cells_n for every skill | exported (matches the warehouse) | **Safe to quote** with SE; teammate-relative, equal-car |
| `fct_telemetry_deltas` | teammate pair × lap × corner | 1,623,427 (169 races) | none; 13-55% NULL deltas (correct, not 0) | exported, no app consumer | **Quote with caveat**: one-lap raw deltas, no n; aggregate before quoting |
| `mart_degradation_history_envelope` | circuit × era × compound × lap_in_stint | 8,115 | n_observations, p10/p90 | exported (**stale**, 8,075 rows) | **Quote with caveat**: only cells with n ≥ 10; the mono columns come from a stale fit (44 NULL); the multipliers are hardcoded fallbacks |
| `fct_stint_features` | stint | 8,945 | `end_cause_confidence`, censoring flags; 82-92% NULL on cut / cliff columns | exported | **Quote with caveat**: stint length and compound are fine; cliff and slope columns are sparse |
| `fct_cliff_prediction_features` | lap | 161,040 | none (ML features and targets) | exported, ML | **Do not quote**: it is a training frame, its targets depend on θ, and the ML layer is parked (PK1) |
| `fct_power_law_training` | race × compound rank | 390 | n_laps, n_stints, r2_within; 14 columns undocumented | ML only | **Do not quote** (training frame) |
| `fct_driver_skill_features` | driver × race | 3,312 | none; no not_null tests | exported, 7 app files | **Do not quote** (ML features, residual-based) |
| `fct_ghost_car_pace` | ego × host × race × lap | 1,384,558 | constructor SE, recombination_confidence | exported, partitioned | **Quote with caveat**: counterfactual, always labelled "what-if", includes the θ tax |
| `fct_ghost_race_finish` | host × ego × race | 30,344 | finish_pos_se, p_beats_next | exported | **Do not quote** the probabilities or SE (GATE-1 uncalibrated); the projected position only as "what-if" |
| `dim_events` | event_id | 6 | none | exported, no consumer | **Do not quote** (placeholder or wrong content) |
| `dim_circuits` / `dim_drivers` / `dim_constructors` / `dim_compounds_season` | reference | 44 / 43 / 19 / 499 | n/a | exported | **Safe** (lookup only) |

---

## Minimum transform-side work before the AI layer is OK

1. **Fix the race-rating interval and n** (C1). Expose `paired_lap_count`. Build the CI from the paired differences themselves (a bootstrap of the median, or the SE of the paired mean if the rating moves to the mean). Add `rating_trust_label` (for example, suppress below 5 paired laps and mark thin below 10). Add tests that `ci_low <= rating_s <= ci_high` and that n is at least the floor. **0.5-1 d.**
2. **Add a coverage and reason table, and reason columns** (C2, gaps). Create one `mart_race_coverage` (race_id: has_telemetry, tyre_qa_status, has_residual, has_rating, n_rated_drivers, reason code). Add `rating_unavailable_reason` / `ci_unavailable_reason` to both rating marts. Cover 2018_1/2/3, 2021_12, 2021_16, 2022_7/11 and 2025_6. Add a test that every `fct_lap_residuals` race appears in the rating mart or has a reason. **0.5-1 d.**
3. **Stop the dirty-air zero-fill reaching aggregates** (C3). Keep the 0.0 fill only inside the additive identity. Add `is_dirty_air_measured` to `fct_lap_residuals`. Compute `mean_dirty_air_tax_s` (both summary marts) and the benchmark dirty_air rows over measured laps only, with NULL plus a reason when there are none. Add a test that no race-level mean equals exactly 0 when it has no measured laps. **0.5 d.**
4. **Be honest about the dirty-air uncertainty and method** (C4). Either drop `dirty_air_tax_se_s` from the marts, or rename it and redocument it as a "convention: 15% of the point estimate". Better: derive it from the θ interval [0.293, 0.370]. Add a `dirty_air_method` column such as `flat_theta_0.331_v16_unvalidated`. Add a dirty-air rule to `policy.json` (strictly an app file, but it depends on this). **0.5 d.**
5. **Add provenance** (C5). Add `label_version`, `theta_air_label_value` and `dbt_invocation_id`/`built_at` to every mart the AI may read. Alternatively, publish a single `mart_build_provenance` row that the export copies into the manifest. **0.5 d.**
6. **Carry the season-mart uncertainty** (C7). Add SE, `rating_confidence`, `total_clean_laps_n` and the anchor flags. Make rank ties CI-aware, or document the rank as a point ordering. **0.25 d.**
7. **Export and freshness** (C6). Add the three AI marts (plus `fct_driver_isolation_race` if the assistant will use it) to `export_app_data.py`. Re-export after the v16 seal. Add a check comparing exported row counts and fingerprints with the warehouse, so a stale CDN fails the run. **0.5-1 d.**
8. **`dim_events`** (C8). Remove it from the export and the warehouse, or replace it with a real events source. **0.25 d.**
9. **Tighten the tests** (C9). Replace the vacuous range tests on the AI marts. Put the residual bound back to a principled value and fix the header text. Complete the TR-019 vacuity audit for at least the tests guarding the AI marts. AI-13: a real-data CI job, or thresholds that hold at fixture scale. **1-2 d.**
10. **Refresh the isotonic fit** (C10), or NULL the mono columns where the fit is missing. Hide envelope cells with n < 10 from the AI. Fix the era comment. **0.5 d.**
11. **Docs and board hygiene** (C11, C12). Document the undocumented columns in `fct_lap_residuals`, `fct_ghost_*`, `fct_power_law_training` and the envelope. Fix the README counts (or derive them through `scripts/docs_facts.py`). Repoint the AI board off CO-32 and `_roadmap/_dirty-air`. Run `--write-order` on the fixes board. Drop the tables with no model. **0.5 d.**

**Total: about 5-8 working days.** Items 1-5 and 7 are the hard gate, about 3-5 days. None of this unblocks the assistant on its own: PK1 (the owner parked the ML and assistant layers on 2026-10-24) and AI-01 (fact cards) still gate it.

---

## What I did not verify
- **CDN data:** The 36 tables served from the CDN. I compared only the 3 parquet files committed under `app/public/data/`.
- **`mart_degradation_predictions`:** Written by ML and absent from the scratch build, so nothing about its band or `is_in_envelope`.
- **Singular tests:** Whether each of the 130 is non-vacuous (TR-019). I spot-read 4.
- **Math behind other intervals:** I did not check the statistics behind `int_era_normalized_driver_rating`'s CI, the isolation SEs or confidence values, the ghost-car SEs, or `int_pit_strategy_value`.
- **Scratch copy vs dev:** Whether the scratch copy matches `data/dev.duckdb`. I assumed it does, since it carries the same leftover tables.
- **Gate status:** Whether GATE-1 was resolved somewhere outside `ISSUES.md`, `PROJECT_PLAN.md` and the boards I read.
- **Event facts:** The real-world accuracy of the `dim_events` rows beyond the two obvious errors.
- **CI fixture build:** Whether it passes.
