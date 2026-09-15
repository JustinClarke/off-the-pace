"""06b panel build. Read-only; writes two cached parquet files to scratchpad/.

Panel A (lap grain)    -- the shipped int_dirty_air_tax_component `panel` CTE, reproduced
                          exactly, plus the untreated laps the model's calibration drops.
Panel B (corner grain) -- Panel A's treatment joined to int_corner_skill_residuals.

The lag is computed over the FULL chronological stint sequence and only then filtered,
which is what the model does (`full_sequence_lag` runs on `geom`, not on `panel`).
Computing it after filtering gives a different treatment mean -- 0.1796 vs 0.1969 in 2018 --
so the per-season mean of D is the reproduction target.

Run:  ./.venv/bin/python scratchpad/d1_build_panels_06b.py
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

DB = "data/dev.duckdb"
OUT = Path("scratchpad")

# The shipped model's panel, with the lag taken over the full sequence first.
PANEL_SQL = """
WITH geom AS (
    SELECT stint_id, lap_id, race_year, race_id, driver_id, lap_number,
           lap_in_stint, is_pit_lap, is_safety_car_lap, is_vsc_lap, is_red_flag_lap
    FROM int_stint_geometry
),
full_sequence AS (
    SELECT g.lap_id,
           g.stint_id,
           LAG(COALESCE(a.dirty_air_share_lap, 0.0), 1, 0.0)
               OVER (PARTITION BY g.stint_id ORDER BY g.lap_in_stint) AS d_lag1,
           LEAD(COALESCE(a.dirty_air_share_lap, 0.0), 1, 0.0)
               OVER (PARTITION BY g.stint_id ORDER BY g.lap_in_stint) AS d_lead1,
           COALESCE(a.dirty_air_share_lap, 0.0)                       AS d_now,
           -- boundary proximity over the full sequence: any SC/VSC/red-flag/pit lap
           -- within +/- 2 laps of this one, inside the same stint.
           MAX(CASE WHEN g.is_safety_car_lap OR g.is_vsc_lap
                          OR g.is_red_flag_lap OR g.is_pit_lap
                    THEN 1 ELSE 0 END)
               OVER (PARTITION BY g.stint_id ORDER BY g.lap_in_stint
                     ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING)        AS near_boundary
    FROM geom AS g
    LEFT JOIN int_lap_air_state AS a ON g.lap_id = a.lap_id
)
SELECT f.lap_id,
       g.stint_id,
       f.race_year,
       f.race_id,
       f.driver_id,
       f.lap_number,
       g.lap_in_stint,
       (f.lap_time_s - COALESCE(fp.field_pace_smoothed_s, f.lap_time_s))
         - f.weight_penalty_s                       AS partial_residual_s,
       fs.d_lag1,
       fs.d_lead1,
       fs.d_now,
       fs.near_boundary,
       CASE WHEN g.lap_in_stint <= 5 THEN 'a01_05'
            WHEN g.lap_in_stint <= 10 THEN 'b06_10'
            WHEN g.lap_in_stint <= 15 THEN 'c11_15'
            WHEN g.lap_in_stint <= 20 THEN 'd16_20'
            WHEN g.lap_in_stint <= 25 THEN 'e21_25'
            ELSE 'f26_plus' END                     AS age_bin,
       f.driver_id || '|' || f.race_id              AS driver_race
FROM int_lap_fuel_state AS f
INNER JOIN int_stint_geometry AS g ON f.lap_id = g.lap_id
INNER JOIN full_sequence AS fs ON f.lap_id = fs.lap_id
LEFT JOIN int_field_pace_curve AS fp
       ON f.race_year = fp.race_year AND f.race_id = fp.race_id
      AND f.lap_number = fp.lap_number
LEFT JOIN int_event_corrections AS c ON f.lap_id = c.lap_id
LEFT JOIN int_track_evolution AS e
       ON f.race_year = e.race_year AND f.race_id = e.race_id
      AND f.lap_number = e.lap_number
WHERE f.lap_time_s IS NOT NULL
  AND COALESCE(c.correction_weight, 1.0) = 1.0
  AND COALESCE(e.rainfall_flag, FALSE) = FALSE
"""

# Corner classes, thresholds fixed in the pre-registration before any fit.
CORNER_SQL = """
WITH cls AS (
    SELECT race_year, race_id, track_id, corner_name,
           MEDIAN(v_min_kph) AS field_median_vmin_kph,
           COUNT(*)          AS corner_obs_n
    FROM int_corner_metrics
    WHERE v_min_kph IS NOT NULL
    GROUP BY 1, 2, 3, 4
),
classed AS (
    SELECT *,
           CASE WHEN field_median_vmin_kph < 125 THEN '1_slow'
                WHEN field_median_vmin_kph < 200 THEN '2_medium'
                ELSE '3_fast' END AS corner_class,
           NTILE(3) OVER (PARTITION BY race_id ORDER BY field_median_vmin_kph)
                                 AS corner_tercile_in_race
    FROM cls
)
SELECT r.corner_id,
       r.lap_id,
       r.driver_id,
       r.race_id,
       r.race_year,
       r.corner_name,
       r.track_id,
       r.corner_residual_total_s,
       r.braking_loss_s,
       r.mid_corner_residual_s,
       r.exit_residual_s,
       c.corner_class,
       c.corner_tercile_in_race,
       c.field_median_vmin_kph,
       r.driver_id || '|' || r.race_id || '|' || r.corner_name AS driver_race_corner
FROM int_corner_skill_residuals AS r
INNER JOIN classed AS c
        ON r.race_id = c.race_id AND r.corner_name = c.corner_name
WHERE r.corner_residual_total_s IS NOT NULL
"""


def main() -> None:
    con = duckdb.connect(DB, read_only=True)

    lap = con.execute(PANEL_SQL).df()
    lap = lap[lap["partial_residual_s"].notna()].copy()
    print(f"Panel A (lap grain): {len(lap):,} rows")

    # --- reproduction target: per-season mean of D must match the shipped table ---
    shipped = con.execute(
        """
        SELECT s.race_year, AVG(d.dirty_air_intensity_lag1) AS shipped_mean
        FROM int_dirty_air_tax_component AS d
        JOIN int_stint_geometry AS s USING (lap_id)
        GROUP BY 1 ORDER BY 1
        """
    ).df()
    mine = lap.groupby("race_year")["d_lag1"].agg(["mean", "size"]).reset_index()
    chk = shipped.merge(mine, on="race_year")
    chk["abs_diff"] = (chk["shipped_mean"] - chk["mean"]).abs()
    print("\nGATE 1 reproduction of the shipped treatment mean, by season:")
    print(chk.to_string(index=False))
    ok = bool((chk["abs_diff"] < 1e-9).all())
    print(f"\nreproduces to 1e-9: {ok}")
    if not ok:
        raise SystemExit("PANEL DOES NOT REPRODUCE THE SHIPPED TREATMENT -- stop.")

    corner = con.execute(CORNER_SQL).df()
    print(f"\nPanel B (corner grain): {len(corner):,} rows")

    # Attach the lap-level treatment and controls to the corner panel.
    keep = ["lap_id", "stint_id", "lap_in_stint", "age_bin", "d_lag1", "d_lead1",
            "near_boundary"]
    corner = corner.merge(lap[keep], on="lap_id", how="inner")
    print(f"Panel B after joining the lap treatment: {len(corner):,} rows")
    print(corner.groupby(["race_year", "corner_class"]).size().unstack(fill_value=0)
          .to_string())

    lap.to_parquet(OUT / "panel_06b_lap.parquet", index=False)
    corner.to_parquet(OUT / "panel_06b_corner.parquet", index=False)
    print("\nwrote scratchpad/panel_06b_lap.parquet, scratchpad/panel_06b_corner.parquet")
    con.close()


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    main()
