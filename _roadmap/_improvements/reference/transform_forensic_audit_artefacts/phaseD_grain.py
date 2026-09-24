"""Declared-key uniqueness for every mart join source + main models. cwd transform/ (stg views)."""
import duckdb, csv, sys
c = duckdb.connect("../data/dev.duckdb", read_only=True)
checks = [
 ("stg_laps", "lap_id", "one row per recorded race lap"),
 ("stg_laps_qualifying", "lap_id", "one row per qualifying lap"),
 ("stg_results", "race_year, race_id, driver_id", "one row per driver x race"),
 ("stg_results_qualifying", "race_year, race_id, driver_id", "one row per driver x quali"),
 ("stg_weather", "lap_id", "one row per lap_id (per-driver)"),
 ("stg_sector_times", "sector_id", "sector_id unique (schema test)"),
 ("stg_pits", "race_year, race_id, driver_id, pit_in_lap_number", "one row per pit stop"),
 ("int_stint_geometry", "lap_id", "lap grain"),
 ("int_lap_residual_decomposed", "lap_id", "lap grain (mart spine)"),
 ("int_lap_anomaly_flags", "lap_id", "lap grain"),
 ("int_compound_cliff_predicted", "lap_id", "lap grain"),
 ("int_lap_thermal_proxy", "lap_id", "lap grain"),
 ("int_lap_air_state", "lap_id", "lap grain"),
 ("int_lap_proximity", "lap_id", "lap grain"),
 ("int_lap_corner_inputs", "lap_id", "lap grain"),
 ("int_lap_corner_drift", "lap_id", "lap grain"),
 ("int_event_corrections", "lap_id", "lap grain"),
 ("int_lap_telemetry_aggregates", "lap_id", "lap grain"),
 ("int_lap_fuel_state", "lap_id", "lap grain"),
 ("int_field_pace_curve", "race_year, race_id, lap_number", "race x lap"),
 ("int_track_evolution", "race_year, race_id, lap_number", "race x lap"),
 ("int_qualifying_driver_summary", "race_year, race_id, driver_id", "driver-weekend (broadcast)"),
 ("int_sc_hazard_history", "circuit_slug, season", "circuit x season (broadcast)"),
 ("int_lap_residual_stint_detrend", "stint_id", "stint"),
 ("int_constructor_structural_pace", "race_year, race_id, constructor_id", "constructor x race"),
 ("race_to_track", "race_id", "seed: race -> track"),
 ("dim_circuits", "circuit_key", "circuit_key"),
 ("dim_compounds_season", "circuit_key, compound_code, season", "circuit x compound x season"),
 ("dim_constructors", "constructor_id", "constructor"),
 ("dim_drivers", "driver_id", "driver"),
 ("dim_events", "race_year, race_id, driver_id, event_type", "per header"),
 ("fct_cliff_prediction_features", "lap_id", "one row per valid race lap"),
 ("fct_stint_features", "stint_id", "one row per stint"),
 ("fct_lap_residuals", "lap_id", "lap grain"),
 ("fct_ghost_car_pace", "host_constructor_id, race_id, driver_id, lap_number", "scenario x lap?"),
 ("fct_ghost_race_finish", "host_constructor_id, race_id, driver_id", "(host constructor, race, driver)"),
 ("fct_driver_skill_features", "race_year, race_id, driver_id", "driver x race"),
]
rows = []
for t, key, decl in checks:
    try:
        n, nk = c.sql(f"select count(*), count(distinct ({key})) from {t}").fetchone()
        nnull = c.sql(f"select count(*) from {t} where " + " or ".join(f"{k.strip()} is null" for k in key.split(","))).fetchone()[0]
        rows.append((t, key, decl, n, nk, n - nk, nnull))
    except Exception as e:
        rows.append((t, key, decl, "ERR", str(e)[:90], "", ""))
w = csv.writer(open(sys.argv[1], "w")); w.writerow(["model","key","declared","rows","distinct_keys","dup_rows","null_key_rows"]); w.writerows(rows)
for r in rows: print(" | ".join(str(x) for x in r))
