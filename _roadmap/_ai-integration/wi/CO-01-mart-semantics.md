# CO-01 — Mart semantics: teammate gap, field rank, positions gained

**Group:** 1 data settled · **Depends on:** none · **Blocker:** none.

**Sources:** `transform/models/marts/mart_race_driver_summary.sql`, `mart_driver_season_summary.sql`, `transform/models/marts/schema.yml`, `transform/models/intermediate/int_driver_race_skill_loro.sql`.

**Audit findings:** T3, T4, T5 (2026-10-15).

Three mart columns compute something other than their names say. AI-01 builds fact cards from these marts, so this lands first. No app page reads these marts yet, so nothing a fan sees today changes.

---

## What exists today (checked on dev, 2026-10-15)

1. **T3, teammate gap doubled.** `driver_skill_loro_s` is already `MEDIAN(own lap − teammate lap)`, so teammates' ratings are exact negatives. `teammate_gap_s = rating_s − teammate rating_s` (`mart_race_driver_summary.sql:99`) is therefore twice the gap: 3,138 of 3,138 race rows have `teammate_gap_s = 2 × rating_s` exactly. The season mart (`mart_driver_season_summary.sql:102`) does the same on the shrunk era rating; pairs sum to within 0.02 s of zero, so it is doubled to within that.
2. **T4, field rank labelled "fastest".** `rank` orders `rating_s` across the whole field (`mart_race_driver_summary.sql:53`, `mart_driver_season_summary.sql:60`) and `schema.yml:2368` says "1 = fastest". It ranks the gap to one's own teammate. "22nd of 22" means "furthest behind his teammate", not "slowest driver".
3. **T5, pit-lane starters lose places.** `positions_gained = grid_position − finish_position` (`mart_race_driver_summary.sql:37`) treats grid 0 as a slot: 35 rows, mean −13.2, worst −18.

## Method

1. `teammate_gap_s`: use the rating itself, since it already is the gap. For the season mart, confirm against `int_era_normalized_driver_rating` (WI-14b, F40) that the same holds, and handle seasons with more than one teammate explicitly.
2. Rename the rank columns (`rank`, `percentile`) or re-describe them so they say what they rank. Keep the values.
3. `positions_gained` is NULL when `grid_position = 0`. Say so in `schema.yml`.

## Acceptance

- Test: on every race row, `teammate_gap_s` equals minus the teammate's, and equals the paired median gap, not twice it.
- Test: `positions_gained IS NULL` wherever `grid_position = 0`.
- `schema.yml` text for the changed columns matches the SQL.

## Output

Rows changed per column, before and after, and one race worked by hand.

## Definition of done

Mart tests pass and both marts build on dev. Do not commit.
