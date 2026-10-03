"""W33 follow-up measurements on a (rebuilt) warehouse, read-only.

1. Season level of pure skill (sizes the Option A offset).
2. Tier-3 age adjustment: pooled within-pair variance of raw - k * dC for a grid of k,
   using the validator's exact design (race, unordered pair, >= 3 pair-laps, 2018-2024).
"""
import sys
import duckdb

db = sys.argv[1] if len(sys.argv) > 1 else "data/dev.duckdb"
con = duckdb.connect(db, read_only=True)

print("== fit method on the warehouse ==")
print(con.sql("SELECT fit_method, car_term_source, COUNT(*) n FROM int_constructor_car_fe_isolation GROUP BY ALL ORDER BY ALL").df().to_string(index=False))

print("\n== season level of pure (fct_driver_isolation_race, and pre-cliff laps) ==")
print(con.sql("""
    WITH r AS (
        SELECT race_year, AVG(pure_skill_gain_s) AS mean_race_pure,
               SUM(pure_skill_gain_s * n_pure_laps) / SUM(n_pure_laps) AS lapw_race_pure,
               COUNT(pure_skill_gain_s) AS n_rated, COUNT(*) AS n_driver_races
        FROM fct_driver_isolation_race GROUP BY race_year
    ),
    l AS (
        SELECT race_year, AVG(CASE WHEN tyre_phase = 'cliff' THEN 1.0 ELSE 0.0 END) AS cliff_share,
               AVG(CASE WHEN NOT pure_is_extrapolated THEN pure_skill_gain_s END) AS mean_lap_pure_precliff
        FROM int_driver_isolation_lap_values GROUP BY race_year
    )
    SELECT * FROM r JOIN l USING (race_year) ORDER BY race_year
""").df().round(4).to_string(index=False))

print("\n== pure-less driver-races by reason ==")
print(con.sql("""
    SELECT COALESCE(car_term_source, '<null>') AS car_term_source,
           COUNT(*) AS n, COUNT(*) FILTER (WHERE pure_skill_gain_s IS NULL) AS n_pure_null
    FROM fct_driver_isolation_race GROUP BY ALL ORDER BY n DESC
""").df().to_string(index=False))
print(con.sql("""
    SELECT COUNT(*) AS driver_races, COUNT(*) FILTER (WHERE pure_skill_gain_s IS NULL) AS no_pure
    FROM fct_driver_isolation_race
""").df().to_string(index=False))
print(con.sql("""
    SELECT car_term_source, race_year, constructor_id, COUNT(*) AS driver_races,
           STRING_AGG(DISTINCT driver_id, ',' ORDER BY driver_id) AS drivers
    FROM fct_driver_isolation_race WHERE car_term_source = 'unidentified'
    GROUP BY ALL ORDER BY race_year, constructor_id
""").df().to_string(index=False))
print(con.sql("""
    SELECT pure_skill_gain_s IS NULL AS no_pure, car_term_source, n_pure_laps = 0 AS zero_pure_laps, COUNT(*) n
    FROM fct_driver_isolation_race WHERE pure_skill_gain_s IS NULL OR car_term_source <> 'driver_id'
    GROUP BY ALL ORDER BY ALL
""").df().to_string(index=False))

print("\n== tier-3 age adjustment: pooled within-pair variance of raw - k*dC ==")
base = """
    WITH p AS (
        SELECT race_id, driver_id, peer_driver_id, relative_pace_raw_gain_s AS raw,
               relative_pace_raw_gain_s - relative_pace_gain_s AS dc, stint_phase, peer_stint_phase
        FROM fct_driver_isolation_pair_lap
        WHERE driver_id < peer_driver_id AND race_year BETWEEN 2018 AND 2024
          AND relative_pace_gain_s IS NOT NULL AND relative_pace_raw_gain_s IS NOT NULL {extra}
    ),
    g AS (
        SELECT race_id, driver_id, peer_driver_id, COUNT(*) AS n,
               VAR_SAMP(raw) * (COUNT(*) - 1) AS ss_raw,
               VAR_SAMP(dc) * (COUNT(*) - 1) AS ss_dc,
               COVAR_SAMP(raw, dc) * (COUNT(*) - 1) AS sp
        FROM p GROUP BY ALL HAVING COUNT(*) >= 3
    )
    SELECT SUM(ss_raw) / SUM(n - 1) AS v_raw, SUM(ss_dc) / SUM(n - 1) AS v_dc,
           SUM(sp) / SUM(n - 1) AS cv, COUNT(*) AS n_pairs, SUM(n) AS n_laps
    FROM g
"""
for label, extra in [("all pair-laps (the V3 tier-3 ii design)", ""),
                     ("both laps pre-cliff", "AND stint_phase <> 'cliff' AND peer_stint_phase <> 'cliff'")]:
    try:
        r = con.sql(base.format(extra=extra)).df().iloc[0]
    except Exception as e:  # peer_stint_phase may be named differently
        print(label, "ERROR", e)
        continue
    print(f"-- {label}: pairs {int(r.n_pairs)}, pair-laps {int(r.n_laps)}")
    kstar = r.cv / r.v_dc if r.v_dc > 0 else float('nan')
    for k in (0.0, 0.5, 0.966, 1.0, kstar):
        v = r.v_raw - 2 * k * r.cv + k * k * r.v_dc
        print(f"   k={k:6.3f}  var={v:.5f}  vs raw {100 * (v / r.v_raw - 1):+.2f}%")
    print(f"   break-even k (adjusted == raw): {2 * kstar:.3f}; variance-minimising k*: {kstar:.3f}")
