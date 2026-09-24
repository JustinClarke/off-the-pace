# Forensic audit of the transform layer — report

> **Round 2 (2026-09-24)** adds F22–F37 in [`transform_forensic_audit_report_round2.md`](transform_forensic_audit_report_round2.md)
> and settles several items in §3's Assumed list below. Current status of every finding from both rounds:
> `.venv/bin/python _improvements/reference/transform_forensic_audit_artefacts/verify_findings.py`.

**Run:** 2026-09-24, against `data/dev.duckdb` (built 2026-09-22 23:23, the v14 substrate; every probe
`read_only=True`). `data/ci.duckdb` was touched only by `make lint-oracle-check`. Charter:
`_improvements/reference/transform_forensic_audit.md`. Phases B–G run in order. Phase A was supplied
settled by the orchestrator and is folded in as finding **F4**.

**Deviations from the charter's permitted commands, both made to stay read-only:**
- `make dbt-test` was run as the identical `dbt test`, but against a byte-copy of the warehouse
  (`scratchpad/.../dbcopy/dev.duckdb`, scratch `profiles.yml`), with `--target-path` and `--log-path` in
  the scratchpad. That kept `transform/target/`, which the Python audits read, untouched.
- `python -m ml.src.features --check` **writes `ml/models/encoders.json`** (`features.py:705`,
  `persist_encoders=True`). It was replicated line-for-line with `persist_encoders=False`
  (`phaseB_features_check_nowrite.py`). The recomputed encoders are byte-identical to the shipped file.

**Contract width used for §5.** `ml/src/schema.py` `FEATURE_COLUMNS` has **39** members (32 plus the seven
`qualifying` columns). `PER_TARGET_FEATURE_MASK` gives `cliff_classifier` 39 and the other four families
32. Phase A's open question 3 is answered: the model card's `feature_count: 32` is `any_log["n_features"]`
(`card.py:257`), the width of whichever training log iterates first, so it is a degradation model's width.
The card's `per_model` block correctly says 39 for the classifier.

All scripts, CSVs and logs are in `transform_forensic_audit_artefacts/` (index at the end).

---

## 1. Verdict

**Partially trustworthy, and not safe to retrain on as-is.** Identity, grain, units and pit/points
reconciliation hold up against independent oracles. The label and the feature prior do not:

- **F1.** 9.5% of labelled training rows carry a fabricated pace delta of 0 s inside their 5-lap label
  window. The median error on each affected lap is 4.2 s.
- **F2.** Ten contract features are compound parameters fitted on the very race they describe. The shipped
  model cannot have them for any new race, and p50 pinball is 6.8% worse on the same rows when it doesn't.
- **F3.** The shipped browser scorer cannot read the v14 manifest.

§4.2 is not a leak (Phase A).

---

## 2. Findings, ranked (severity × blast radius)

| # | Sev | Where | What | Verdict | A published number moves? |
| :-- | :-- | :-- | :-- | :-- | :-- |
| F1 | **Critical** | `int_lap_residual_decomposed.sql:294,309` | `pace_delta_s` is COALESCEd to 0 when the field curve is missing. The label is fabricated in 9.48% of labelled rows | Definitely wrong | **Yes**, every trio and cliff headline, all versions |
| F2 | **High** | `fit_compound_cliff.py:230` → `dim_compounds_season` → mart `:578-582`, `int_compound_cliff_predicted.sql:92-96` | Compound "prior" parameters are fitted on the scored race itself (2018–2024) and carried forward for 2025. That is 10 features plus the eligibility gate | Definitely wrong (mechanism); magnitude **measured** | **Yes.** v13 and earlier `cv_final_fold` headlines were scored with in-race values (optimistic vs serving). v14's 2025 fold pays the train/serve skew instead |
| F3 | **High** (shipped) | `app/src/ml/featureVector.ts:57-58,67`, `infer.ts:101-105` | Browser inference reads `manifest.input.n_features`/`feature_order`, which v14's manifest no longer has. It throws `TypeError`, and would feed one width to 32- and 39-wide models anyway | Definitely wrong | No metric; the Degradation Simulator's model output and `verifyParity` are broken |
| F4 | **High** (process) | `ml/src/features.py:54-57` (+ card.py, model_card.yml, README, test_predict) | Phase A: the holdout resolver can never resolve a populated season; prose is stale; the test is tautological; there is no untouched season left, and 02c v14 has already spent 2025 | Definitely wrong (mechanism) | No (Phase A); forward risk to every future gate |
| F5 | **Medium** | `int_dirty_air_tax_component.sql:195-206` | `theta_air` is one global slope over all seasons. The 2025 ingest moved it 0.1310 → 0.1521 and relabelled 2018–2024, which falsifies "v14 comparable to v13 at fixed target" (`schema.py:479`) | Definitely wrong (claim) | v13↔v14 comparisons are not fixed-target (small: mean \|Δ\| 0.02 s) |
| F6 | **Medium** | `int_lap_fuel_state.sql:20,36-42,58,73-77` | `fuel_mass_kg` counts laps from the realised last *valid* lap, so it reaches forward to how the race ended (12/172 races). The declared exemption's premise is false | Definitely wrong (mechanism); ML magnitude unmeasured | Probably small |
| F7 | **Medium** | `int_compound_cliff_predicted.sql:120-156,194-210`; mart `:509-514` | 2025 cells missing from the seed get fabricated cliff features (999/0) on 1,409 rows (7%), and the same default enters their label | Definitely wrong | Yes, the v14 2025 fold contains these rows (see F2 decomposition) |
| F8 | **Medium** | `race_to_track.csv` (no `2018_14`); INNER JOINs `int_lap_fuel_state.sql:62`, `int_compound_cliff_predicted.sql:90` | The 2018 Italian GP disappears silently (833 valid laps). This is the charter §3 "2018 cause" | Definitely wrong | Marginal (0.5% of laps) |
| F9 | Medium-Low | `int_lap_anomaly_flags.sql:235-243`; mart `:912-916` | `is_training_eligible` keeps residual spikes past the in-race seed onset and drops them otherwise. It also conditions on residual(t), a term of the label | Probably wrong | Unmeasured |
| F10 | Low-Med | `int_lap_residual_decomposed_qualifying.sql:95-104,144-145,167-171`; exemption `intermediate/schema.yml:1910-1925` | `quali_skill_session_avg_s` subtracts race-day track evolution and in-race seed wear. The exemption says no race-scoped reads | Probably wrong | Unmeasured (cliff only) |
| F11 | Low-Med (guards) | `features.py:705`; stale baselines; `assert_stint_geometry_2018_compound_code_null` | The audit CLI writes a shipped artefact. Both drift gates are red on stale baselines. One dbt test fails (2025 compound_code) | Definitely | No |
| F12 | Low | `int_lap_air_state.sql:178-195`, `int_lap_proximity.sql:406-426` | 2018 laps with no car telemetry (~9.4% of 2018) get fabricated "free air" | Definitely wrong (default) | Unmeasured |
| F13 | Low | `seeds/raw_dim_events.csv`, no column type in `dbt_project.yml` | `race_id` loads as INTEGER (`202110`) and matches nothing. §4.6's feared weight bias does not exist | Definitely wrong | No |
| F14 | Low | `stg_results.sql:52-61` (bronze origin) | 3 DSQs with a numeric `ClassifiedPosition` read as classified finishers | Definitely wrong | No |
| F15 | Low | `app/.../counterfactual-championship/queries.ts:34-38,87-88` | "Actual Pts" ≠ official points: no fastest lap, no sprints, counted races only | Probably wrong (label) | App only |
| F16 | Low | `mart_corner_skill_driver.sql:234`; `app/.../synthetic-teammate/queries.ts:28-29` | `ANY_VALUE` picks an arbitrary constructor or teammate for driver-seasons with more than one | Definitely wrong | App only |
| F17 | Low | `dim_constructors.sql:42-44`; `dim_drivers.sql:25-26`; `fct_driver_skill_features.sql:153-154` | §4.4/§4.5 confirmed but consumed by nothing that computes. "Aero" and "power" pace indices are the same column | Definitely wrong | No |
| F18 | Low | bronze `2020_1` | Lap numbering is offset: race control shows the chequered flag on lap 71, stg max is 68, and Jolpica pit laps are +5 | Definitely wrong (bronze) | Marginal |
| F19 | Low | `src_formula1.yml:16` (§4.1) | `session_type` is declared but absent. Separation is by glob depth only | Definitely wrong (contract); latent | No |
| F20 | Low | doc drift (list in F20) | Mart header, "42nd feature", "not yet in contract" ×2, card summary, features.py docstring | Definitely wrong (text) | No |
| F21 | Low-Med | `data/fits/*.parquet` (window 2018_to_2024); `check_freshness.py:27-30` | The offline fits were never refitted for 2025. The ghost standings and simulator history silently stop at 2024, and the freshness guard cannot see it | Definitely wrong | App only |

---

### F1 — The label is fabricated wherever the field-pace curve has no row

- **Severity:** Critical.
- **file:line:** `transform/models/intermediate/int_lap_residual_decomposed.sql:294` (`lap_time_s - COALESCE(base_track_pace_s, lap_time_s) AS pace_delta_s`) and `:309` (the same expression inside `driver_skill_residual_s`). Root cause of the missing rows: `int_field_pace_curve.sql:56-60`.
- **Column / transformation:** `pace_delta_s` → `driver_skill_residual_s` → `next_5_lap_cumulative_jump_s`, `laps_until_cliff_class` (`fct_cliff_prediction_features.sql:609-709`).
- **Intended grain:** one row per valid race lap. The field curve is (race, lap_number).
- **Observed behaviour:**
  - 14,892 of 160,207 spine laps (9.3%) have `base_track_pace_s` NULL. All 14,892 get `pace_delta_s = 0`, so the residual becomes minus the sum of the components.
  - Every one of 171 races has some. 14,065 have no curve row at all; 827 have a row with a NULL value.
  - Where they fall: 2,358 in laps 1–3, 4,601 in a race's last 3 laps, and 7,933 mid-race.
  - Three causes, all in the eligibility CTE. It drops `valid_lap_in_stint = 1` and the last two valid laps of every stint, including the final stint, which has no in-lap (`:56-57`). It also drops every lap over 107% of the race's fastest lap (`:59`), which blanks whole mixed-condition races with `rainfall_flag` FALSE: 2025_1 100%, 2025_12 80%, 2024_9 76%, 2019_11 75%, 2022_17 68%.
  - The injected error equals −(lap_time − true base). Against the nearest non-null base in the same race it is a **median 4.22 s, mean 6.35 s, p90 14.9 s**.
  - **9,052 of 95,513 labelled training rows (9.48%)** have such a lap in t..t+5, 1,289 of them in the 2025 eval fold. Those rows look like a different population: label mean **+1.88 s vs −0.70 s**, SD **7.58 vs 3.52**, cliff-within-5-laps share **35.1% vs 18.6%**.
  - For the cliff label, which scans to stint end, at least 23,136 of 132,265 labelled rows (17.5%) have one within the next five laps.
- **Reproducible query:** `phaseD_base_null_label.py`, `phaseD_base_null_size.py`. Core:
  `select count(*) filter (where base_track_pace_s is null and pace_delta_s = 0) from int_lap_residual_decomposed` → 14,892.
- **Why it is wrong:** 0 s is not a measurement of the lap's pace relative to the field. It is the 08q `theta_air` pattern: a default indistinguishable from a value, entering the label directly. The correct value is "unknown", so the residual, and every label window touching it, should be NULL.
- **Verdict:** Definitely wrong. The wrong value, the independent estimate of the right one, and the creating line are all shown.
- **Earliest point:** `int_field_pace_curve` eligibility (coverage), made harmful by the COALESCE at `:294`.
- **Isolated or systematic:** systematic. Every race's first and last laps, plus mixed-condition races.
- **ML impact:** four of five families' targets (trio and cliff). Stint life's target is synthesised from stint length and is unaffected. `anomaly_class` runs its MAD test on the same residual, so eligibility is probably perturbed too (Assumed, unmeasured). App surfaces built on `driver_skill_residual_s` (ghost car, lap waterfall, skill leaderboards) inherit the 9.3% of fabricated laps unless they filter them (Assumed).
- **Recommended fix:** drop the COALESCE, so NULL propagates and the LEAD sums and cliff scan see NULL. Then restore coverage deliberately: exclude only true in-laps (`is_pit_lap`), not the final stint's last two laps, and replace the race-wide 107% gate with a per-lap or rolling reference so mixed-condition races keep a curve. This changes the target, so it needs a version bump and fixed-target comparisons (the 08m discipline).
- **Test that would have caught it:** `assert_pace_delta_requires_field_base.sql` (§8 T1) and `assert_label_window_has_measured_base.sql` (T2).
- **How I could be wrong:**
  1. The 4.2 s error is measured against the *nearest* non-null base. In a mixed-condition race that neighbour may itself come from a different track state, so the true error could be smaller or larger. The fabrication itself does not depend on this.
  2. A downstream filter I did not trace might exclude these rows from training. It does not in `load_features`: the rows are `is_training_eligible` with non-null targets, and I counted them from that population.
  3. The authors may have intended "0 = at field pace" as a neutral fill. Even so, it enters a forward *difference*, where it is not neutral.

### F2 — The compound "prior" is fitted on the race it describes

- **Severity:** High.
- **file:line:**
  - `transform/tasks/coefficients/fit_compound_cliff.py:230`: `fit_group` filters `race_year == season` on the (track, compound) group.
  - `:363-370`: the cross-season fallback pools every season in the default window (`:414`, 2018–2024).
  - `survival.py:42-160`: onset is the age at which a >0.5 s spike over the trailing median persists 2 laps. Severity and wear are computed on the same stints.
  - Joins: `fct_cliff_prediction_features.sql:578-582` and `int_compound_cliff_predicted.sql:92-96`.
- **Columns:** `compound_wear_gradient`, `compound_cliff_onset_laps`, `compound_cliff_severity` (fitted), and the derived `expected_compound_pace_s`, `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff`. Those are 7 information-bearing features. `compound_grip_peak` and `compound_optimal_temp_low/high` are one constant per compound (verified: one distinct value each), so they carry nothing beyond `compound` except their NULL pattern (F7). Beyond the features, the same seed feeds `compound_component_s` (label) and `anomaly_class` (eligibility, F9).
- **Intended grain:** a pre-race prior per (venue, compound, season).
- **Observed behaviour:**
  - **All 171 (track_id, season) cells in the mart are exactly one race**, so a `cox_km_survival` cell is fitted on the one race it is then joined back onto, including the scored stint's own future laps.
  - Training-eligible rows by `fit_source`: 2018–2024 `cox_km_survival` 116,385 (97.1%); `cross_season_fallback` 2,827 (pooled 2018–2024, which crosses the season split for every fold but the last); class default 570. 2025: `carried_forward_2024` 18,248, class default 508, no cell 1,409.
  - The 2025 rows are the 2024 fit copied forward, a legitimate pre-race prior. So training rows and 2025 eval rows use different kinds of value.
- **Magnitude, measured** (`phaseC_seed_magnitude*.py/.json/.log`):
  - Setup: v13-shaped fold (production `_season_folds`; train ≤2023, eval 2024); production `evaluate._fit` with v14 best params. The seed-derived columns were rebuilt by re-running the **compiled production SQL** of `int_compound_cliff_predicted` against a counterfactual `dim_compounds_season` where 2024 := 2023, the 2025 rule. The rebuild reproduces the mart exactly on untouched 2023 (max |diff| 0.0), and 97% of 2024 rows change value under the lag.
  - A = eval on in-race values. B = the same model on lagged values; there is no refit, so no reseed noise. C = lagged in both train and eval, one refit. On rows with a lagged cell (86% for both targets), B is also reported separately.

    | Family | A | B | A−B | A−B, rows with a lagged cell | C | A−C |
    | :-- | --: | --: | --: | --: | --: | --: |
    | cliff macro-F1 ↑ | 0.3633 | 0.3443 | +0.0190 | +0.0024 | 0.3618 | +0.0015 |
    | p50 pinball ↓ | 0.9553 | 1.0201 | −0.0649 (+6.8%) | −0.0659 | 0.9617 | −0.0064 |
    | stint-life AFT NLL ↓ | 1.9963 | 2.0297 | −0.0334 | n/r | 2.0723 | −0.0761 |

    For p50 the model leans on the in-race *values*. Where a prior-season cell exists, swapping it in costs 6.9% pinball, which fits 08l's finding that 88–93% of the trio's skill echoes the seed arithmetic in the label: the label is built with the same in-race curve. For cliff, the values barely matter (+0.0024) and the loss comes from rows with no cell (F7). A pipeline trained honestly on lagged values (C) recovers p50 and cliff to within 0.7% and 0.0015 F1.
- **Why it is wrong:** 00c's standard is that a feature contemporaneous with the target, computed from the race being predicted, is leakage. 08l cleared the seed as "available at prediction time" (`work/08-foundations-repair.md:2244`) without examining the fit population. The fit population is the scored race. **That is new evidence against a settled line, not a re-litigation.** The "race-scoped spine" acceptance (`08…:133-160`) covers the label decomposition, not features.
- **Verdict:** Definitely wrong for the mechanism (171/171 single-race cells; the feature is a function of the race's later laps). Magnitude measured as above.
- **Earliest point:** the offline fitter. The seed CSV carries no fit population beyond `data_window`, so no dbt test or Python audit can see it (§6).
- **Isolated or systematic:** systematic, covering 97% of 2018–2024 training rows.
- **ML impact:**
  - v13 and earlier `cv_final_fold` headlines (eval 2024, in-race cells) are A-type: optimistic relative to what the model does on a race it has not seen.
  - v14's published 2025 fold is B-type: honest, but it carries the skew penalty.
  - The app's per-lap predictions for 2018–2024 are scored with in-race values.
  - v13→v14 headline comparisons are confounded by the A/B switch, on top of F5.
- **Recommended fix:** a ruling first (§10 WI-2). Either fit each season's cell on seasons strictly before it (point-in-time, like `int_sc_hazard_history`), or declare the same-race seed an accepted, spine-style exemption *and* make training consistent with serving. The measurement says the honest pipeline costs little (C ≈ A).
- **Test:** T3 (seed provenance must predate the row's season), plus a Python lineage test that `audit_forward_window` cannot provide.
- **How I could be wrong:**
  1. B mixes "lagged value" with "no cell" (14% of 2024 rows vs 7% of 2025). The cell-rows column separates them, and the p50 effect survives the split.
  2. C is one refit, so its small deltas are inside plausible reseed noise. The tree's recorded floors are p50 ~0.008–0.011 and cliff ~0.004–0.007, but those were measured under a different protocol and are not comparable. I did not run a floor.
  3. One could hold that a post-hoc analysis product may use same-race fits, as the spine does. The features are nonetheless served for new races, where the value cannot exist.

### F3 — The browser cannot score v14

- **Severity:** High for the shipped surface.
- **file:line:** `app/src/ml/featureVector.ts:57-58,67,70`, `app/src/ml/infer.ts:101-105`. Callers: `features/degradation-simulator/page.tsx:159`, `ml/verifyParity.ts:137`.
- **Observed behaviour:** the shipped `app/public/models/manifest.json` (v14, identical to `ml/models/manifest.json`) has `input` keys {`tensor_name`, `dtype`, `feature_union`, `per_model_feature_order`, `encoding`}. There is no `n_features` and no `feature_order`; per-model orders (32/32/32/39/32) live under `models[]`. Reproduced in plain Node (`phaseF_manifest_contract.mjs`, no app code executed): `buildFeatureVector` throws `TypeError: Cannot read properties of undefined (reading 'length')`. Even if repaired naively, `predictLaps` builds one matrix and feeds it to five models of two widths.
- **Why it is wrong:** v13 made the contract per-model (the note at `schema.py:403-410` predicted exactly this), and the export changed on 2026-09-21. `app/src/ml` was last changed 2026-08-24 (`cdf2523`) and never followed. `featureVector.test.ts:79-80` still asserts `n_features == 32` against the shipped manifest, so it would fail.
- **Verdict:** Definitely wrong.
- **Earliest point:** the app inference layer.
- **Isolated or systematic:** isolated to browser inference.
- **ML impact:** none on metrics. The simulator's model output shows an error, and `make app-parity` cannot pass.
- **Fix:** read `models[i].feature_order` and build one vector per model.
- **Test:** the existing `featureVector.test.ts` would have caught it if it ran on the v14 manifest. Add T7.
- **How I could be wrong:** production reads models from the CDN (`MODELS_BASE`). If the CDN still serves a pre-v13 manifest, prod works today and breaks on the next publish. I did not query the network (Assumed).

### F4 — Holdout mechanism and stale prose (Phase A, orchestrator-verified; restated with the charter's fields)

- **Severity:** High (process).
- **file:line:** `ml/src/features.py:54-57` returns `MAX(race_year)+1`, which is absent by construction. Stale prose:
  - `card.py:46-50` (`HOLDOUT_NOTE`), `:242` ("Trained on 2018–2024"), `:345` (E1), `:474`.
  - `ml/model_card.yml:7`, `:24-26`, `:963`, `:1049`.
  - `README.md:167`.
  - Tautological test: `ml/tests/test_predict.py:36`.
- **Observed behaviour:** v14 trains on 2018–2025 and `holdout_season` is 2026 with 0 rows (reproduced: `phaseB_features_check.log`). The published headline is honestly labelled `cv_final_fold` on 2025. Tuning predates the 2025 ingest.
- **New from this audit:**
  - `ml/artefacts/02c_corner_inputs_arms_v14.json` (2026-09-23) scored its admission gate with `n_train 81,562 / n_eval 13,951`. 13,951 is exactly 2025's labelled count (Phase D probe), so **2025 has already been spent once as a selection fold.**
  - The manifest's `dataset_fingerprint` `87e1d013…` equals the fingerprint this warehouse produces now, so v14 was trained on exactly this build.
  - `feature_count: 32` is resolved (see the header).
  - The card summary also still lists "powertrain … weather" feature families, which were dropped in Phase 9.
- **Verdict:** Definitely wrong (mechanism and text).
- **ML impact:** no published number moves. Every future gate on v14 folds consumes 2025.
- **Fix:** see WI-3.
- **Test:** T8.
- **How I could be wrong:** if the programme intends no untouched season, the resolver is merely misnamed. The prose would still be wrong.

### F5 — `theta_air` pools every season, so ingesting a season relabels the past

- **Severity:** Medium.
- **file:line:** `int_dirty_air_tax_component.sql:195-206`: one `COVAR_POP/VAR_POP` over the whole panel, no season key. It enters the label through `dirty_air_tax_s`.
- **Observed behaviour:** I re-ran the compiled production SQL with only the panel filtered (`phaseC_theta_air_2025.py`).
  - θ(all seasons, as built) = **0.152123**. The built table implies 0.152123.
  - θ(≤2024) = **0.131000**, which is the v13/08q value quoted at `schema.py:507-508`.
  - θ(≤2023) = 0.162842.
  - The 2025 ingest therefore changed the label on every 2018–2024 dirty-air lap: mean |Δ `next_5_lap_cumulative_jump_s`| 0.019–0.023 s per season, 16–19% of eligible rows move more than 50 ms (label SD 3.3–5.0 s; `phaseC_theta_label_move.py`, which ignores the drift term's own movement).
- **Why it is wrong:** `schema.py:479` says "v14 IS comparable to v13 head-to-head at fixed target … nothing about the label definition moves here." That is false. The eval fold's labels are also defined with a slope fitted partly on the eval fold.
- **Verdict:** Definitely wrong (the claim). The mechanism is a policy question.
- **ML impact:** small in magnitude, but it removes the fixed-target premise of v13↔v14 comparisons, and `_guard_target_change` cannot see it because it compares names.
- **Fix:** estimate on a declared window (seasons before the eval season), or freeze θ per version.
- **Test:** T9, a label-stability check across builds.
- **How I could be wrong:** if the label is meant to move with data, only the comparability claim is wrong. The shift estimate ignores clip bounds and drift re-estimation.

### F6 — `fuel_mass_kg` counts laps from the realised last valid lap

- **Severity:** Medium.
- **file:line:** `int_lap_fuel_state.sql:20` (`WHERE is_valid_lap`), `:36-42` (`MAX(lap_number)`), `:58`, `:73-77`. Exemption: `intermediate/schema.yml:233-241`.
- **Observed behaviour:** 12 of 172 races have MAX(valid lap) < MAX(lap) (`fuel_race_lap_count_gap.csv`):
  - 2022_16 (6 laps), 2023_3 (5), 2025_10 (4), 2019_2 (3), 2020_15 (3), and seven 1-lap cases.
  - 2022_18 (29 laps run, rain-shortened) prices fuel for 28 laps.
  - Every lap of those races carries fuel shifted by gap × rate, which encodes how the race ended.
- **Why it is wrong:** the declared exemption says the proxy diverges "only where a race is stopped early … NOT been measured". The premise is false, because the valid-lap filter also diverges on neutralised finishes, and it is now measured. Fuel loaded is a pre-race quantity.
- **Verdict:** Definitely wrong (forward reach, shown). ML magnitude not measured.
- **Earliest point:** `int_lap_fuel_state`. The same proxy is reused by `int_sc_hazard_history` (not in the contract).
- **ML impact:** a feature in all five families, and the label's fuel component. Probably small: 7% of races, a constant shift per race.
- **Fix:** a scheduled-laps column on `dim_events`, or at minimum MAX over *all* laps. `lap_length_km` is not a usable substitute: it is one value per slug across layout changes (Russia, pre-2021 Abu Dhabi).
- **Test:** T6.
- **How I could be wrong:** within a circuit the shift is a race constant, and trees may not exploit it. The effect could be nil.

### F7 — Missing 2025 seed cells get fabricated cliff features

- **Severity:** Medium.
- **file:line:** `int_compound_cliff_predicted.sql:120,124,146,147,152,156,194,196,210` (999 onset, 0 severity/wear/grip). The mart's direct `compound_*` columns are left NULL (`:509-514`).
- **Observed behaviour:**
  - 1,409 of 20,165 2025 training rows (7%) have no cell: 2025_21 all slicks, 2025_4 MEDIUM, 2025_13 INTERMEDIATE. A 2024 cell was never fitted for those (venue, compound) pairs to carry forward.
  - On them: `cliff_onset_passed` FALSE, `laps_past_cliff` 0, `expected_degradation_rate` exactly 0, `expected_compound_pace_s` = temperature term only. The same defaults enter the **label** via `compound_component_s`.
  - This NULL-plus-default pattern never occurs in 2018–2024 training rows.
  - In the 2024 simulation (F2), the 14% of rows without a cell cost cliff macro-F1 about 0.017 of the 0.019. Scaling to 2025's 7% is an inference.
- **Verdict:** Definitely wrong (fabricated default; inconsistent NULL handling of one missing cell).
- **Fix:** refuse to build with uncovered cells (T5), or carry the fallback hierarchy forward (venue history, then class default) explicitly.
- **How I could be wrong:** a NULL onset has no honest numeric value. The COALESCE to 999 may be the least-bad choice for the features. It is not acceptable in the label.

### F8 — The 2018 Italian GP silently disappears

- **Severity:** Medium.
- **Observed behaviour:** `race_to_track.csv` has no `2018_14`. The INNER JOINs at `int_lap_fuel_state.sql:62` and `int_compound_cliff_predicted.sql:90` drop all 927 laps (833 valid). It is the only valid-lap loss before the spine (`stg valid 161,040` vs `spine 160,207`, difference = 2018_14).
- **Known but not declared:** `fit_compound_cliff.py:111` ("2018_14 is a known, unrelated seed gap"). The seed even carries a `2018_14` pseudo-circuit row.
- **2021 cause, for completeness:** 2021_12 is legitimately empty: 60 laps, all neutralised.
- **Verdict:** Definitely wrong: a whole event dropped with no stated cause.
- **Test:** T4.
- **How I could be wrong:** the omission might be deliberate (for example Monza 2018 data quality). Nothing in the tree says so.

### F9 — Training eligibility depends on the in-race seed and on a label term

- **Severity:** Medium-Low.
- **file:line:** `int_lap_anomaly_flags.sql:235-243`. `clean_cliff` (kept) and `mistake` (excluded) differ **only** by `cliff_onset_passed`, which is the in-race seed (F2). Both require `mad_score>3 AND residual > trailing median`, a condition on residual(t), which the label subtracts five times.
- **Observed label means (age>3):** normal −0.43, mistake −5.03 (excluded, 4,262 labelled), clean_cliff −7.87 (kept, 866 labelled).
- **Verdict:** Probably wrong. The mechanism is traced. The effect on metrics is unmeasured: it needs an arm with eligibility decoupled from the seed.
- **How I could be wrong:** excluding driver-error laps is defensible cleaning. The objection is to the in-race coupling, and to eval metrics being quoted on a residual-selected population without saying so.

### F10 — A qualifying feature reads race-day data

- **Severity:** Low-Medium.
- **Observed behaviour:**
  - `weather_proxy` (`int_lap_residual_decomposed_qualifying.sql:95-104`) takes one `int_track_evolution` row per event: race-day rubber and ambient, via `DISTINCT ON (race_year, race_id) ORDER BY race_year, race_id` with no tiebreak. It is stable across thread counts because the source is stored in lap order; the lap picked is median lap 4, max lap 50 (`phaseD` probe). Its spread across a race's laps is a median 0.47 s, max 2.29 s.
  - `compound_component_s` uses the in-race seed wear gradient (`:144-145,167-171`).
  - Both are subtracted into `quali_driver_skill_residual_s`, hence into `quali_skill_session_avg_s` (a contract feature, cliff only).
  - The exemption text (`intermediate/schema.yml:1918-1920`, "no column this model SELECTs reads anything race-scoped") is contradicted.
- **Verdict:** Probably wrong. Magnitude unmeasured; the race-day term is a per-event constant.
- **How I could be wrong:** a per-event constant carries little information about within-race degradation. The effect is probably small.

### F11 — The guards' own state

- `features --check` writes `ml/models/encoders.json` (`features.py:705`). An audit CLI must not mutate a shipped artefact.
- `make data-profile-check` fails with 197 drift lines. The baseline is from 2026-09-07 (c7de693) and predates 12a-1.
- `make lint-oracle-check` fails with 6 of 7 `fct_*` hashes drifted. The baseline is from 2026-09-11, and the check runs on `ci.duckdb` only.
- Both gates are red for expected reasons, so **currently they gate nothing.**
- The dbt suite has 672 PASS and 1 FAIL: `assert_stint_geometry_2018_compound_code_null` rule 2, because all 24,680 2025 slick stint-laps have NULL `compound_code` (`tyre_allocations` covers 2019–2024). The 12a-1 history entry reads "757 PASS", which does not reproduce against the current tree.
- **Verdict:** Definitely.
- **How I could be wrong:** the red gates may be deliberately awaiting a re-snapshot. Nothing records that.

### F12–F21 (low severity; full fields condensed)

**F12. 2018 fabricated free air**
- file:line: `int_lap_air_state.sql:178-195` (COALESCE 0 / `'free_air'`); `int_lap_proximity.sql:406-426` (share_* COALESCE 0).
- Observed: `min_gap_s` is NULL on 5.5% of training rows per season (the leader, correctly free air) but 14.9% in 2018. So about 9.4% of 2018 rows have no car telemetry and get dirty-air 0 and proximity shares 0. Only `gap_ahead_*` NULL (9.7% in 2018 vs about 0% elsewhere) distinguishes them.
- Verdict: Definitely (default). Impact unmeasured. Test: T15.
- Could be wrong if: trees route on the `gap_ahead_*` NaN and recover the distinction.

**F13. `raw_dim_events.race_id` loaded as INTEGER**
- Observed: `202110`, `202112`, …, because DuckDB reads `2021_10` as a digit-separated numeric and `dbt_project.yml` declares no type. `dim_events` and `stg_events` match nothing.
- Consumers: `fit_compound_cliff.py:136` `forced_stop_flag` (always FALSE; the field is unused by the fit), and the app export (`useRaces.ts` has no callers and queries non-existent `season`/`round` columns).
- §4.6: the feared 2021-only `correction_weight` bias **does not exist**. `int_event_corrections` no longer reads `stg_events`; weights are data-derived, and the downweight share is 16–21% every season. `seed_manual_lap_exceptions` is header-only.
- Verdict: Definitely. Impact nil.

**F14. Three DSQs read as classified finishers**
- Observed: HAM and LEC at 2023_18 and RUS at 2024_14 carry a numeric `ClassifiedPosition` in bronze, so they read as classified with `is_dnf` FALSE. The other 13 DSQs are `non_classified`.
- Earliest point: bronze. Consumers: `int_stint_end_regime`, `fct_ghost_race_finish.actual_is_dnf`.
- Fix: route `status = 'Disqualified'` explicitly. Test: T13.

**F15. Counterfactual-championship "Actual Pts"**
- Observed: the Jolpica oracle (final standings only; the charter's "per round" is wrong, since only the final round is ingested) versus the app's table applied to FastF1 finishes: equal for 20/20 drivers in 2018, 14/20 in 2019, and the max gap is 54 points (2023). FastF1 race points themselves equal official totals for all 63 driver-seasons 2018–2020; they diverge from 2021 exactly as sprints begin.
- The methodology discloses the table, but "Actual Pts" and "real-world result" (`methodology.tsx:28`) overstate what is shown.
- Verdict: Probably wrong (label).

**F16. `ANY_VALUE` collapses**
- 7 driver-seasons in `mart_corner_skill_driver` show an arbitrary constructor (for example GAS 2019).
- 28 driver-seasons in the app's synthetic-teammate view show one of 2–3 teammates while averaging over all of them.
- Verdict: Definitely (display).

**F17. §4.4 / §4.5 values wrong, nothing computes on them**
- `pu_family`: `unknown_pu` on 3 of 19 constructors. It is a pure passthrough to `fct_driver_skill_features` and `fct_lap_residuals`; no pace index reads it, so the header claim at `reference/schema.yml:138` is false, and the app never reads it.
- `dim_drivers.driver_number`: lexicographic MAX (VER → `'33'`), read by nothing. `int_lap_proximity` uses per-race numbers from `stg_results`, which is correct.
- `fct_driver_skill_features.sql:153-154`: the "power" and "aero" pace indices are the same column.
- Rulings: `constructor_id`'s rename-split is harmless for per-race pace, since every consumer keys per race or season. `pu_family` should be keyed on the constructor *entity*.

**F18. 2020_1 lap numbering**
- Observed: `stg_race_control` has the CHEQUERED flag at lap 71, while `stg_laps` runs laps 1–68. Jolpica pit laps are ours +5 (36 stops) and +4 (2).
- Two independent sources disagree with bronze laps, so the defect is in bronze ingestion.
- Impact: one race's `lap_number` and `fuel_mass_kg`, and alignment of its field curve.

**F19. §4.1 `session_type` declared but absent**
- Confirmed. It is structurally unguarded but **currently clean beyond the file listing**: `lap_id` (season, race, driver, lap) is unique over 189,418 rows, and lap numbers are contiguous per driver, so no second session is mixed in.
- Severity rises to critical the day FP ingestion lands (02f).

**F20. Doc drift**
- `fct_cliff_prediction_features.sql:1-4`: the target is named `next_lap_degradation_jump_detrended_s`, but the model uses `next_5_lap_cumulative_jump_s` (§4.7).
- The same file: `:755` ("42nd feature"), `:774-776` (proximity "not yet in the ML feature contract", in since v11), and `:834-840` (qualifying "NOT yet in … FEATURE_COLUMNS", in since v13).
- `features.py:598` says `int_field_pace_curve` feeds `push_residual`. It does not: `int_lap_thermal_proxy` uses its own trailing median.
- `card.py:242` / `model_card.yml:7` summary: "powertrain, weather" feature families (dropped in Phase 9) and "Trained on 2018–2024".
- `reference/schema.yml:138` (`pu_family`).

**F21. Stale offline fits**
- `constructor_car_fe.parquet` and `degradation_isotonic.parquet` carry `data_window 2018_to_2024`, fitted 07-07 and 06-15. They were never refitted after 12a-1.
- `driver_skill_field_s` is NULL on all 459 2025 driver-races. `int_driver_circuit_era_affinity` filters `IS NOT NULL`, so the post-2022 era covers at most 3 seasons, and 2025 rookies (ANT, BOR, HAD) are absent. The app labels the era "2022–2024" (`ghost-race-standings/page.tsx:116`), so it is accidentally honest.
- `check_freshness.py:27-30` checks only two seeds, by fit-date age, not data-window coverage.
- Neither parquet fit touches the ML lineage (verified via the manifest `parent_map`).

---

## 3. Verified / Assumed

**Verified** (ran something; the query or script is named in each finding):
- Guard results: dbt 672/1 fail; features audit CLEAN with 0 known_leaks and 36 survey items; profile and oracle gates red, with baseline dates.
- F1 counts, positions, injected error, affected-row share and label statistics.
- F2: 171/171 single-race cells; the fit_source shares; the three-arm magnitude with an exact reproduction check.
- F3: manifest keys, the thrown TypeError (Node replica), app-layer commit date, callers.
- F4 additions: the 02c v14 `n_eval` equals 2025's labelled count; the fingerprint match; the `feature_count` source.
- F5: θ values by re-running compiled production SQL, and the label-shift estimate.
- F6: the 12 divergent races. F7: 1,409 rows and their defaults. F8: the 2018_14 drop and its cause. F9: label means by class.
- F10: the pick's lap distribution and within-race spread; stability across thread counts.
- F12–F18 counts. F18 against race control and Jolpica.
- The pit oracle (100% match for 2019 and 2021–2025) and the points oracle (63/63 for 2018–2020).
- Every clean-list query in §4.

**Assumed** (inferred, not run):
- F1 perturbs `anomaly_class` and therefore eligibility. App aggregates built on the residual do not filter the fabricated laps.
- F7's cost at 2025's 7% prevalence scales from the 2024 simulation's 14%.
- F2 arm C's deltas are inside reseed noise (no floor was run).
- The magnitude of F6, F9, F10 and F12 on published metrics.
- That prod CDN serves the v14 manifest (F3).
- That the v13→v14 "trio improved 7–10%" (build-log) is confounded by F2's A/B switch and F5. I did not re-run v13.
- That shrinkage floors bind for reserve drivers (§5.2). `assert_affinity_min_races` passes, but I did not independently re-derive it.
- That `stg_telemetry_position` session separation matches `raw_telemetry`'s (not traced).
- That the 2018_14 omission is unintentional.
- That the other ~25 app feature queries are free of F15/F16-class defects. I read counterfactual-championship, synthetic-teammate, ghost-race-standings and the `ml/` layer, not all 34 features.

---

## 4. Clean list (checked; no defect)

| Category | Evidence |
| :-- | :-- |
| No forward-reaching **window** on any contract feature's chain | `phaseC_window_sweep.py` → `phaseC_windows.csv`: 125 windows. The forward ones are labels, geometry, same-lap proximity, and label-spine or off-contract items |
| Thermal block (08e) backward-only | `int_lap_thermal_proxy.sql`: own trailing median plus LAGs; does not read the centred field curve |
| Label's drift term reaches nothing else | `grep -rln drift_s_per_lap` → mart label, barred in schema, one scratch script |
| Season folds cannot leak the 5-lap overlap | `train.py:179-196`: whole seasons per fold; stints never cross races; target NULL unless 5 same-stint laps follow |
| Encoders train-only; `MISSING_ORDINAL` cannot collide | `features.py:61-69`: 0..k-1, sentinel −1.0 (`schema.py:262`); unseen → NaN → −1 (`:79`); `compound` has no 2025-only level (Phase A) |
| Survival weights and SC hazard season-lagged | `fct_cliff_prediction_features.sql:238-293` (ROWS … 1 PRECEDING); `int_sc_hazard_history` (08f/02d); neither is a v14 feature |
| Grain: every join key unique, no fan-out | `phaseD_grain.py` → `phaseD_grain.csv` (37 models); mart rows 160,207 = spine rows 160,207 |
| `lap_id` no delimiter collision | `lap_id` unique in stg_laps (189,418/189,418) |
| One constructor per (driver, race) | 0 violations in stg_laps and stg_results; laps agree with results |
| Exactly one P1 per race; `is_classified`∧`is_dnf` never | 0 violations |
| `is_dnf` vs final-stint cause agree up to definition | Cross-tab in PHASE_EF (61 classified retirements, 12 DSQ-after-flag) |
| Units: every `/1e9` once | `grep 1e9 models/staging` (22 sites, staging only); min lap 55.4 s |
| `time_or_gap_s`, `pit_duration_s` not misused | No model consumer of either; 0 non-positive durations |
| Stint geometry and fuel physical invariants | age non-decreasing, lap_in_stint contiguous from 1, age ≥ lap_in_stint, stint_number monotone, fuel ≥ 0 and non-increasing: 0 violations each |
| 2018 compounds keep legacy names | No C-codes in 2018; rule 1 of the compound_code test passes |
| Race separation from qualifying (today) | Race sources read race depth; `lap_id` unique; laps contiguous; no model reads Q weather |
| `race_id` ↔ round | 172/172 agree with the bronze schedule's EventName |
| Pit stops vs Jolpica | 100% of Jolpica stops matched at the same lap in 2019 and 2021–2025; stg ⊇ Jolpica |
| FastF1 race points vs official | 63/63 driver-seasons equal 2018–2020 (post-2021 gaps equal the un-ingested sprints) |
| `stg_laps.circuit_key` alias (§4.3) | Read by no model. Consumers use `race_to_track.track_id` / `dim_circuits.circuit_id`. 01b premise holds under both readings |
| `correction_weight` season-shaped bias (§4.6) | Not present: data-derived classes, 16–21% downweighted every season |
| Encoders shipped = trained; manifest per-model orders | `diff` identical; 32/32/32/39/32 |
| LORO shipped as contemporaneous, not predictive | `ghost-race-standings/methodology.tsx:48` |
| Nationality not fabricated | `dim_drivers.sql:4`; no other hit |
| `debut_year` not read as experience | Only `fct_driver_skill_features.driver_debut_year` (unread by app); app "joined" label says "debuted after the opening season" |

**Absent by construction** (charter §0; stated so the omission is not silent):
- No points or standings model: `grep points transform/models/marts/*.sql` → 0.
- `stg_results.points` has no model consumer.
- No sprint sessions: no `session=*` other than Q under `data/bronze/laps/`.
- No practice sessions (same evidence).
- `dim_events.round_number` joined by nothing.
- No fastest-lap-point, tie-break or cumulative-points logic in `transform/` (the app has one; F15).
- Grid and finish positions are not ML features (`schema.py FEATURE_COLUMNS`).
- Jolpica is consumed by nothing (`grep -rln jolpica transform/models transform/seeds app/src ml/src scripts` → none). §4.8 confirmed.

---

## 5. Information-timestamp table (39 contract features)

t = the scored lap. "End of lap t" means knowable once lap t is complete. Masked = removed by `PER_TARGET_FEATURE_MASK`.

| # | Feature | Group | Families | Source (model:line) | Effective information timestamp | Status |
| --: | :-- | :-- | :-- | :-- | :-- | :-- |
| 1 | lap_number | stint_position | all 5 | stg_laps LapNumber | start of lap t | OK (2020_1 offset, F18) |
| 2 | lap_in_stint | stint_position | all 5 | int_stint_geometry ROW_NUMBER, backward | start of lap t | OK |
| 3 | age_in_stint | stint_position | all 5 | int_stint_geometry:100 `tyre_life` | start of lap t | OK |
| 4 | fuel_mass_kg | stint_position | all 5 | int_lap_fuel_state:36-42,73-77 | **end of race** (realised last valid lap) | **Forward, F6** |
| 5 | compound | compound | all 5 | stg_laps | lap t | OK |
| 6 | compound_grip_peak | compound | all 5 | seed; constant per compound | pre-race | OK value; NULL on 2025 no-cell rows (F7) |
| 7 | compound_wear_gradient | compound | all 5 | seed per (track, compound, season) | **end of race** 2018–24 (same-race fit); pre-race 2025 | **F2** |
| 8 | compound_optimal_temp_low | compound | all 5 | seed; constant | pre-race | OK (F7 NULLs) |
| 9 | compound_optimal_temp_high | compound | all 5 | seed; constant | pre-race | OK (F7 NULLs) |
| 10 | compound_cliff_onset_laps | compound | all 5 | seed (KM on same race) | **end of race** 2018–24 | **F2** |
| 11 | compound_cliff_severity | compound | all 5 | seed | **end of race** 2018–24 | **F2** |
| 12 | expected_compound_pace_s | cliff_prior | all 5 | int_compound_cliff_predicted:194-202 (seed + age + track temp at t) | **end of race** via seed | **F2**, F7 |
| 13 | expected_degradation_rate_s_per_lap | cliff_prior | all 5 | same:207-218 | **end of race** via seed | **F2**, F7 |
| 14 | cliff_onset_passed | cliff_prior | all 5 | same:124-125 (age > onset) | **end of race** via seed | **F2**, F7 |
| 15 | laps_past_cliff | cliff_prior | all 5 | same:118-123 | **end of race** via seed | **F2**, F7 |
| 16 | push_residual | thermal | all 5 | int_lap_thermal_proxy (own trailing median, valid laps < t) | end of lap t | OK (08e; assert_no_future_leakage) |
| 17 | cumulative_push_load_surface | thermal | all 5 | same, LAG 0..4 | end of lap t | OK |
| 18 | cumulative_push_load_bulk | thermal | all 5 | same, LAG 0..7 | end of lap t | OK |
| 19 | surface_bulk_ratio | thermal | all 5 | mart:544-550 arithmetic on 17/18 | end of lap t | OK |
| 20 | dirty_air_share_lap | dirty_air | all 5 | int_lap_air_state (raw telemetry, lap t) | end of lap t | OK; 2018 default (F12) |
| 21 | dirty_air_thermal_load_surface | dirty_air | all 5 | same, LAG EWMA | end of lap t | OK |
| 22 | dirty_air_thermal_load_bulk | dirty_air | all 5 | same | end of lap t | OK |
| 23 | air_state_dominant | dirty_air | all 5 | same | end of lap t | OK; 2018 default (F12) |
| 24 | share_lap_within_1s | proximity | all 5 | int_lap_proximity (position channel, lap t) | end of lap t | OK; 2018 default (F12) |
| 25 | share_lap_within_2s | proximity | all 5 | same | end of lap t | OK |
| 26 | share_lap_in_train | proximity | all 5 | same | end of lap t | OK |
| 27 | share_lap_behind_within_1s | proximity | all 5 | same (car behind at same bin, LEAD over crossings) | end of lap t (+ seconds) | OK |
| 28 | time_within_1s | proximity | all 5 | same | end of lap t | OK |
| 29 | gap_ahead_min_s | proximity | all 5 | same | end of lap t | OK (native NULL) |
| 30 | gap_ahead_median_s | proximity | all 5 | same | end of lap t | OK |
| 31 | ahead_identity_stability | proximity | all 5 | same | end of lap t | OK |
| 32 | n_distinct_cars_ahead_3s | proximity | all 5 | same | end of lap t | OK |
| 33 | quali_push_laps_n | qualifying | cliff only | int_qualifying_driver_summary (Saturday) | pre-race | OK (documented 0 indicator) |
| 34 | quali_constructor_pace_mean_s | qualifying | cliff only | int_constructor_structural_pace_qualifying | pre-race | OK |
| 35 | quali_constructor_pace_se_mean_s | qualifying | cliff only | same | pre-race | OK |
| 36 | quali_pace_delta_best_s | qualifying | cliff only | lap − segment median (quali only) | pre-race | OK |
| 37 | quali_ratio_to_segment_best_min | qualifying | cliff only | quali only | pre-race | OK |
| 38 | quali_skill_session_avg_s | qualifying | cliff only | int_qualifying_decomposed ← race-day int_track_evolution + in-race seed | **race day** (early race lap) + end of race (seed) | **F10** |
| 39 | quali_segments_contested_n | qualifying | cliff only | quali only | pre-race | OK |

**Forward or contemporaneous: 9 of 39** (rows 4, 7, 10–15, 38). The derived cliff_prior columns inherit the seed's timestamp. Rows 6, 8 and 9 are constants.

---

## 6. Grain table (declared vs actual)

All from `phaseD_grain.csv`; "dups" = rows − distinct keys; NULL-key rows 0 everywhere.

| Model | Declared grain | Key checked | Rows | Dups |
| :-- | :-- | :-- | --: | --: |
| stg_laps | race lap | lap_id | 189,418 | 0 |
| stg_laps_qualifying | quali lap | lap_id | 53,690 | 0 |
| stg_results | driver × race | (race_year, race_id, driver_id) | 3,458 | 0 |
| stg_results_qualifying | driver × quali | same | 3,459 | 0 |
| stg_weather | per lap_id | lap_id | 189,418 | 0 |
| stg_sector_times | sector | sector_id | 563,294 | 0 |
| stg_pits | pit stop | (year, race, driver, pit_in_lap) | 6,177 | 0 |
| int_stint_geometry | lap | lap_id | 189,418 | 0 |
| int_lap_residual_decomposed | valid lap (spine) | lap_id | 160,207 | 0 |
| int_lap_anomaly_flags / int_compound_cliff_predicted / int_lap_fuel_state / int_lap_telemetry_aggregates | valid lap | lap_id | 160,207 each | 0 |
| int_lap_thermal_proxy / int_lap_air_state / int_lap_proximity / int_event_corrections | all laps | lap_id | 189,418 each | 0 |
| int_lap_corner_inputs / int_lap_corner_drift | lap | lap_id | 157,699 each | 0 |
| int_field_pace_curve | race × lap | (year, race, lap_number) | 8,470 | 0 (coverage gap F1) |
| int_track_evolution | race × lap | same | 7,818 | 0 |
| int_qualifying_driver_summary | driver-weekend (broadcast) | (year, race, driver) | 3,387 | 0 |
| int_sc_hazard_history | circuit × season (broadcast) | (circuit_slug, season) | 173 | 0 |
| int_lap_residual_stint_detrend | stint | stint_id | 8,177 | 0 |
| int_constructor_structural_pace | constructor × race | (year, race, constructor) | 1,694 | 0 |
| race_to_track (seed) | race | race_id | 172 | 0 (missing 2018_14, F8) |
| dim_circuits / dim_compounds_season / dim_constructors / dim_drivers | per header | circuit_key / (circuit, compound, season) / constructor_id / driver_id | 44 / 510 / 19 / 43 | 0 |
| dim_events | race-level event | event_id | 6 | 0 (race_id mangled, F13) |
| fct_cliff_prediction_features | valid race lap | lap_id | 160,207 | 0 (= spine) |
| fct_stint_features | stint | stint_id | 9,643 | 0 |
| fct_lap_residuals | lap | lap_id | 160,207 | 0 |
| fct_driver_skill_features | driver × race | (year, race, driver) | 3,293 | 0 |
| fct_ghost_car_pace | host × race × ego × lap | ghost_id | 1,501,422 | 0 |
| fct_ghost_race_finish | host × race × ego | ghost_race_id | 32,075 | 0 |
| mart_corner_skill_driver | driver × season | (race_year, driver_id) | 161 | 0 (constructor arbitrary, F16) |

Race conservation, stg → mart: 21→20 (2018, F8), 22→21 (2021, legitimate), every other season equal.

---

## 7. Guard coverage map

| Guard | What it checks | Reaches | Does NOT reach | State today |
| :-- | :-- | :-- | :-- | :-- |
| `EXCLUDED_LEAKAGE_COLUMNS` (`test_features.py:46`, `features.py:706`) | Name-set intersection of X with a deny-list | Named columns only | Any unlisted leaky column (§6.1). **All F2 columns pass**: they are not listed | CLEAN (32) |
| `audit_forward_window` (`features.py:341-393`) | LEAD / FOLLOWING / self-join inequality on each feature's definition, following **bare renames only** (`:388-390`) | Compiled SQL of the 45 mart-lineage models | Arithmetic or COALESCE chains; whole-partition windows (PARTITION BY without ORDER BY); seeds; Python fits (`fit_compound_cliff.py`); parquet fits; ml-side synthesis; app SQL; off-lineage models | CLEAN |
| `audit_aggregation_scope` | Every GROUP BY in lineage pins one lap, or is declared | GROUP BY in the 45 lineage models; 28 declared `accepted` exemptions | Windows; seeds and fits (F2 is a GROUP BY in Python); the *truth* of exemption reasons. Two are now falsified: fuel (F6) and quali summary (F10) | CLEAN, 0 known_leak |
| `survey_aggregation_scope` | Same, off-lineage (report-only) | 36 findings | — | Report-only |
| `assert_no_future_leakage.sql` | Independent re-derivation of the thermal baseline and EWMAs | int_lap_thermal_proxy only | Everything else. Restates EWMA weights and the `>=1` floor (drift surface) | PASS |
| `assert_lap_7term_identity` / `assert_additive_identity` | pace_delta = Σ components + residual | Arithmetic closure | **Tautological**: the residual is defined as the remainder (`int_lap_residual_decomposed.sql:306-315`). Proves nothing about F1's fabricated `pace_delta_s` | PASS |
| Component tests (fuel monotonicity, coefficient signs, wear bound, severity bound, …) | Per-component physical bounds | Their component | Base coverage; seed provenance | PASS |
| `assert_stint_geometry_2018_compound_code_null` | 2018 NULL and 2019+ slick resolved | compound_code | — | **FAIL** (2025) |
| Schema tests (unique/not_null/accepted_values) | Keys and enums | Declared columns | Semantics | PASS |
| `data-profile-check` | Row counts, null rates, means vs baseline | 20+ tables | Per-season null rates (would catch F7 and F12 only by season) | **FAIL**, stale baseline, gates nothing |
| `lint-oracle-check` | Byte stability of `fct_*` | ci.duckdb (fixtures) | dev.duckdb entirely | **FAIL**, stale baseline |
| `check_freshness.py` | Two seeds' fit_date age ≤365 d | compound_cliff_params, circuit_reference | Data-window coverage vs ingested seasons; parquet fits (F21); race_to_track and tyre_allocations coverage (F8, the failing test) | not run (non-fatal) |
| `_guard_target_change` (`train.py`) | Target column **name** unchanged within a version | Names | Label value changes (F5, 08m, 08q) | — |
| ONNX parity (`test_onnx_parity.py`, manifest `onnx_parity`) | Booster == ONNX on the same vector | Python-side scoring | Whether the browser builds that vector (F3) | Python PASS; browser unverified |
| `test_predict.py:36` | `not is_holdout.any()` | — | Tautological under the resolver (F4) | PASS by construction |

**What passing establishes:** keys are unique; enumerated forward windows and GROUP BYs on the feature rename chains are backward or declared; named leakage columns are absent; components respect bounds; Python ONNX equals the booster.
**What it does not establish:** that the label is measured (F1); that any seed or offline fit is point-in-time (F2); that the exemptions' reasons are true (F6, F10); that the app can score (F3); that a new season is fully onboarded (F7, F8, F21).

---

## 8. Recommended tests (tree style)

"Blocks" = fails the build (a dbt singular test, or pytest in CI).

| ID | File | Checks | Model | A failure means | Blocks |
| :-- | :-- | :-- | :-- | :-- | :-- |
| T1 | `transform/tests/assert_pace_delta_requires_field_base.sql` | Rows with `base_track_pace_s IS NULL AND pace_delta_s IS NOT NULL` | int_lap_residual_decomposed | A fabricated closure base | Yes |
| T2 | `transform/tests/assert_label_window_has_measured_base.sql` | Independent re-derivation: every mart row with non-null `next_5_lap_cumulative_jump_s` has t..t+5 all with non-null `int_field_pace_curve` at their lap_number (join the curve directly, not the spine column) | fct_cliff_prediction_features | Label built on an unmeasured lap | Yes |
| T3 | `transform/tasks/coefficients/tests/test_seed_point_in_time.py` + a `fit_seasons_max` column in the seed | Every `dim_compounds_season` cell used by a mart row was fitted on seasons < the row's season (or is declared class-default) | seed / fitter | Same-race or future-season fit (F2) | Yes once the column exists |
| T4 | `transform/tests/assert_race_to_track_covers_all_races.sql` | Every `stg_laps.race_id` has a race_to_track row | race_to_track | A race will vanish via INNER JOIN (F8) | Yes |
| T5 | `transform/tests/assert_compound_params_cover_mart.sql` | Every (track, season, compound) in the spine has a cell | dim_compounds_season | Fabricated cliff features and labels (F7) | Yes (warn during onboarding) |
| T6 | `transform/tests/assert_fuel_start_is_pre_race.sql` | `race_lap_count` = scheduled laps (new `dim_events` column); interim: = MAX over all laps | int_lap_fuel_state | Fuel encodes the race ending (F6) | Yes |
| T7 | `ml/tests/test_manifest_app_contract.py` (+ app vitest) | For every model, `feature_order == schema.feature_columns_for(name)`; a Node test runs `buildFeatureVector` per model against the shipped manifest | manifest / app | Browser cannot score (F3) | Yes |
| T8 | `ml/tests/test_holdout_policy.py` | Declared holdout season has rows, or `holdout_populated: false` is written into the card and README; replaces the tautology at `test_predict.py:36` | features / card | Mechanism silently never fires (F4) | Yes |
| T9 | `transform/tests/assert_prior_season_labels_frozen.sql` (vs a stored per-season label hash) | 2018..N−1 label hash unchanged when season N ingests, unless the version bumps | fct_cliff_prediction_features | A pooled label parameter moved history (F5) | Warn |
| T10 | `ml/tests/test_quali_lineage_is_quali_only.py` | `int_qualifying_driver_summary` ancestors (manifest `parent_map`) exclude race-side models (`int_track_evolution`, in-race seed) | lineage | Race data in a pre-race feature (F10) | Yes |
| T11 | `ml/tests/test_features_check_is_readonly.py` | `_check` leaves `ml/models/encoders.json` mtime and hash unchanged | features CLI | The audit mutates artefacts (F11) | Yes |
| T12 | `ml/tests/test_forward_window_follows_arithmetic.py` | A synthetic model where a feature is `x + 0` over a FOLLOWING window must be flagged | audit | Coverage hole (§7) | Yes |
| T13 | `transform/tests/assert_dsq_not_classified.sql` | `status = 'Disqualified'` ⇒ NOT is_classified | stg_results | Bronze gives a DSQ a position (F14) | Warn |
| T14 | `transform/tests/assert_constructor_single_valued.sql` | Any per-(driver, season) output carrying constructor_id has count(distinct) = 1 or is flagged | mart_corner_skill_driver | Arbitrary label (F16) | Warn |
| T15 | extend `snapshot_data_profile.py` | Per-season null and zero share of each contract feature within tolerance of the other seasons | mart | Season-shaped defaults (F7, F12) | Yes after re-snapshot |

---

## 9. Remediation plan

Ordered within each tier by whether a published number moves.

**Before training (anything retrained now bakes these in)**
1. F1: stop fabricating `pace_delta_s`, and repair field-curve coverage. Label moves: version bump, fixed-target comparisons only.
2. F2: rule on the compound seed. Point-in-time fits, or a declared exemption with serving-consistent values. Measured cost of the honest pipeline: p50 +0.7%, cliff −0.0015 F1 (single refit).
3. F7 / F8 / F21 and the failing dbt test: season-onboarding completeness (race_to_track, tyre_allocations, seed cells, parquet fits for 2025).
4. F6: fuel from the scheduled distance.
5. F5: window `theta_air`, or freeze it per version.
6. F9 and F10: decouple eligibility from the seed; take race data out of the qualifying chain.

**Before evaluation (before any new headline is quoted or compared)**
1. F4: declare an untouched season; fix or rename the resolver; retire the stale prose and the tautological test; stop spending 2025 in admission gates (02c v14 already has).
2. Annotate every v13↔v14 comparison as not fixed-target (F5) and protocol-switched (F2 A→B).
3. Model card: per-model `feature_count` and `n_training_rows`; a summary that matches the contract.

**Lower-risk cleanup (no published number moves)**
1. F3: per-model browser vectors. This is user-facing breakage; do it independently and soon.
2. F13 (type the seed or delete it and the dead `useRaces`), F14, F15 labels, F16, F17 (key `pu_family` on the entity; order `driver_number` by season; drop the duplicate index), F19 (drop or populate `session_type`), F20 doc drift, F18 (re-pull 2020_1 or declare it).

**Post-build monitoring**
1. F11: make `features --check` read-only; re-snapshot both drift baselines on the v14 build and make them blocking; add T15.
2. Freshness: coverage by `data_window` against MAX(race_year) for every seed and parquet fit, not by fit-date age.
3. Extend the audits (T12; seed/fit provenance via T3); re-validate exemption reasons when their numbers are measured (F6 and F10 were falsified here).

---

## 10. Proposed work items (for the user to place; not written to `build-log.json`)

| ID (proposed) | Title | Suggested group | Stage | Blocker |
| :-- | :-- | :-- | :-- | :-- |
| WI-1 | Label spine: remove the `pace_delta_s` COALESCE and repair field-curve coverage (F1, T1, T2) | 08 foundations | SPEC | None; blocks any v15 retrain |
| WI-2 | Compound seed point-in-time: lagged fits, or declared same-race exemption plus serving parity (F2, F7, F9; T3, T5) | 08 foundations | SPEC | **Human ruling** (00c standard vs spine acceptance); magnitude already measured |
| WI-3 | Holdout policy after 12a-1: untouched season, resolver, prose, test; freeze 2025 out of gates (F4, T8) | 12 season coverage | SPEC | **Human decision**: which season is held out |
| WI-4 | Browser inference per-model vectors (F3, T7) | 06 publication / app | SPEC | None |
| WI-5 | Season-onboarding completeness gate: race_to_track, tyre_allocations, compound seed, parquet fits, scheduled laps (F6, F7, F8, F21; T4, T5, T6) | 12 season coverage | SPEC | None |
| WI-6 | Pooled label parameters windowed, plus label-stability monitor (F5, T9) | 08 foundations | SPEC | Ruling: may labels move with ingestion? |
| WI-7 | Guard repairs: read-only features CLI, blocking drift baselines, audit coverage (F11; T11, T12, T15) | 09 scoring instruments | SPEC | None |
| WI-8 | Qualifying chain quali-only (F10, T10) | 02 feature expansion | SPEC | WI-2 (shares the seed) |
| WI-9 | Cleanup bundle: F13–F20 | 08 foundations (low) | OPEN | None |

---

## Artefact index (`transform_forensic_audit_artefacts/`)

- **Phase notes:** `PHASE_B_guards.md`, `PHASE_C_leakage.md`, `PHASE_D_grain_defaults.md`, `PHASE_EF_identity_units_oracles_surface.md`.
- **Guards:** `phaseB_dbt_test.log` (+ `_run1_catalogname_artefact.log`), `phaseB_features_check_nowrite.py`/`.log`, `phaseB_data_profile_check.log`, `phaseB_lint_oracle_check.log`.
- **Leakage:** `phaseC_window_sweep.py` → `phaseC_windows.csv`, `phaseC_exemptions.txt`, `phaseC_theta_air_2025.py`, `phaseC_theta_label_move.py`, `phaseC_seed_magnitude.py`/`_v2.py` → `.json`/`.log`.
- **Grain and defaults:** `phaseD_grain.py` → `phaseD_grain.csv`, `phaseD_coalesce_classify.py` → `phaseD_coalesce_classified.csv` (all 428 sites), `phaseD_base_null_label.py`, `phaseD_base_null_size.py`, `probe_feature_null_by_season.py` → `feature_null_by_season.csv`, `fuel_race_lap_count_gap.csv`.
- **Oracles and identity:** `phaseE_oracle_points.py`, `phaseE_oracle_pits.py`/`2.py`, `phaseE_lap_coverage.py`.
- **Shipped surface:** `phaseF_manifest_contract.mjs`.
- **Warehouse copy** used only for dbt test: `dbcopy/dev.duckdb`, `dbt_profile/`, `dbt_target/`, `dbt_logs/`.
