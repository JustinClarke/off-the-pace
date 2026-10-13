# Intermediate Models

The mathematical engine of the pipeline. These models apply physics corrections,
causal decomposition, and Bayesian shrinkage to produce clean driver-skill signals
and tyre-degradation estimates from raw lap data.

All models are materialised as **tables**, except `int_lap_fuel_state_qualifying`, which is a view.

---

## Layer contract

- Sources: `{{ ref('stg_*') }}` and `{{ ref('dim_*') }}` only  -  never raw tables.
- No presentation logic (rounding, formatting)   that lives in marts.
- Every additive decomposition must pass the corresponding identity-closure singular test.

---

## Model map

| Model | Grain | Purpose |
|---|---|---|
| `int_stint_geometry` | lap | Tyre age, stint number, in/out-lap flags |
| `int_lap_fuel_state` | lap | Fuel-burnoff weight correction (race) |
| `int_lap_fuel_state_qualifying` | lap | Fuel correction for qualifying runs |
| `int_lap_air_state` | lap | Dirty-air exponential-weighted thermal load |
| `int_dirty_air_tax_component` | lap | Causal pace-delta attributed to dirty air |
| `int_lap_thermal_proxy` | lap | Push-load EW cumulative thermal state |
| `int_corner_metrics` | lap × sector | Per-sector traction and braking metrics |
| `int_corner_skill_residuals` | lap × sector | Sector-level skill residuals |
| `int_track_evolution` | lap | Rubber-in lap progression (track grip index) |
| `int_compound_cliff_predicted` | lap | Expected compound pace curve (from seeds) |
| `int_field_pace_curve` | lap | Field-median smoothed pace reference |
| `int_lap_residual_decomposed` | lap | Full additive decomposition (race) |
| `int_lap_residual_decomposed_qualifying` | lap | Full additive decomposition (qualifying) |
| `int_sector_residual_decomposed` | lap × sector | Sector-grain decomposition |
| `int_pit_strategy_cost_curve` | stint × horizon × candidate lap | `Total_Cost(L)` surface: wear on each set, plus SC-discounted pit loss |
| `int_pit_strategy_value` | stint | Optimal pit lap (argmin of the cost curve) and the verdict on the actual one |
| `int_qualifying_decomposed` | lap | Qualifying pace decomposition |
| `int_lap_anomaly_flags` | lap | Anomaly classification (mistake, conditions, etc.) |
| `int_event_corrections` | lap | Manual correction weights from `stg_events` |
| `int_synthetic_teammate` | driver × race | Virtual teammate reference pace |
| `int_driver_circuit_affinity` | driver × circuit | Bayesian-shrunken circuit gap to the teammate; `affinity_vs_driver_mean_s` = deviation from the driver's own mean (the drawn affinity, F44) |
| `int_driver_season_ratings` | driver × season | Posterior season rating with CIs: median lap-by-lap gap to the teammate (F40), shrunk toward the season mean |
| `int_era_normalized_driver_rating` | driver × season | Published season rating; no era offset (teammate-relative, F45), bridge-driver shift kept as a diagnostic |
| `int_constructor_structural_pace` | constructor × race | Team power/aero index isolated from driver |
| `int_constructor_structural_pace_qualifying` | constructor × race | Constructor index for qualifying |
| `int_circuit_x_constructor_interaction` | constructor × circuit | Interaction term: team vs. circuit characteristics |
| `int_constructor_car_fe` | constructor × race | De-biased car pace: the constructor × race fixed effect from a two-way FE fit (reads `data/fits/`) |
| `int_constructor_deg_sensitivity` | season × constructor × compound | How fast a team's tyres degrade against the field, empirical-Bayes shrunk |
| `int_driver_circuit_era_affinity` | driver × circuit × era | Circuit affinity split at the 2022 regulation boundary |
| `int_driver_race_skill_loro` | driver × race | Equal-car race rating: median lap-by-lap gap to the teammate |
| `int_lap_normalized_pace` | lap | Lap pace with the dirty-air cost removed, so traffic laps stay usable for wear fits |
| `int_lap_residual_stint_detrend` | stint | Pre-cliff linear drift of the skill residual, used to detrend the degradation target |
| `int_lap_telemetry_aggregates` | lap | Powertrain aggregates and within-stint cliff signals from car telemetry |
| `int_lap_proximity` | lap | Pairwise track gaps from the telemetry position channel (the `proximity` ML features) |
| `int_lap_corner_inputs` | lap | Corner residuals rolled up from lap × corner to lap grain |
| `int_corner_drift_from_early_stint` | lap × corner | Corner residuals measured against the stint's first six laps (drift) |
| `int_lap_corner_drift` | lap | Corner drift rolled up to lap grain |
| `int_track_geometry` | season × circuit × 25 m bin | Gradient and curvature from X/Y/Z telemetry |
| `int_tyre_surface_vs_bulk_decoupling` | lap (post-cliff) | Whether post-cliff degradation is surface-recoverable or structural |
| `int_stint_end_regime` | stint | Track regime on the stint's final lap (green, VSC, safety car, red flag), so neutralised stops separate from tyre-driven ones |
| `int_sc_hazard_history` | circuit × season | Safety-car hazard per racing lap, estimated from earlier seasons only |
| `int_pit_loss_circuit` | circuit | Empirical pit-lane loss prior read by `int_pit_strategy_value` |
| `int_qualifying_segments` | race × segment | Q1/Q2/Q3 windows recovered from the session-status timeline |
| `int_qualifying_push_laps` | qualifying lap | Segment assignment and the push-lap gate |
| `int_qualifying_driver_summary` | driver × race | Driver-weekend qualifying summary (the `qualifying` ML features) |
| `int_driver_isolation_lap_panel` | lap | Driver isolation step 0: the clean-lap panel and field-centred isolated time |
| `int_constructor_car_fe_isolation` | constructor × race | Driver-isolation car term, fitted per era on pre-cliff clean laps (reads `data/fits/`) |
| `int_driver_isolation_lap_pace` | lap | Isolated pace with the car removed; positive = faster |
| `int_driver_isolation_lap_values` | lap | Pure-skill rating per lap, with the declared season offset |
| `int_driver_isolation_stint_tyre` | stint | Stint pace line on tyre age, the leave-driver-out peer slope, and the car's degradation character |
| `int_power_law_lap` | lap | The shared lap set every power-law tyre-curve fit and grading reads |
| `int_stint_power_law_fit` | stint | Per-stint power-law fit `y = intercept + alpha · age^beta` (descriptive) |
| `int_cell_power_law_fit` | race × compound hardness rank | Pooled power-law fit; the training target for the power-law model |

---

## Key patterns

**Additive identity:** The race-lap decomposition satisfies:
```
pace_delta = fuel_component + compound_component + constructor_component
           + dirty_air_tax + driver_skill_residual  (± 0.0001 s)
```
Rubber and ambient are inside `base_track_pace_s` and are informational columns, not terms.
The qualifying decomposition still carries them as separate terms (seven in all). Both are
enforced by singular tests in `tests/`.

**Bayesian shrinkage:** Use `{{ bayesian_shrinkage(...) }}` macro for all
panel-level estimates. Shrinks toward a zero-centred prior when sample size is small.
See `macros/README.md` for the exact conjugate formula.

**Clean lap predicate:** Use `{{ clean_lap_filter() }}` macro wherever driver skill
is extracted. This is the canonical definition of a "clean" lap  -  do not re-implement it inline.

---

## Exploring this layer

```bash
# Materialize all intermediate models
dbt run --selector intermediate_only --profiles-dir profiles --target dev

# Run only the identity-closure tests
dbt test --selector math_tests --profiles-dir profiles --target dev

# Browse the full lineage
dbt docs generate --profiles-dir profiles && dbt docs serve
```
