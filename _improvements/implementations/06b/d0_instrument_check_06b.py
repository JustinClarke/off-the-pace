"""06b gate-1 instrument check.

Reproduces every number the leaf doc marks Verified 2026-09-07 for 06b out of the
warehouse, before anything is built on them. Read-only.

Run:  ./.venv/bin/python scratchpad/d0_instrument_check_06b.py
"""
from __future__ import annotations

import duckdb
import pandas as pd

DB = "data/dev.duckdb"
pd.set_option("display.width", 200)


def main() -> None:
    con = duckdb.connect(DB, read_only=True)

    print("=" * 78)
    print("CLAIM 1  the tax at a given following intensity is identical 2018 vs 2024")
    print("=" * 78)
    df = con.execute(
        """
        SELECT s.race_year,
               COUNT(*)                                       AS laps,
               AVG(d.dirty_air_intensity_lag1)                AS mean_intensity_lag1,
               MAX(d.dirty_air_tax_s)                         AS max_tax_s,
               MAX(d.dirty_air_tax_s / NULLIF(d.dirty_air_intensity_lag1, 0))
                                                              AS implied_theta,
               MIN(d.dirty_air_tax_s / NULLIF(d.dirty_air_intensity_lag1, 0))
                                                              AS implied_theta_min
        FROM int_dirty_air_tax_component AS d
        JOIN int_stint_geometry AS s USING (lap_id)
        GROUP BY 1 ORDER BY 1
        """
    ).df()
    print(df.to_string(index=False))

    print()
    print("=" * 78)
    print("CLAIM 2  dirty_air_share_lap support -- is the calibration regressor binary?")
    print("=" * 78)
    print(
        con.execute(
            "SELECT dirty_air_share_lap, COUNT(*) AS n FROM int_lap_air_state "
            "GROUP BY 1 ORDER BY 1"
        ).df().to_string(index=False)
    )
    print()
    print("distinct dirty_air_intensity_lag1 values shipped by the model:")
    print(
        con.execute(
            "SELECT DISTINCT dirty_air_intensity_lag1 FROM int_dirty_air_tax_component "
            "ORDER BY 1"
        ).df().to_string(index=False)
    )

    print()
    print("=" * 78)
    print("CLAIM 3  the degenerate-calibration hypothesis")
    print("=" * 78)
    print(
        "The model's calibration_panel filters `dirty_air_share_lag1 > 0`. If the\n"
        "regressor is binary that filter leaves a constant, VAR_POP = 0, the NULLIF\n"
        "returns NULL and COALESCE(..., 0.5) fires. Replaying the exact SQL:"
    )
    theta = con.execute(
        """
        WITH panel AS (
            SELECT f.lap_id,
                   (f.lap_time_s - COALESCE(fp.field_pace_smoothed_s, f.lap_time_s))
                     - f.weight_penalty_s AS partial_residual_s,
                   LAG(COALESCE(a.dirty_air_share_lap, 0.0), 1, 0.0) OVER (
                       PARTITION BY g.stint_id ORDER BY g.lap_in_stint
                   ) AS dirty_air_share_lag1
            FROM int_lap_fuel_state AS f
            JOIN int_stint_geometry AS g USING (lap_id)
            LEFT JOIN int_lap_air_state AS a USING (lap_id)
            LEFT JOIN int_field_pace_curve AS fp
              ON f.race_year = fp.race_year AND f.race_id = fp.race_id
             AND f.lap_number = fp.lap_number
            LEFT JOIN int_event_corrections AS c USING (lap_id)
            LEFT JOIN int_track_evolution AS e
              ON f.race_year = e.race_year AND f.race_id = e.race_id
             AND f.lap_number = e.lap_number
            WHERE f.lap_time_s IS NOT NULL
              AND COALESCE(c.correction_weight, 1.0) = 1.0
              AND COALESCE(e.rainfall_flag, FALSE) = FALSE
        )
        SELECT COUNT(*) AS calibration_n,
               VAR_POP(dirty_air_share_lag1) AS var_x,
               COVAR_POP(partial_residual_s, dirty_air_share_lag1) AS cov_xy,
               COALESCE(COVAR_POP(partial_residual_s, dirty_air_share_lag1)
                        / NULLIF(VAR_POP(dirty_air_share_lag1), 0), 0.5) AS theta_air
        FROM panel
        WHERE dirty_air_share_lag1 > 0 AND partial_residual_s IS NOT NULL
        """
    ).df()
    print(theta.to_string(index=False))

    con.close()


if __name__ == "__main__":
    main()
