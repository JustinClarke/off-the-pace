# Tests

Singular SQL tests that encode mathematical identities and domain constraints too
complex for schema YAML. All run as part of `dbt test` (or `make dbt-test`).

A test **passes when it returns zero rows**. Each test is in one of three states:

- **✅ Active** runs real logic that can fail the build.
- **⏸️ Inert** real logic is present but disabled in this checkout because the
  baseline snapshot it compares against isn't committed; it passes vacuously until
  a snapshot is generated.
- **📝 Placeholder** `SELECT 1 WHERE FALSE`; wired up once the upstream model
  (or its confidence intervals) lands. These carry `tags: ['placeholder']`, so
  `dbt test --exclude tag:placeholder` measures real coverage only.

## Identity-Closure Tests

Additive identities and shrinkage bounds the transform layer must satisfy. The
closure checks are built on the [`assert_additive_identity`](../macros/assert_additive_identity.sql) macro.

| File | Identity | Model(s) | Status |
|---|---|---|---|
| `assert_residual_decomposition_identity.sql` | 6-term lap residual closure | `int_lap_residual_decomposed` | ✅ Active |
| `assert_lap_7term_identity.sql` | 7-term lap residual (dirty air extracted) | `int_lap_residual_decomposed` | ✅ Active |
| `assert_qualifying_7term_identity.sql` | Qualifying 7-term identity | `int_qualifying_decomposed` | ✅ Active |
| `assert_sector_residual_identity.sql` | Sector-grain residual identity | `int_sector_residual_decomposed` | ✅ Active |
| `assert_sector_aggregates_to_lap.sql` | Sector-to-lap re-aggregation: summed sector-grain explained physics components (fuel, compound, rubber, ambient, constructor, dirty-air) equal the lap-grain component, within 0.001s float-accumulation tolerance. **Warn severity**: 11,892 of 161,040 three-sector laps (7.4%) currently fail on the `dirty_air` term alone (max 0.161s) -- the sector allocation gates on the CURRENT lap's `dirty_air_share_lap` while the lap-grain tax it redistributes is priced from the PREVIOUS lap's `dirty_air_share_lag1` (`int_dirty_air_tax_component.sql`'s causal lag). New finding, not yet numbered; out of scope for a guard-repair item (WI-07) to fix, so this is a real, non-blocking gate rather than a stub | `int_sector_residual_decomposed`, `int_lap_residual_decomposed` | ✅ Active |
| `assert_corner_closure.sql` | Corner-grain closure: braking + mid-corner + exit = total corner residual (within 0.001s) | `int_corner_skill_residuals` | ✅ Active |
| `assert_ghost_car_self_consistency.sql` | Ghost-car degenerate identity (self-match ⇒ zero delta) | `fct_ghost_car_pace` | ✅ Active |
| `assert_example_identity_closure.sql` | Usage example for the `assert_additive_identity` macro (superseded as canonical by `assert_lap_7term_identity`) | `int_lap_residual_decomposed` | ✅ Active |
| `assert_deg_slope_centering.sql` | Constructor deg-slope centring (raw − field mean) | `int_constructor_deg_sensitivity` | ✅ Active |
| `assert_cliff_hinge_centering.sql` | Constructor cliff-onset hinge centring | `int_constructor_deg_sensitivity` | ✅ Active |
| `assert_affinity_shrinkage_bounds.sql` | Shrinkage bounds (circuit affinity) | `int_driver_circuit_affinity` | ✅ Active |
| `assert_era_affinity_shrinkage_bounds.sql` | Shrinkage bounds (circuit affinity, era-segmented) | `int_driver_circuit_era_affinity` | ✅ Active |
| `assert_era_rating_shrinkage_bounds.sql` | Shrinkage bounds (era rating) | `int_driver_season_ratings` | ✅ Active |
| `assert_affinity_ci_brackets_mean.sql` | Credible interval brackets the posterior mean (`ci_low ≤ shrunk ≤ ci_high`) | `int_driver_circuit_affinity`, `int_driver_circuit_era_affinity` | ✅ Active |

## Domain Constraint Tests

| File | What it asserts | Model(s) | Status |
|---|---|---|---|
| `assert_stint_boundary_integrity.sql` | Fuel state, thermal proxy, and air state all reset correctly at stint boundaries | `int_lap_fuel_state`, `int_lap_thermal_proxy`, `int_lap_air_state` | ✅ Active |
| `assert_no_future_leakage.sql` | Trailing window functions use only past laps no look-ahead in EW averages | `int_lap_thermal_proxy` | ✅ Active |
| `assert_synthetic_teammate_identity.sql` | `driver_skill_proxy` ≈ 0 when ego and teammate are the same driver | `int_synthetic_teammate`, `int_stint_geometry` | ✅ Active |
| `assert_field_pace_honest_range.sql` | Field pace curve stays within ±5s of the overall race median | `int_field_pace_curve` | ✅ Active |
| `assert_mad_floor.sql` | MAD scale estimator is floored at 0.10s (prevents cliff self-masking) | `int_lap_anomaly_flags` | ✅ Active |
| `assert_track_evolution_monotone.sql` | Track-evolution's raw (pre-clamp) per-race rubber-in OLS slope stays within a physically plausible ±0.5s/lap band. F34: the old body checked the PUBLISHED `rubber_component_s` column, built as `LEAST(raw_slope, 0.0)` -- floored at zero by construction, so it could never fail (vacuous). A strict "raw slope <= 0" is not viable either: 106 of 171 races (62%) have a positive raw slope, which this in-SQL linear approximation's own header admits ("captures ~80% of the rubber effect") -- so this re-derives the raw slope independently and bounds it as a blowup/sanity gate instead of a strict-monotonicity one | `int_track_evolution`, `int_field_pace_curve` | ✅ Active |
| `assert_sc_hazard_probability_bounds.sql` | Per-lap SC/VSC/any hazard rates are valid probabilities in [0, 1] and `any` ≥ each component | `int_sc_hazard_history` | ✅ Active |
| `assert_sc_hazard_no_forward_leakage.sql` | The season-`S` hazard is built from seasons `< S` only: trailing totals re-derived with an inequality join must match, each rate must equal its own numerator/denominator, and prior exposure must be non-decreasing in season | `int_sc_hazard_history` | ✅ Active |
| `assert_corner_trailing_window_no_forward_reach.sql` | The corner field median at lap `t` draws on no lap `>= t` (the `02g` rebuild of the `FLOOR(lap/5)*5` block bucket) | `int_corner_skill_residuals` | ✅ Active |
| `assert_corner_inputs_lap_grain_closure.sql` | The lap-grain roll-up is faithful to the corner grain it summarises, so an upstream fan-out cannot reach the feature contract silently | `int_lap_corner_inputs`, `int_corner_skill_residuals` | ✅ Active |
| `assert_driver_skill_residual_reasonable.sql` | Driver-skill residual per race is centred near 0 (mean < ±1s) | `fct_lap_residuals` | ✅ Active |
| `assert_raw_laps_has_both_sessions.sql` | Both race (`stg_laps`) and qualifying (`stg_laps_qualifying`) laps are present with data | `stg_laps`, `stg_laps_qualifying` | ✅ Active |
| `assert_p_beats_next_geq_half.sql` | Pairwise consistency: `p_beats_next` ≥ 0.5 for adjacently-ranked drivers (ranked by ascending predicted pace) | `fct_ghost_race_finish` | ✅ Active |
| `assert_constructor_coefficient_signs.sql` | Every season has at least one constructor genuinely faster than the field (`MIN(constructor_structural_pace_s) < 0`) and at least one identified (non-degenerate) CI. Seasons whose dry panel holds fewer than two constructors are skipped (a lone constructor is centred on itself); since WI-05's wet-flag fix that is the CI fixtures' all-wet 2024 São Paulo | `int_constructor_structural_pace` | ✅ Active |
| `assert_aero_penalty_negative.sql` | Dirty-air tax is always a penalty, never a bonus: theta_air, the fitted coefficient dirty_air_tax_s's clamp is built from, must be >= 0. F34: the old body checked the PUBLISHED `dirty_air_tax_s` column, which is CLAMPed to [0, 5.0] and so can never be negative by construction (vacuous). This re-derives theta_air from any lap whose clamp did not bind, plus a second check for the degenerate case where every positive-exposure lap clamps to exactly 0 and there is nothing left to recover it from | `int_dirty_air_tax_component` | ✅ Active |
| `assert_thermal_variance_positive.sql` | Track temperature genuinely varies within a race (range ≥ 0.1 °C), catching a stalled or missing thermal join | `int_track_evolution` | ✅ Active |
| `assert_fuel_curve_monotonicity.sql` | Fuel weight penalty strictly decreases as fuel burns off within a stint | `int_lap_fuel_state` | ✅ Active |
| `assert_stint_boundaries_match_pits.sql` | T19 (WI-05, F24; replaces `assert_stint_boundaries_correct`, which passed on all three races whose stint numbering ignores the pit stops): every race was cross-checked against `stg_pits`; a served stint change has an in-lap within the window before it (or a red flag); a quarantined unit's stint changes sit on the pit record and it serves no compound or tyre age; no race still served from bronze misses the quarantine share of its racing stops; tyre age rises strictly within a stint | `int_stint_geometry`, `stg_pits`, `int_lap_residual_decomposed` | ✅ Active |
| `assert_stint1_includes_lap1.sql` | T20 (WI-05, F25): lap 1 is on the driver's first stint, that stint's `lap_in_stint` counts from lap 1, and its tyre age rises by one a lap over laps 1-3 (the 2018 lap-1 gap filled with its TyreLife offset) | `int_stint_geometry` | ✅ Active |
| `assert_stint_geometry_2018_compound_code_null.sql` | 08p: `compound_code` NULL rule in both directions -- every 2018 row is NULL (Pirelli's relative naming starts 2019; `stg_tyre_allocations` covers 2019-2024 only), and every 2019+ slick (HARD/MEDIUM/SOFT) lap resolves a code. Rule 1 alone is satisfiable vacuously by a column that is NULL everywhere, which is exactly what shipped once (a join across two disjoint `circuit_key` domains matched zero rows and this test's first version passed anyway) -- rule 2 is what makes it non-vacuous. INTERMEDIATE/WET are excluded (not on the C1-C5 scale, so NULL is correct for them) | `int_stint_geometry` | ✅ Active |
| `assert_race_to_track_covers_all_races.sql` | T4 (WI-05, F8): every `stg_laps` race has a `race_to_track` row whose slug resolves in `dim_circuits`, and every race with a valid lap reaches `int_lap_fuel_state`, `int_compound_cliff_predicted` and the lap spine -- no race dropped by an INNER JOIN | `race_to_track`, `int_lap_fuel_state`, `int_compound_cliff_predicted`, `int_lap_residual_decomposed` | ✅ Active |
| `assert_fuel_load_matches_scheduled_distance.sql` | T6 + T24 folded per F52 (WI-05, F6, F32): every race has a scheduled distance; `race_lap_count` is it and covers every lap run; the implied starting load is one number per race, within the season's FIA limit, and burns to zero over the scheduled laps; no run lap finds the tank empty; scheduled laps x lap length is a 250-320 km race distance | `int_lap_fuel_state`, `race_scheduled_laps` | ✅ Active |
| `assert_rain_flag_matches_tyres.sql` | T21 (WI-05, F26): a race flagged wet on most laps had cars on inters/wets (> 5%), and a race run mostly on inters/wets carries a wet flag | `stg_weather`, `stg_laps` | ✅ Active |
| `assert_quali_valid_share_consistent_across_seasons.sql` | T25 (WI-05, F33): among quali laps that pass every non-technical gate, each season's valid share is within 0.05 of the other seasons' median (2018 lost 26% to the IsAccurate sync flag) | `stg_laps_qualifying` | ✅ Active |
| `assert_pace_delta_flat_by_race_fifth.sql` | `pace_delta_s` carries no within-race fuel trend on the field curve's own eligible panel: every fifth of race distance sits within 0.15s of the panel mean | `int_lap_fuel_state`, `int_field_pace_curve` | ✅ Active |
| `assert_affinity_min_races.sql` | No era-segmented affinity is published from fewer than 2 races at that circuit | `int_driver_circuit_era_affinity` | ✅ Active |
| `assert_rating_confidence.sql` | No global LORO confidence collapse: drivers with ≥ 5 races keep `rating_confidence` ≥ 0.3 | `int_driver_season_ratings` | ✅ Active |
| `assert_rating_top_season_well_supported.sql` | Results-anchored: the top-rated driver-season of all time rests on ≥ 10 races, not a small-sample artifact. Self-limiting on warehouses too thin to test (fires only once some season could clear the bar) | `int_era_normalized_driver_rating` | ✅ Active |
| `assert_corner_skill_cell_winsorized.sql` | Season corner-skill means stay inside the ±1.0s per-cell winsorization bound (a lap-weighted mean of winsorized cells cannot exceed it) | `mart_corner_skill_driver` | ✅ Active |
| `assert_corner_skill_phase_gate.sql` | A phase z-score needs ≥ 30 cells, and `corner_skill_index` needs all three phases populated | `mart_corner_skill_driver` | ✅ Active |
| `assert_corner_skill_sign_convention.sql` | 00d: all three corner phases share one sign convention (a row credited with lost time must brake no later than any row in the same group credited with gained time -- pinned against the raw geometry, not a recomputed median, so the test doesn't verify the construction using the construction), and `corner_skill_index` is the plain, unnegated sum of the three published z-scores. `braking_loss_s` was built with the opposite sign to the other two phases (later braking is faster, so the column named "loss" was measuring a gain) -- invisible to `assert_corner_closure` (sums to the total under either sign) and every other existing corner test, all of which are sign-agnostic. Non-vacuous: 98,769 of 98,769 eligible groups violated it under the old sign, 0 under the corrected one | `int_corner_skill_residuals`, `int_corner_metrics`, `mart_corner_skill_driver` | ✅ Active |
| `assert_cliff_predictions_valid.sql` | A slick-compound (SOFT/MEDIUM/HARD) lap never carries a NULL `compound_cliff_onset_laps`, catching a silently failed seed join. F34: the old body flagged the literal `expected_compound_pace_s = 0.0 OR = 0.5` sentinels, left over from a COALESCE fallback F7 already removed -- no row has hit them since, so the check was vacuous. Checking `expected_compound_pace_s` itself (even widened to a range) does not work either: it is legitimately NULL on a lap with a real seed cell but an unknown tyre age (F39), a different, already-covered condition, not a failed join | `int_compound_cliff_predicted` | ✅ Active |
| `assert_cliff_seed_severity_bounded.sql` | Cliff-seed tripwire: fitted severity ≤ 1.6 s/lap, and the cross-season fallback never fires from fewer than 8 real stints | `compound_cliff_params` (seed) | ✅ Active |
| `assert_ghost_recombination.sql` | Ghost lap-time predictions stay within ±10s of the actual lap (fuel-envelope and interpolation guard) | `fct_ghost_car_pace` | ✅ Active |
| `assert_ghost_self_scenario_rank.sql` | Results-anchored: self-scenario ghost pace recovers official finishing order (mean per-race Spearman ρ ≥ 0.5, no race negatively correlated). Validates recombination pace, not the counterfactual car swap | `fct_ghost_race_finish`, `stg_results` | ✅ Active |
| `assert_cliff_class_horizon_partition.sql` | `laps_until_cliff_class` buckets partition the remaining-stint horizon as their names read: first crossing of the >1.0s detrended threshold at true lap offsets, scanned over the whole stint, so `6_plus` is 6-or-more and `none_in_stint` means no crossing at all | `fct_cliff_prediction_features` | ✅ Active |
| `assert_stint_censoring_partition.sql` | Stint-life right-censoring is a partition: each driver-race has exactly one censored stint the last one, ended by the flag or a retirement rather than a tyre change. Two would mean a broken window partition, zero would mean the flag never fired and every row trained as an uncensored observation | `fct_stint_features` | ✅ Active |
| `assert_track_status_flag_partition.sql` | FastF1 TrackStatus decode: `is_safety_car_lap`/`is_vsc_lap`/`is_red_flag_lap` match digits 4 / 6-7 / 5 exactly, their union is the neutralised set (`[4567]`), and no neutralised lap is valid | `stg_laps` | ✅ Active |
| `assert_quali_segment_matches_official.sql` | Recovered Q1/Q2/Q3 windows: every official segment time was set inside the segment the lap was assigned to. Official times with no matching lap, and a segment time identical to the next segment's, are skipped as source artefacts rather than failed | `int_qualifying_segments`, `int_qualifying_push_laps`, `stg_results_qualifying` | ✅ Active |
| `assert_pit_stop_grain.sql` | Pit-stop grain and duration: one row per stop (never per pit lap), the out-lap is the next lap, the three exit-side columns resolve together, and `pit_duration_s` is positive and equals its two stamps | `stg_pits` | ✅ Active |
| `assert_pit_loss_excludes_neutralised.sql` | Pit-loss stop population: the model counted exactly the green-flag stops (no SC/VSC/red in-lap or out-lap), event slugs sharing a physical venue carry one pooled estimate, and the EB value lies between the circuit and global medians | `int_pit_loss_circuit` | ✅ Active |
| `assert_pit_loss_pushes_optimum_later.sql` | A longer pit lane never pulls the modelled optimum forward: the same cost curve re-minimised at a pit lane 15 s longer must not return an earlier lap. The property the `Total_Cost(L)` rewrite exists to establish, checked against the implementation rather than restated | `int_pit_strategy_cost_curve` | ✅ Active |
| `assert_pit_discount_monotone.sql` | The safety-car pit discount is non-increasing in the candidate lap the mechanism underneath the gate above. A `pit_sc_loss_multiplier` above 1 would invert it and make the model recommend stopping *earlier* where safety cars are more likely | `int_pit_strategy_cost_curve` | ✅ Active |
| `assert_pit_ended_stints_have_stop.sql` | T23 (WI-13, F31): every stint that ended in a stop (`stint_end_cause` `green_pit` / `sc_pit` / `vsc_pit` / `red`) carries its `actual_pit_lap`. The stop used to be matched only up to the stint's last *valid* lap + 1, so one taken after a run of SC/VSC/red-flag or other invalid laps was missed and the stint was graded as if it never stopped (verdict NULL, cost 0.0, and the app drew its bar to the chequered flag): 418 stints on the 2026-09-24 dev build, 107 of 116 red-flag-ended. It is now matched inside the stint's full span, up to `int_stint_end_regime.end_lap_number` | `int_pit_strategy_value`, `int_stint_end_regime` | ✅ Active |
| `assert_corner_window_geometry.sql` | Derived corner windows: each window contains its own apex, stays inside its neighbouring apexes, respects the configured entry/exit margins, borrowed geometry never crosses event slugs, and the corner count matches the source session | `dim_corners`, `stg_circuit_info` | ✅ Active |
| `assert_no_cap_valued_wear.sql` | T29, data half (WI-02, F39): on a lap with no known tyre age, every age-dependent column of the wear curve (`compound_wear_s`, `expected_compound_pace_s`, `laps_past_cliff`, `expected_degradation_rate_s_per_lap`) is NULL. DuckDB's `LEAST` skips NULL arguments, so an unknown age used to come out as the 10 s bound itself on 4,107 laps -- a value every range test accepts. The lint half is `transform/tasks/coefficients/tests/test_sql_least_greatest_nullable.py` | `int_compound_cliff_predicted` | ✅ Active |
| `assert_survival_weight_neutral_without_prior_curve.sql` | T29 data half for `survival_weight` (WI-13): a lap with no prior-season survival cell -- the first ingested season, a lap with no compound, a (compound, `lap_in_stint`) no earlier season reached -- carries the documented unweighted 1.0. The clip was `GREATEST(0.25, LEAST(4.0, ...))`, which turned the NULL into 4.0, the maximum weight: 24,800 rows on the 2026-09-24 dev build (every 2018 row among them), 18,878 training-eligible. The "no prior cell" population is re-derived from `int_lap_residual_decomposed`, not read off the model | `fct_cliff_prediction_features`, `int_lap_residual_decomposed` | ✅ Active |
| `assert_low_sample_cliff_cells_unshifted.sql` | T29 data half for `cliff_onset_shift_laps` (WI-13): a cell flagged `is_low_sample_cliff` keeps the field's cliff timing (shift exactly 0, never NULL). A compound-season with no post-onset laps has no `ref_depth`, and the old `LEAST(GREATEST(..., -3.0), 3.0)` turned that NULL into -3.0, the harshest shift (2018 Renault HARD, 1 of 233 cells) | `int_constructor_deg_sensitivity` | ✅ Active |
| `assert_compound_params_cover_mart.sql` | T5 (WI-02, F7): every (venue, season, compound) a valid lap is priced on has a `dim_compounds_season` cell, so the build stops before a new season reaches the marts with a missing cell (which the curve used to price as onset 999 / severity 0 / wear 0, into the label). The explicit fallback that fills a gap is `fit_compound_cliff.py --fill-gaps` | `dim_compounds_season`, `int_stint_geometry`, `race_to_track` | ✅ Active |
| `assert_compound_wear_bounded.sql` | The compound wear curve respects `var('compound_wear_max_s_per_lap')`. Asserted on `compound_wear_s` rather than the pace total, because the total legitimately exceeds the bound by per-lap constants. Added by Phase 8; this README row was missed at the time, which broke `transform_docs_facts.py` (it raises on any uncategorised singular test) until Phase 10a added it | `int_compound_cliff_predicted` | ✅ Active |
| `assert_proximity_crossing_total_order.sql` | Both window orderings `int_lap_proximity` depends on are total orders, so `LAG`/`LEAD` cannot pick an arbitrary neighbour inside a tied block. A reproducibility gate, added because the model shipped without it and two builds of identical SQL disagreed: 223,602 of 15,821,726 crossings tie on `(race_id, track_bin, crossing_time_s)`, and 76 more tie at the lap rollover where FastF1 gives the transition sample to both laps. Invisible to row-count, null-rate, range and even the blue-flag check — the values stay plausible and only the neighbour assignment moves | `int_lap_proximity`, `stg_telemetry_position` | ✅ Active |
| `assert_proximity_train_subset_of_within1s.sql` | `share_lap_in_train` can never exceed `share_lap_within_1s`, of which it is a subset by construction (a train bin requires the within-1 s condition plus one more). Exact, not toleranced: both are averages of 0/1 over the identical bin set | `int_lap_proximity` | ✅ Active |
| `assert_proximity_agrees_with_blue_flags.sql` | The position-channel proximity measure agrees with the FIA's own traffic label: on laps carrying a waved blue flag the median closest car (ahead or behind) is materially smaller than on the rest, per season and not pooled. The only traffic check in the project not derived from the same telemetry as the thing it checks. **Vacuous on the CI fixture by design** (12/1/0 blue flags per season against an `n_blue >= 100` guard) — a dev/prod gate, see the test header | `int_lap_proximity`, `stg_race_control` | ✅ Active |
| `assert_stint_end_cause_partition.sql` | `stint_end_cause` partitions the stint population exactly as its class names read, under the declared precedence: censoring outranks regime, and within an uncensored stint `red_flag` > `safety_car` > `vsc` > `green`. Re-derives the label independently of the model's CTEs — it reaches the final lap through `MAX(lap_number)` rather than a row-number, and rebuilds the censoring window and the running-at-the-flag test from staging — so it fails on drift rather than moving with it. 276 stints whose final lap carries red *and* safety car change class if the CASE is reordered, with nothing else failing | `int_stint_end_regime`, `int_stint_geometry`, `stg_results` | ✅ Active |
| `assert_dsq_not_classified.sql` | T13 (WI-09, F14): a disqualified driver is never a classified finisher: every `stg_results` row with `status = 'Disqualified'` has `is_classified` FALSE, `is_dnf` TRUE and `dnf_cause` `non_classified`. The flags used to read `ClassifiedPosition` alone, and bronze leaves a numeric one on HAM and LEC (2023_18) and RUS (2024_14), so those three read as classified finishers and `fct_ghost_race_finish` published an official finishing position for them. `status` is now decided first. Default severity (error), not the audit's warn: bronze can no longer trip it, only a change to the flags can | `stg_results` | ✅ Active |
| `assert_air_state_no_telemetry_share_by_season.sql` | T15 (WI-07): guards F12 (2018's fabricated free-air/zero telemetry share) against getting worse or spreading, without fixing it (deferred to WI-01/WI-15a pending decision FD6). Per-season (not pooled) share of `gap_ahead_min_s IS NULL` -- 2018 may not exceed 15% (measured 9.18%), every other season may not exceed 2% (measured <= 0.04%). **Warn severity**: guards a known, deliberately-deferred defect | `fct_cliff_prediction_features` | ✅ Active |
| `assert_pu_family_coverage.sql` | F54 (WI-09): no constructor in `dim_constructors` falls through to `unknown_pu`. The mapping is a hand-kept list keyed on the team name and F1 renames teams every year or two; three of 19 constructors (Alfa Romeo Racing, Kick Sauber, Racing Bulls, all renames) were unmapped with nothing to flag it. **Warn severity**: an unmapped name is a to-do, not a reason to stop a season's ingestion, and nothing computes on `pu_family` today | `dim_constructors` | ✅ Active |
| `assert_raw_laps_race_depth_is_race_only.sql` | F19 (WI-09): no file the race-lap glob (`laps/*/*/*.parquet`) reads declares a `session_type` other than `R`. Race files carry no such column today, so directory depth is the only thing keeping qualifying and any future practice or sprint session out of `stg_laps`; the source description used to claim a `session_type` column and a coalesce that were never built. Reads the raw files with `union_by_name`, so the column is seen even when the first file lacks it; `unique(stg_laps.lap_id)` covers a second session written with no marker | `bronze_f1.raw_laps`, `stg_laps` | ✅ Active |

## Regression Gates

Baseline-comparison gates that fail if a code change regresses a headline statistic.
They are **inert in a fresh checkout** because the committed baseline snapshot is not
included, so they pass vacuously until a snapshot is generated.

| File | What it gates | Model(s) | Status |
|---|---|---|---|
| `assert_constructor_pace_propagates.sql` | `constructor_component_s` must reduce variance in `driver_skill_residual_s` vs the pre-release baseline | `fct_lap_residuals`, `int_constructor_structural_pace` | ⏸️ Inert |
| `assert_residual_variance_shrinks.sql` | `driver_skill_residual_s` variance must not regress vs the baseline snapshot (SHA `7d4a58f`) | `fct_lap_residuals` | ⏸️ Inert |

## Lint & byte-stability gate

`sqlfluff lint models/` is a **genuinely enforcing** hard-fail gate (CI + `make
transform-check`). It connects to the checked-in dbt profile via `.sqlfluff`
(`profiles_dir = profiles`, `target = ci`), so the dbt templater renders models the
same way locally and in CI. The only excluded model is `fct_ghost_race_finish.sql`
(`.sqlfluffignore`) it exceeds sqlfluff's parse-depth limit and is hand-maintained.

Style fixes must not move model *output*. The **byte-stability oracle**
(`scripts/snapshot_model_hashes.py`) enforces that: it computes an order-independent
content hash of every materialized model and hard-fails (`--check`) if any `fct_*`
mart drifts from the committed baseline (`tests/model_hashes.baseline.json`). `duckdb`
is pinned in `requirements.txt` so the float-content hashes match across environments.
Treat the baseline like an approval test: when model *logic* changes intentionally,
regenerate it with `make lint-oracle-snapshot` and commit. The gate runs as CI
"Gate 1c" and in `make transform-check`.

## Fixtures

`fixtures/bronze/` contains small representative parquet files used by CI and by
`assert_no_future_leakage` (which loads a known stint and asserts exact values).
Three races are committed:
- Bahrain 2023 clean dry race, multiple compounds
- Italy 2020 low-energy circuit, sprint-style strategy
- São Paulo 2024 wet/mixed conditions

See [fixtures/README.md](fixtures/README.md) for how to refresh fixture files.
