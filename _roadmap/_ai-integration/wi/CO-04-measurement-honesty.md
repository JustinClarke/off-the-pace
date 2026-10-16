# CO-04 — Measurement honesty: missing telemetry, safety-car smoothing, thin cells

**Group:** D carry-over · **Depends on:** none · **Blocker:** none.

**Sources:** `transform/models/intermediate/int_lap_air_state.sql`, `int_field_pace_curve.sql`, `int_lap_residual_decomposed.sql`.

**Audit findings:** 5, 6; T7 as a check-run.

Label-moving: it rides the single version bump in CO-03.

---

## What exists today (checked on dev, 2026-10-15)

1. **FD6 ruled but not built (finding 5).** FD6 ruled B: a missing measurement is NULL, not a guess. `int_lap_air_state.sql` still writes 'free_air' for a NULL gap (line 144) and coalesces to 0.0 / 'free_air' (213, 219, 221). Laps with no gap: 2018 13.4%, every other season 4.9–5.1%.
   **Most of those NULLs are correct.** Outside 2018, 98–100% of NULL-gap laps are the race leader, who has no car ahead and really is in free air. The defect is 2018's non-leader NULLs, 8.1% of its laps (Australia and Bahrain have no position telemetry at source, per FD6). A blanket NULL would wrongly blank every leader lap in all eight seasons.
2. **W43, smoother crosses safety cars (finding 6).** `int_field_pace_curve.sql:154` is still `ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING` with no boundary. W43 measured −0.70 s on restart laps.
3. **W44, thin cells used anyway (finding 6).** `int_field_pace_curve` sets `low_sample_flag` (fewer than 5 cars) and `int_lap_residual_decomposed.sql` never reads it.
4. **T7.** `air_state_dominant` is `MODE()` over three sectors (`int_lap_air_state.sql:185`), so it picks arbitrarily when all three differ.

## Method

1. NULL the air state and dirty-air terms only where the car is not the leader and the gap is missing. Leader laps stay 'free_air'.
2. Stop the smoothing window at safety-car, VSC and red-flag boundaries.
3. Thin cells: NULL the field base below 5 cars, the same "NULL, not a guess" rule as F1 and FD6. This is an assumption, not a ruling. If it moves more labels than W44's estimate (702 labels by more than 2 s), show the user before CO-03.
4. **T7 check-run.** Count training-eligible laps where all three sector states differ. If more than 1%, add a deterministic tie-break; otherwise record the count.

## Acceptance

- Test: no non-leader lap with a missing gap takes 'free_air' or 0.0; leader laps are unchanged.
- Test: on a known safety-car race, no smoothed cell averages across the neutralised laps.
- Test: no residual uses a cell with `low_sample_flag` set.

## Output

Per season: laps NULLed, cells NULLed, labels moved by more than 0.5 s; the T7 count.

## Definition of done

Tests pass and the per-season counts are recorded. Do not commit.
