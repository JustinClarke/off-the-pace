"""TX-08 vacuity audit driver (scratch only).

For each test guarding the AI marts and fct_lap_residuals: corrupt the model table on
the scratch copy (break exactly the property the test claims to guard), run that one test
with `dbt test -s <test>`, record PASS/FAIL, restore the table from a backup copy taken
before the audit. The mutated models are rebuilt by dbt afterwards (hash --check).

usage: mutate.py <wrapper.sh> <db> <manifest> <results.tsv> [only_test ...]
"""
import json
import re
import subprocess
import sys

import duckdb

WRAP, DB, MANIFEST, OUT = sys.argv[1:5]
ONLY = set(sys.argv[5:])
TARGETS = ["fct_lap_residuals", "mart_race_driver_summary", "mart_driver_season_summary",
           "mart_metric_benchmark", "mart_race_coverage"]

ONE = "rowid IN (SELECT rowid FROM {m} WHERE {w} ORDER BY rowid LIMIT 1)"


def one(m, w="TRUE"):
    return ONE.format(m=m, w=w)


# Hand mutations for singular tests: test -> list of (label, [sql...])
F, R, SS, B, C = TARGETS
SINGULAR = {
    "assert_residual_variance_shrinks": [
        ("constructor term zeroed (removes no variance)", [f"UPDATE {F} SET constructor_component_s = 0"]),
    ],
    "assert_driver_skill_residual_reasonable": [
        ("one ml_eligible residual set to 15.5 s (old 19 s bound would pass)",
         [f"UPDATE {F} SET driver_skill_residual_s = 15.5 WHERE {one(F, 'ml_eligible AND driver_skill_residual_s IS NOT NULL')}"]),
    ],
    "assert_dirty_air_fill_only_where_base_unmeasured": [
        ("pace_delta_s NULLed on a lap that has a dirty-air row",
         [f"UPDATE {F} SET pace_delta_s = NULL WHERE {one(F, 'pace_delta_s IS NOT NULL')}"]),
    ],
    "assert_every_lap_race_rated_or_explained": [
        ("all rating rows of one OK-coverage race deleted",
         [f"DELETE FROM {R} WHERE race_id = (SELECT MIN(race_id) FROM {C} WHERE coverage_reason = 'OK' AND has_rating)"]),
        ("one coverage row deleted",
         [f"DELETE FROM {C} WHERE race_id = (SELECT MIN(race_id) FROM {C})"]),
        ("has_telemetry FALSE on a race with laps that is not a known gap",
         [f"UPDATE {C} SET has_telemetry = FALSE WHERE race_id = (SELECT MIN(race_id) FROM {C} WHERE has_telemetry AND n_lap_rows > 0)"]),
    ],
    "assert_mart_season_uncertainty_carried": [
        ("rating_se_s of one row x1.01", [f"UPDATE {SS} SET rating_se_s = rating_se_s * 1.01 WHERE {one(SS)}"]),
        ("rank_separated_from_next flipped on one non-NULL row",
         [f"UPDATE {SS} SET rank_separated_from_next = NOT rank_separated_from_next WHERE {one(SS, 'rank_separated_from_next IS NOT NULL')}"]),
    ],
    "assert_mart_race_ci_brackets_rating": [
        ("ci_low moved above rating_s on one row",
         [f"UPDATE {R} SET ci_low = rating_s + 0.01 WHERE {one(R, 'ci_low IS NOT NULL')}"]),
        ("trust label of one 'ok' row set to 'thin'",
         [f"UPDATE {R} SET rating_trust_label = 'thin' WHERE {one(R, chr(39)+'ok'+chr(39)+' = rating_trust_label')}"]),
        ("paired_lap_count +1 on one row", [f"UPDATE {R} SET paired_lap_count = paired_lap_count + 1 WHERE {one(R)}"]),
    ],
    "assert_mart_positions_gained_pit_lane": [
        ("positions_gained +1 on one grid-slot row",
         [f"UPDATE {R} SET positions_gained = positions_gained + 1 WHERE {one(R, 'positions_gained IS NOT NULL')}"]),
    ],
    "assert_mart_season_teammate_gap": [
        ("teammate_gap_s doubled on one row (the old CO-01 defect)",
         [f"UPDATE {SS} SET teammate_gap_s = 2 * rating_s WHERE {one(SS, 'teammate_id IS NOT NULL AND rating_s <> 0')}"]),
    ],
    "assert_dirty_air_mean_excludes_unmeasured": [
        ("race mart mean_dirty_air_tax_s +0.01 on one row",
         [f"UPDATE {R} SET mean_dirty_air_tax_s = mean_dirty_air_tax_s + 0.01 WHERE {one(R, 'mean_dirty_air_tax_s IS NOT NULL')}"]),
        ("benchmark dirty_air sample_size +1 (the 0.0 fill counted)",
         [f"UPDATE {B} SET sample_size = sample_size + 1 WHERE {one(B, chr(39)+'dirty_air_tax_s'+chr(39)+' = metric_name')}"]),
    ],
    "assert_mart_race_teammate_gap": [
        ("teammate_gap_s doubled on one row",
         [f"UPDATE {R} SET teammate_gap_s = 2 * teammate_gap_s WHERE {one(R, 'teammate_id IS NOT NULL AND teammate_gap_s <> 0')}"]),
    ],
    "assert_reason_iff_missing": [
        ("ci_unavailable_reason NULLed where the CI is missing",
         [f"UPDATE {R} SET ci_unavailable_reason = NULL WHERE {one(R, 'ci_low IS NULL')}"]),
        ("residual_unavailable_reason set where n_clean_laps is present",
         [f"UPDATE {R} SET residual_unavailable_reason = 'NO_ML_ELIGIBLE_LAPS' WHERE {one(R, 'n_clean_laps IS NOT NULL')}"]),
    ],
    # TX-08's own new test
    "assert_ai_mart_counts_consistent": [
        ("race n_drivers +1 on one row", [f"UPDATE {R} SET n_drivers = n_drivers + 1 WHERE {one(R)}"]),
        ("race laps_completed -1 on one row", [f"UPDATE {R} SET laps_completed = laps_completed - 1 WHERE {one(R)}"]),
        ("race n_clean_laps -1 on one non-NULL row", [f"UPDATE {R} SET n_clean_laps = n_clean_laps - 1 WHERE {one(R, 'n_clean_laps IS NOT NULL')}"]),
        ("race n_clean_laps 0 instead of NULL", [f"UPDATE {R} SET n_clean_laps = 0 WHERE {one(R, 'n_clean_laps IS NULL')}"]),
        ("season n_drivers +1 on one row", [f"UPDATE {SS} SET n_drivers = n_drivers + 1 WHERE {one(SS)}"]),
        ("season n_races +100 on one row", [f"UPDATE {SS} SET n_races = n_races + 100 WHERE {one(SS)}"]),
        ("season teammate_gap_rank set to n_drivers + 1", [f"UPDATE {SS} SET teammate_gap_rank = n_drivers + 1 WHERE {one(SS)}"]),
        ("benchmark lap_time_s sample_size -1", [f"UPDATE {B} SET sample_size = sample_size - 1 WHERE {one(B, chr(39)+'lap_time_s'+chr(39)+' = metric_name')}"]),
        ("benchmark row deleted (one metric-season missing)", [f"DELETE FROM {B} WHERE {one(B, chr(39)+'fuel_component_s'+chr(39)+' = metric_name')}"]),
    ],
}


def generic_mutation(node):
    md = node["test_metadata"]
    kind = md["name"]
    kw = md.get("kwargs") or {}
    m = node["attached_node"].split(".")[-1]
    col = node.get("column_name") or kw.get("column_name")
    where = node["config"].get("where") or "TRUE"
    if kind == "not_null":
        return f"{col} NULLed on one row", [f"UPDATE {m} SET {col} = NULL WHERE {one(m, where)}"]
    if kind in ("unique", "unique_combination_of_columns"):
        return "one row duplicated", [f"INSERT INTO {m} SELECT * FROM {m} WHERE {one(m)}"]
    if kind == "relationships":
        return f"{col} set to a key not in the parent", [
            f"UPDATE {m} SET {col} = 'TX08_NOT_A_KEY' WHERE {one(m, col + ' IS NOT NULL')}"]
    if kind == "accepted_values":
        return f"{col} set to an unlisted value", [
            f"UPDATE {m} SET {col} = 'TX08_BOGUS' WHERE {one(m, where)}"]
    if kind == "accepted_range":
        lo, hi = kw.get("min_value"), kw.get("max_value")
        sqls, labels = [], []
        if lo is not None:
            labels.append(f"{col} = {lo} - 1")
            sqls.append(f"UPDATE {m} SET {col} = {lo} - 1 WHERE {one(m, where if where != 'TRUE' else col + ' IS NOT NULL')}")
        if hi is not None:
            labels.append(f"{col} = {hi} + 1")
            sqls.append(f"UPDATE {m} SET {col} = {hi} + 1 WHERE {one(m, where if where != 'TRUE' else col + ' IS NOT NULL')}")
        # each bound is its own mutation
        return [(lab, [s]) for lab, s in zip(labels, sqls)]
    if kind == "expression_is_true":
        return None
    return None


def run_test(name):
    p = subprocess.run([WRAP, "test", "-s", name], capture_output=True, text=True)
    out = p.stdout + p.stderr
    mt = re.search(r"Done\. PASS=(\d+) WARN=(\d+) ERROR=(\d+) SKIP=(\d+)", out)
    fails = re.findall(r"(FAIL|WARN) (\d+) " + re.escape(name[:40]), out)
    if not mt:
        return "NO_RUN", out[-600:]
    p_, w_, e_, s_ = map(int, mt.groups())
    if p_ + w_ + e_ == 0:
        return "NOT_SELECTED", ""
    if e_:
        return "FAIL", fails[0][1] if fails else "?"
    if w_:
        return "WARN", fails[0][1] if fails else "?"
    return "PASS", "0"


def main():
    man = json.load(open(MANIFEST))
    plan = []
    for node in man["nodes"].values():
        if node["resource_type"] != "test":
            continue
        deps = [d.split(".")[-1] for d in node["depends_on"]["nodes"]]
        if not any(t in deps for t in TARGETS):
            continue
        name = node["name"]
        if ONLY and name not in ONLY:
            continue
        if node.get("test_metadata"):
            att = (node.get("attached_node") or "").split(".")[-1]
            if att not in TARGETS:
                continue
            g = generic_mutation(node)
            if g is None:
                plan.append((name, "NO GENERIC MUTATION", []))
                continue
            if isinstance(g, tuple):
                g = [g]
            for lab, sqls in g:
                plan.append((name, lab, sqls))
        else:
            muts = SINGULAR.get(name)
            if not muts:
                plan.append((name, "NO HAND MUTATION DEFINED", []))
                continue
            for lab, sqls in muts:
                plan.append((name, lab, sqls))

    con = duckdb.connect(DB)
    con.execute("CREATE SCHEMA IF NOT EXISTS tx08_bak")
    for t in TARGETS:
        if not con.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='tx08_bak' AND table_name='{t}'").fetchone()[0]:
            con.execute(f"CREATE TABLE tx08_bak.{t} AS SELECT * FROM main.{t}")
    con.close()

    with open(OUT, "a") as fh:
        for name, lab, sqls in plan:
            if not sqls:
                fh.write(f"{name}\t{lab}\t-\t-\t-\n"); fh.flush()
                continue
            # clean run first (must pass), then mutated run
            con = duckdb.connect(DB)
            touched = set()
            changed = 0
            for s in sqls:
                r = con.execute(s).fetchall()
                changed += r[0][0] if r and isinstance(r[0][0], int) else 0
                touched.update(t for t in TARGETS if re.search(rf"\b{t}\b", s.split(" WHERE ")[0]))
            con.close()
            res, n = run_test(name)
            con = duckdb.connect(DB)
            for t in touched:
                con.execute(f"CREATE OR REPLACE TABLE main.{t} AS SELECT * FROM tx08_bak.{t}")
            con.close()
            verdict = "OK (test fails)" if res in ("FAIL", "WARN") else "VACUOUS" if res == "PASS" else res
            fh.write(f"{name}\t{lab}\trows_changed={changed}\t{res} {n}\t{verdict}\n"); fh.flush()
            print(name, lab, changed, res, n, verdict, flush=True)


main()
