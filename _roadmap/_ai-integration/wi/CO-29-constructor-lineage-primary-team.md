# CO-29 — Team lineage, and one primary team per driver-season

**Status:** SPEC (nothing run). **Group:** 1 data settled · **Depends on:** none · **Blocker:** none. Raised 2026-10-23 from the CO-26 relationships tests and parquet trace.

**Sources:** `transform/models/reference/dim_constructors.sql`, `transform/models/marts/mart_corner_skill_driver.sql`, `transform/models/marts/schema.yml`, `transform/models/intermediate/schema.yml`.

## Problem

`mart_corner_skill_driver.sql:234` labels a driver-season with `STRING_AGG(DISTINCT constructor_id, ', ')`, so 6 published rows carry strings that are not constructors (CO-26's relationships test fails on them):

| Season | Driver | Label | Kind |
|---|---|---|---|
| 2018 | OCO, PER | Force India, Racing Point | Same team renamed mid-season |
| 2019 | GAS, ALB | Toro Rosso, Red Bull Racing | Real moves between two teams |
| 2025 | LAW, TSU | Red Bull Racing, Racing Bulls | Real moves between two teams |

The skill numbers are unaffected (the car-effect join uses the per-race constructor); only the label is wrong, and the app page does not show it.

Separately, `dim_constructors` is built from whichever laps are loaded and has no lineage, so on the CI fixture it lacks teams the frozen fits contain (CO-26 sets those two tests to warn on CI for this reason).

## Method

1. Add `constructor_lineage_id` to `dim_constructors` from a fixed list (next to the pu_mapping VALUES, or a seed): Force India → Racing Point → Aston Martin; Toro Rosso → AlphaTauri → RB → Racing Bulls; Sauber → Alfa Romeo / Alfa Romeo Racing → Kick Sauber; Renault → Alpine. Owner's ruling (2026-10-23): a rename is the same team.
2. Build `dim_constructors` from that fixed list, not from loaded laps, so the CI fixture has every team; then return the two `int_constructor_car_fe*` relationships tests to error on every target.
3. In `mart_corner_skill_driver`'s `driver_season` CTE, replace STRING_AGG with one primary team, `arg_max(constructor_id, n_cells)` (ties to the latest race), and add `constructors_driven` (ordered) so a move stays visible.

## Definition of done

`mart_corner_skill_driver.constructor_id` relationships test passes at error with no `where:`; the `int_constructor_car_fe*` tests pass at error on the CI fixture; the 6 rows show one team each, with the move listed. Do not commit.
