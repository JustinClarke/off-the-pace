# Tests

Singular SQL tests that encode domain constraints too complex for schema YAML.
All run as part of `dbt test` (or `make dbt-test`).

## Identity-Closure Tests (§3.4 Catalogue)

These tests enforce the mathematical identities that the transform layer must satisfy. See [`06_residual_layer.md`](../../docs/docs/learn-dbt/06_residual_layer.md) for the complete catalogue, rationale, and forward-reference tests.

| File | Identity | Group | Status |
|---|---|---|---|
| `assert_residual_decomposition_identity.sql` | First: 6-term lap residual | First | ✅ Active |
| `assert_lap_7term_identity.sql` | First: 7-term lap residual (dirty air extracted) | First | 🔲 First Group |
| `assert_sector_residual_identity.sql` | Second: sector-grain identity | Second | 📝 Placeholder |
| `assert_sector_aggregates_to_lap.sql` | Second: sector-to-lap re-aggregation | Second | 📝 Placeholder |
| `assert_qualifying_7term_identity.sql` | Third: qualifying 7-term identity | Third | 📝 Placeholder |
| `assert_ghost_car_self_consistency.sql` | Third: ghost-car degenerate identity | Third | 📝 Placeholder |
| `assert_affinity_shrinkage_bounds.sql` | Fourth: shrinkage bounds (circuit affinity) | Fourth | 📝 Placeholder |
| `assert_era_rating_shrinkage_bounds.sql` | Fourth: shrinkage bounds (era rating) | Fourth | 📝 Placeholder |

**Placeholder tests** (subsequent groups) return `SELECT 1 WHERE FALSE` until their corresponding model is available. Once the model lands, uncomment the actual test logic.

## Domain Constraint Tests

| File | What it asserts | Models tested |
|---|---|---|
| `assert_stint_boundary_integrity.sql` | Fuel state, thermal proxy, and air state all reset correctly at stint boundaries | `int_lap_fuel_state`, `int_lap_thermal_proxy`, `int_lap_air_state` |
| `assert_no_future_leakage.sql` | Trailing window functions use only past laps-no look-ahead in EW averages | `int_lap_thermal_proxy`, `int_lap_air_state` |
| `assert_synthetic_teammate_identity.sql` | Self-match driver_skill_proxy ≈ 0 when ego and teammate are the same driver | `int_synthetic_teammate` |
| `assert_field_pace_honest_range.sql` | Field pace curve stays within ±5s of overall race median | `int_field_pace_curve` |
| `assert_mad_floor.sql` | MAD scale estimator is floored at 0.10s (prevents cliff self-masking) | `int_lap_anomaly_flags` |
| `assert_pos_degradation.sql` | Positive degradation detected in representative high-wear stints | `int_compound_cliff_predicted` |
| `assert_track_evolution_monotone.sql` | Rubber-in evolution is monotonically non-negative within a race | `int_track_evolution` |
| `assert_constructor_confidence_monotone.sql` | Constructor index confidence increases with lap count (more data = more confidence) | `int_constructor_pace_index` |
| `assert_driver_skill_residual_reasonable.sql` | Driver skill residual distribution per race is centred near 0 (mean < ±1s) | `int_lap_residual_decomposed` |

## Fixtures

`fixtures/bronze/` contains small representative parquet files used by CI and by
`assert_no_future_leakage` (which loads a known stint and asserts exact values).
Three races are committed:
- Bahrain 2023-clean dry race, multiple compounds
- Italy 2020-low-energy circuit, sprint-style strategy
- São Paulo 2024-wet/mixed conditions

See [fixtures/README.md](fixtures/README.md) for how to refresh fixture files.
