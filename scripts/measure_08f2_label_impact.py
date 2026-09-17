"""08f-2 isolation probe -- does the circuit x constructor interaction rebuild
change the model's LABELS, not just a barred feature?

WHY THIS EXISTS. `08f-2` rebuilt `int_circuit_x_constructor_interaction.sql` from
season-pooled GROUP BYs to point-in-time expanding windows (leaf doc
`_improvements/work/08-foundations-repair.md`, section `08f`, ~line 517). That
fix is already built and already live -- this script does not change it. What
had never been measured: `driver_skill_residual_s` (fed by
`circuit_constructor_interaction_s` via `constructor_component_s`) is barred
from ever being a model INPUT (`ml/src/schema.py::EXCLUDED_LEAKAGE_COLUMNS`,
"causal leakage"), but IS consumed inside `fct_cliff_prediction_features.sql`
to CONSTRUCT several of the model's target/label columns
(`next_3_lap_cumulative_jump_s`, `next_5_lap_cumulative_jump_s` ==
`DEGRADATION_TARGET`, `drift_s_per_lap`, `laps_until_cliff_class` ==
`CLIFF_TARGET`). Nobody had quantified how much 08f-2 moves those labels.

This is NOT the six-gate process in `_improvements/foundations/gates.md` --
no add-ablation, no permutation-null, no e-values. It is a single row-matched
before/after diff, isolating 08f-2 alone.

METHOD (manual steps, run once; this script is the read-only analysis half).

1. Add a scratch `gate_before` dbt target to `transform/profiles/profiles.yml`,
   pointed at `../data/gate_before.duckdb` (never `dev.duckdb` -- sources are
   `external_location` bronze parquet paths, independent of target). Same
   shape as `08g`'s `gate_before` target
   (`_improvements/work/08-foundations-repair.md` ~line 1071).

   dbt seed --select circuit_reference compound_cliff_params race_to_track \\
       seed_manual_lap_exceptions --target gate_before
   dbt run --select +fct_cliff_prediction_features --target gate_before

   (39 ancestor models -- the mart's whole lineage, not all 74 project
   models; `dbt ls --select +fct_cliff_prediction_features` confirms the
   count.) Export the AFTER (current, shipped) snapshot -- see `export()`
   below for the exact columns/tables.

2. Find the correct pre-08f-2 commit for THIS file specifically -- do not
   reuse `08g`'s c7c8509 (that revert was for `08e`+`08f-2` COMBINED across
   TWO files, and verified-by-diff here to predate an unrelated fix to this
   same file, the circuit_id physical-venue pooling change). The right commit
   is whatever immediately precedes the commit that actually introduced the
   point-in-time windows -- verify with:

   git log --follow --format='%h %ad %s' --date=short -- \\
       transform/models/intermediate/int_circuit_x_constructor_interaction.sql

   (2026-09-17 run: `bbe3e48` introduced 08f-2 despite an unrelated commit
   message; `e5bcd35`, its immediate predecessor in this file's own history,
   is the correct pre-fix content -- confirmed by `git diff e5bcd35 bbe3e48
   -- <path>` showing exactly the GROUP BY -> window-function rewrite and
   nothing else.)

   git show e5bcd35:transform/models/intermediate/int_circuit_x_constructor_interaction.sql \\
       > transform/models/intermediate/int_circuit_x_constructor_interaction.sql

3. Re-run the same `dbt run --select +fct_cliff_prediction_features --target
   gate_before` (rebuilds the whole lineage; simpler and safer than hand-
   picking the affected subtree). Export the BEFORE snapshot.

4. `git checkout HEAD -- transform/models/intermediate/int_circuit_x_constructor_interaction.sql`
   immediately -- restore the working tree before doing anything else.

5. Run this script against the two snapshot directories to get every table
   in `_improvements/eval/08f/MEASUREMENTS.md`.

6. Delete `data/gate_before.duckdb` and the `gate_before` block in
   `transform/profiles/profiles.yml`. Nothing from this probe persists on
   disk or in git.

INSTRUMENT CHECK (built into this script, and cross-checked against
production). A column with NO path to `int_circuit_x_constructor_interaction`
-- `push_residual` (family T / `int_lap_thermal_proxy`, an unrelated sibling
lineage), `fuel_mass_kg`, `expected_compound_pace_s` -- must come back
bit-identical between the two builds, AND identical to `data/dev.duckdb`
(read-only, never opened for write here) at max abs diff 0.0 on all three,
137,447/137,447 rows matched. This is what closes the confound: if isolation
had leaked into something else in the DAG, this check would show it.

THE HEADLINE MECHANISM, VERIFIED NOT ASSUMED. `circuit_constructor_interaction_s`
has grain (race_year, race_id, constructor_id) -- one value per constructor per
race, constant across every lap of every stint that constructor ran that race.
`driver_skill_residual_s = pace_delta_s - ... - constructor_component_s - ...`
where `constructor_component_s = constructor_structural_pace_s +
circuit_constructor_interaction_s` (`int_lap_residual_decomposed.sql:223-225,
309-315`), so `08f-2`'s change to `circuit_constructor_interaction_s` shifts
`driver_skill_residual_s` by an EXACT constant within each (race_year, race_id,
constructor_id) group (verified: max within-group stddev of the per-lap diff
is 6.7e-16, pure float noise -- not "small", exactly zero). Every target this
script checks is built from WITHIN-STINT differences or an OLS slope of
`driver_skill_residual_s` against `lap_in_stint` (`fct_cliff_prediction_features.sql`
~490-580, `int_lap_residual_stint_detrend.sql`), and a stint never spans more
than one (race_year, race_id, constructor_id) cell -- so the constant cancels
exactly out of every one of them. `int_lap_anomaly_flags.sql`'s trailing-MAD
window (`anomaly_class`, and via it `is_training_eligible`) is partitioned by
(race_year, race_id, driver_id), which nests inside the same constant-shift
group, so it cancels there too. This script's job is to CONFIRM that
prediction empirically over the full population, not to derive it.

Reads two directories of parquet snapshots exported read-only from the scratch
warehouse (see `export()`). Writes nothing to `ml/models/`, nothing to the
warehouse, nothing to git.

Usage:
    PYTHONPATH=. python3 scripts/measure_08f2_label_impact.py \\
        --after-dir <dir with after_*.parquet> --before-dir <dir with before_*.parquet>
"""
from __future__ import annotations

import argparse

import duckdb


TABLES = ("cci", "residual", "detrend", "mart")


def export(con: "duckdb.DuckDBPyConnection", out_dir: str, prefix: str) -> None:
    """Snapshot the columns this probe needs from a built `gate_before` warehouse.

    Call once per build (AFTER, then BEFORE) before rebuilding in place --
    the scratch warehouse's tables get overwritten by the next `dbt run`.
    """
    con.sql(f"""
        COPY (
            SELECT race_year, race_id, constructor_id, circuit_constructor_interaction_s,
                   interaction_obs_n, interaction_se_s
            FROM int_circuit_x_constructor_interaction
        ) TO '{out_dir}/{prefix}_cci.parquet' (FORMAT PARQUET)
    """)
    con.sql(f"""
        COPY (
            SELECT lap_id, stint_id, race_year, race_id, constructor_id, driver_skill_residual_s
            FROM int_lap_residual_decomposed
        ) TO '{out_dir}/{prefix}_residual.parquet' (FORMAT PARQUET)
    """)
    con.sql(f"""
        COPY (
            SELECT stint_id, drift_s_per_lap
            FROM int_lap_residual_stint_detrend
        ) TO '{out_dir}/{prefix}_detrend.parquet' (FORMAT PARQUET)
    """)
    con.sql(f"""
        COPY (
            SELECT lap_id, stint_id, race_year, race_id, lap_in_stint, is_training_eligible,
                   anomaly_class, cliff_candidate_flag,
                   next_lap_degradation_jump_detrended_s, next_lap_degradation_jump_s,
                   next_3_lap_cumulative_jump_s, next_5_lap_cumulative_jump_s, laps_until_cliff_class,
                   push_residual, fuel_mass_kg, expected_compound_pace_s
            FROM fct_cliff_prediction_features
        ) TO '{out_dir}/{prefix}_mart.parquet' (FORMAT PARQUET)
    """)


def load(con: "duckdb.DuckDBPyConnection", in_dir: str, prefix: str) -> None:
    for t in TABLES:
        con.sql(f"""
            CREATE OR REPLACE TABLE {prefix}_{t} AS
            SELECT * FROM read_parquet('{in_dir}/{prefix}_{t}.parquet')
        """)


def run(after_dir: str, before_dir: str) -> None:
    con = duckdb.connect()
    load(con, after_dir, "after")
    load(con, before_dir, "before")

    print("=== ROW COUNTS (must match; grain is unchanged by 08f-2) ===")
    for t in TABLES:
        a = con.sql(f"SELECT COUNT(*) FROM after_{t}").fetchone()[0]
        b = con.sql(f"SELECT COUNT(*) FROM before_{t}").fetchone()[0]
        print(f"{t}: after={a} before={b}")

    print("\n=== INSTRUMENT CHECK: columns with no path to the 08f-2 lineage ===")
    print(con.sql("""
        SELECT
            COUNT(*) AS n,
            MAX(ABS(a.push_residual - b.push_residual)) AS max_diff_push_residual,
            MAX(ABS(a.fuel_mass_kg - b.fuel_mass_kg)) AS max_diff_fuel_mass_kg,
            MAX(ABS(a.expected_compound_pace_s - b.expected_compound_pace_s)) AS max_diff_compound_pace
        FROM after_mart a JOIN before_mart b USING (lap_id)
    """).fetchdf().to_string(index=False))

    print("\n=== MECHANISM CHECK: is the driver_skill_residual_s shift an exact")
    print("    constant within (race_year, race_id, constructor_id)? ===")
    print(con.sql("""
        WITH d AS (
            SELECT a.race_year, a.race_id, a.constructor_id,
                   a.driver_skill_residual_s - b.driver_skill_residual_s AS diff
            FROM after_residual a JOIN before_residual b USING (lap_id)
        )
        SELECT MAX(within_group_sd) AS max_within_group_stddev
        FROM (SELECT race_year, race_id, constructor_id, STDDEV(diff) AS within_group_sd
              FROM d GROUP BY 1, 2, 3)
    """).fetchdf().to_string(index=False))

    print("\n=== 1. circuit_constructor_interaction_s (race x constructor grain) ===")
    con.sql("""
        CREATE OR REPLACE TABLE cci_diff AS
        SELECT a.race_year, a.race_id, a.constructor_id,
               a.circuit_constructor_interaction_s - b.circuit_constructor_interaction_s AS diff
        FROM after_cci a JOIN before_cci b USING (race_year, race_id, constructor_id)
    """)
    print(con.sql("""
        SELECT race_year, COUNT(*) AS n,
               COUNT(*) FILTER (WHERE ABS(diff) > 1e-9) AS n_changed,
               AVG(ABS(diff)) AS mean_abs_diff, MEDIAN(ABS(diff)) AS median_abs_diff,
               MAX(ABS(diff)) AS max_abs_diff
        FROM cci_diff GROUP BY race_year ORDER BY race_year
    """).fetchdf().to_string(index=False))

    print("\n=== 2. driver_skill_residual_s (lap grain) -- barred input, not a label ===")
    con.sql("""
        CREATE OR REPLACE TABLE resid_diff AS
        SELECT a.lap_id, a.race_year,
               a.driver_skill_residual_s - b.driver_skill_residual_s AS diff
        FROM after_residual a JOIN before_residual b USING (lap_id)
    """)
    print(con.sql("""
        SELECT race_year, COUNT(*) AS n,
               COUNT(*) FILTER (WHERE ABS(diff) > 1e-9) AS n_changed,
               AVG(ABS(diff)) AS mean_abs_diff, MEDIAN(ABS(diff)) AS median_abs_diff,
               MAX(ABS(diff)) AS max_abs_diff
        FROM resid_diff GROUP BY race_year ORDER BY race_year
    """).fetchdf().to_string(index=False))
    print(con.sql("""
        SELECT QUANTILE_CONT(ABS(diff), 0.50) AS p50, QUANTILE_CONT(ABS(diff), 0.90) AS p90,
               QUANTILE_CONT(ABS(diff), 0.99) AS p99, MAX(ABS(diff)) AS p100
        FROM resid_diff
    """).fetchdf().to_string(index=False))

    print("\n=== 3. drift_s_per_lap (stint grain) -- feeds detrended targets ===")
    print(con.sql("""
        SELECT COUNT(*) AS n,
               COUNT(*) FILTER (WHERE ABS(a.drift_s_per_lap - b.drift_s_per_lap) > 1e-9) AS n_changed,
               MAX(ABS(a.drift_s_per_lap - b.drift_s_per_lap)) AS max_abs_diff
        FROM after_detrend a JOIN before_detrend b USING (stint_id)
    """).fetchdf().to_string(index=False))

    print("\n=== 4. next_5_lap_cumulative_jump_s == DEGRADATION_TARGET ===")
    print(con.sql("""
        SELECT COUNT(*) AS n,
               COUNT(*) FILTER (WHERE ABS(a.next_5_lap_cumulative_jump_s - b.next_5_lap_cumulative_jump_s) > 1e-9) AS n_changed,
               MAX(ABS(a.next_5_lap_cumulative_jump_s - b.next_5_lap_cumulative_jump_s)) AS max_abs_diff
        FROM after_mart a JOIN before_mart b USING (lap_id)
        WHERE a.next_5_lap_cumulative_jump_s IS NOT NULL AND b.next_5_lap_cumulative_jump_s IS NOT NULL
        AND a.is_training_eligible AND b.is_training_eligible
    """).fetchdf().to_string(index=False))

    print("\n=== 5. laps_until_cliff_class == CLIFF_TARGET (categorical) ===")
    n_total = con.sql("SELECT COUNT(*) FROM after_mart a JOIN before_mart b USING (lap_id)").fetchone()[0]
    n_changed = con.sql("""
        SELECT COUNT(*) FROM after_mart a JOIN before_mart b USING (lap_id)
        WHERE a.laps_until_cliff_class IS DISTINCT FROM b.laps_until_cliff_class
    """).fetchone()[0]
    print(f"total rows: {n_total}, class changed: {n_changed}")

    print("\n=== 6. is_training_eligible / anomaly_class population check ===")
    print("(secondary; NOT a re-test of whether cliff_candidate_flag carries")
    print(" information -- that question is settled/pruned by 08g/08j.)")
    print(con.sql("""
        SELECT
            COUNT(*) FILTER (WHERE a.is_training_eligible IS DISTINCT FROM b.is_training_eligible) AS eligibility_flipped_n,
            COUNT(*) FILTER (WHERE a.anomaly_class IS DISTINCT FROM b.anomaly_class) AS anomaly_class_changed_n
        FROM after_mart a JOIN before_mart b USING (lap_id)
    """).fetchdf().to_string(index=False))

    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-dir", required=True)
    parser.add_argument("--before-dir", required=True)
    args = parser.parse_args()
    run(args.after_dir, args.before_dir)
