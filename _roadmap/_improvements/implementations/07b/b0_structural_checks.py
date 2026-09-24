"""07b structural / coverage checks -- run BEFORE the pre-registration is written.

Per epistemics.md and 07a's own precedent: schema/coverage facts (row counts, NULL
rates, join resolution) may be established before pre-registering, as long as no
outcome-vs-instrument contrast is computed. This script computes zero contrasts.

Read-only against data/dev.duckdb.
"""
import duckdb
import numpy as np
import pandas as pd

con = duckdb.connect("/Users/justin/github/off-the-pace/data/dev.duckdb", read_only=True)

# ---------------------------------------------------------------------------
# 1. Gate-1 substitute: reproduce 07a's / 00b's headline before building on it.
# ---------------------------------------------------------------------------
q = """
WITH stints AS (
    SELECT stint_id, is_censored_stint FROM int_stint_end_regime
),
final_lap AS (
    SELECT stint_id, is_safety_car_lap, is_vsc_lap
    FROM int_stint_geometry
    QUALIFY ROW_NUMBER() OVER (PARTITION BY stint_id ORDER BY lap_in_stint DESC) = 1
)
SELECT
    s.is_censored_stint,
    COUNT(*) AS n_stints,
    SUM(CASE WHEN f.is_safety_car_lap OR f.is_vsc_lap THEN 1 ELSE 0 END) AS n_sc_vsc_end,
    AVG(CASE WHEN f.is_safety_car_lap OR f.is_vsc_lap THEN 1.0 ELSE 0.0 END) AS pct_sc_vsc_end
FROM stints s
JOIN final_lap f ON s.stint_id = f.stint_id
GROUP BY s.is_censored_stint
ORDER BY s.is_censored_stint
"""
print("=== Gate 1: reproduce 07a/00b headline ===")
print(con.execute(q).df())

# ---------------------------------------------------------------------------
# 2. Panel construction check -- match 07a's 90,597 / 6,967 / 5,360 exactly.
# ---------------------------------------------------------------------------
panel_q = """
WITH uncensored AS (
    SELECT stint_id FROM int_stint_end_regime WHERE is_censored_stint = FALSE
)
SELECT
    COUNT(*) AS n_moments,
    SUM(CASE WHEN g.is_safety_car_lap OR g.is_vsc_lap THEN 1 ELSE 0 END) AS n_z1_any,
    SUM(CASE WHEN g.is_red_flag_lap THEN 1 ELSE 0 END) AS n_red_flag_any,
    SUM(CASE WHEN g.is_red_flag_lap AND NOT (g.is_safety_car_lap OR g.is_vsc_lap) THEN 1 ELSE 0 END)
        AS n_red_flag_only,
    COUNT(DISTINCT g.stint_id) AS n_stints
FROM int_stint_geometry g
JOIN uncensored u ON g.stint_id = u.stint_id
"""
print("\n=== Panel size check ===")
print(con.execute(panel_q).df())

# pit moments = final lap of each uncensored stint
pit_q = """
WITH uncensored AS (
    SELECT stint_id FROM int_stint_end_regime WHERE is_censored_stint = FALSE
),
final_lap AS (
    SELECT g.stint_id, g.is_safety_car_lap, g.is_vsc_lap, g.is_red_flag_lap
    FROM int_stint_geometry g
    JOIN uncensored u ON g.stint_id = u.stint_id
    QUALIFY ROW_NUMBER() OVER (PARTITION BY g.stint_id ORDER BY g.lap_in_stint DESC) = 1
)
SELECT
    COUNT(*) AS n_pit_moments,
    SUM(CASE WHEN is_safety_car_lap OR is_vsc_lap THEN 1 ELSE 0 END) AS n_pit_under_z1,
    SUM(CASE WHEN is_red_flag_lap THEN 1 ELSE 0 END) AS n_pit_under_red_flag,
    SUM(CASE WHEN is_red_flag_lap AND NOT (is_safety_car_lap OR is_vsc_lap) THEN 1 ELSE 0 END)
        AS n_pit_under_red_flag_only
FROM final_lap
"""
print("\n=== Pit moment check ===")
print(con.execute(pit_q).df())

# red-flag-only control arm hazard, matching 07a's "103 moments, all stint ends"
rf_only_q = """
WITH uncensored AS (
    SELECT stint_id FROM int_stint_end_regime WHERE is_censored_stint = FALSE
),
moments AS (
    SELECT g.*,
        ROW_NUMBER() OVER (PARTITION BY g.stint_id ORDER BY g.lap_in_stint DESC) AS rn_from_end
    FROM int_stint_geometry g
    JOIN uncensored u ON g.stint_id = u.stint_id
)
SELECT
    COUNT(*) AS n_red_flag_only_moments,
    SUM(CASE WHEN rn_from_end = 1 THEN 1 ELSE 0 END) AS n_that_are_stint_end
FROM moments
WHERE is_red_flag_lap AND NOT (is_safety_car_lap OR is_vsc_lap)
"""
print("\n=== Red-flag-only moments (control-arm contamination, item 1) ===")
print(con.execute(rf_only_q).df())

# race_to_track resolution -- confirm 2018_14 missing, count affected uncensored risk-set moments
r2t_q = """
WITH uncensored AS (
    SELECT stint_id FROM int_stint_end_regime WHERE is_censored_stint = FALSE
)
SELECT g.race_year, g.race_id, COUNT(*) AS n_moments
FROM int_stint_geometry g
JOIN uncensored u ON g.stint_id = u.stint_id
WHERE g.race_id NOT IN (SELECT race_id FROM race_to_track)
GROUP BY g.race_year, g.race_id
"""
print("\n=== race_to_track unresolved races, uncensored risk-set moments (item 2) ===")
print(con.execute(r2t_q).df())

con.close()
