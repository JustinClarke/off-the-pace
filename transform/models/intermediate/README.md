# Intermediate Models

The mathematical engine of the pipeline. These models apply physics corrections,
causal decomposition, and Bayesian shrinkage to produce clean driver-skill signals
and tyre-degradation estimates from raw lap data.

All models are materialised as **views** (no storage cost; recomputed on demand).

---

## Layer contract

- Sources: `{{ ref('stg_*') }}` and `{{ ref('dim_*') }}` only   never raw tables.
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
| `int_pit_strategy_value` | stint | Undercut/overcut strategy value estimate |
| `int_qualifying_decomposed` | lap | Qualifying pace decomposition |
| `int_lap_anomaly_flags` | lap | Anomaly classification (mistake, conditions, etc.) |
| `int_event_corrections` | lap | Manual correction weights from `stg_events` |
| `int_synthetic_teammate` | driver × race | Virtual teammate reference pace |
| `int_driver_circuit_affinity` | driver × circuit | Bayesian-shrunken circuit affinity |
| `int_driver_season_ratings` | driver × season | Posterior driver rating with CIs |
| `int_era_normalized_driver_rating` | driver × season | Era-bridged rating (anchor shrinkage) |
| `int_constructor_structural_pace` | constructor × race | Team power/aero index isolated from driver |
| `int_constructor_structural_pace_qualifying` | constructor × race | Constructor index for qualifying |
| `int_constructor_structural_pace_qualifying` | constructor × circuit | Constructor pace by circuit type |
| `int_circuit_x_constructor_interaction` | constructor × circuit | Interaction term: team vs. circuit characteristics |

---

## Key patterns

**Additive identity:** Every decomposition model satisfies:
```
total = fuel_component + compound_component + rubber_component
      + ambient_component + constructor_component + dirty_air_tax
      + driver_skill_residual  (± 0.0001 s)
```
This is enforced by singular tests in `tests/`.

**Bayesian shrinkage:** Use `{{ bayesian_shrinkage(...) }}` macro for all
panel-level estimates. Shrinks toward a zero-centred prior when sample size is small.
See `macros/README.md` for the exact conjugate formula.

**Clean lap predicate:** Use `{{ clean_lap_filter() }}` macro wherever driver skill
is extracted. This is the canonical definition of a "clean" lap   do not re-implement it inline.

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
