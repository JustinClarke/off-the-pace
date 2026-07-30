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
| `assert_sector_aggregates_to_lap.sql` | Sector-to-lap re-aggregation | | 📝 Placeholder |
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
| `assert_track_evolution_monotone.sql` | Rubber-in evolution is monotonically non-negative within a race | `int_track_evolution` | ✅ Active |
| `assert_sc_hazard_probability_bounds.sql` | Per-lap SC/VSC/any hazard rates are valid probabilities in [0, 1] and `any` ≥ each component | `int_sc_hazard_history` | ✅ Active |
| `assert_driver_skill_residual_reasonable.sql` | Driver-skill residual per race is centred near 0 (mean < ±1s) | `fct_lap_residuals` | ✅ Active |
| `assert_raw_laps_has_both_sessions.sql` | Both race (`stg_laps`) and qualifying (`stg_laps_qualifying`) laps are present with data | `stg_laps`, `stg_laps_qualifying` | ✅ Active |
| `assert_p_beats_next_geq_half.sql` | Pairwise consistency: `p_beats_next` ≥ 0.5 for adjacently-ranked drivers (ranked by ascending predicted pace) | `fct_ghost_race_finish` | ✅ Active |
| `assert_constructor_coefficient_signs.sql` | Every season has at least one constructor genuinely faster than the field (`MIN(constructor_structural_pace_s) < 0`) and at least one identified (non-degenerate) CI | `int_constructor_structural_pace` | ✅ Active |
| `assert_constructor_confidence_monotone.sql` | Constructor-index confidence increases with lap count (more data ⇒ more confidence) | `int_constructor_structural_pace` | 📝 Placeholder (superseded by a `dbt_expectations` pair test in `schema.yml` after `int_constructor_pace_index` was folded into `int_constructor_structural_pace`) |
| `assert_cliff_stints_have_falloff.sql` | Informational (non-blocking): flags stints with a detected cliff but minimal end-of-stint pace falloff | | 📝 Placeholder |
| `assert_aero_penalty_negative.sql` | Dirty-air tax is always a penalty, never a bonus (`dirty_air_tax_s` ≥ 0, positive = slower) | `int_dirty_air_tax_component` | ✅ Active |
| `assert_thermal_variance_positive.sql` | Track temperature genuinely varies within a race (range ≥ 0.1 °C), catching a stalled or missing thermal join | `int_track_evolution` | ✅ Active |
| `assert_fuel_curve_monotonicity.sql` | Fuel weight penalty strictly decreases as fuel burns off within a stint | `int_lap_fuel_state` | ✅ Active |
| `assert_stint_boundaries_correct.sql` | `age_in_stint` increases strictly with lap number inside a stint (off-by-one guard near pit stops) | `int_lap_residual_decomposed` | ✅ Active |
| `assert_pace_delta_flat_by_race_fifth.sql` | `pace_delta_s` carries no within-race fuel trend on the field curve's own eligible panel: every fifth of race distance sits within 0.15s of the panel mean | `int_lap_fuel_state`, `int_field_pace_curve` | ✅ Active |
| `assert_affinity_min_races.sql` | No era-segmented affinity is published from fewer than 2 races at that circuit | `int_driver_circuit_era_affinity` | ✅ Active |
| `assert_rating_confidence.sql` | No global LORO confidence collapse: drivers with ≥ 5 races keep `rating_confidence` ≥ 0.3 | `int_driver_season_ratings` | ✅ Active |
| `assert_rating_top_season_well_supported.sql` | Results-anchored: the top-rated driver-season of all time rests on ≥ 10 races, not a small-sample artifact. Self-limiting on warehouses too thin to test (fires only once some season could clear the bar) | `int_era_normalized_driver_rating` | ✅ Active |
| `assert_corner_skill_cell_winsorized.sql` | Season corner-skill means stay inside the ±1.0s per-cell winsorization bound (a lap-weighted mean of winsorized cells cannot exceed it) | `mart_corner_skill_driver` | ✅ Active |
| `assert_corner_skill_phase_gate.sql` | A phase z-score needs ≥ 30 cells, and `corner_skill_index` needs all three phases populated | `mart_corner_skill_driver` | ✅ Active |
| `assert_cliff_predictions_valid.sql` | `expected_compound_pace_s` never rests on the 0.0/0.5 default sentinels, catching a silently failed seed join | `int_compound_cliff_predicted` | ✅ Active |
| `assert_cliff_seed_severity_bounded.sql` | Cliff-seed tripwire: fitted severity ≤ 1.6 s/lap, and the cross-season fallback never fires from fewer than 8 real stints | `compound_cliff_params` (seed) | ✅ Active |
| `assert_ghost_recombination.sql` | Ghost lap-time predictions stay within ±10s of the actual lap (fuel-envelope and interpolation guard) | `fct_ghost_car_pace` | ✅ Active |
| `assert_ghost_self_scenario_rank.sql` | Results-anchored: self-scenario ghost pace recovers official finishing order (mean per-race Spearman ρ ≥ 0.5, no race negatively correlated). Validates recombination pace, not the counterfactual car swap | `fct_ghost_race_finish`, `stg_results` | ✅ Active |

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
