"""11b · s0 — verify the leaf doc's "everything needed already exists" claim.

Read-only. Opens the four tables R6 Part 3 names as the DP's substrate plus the
prediction mart, and checks row count, grain, join key and column semantics
against what `work/11-parallel-surfaces.md` and `research/R6` assert.

    python3 _improvements/implementations/11b/s0_verify_substrate.py

Writes s0_substrate.json alongside. Writes nothing else, anywhere.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "s0_substrate.json"
DB = ROOT / "data" / "dev.duckdb"
MART = ROOT / "data" / "marts" / "mart_degradation_predictions.parquet"

# What the leaf doc / R6 Part 3 claim, verbatim.
CLAIMED = {
    "int_pit_strategy_cost_curve": {"rows": 386036, "what": "cost of stopping at each lap"},
    "int_pit_strategy_value": {"rows": 7129, "what": "realised strategy value per stint"},
    "int_pit_loss_circuit": {"rows": None, "what": "empirical pit loss per venue"},
    "int_sc_hazard_history": {"rows": 36, "what": "per-lap SC/VSC hazard per circuit, EB-shrunk"},
}


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    q = lambda s: con.execute(s).fetchall()
    rec: dict = {"db": str(DB), "claimed": CLAIMED, "tables": {}, "findings": []}

    for t, claim in CLAIMED.items():
        cols = {r[0]: r[1] for r in q(f"describe {t}")}
        n = q(f"select count(*) from {t}")[0][0]
        rec["tables"][t] = {"rows": n, "claimed_rows": claim["rows"], "columns": cols}
        if claim["rows"] is not None and claim["rows"] != n:
            rec["findings"].append(
                f"{t}: leaf doc says {claim['rows']} rows, warehouse has {n}"
            )

    # --- grain checks -----------------------------------------------------
    grains = {
        "int_pit_strategy_cost_curve": ["stint_id", "horizon_scope", "candidate_pit_lap_offset"],
        "int_pit_strategy_value": ["stint_id"],
        "int_pit_loss_circuit": ["circuit_slug"],
        "int_sc_hazard_history": ["circuit_slug", "season"],
    }
    for t, keys in grains.items():
        k = ", ".join(keys)
        n, d = q(f"select count(*), count(distinct ({k})) from {t}")[0]
        rec["tables"][t]["grain"] = keys
        rec["tables"][t]["grain_unique"] = (n == d)
        if n != d:
            rec["findings"].append(f"{t}: NOT unique on {keys} ({n} rows, {d} keys)")

    # --- SC hazard: is it a per-LAP profile or a flat per-lap RATE? -------
    hz = q("""
        select season, count(*) n, count(any_hazard_per_lap_shrunk) n_nonnull,
               min(any_hazard_per_lap_shrunk), avg(any_hazard_per_lap_shrunk),
               max(any_hazard_per_lap_shrunk)
        from int_sc_hazard_history group by 1 order by 1
    """)
    rec["sc_hazard_by_season"] = [
        {"season": r[0], "rows": r[1], "non_null_shrunk": r[2],
         "min": r[3], "mean": r[4], "max": r[5]} for r in hz
    ]
    rec["sc_hazard_has_lap_axis"] = any(
        "lap" == c for c in rec["tables"]["int_sc_hazard_history"]["columns"]
    )

    # --- is the hazard consumed? -----------------------------------------
    consumers = []
    for p in (ROOT / "transform" / "models").rglob("*.sql"):
        if p.name == "int_sc_hazard_history.sql":
            continue
        if "int_sc_hazard_history" in p.read_text():
            consumers.append(str(p.relative_to(ROOT)))
    rec["sc_hazard_dbt_consumers"] = sorted(consumers)

    # --- cost curve: what supplies the running cost? ---------------------
    cc_sql = (ROOT / "transform/models/intermediate/int_pit_strategy_cost_curve.sql").read_text()
    rec["cost_curve_running_cost_source"] = {
        "reads_dim_compounds_season": "dim_compounds_season" in cc_sql,
        "reads_mart_degradation_predictions": "mart_degradation_predictions" in cc_sql,
        "reads_any_ml_prediction": any(
            s in cc_sql for s in ("predicted_degradation", "mart_degradation", "ml/models")
        ),
    }
    # compound params are a SEED, not a fit
    seed_rows = q("select count(*) from compound_cliff_params")[0][0]
    rec["compound_cliff_params_rows"] = seed_rows
    rec["dim_compounds_season_is_seed_lift"] = "compound_cliff_params" in (
        ROOT / "transform/models/reference/dim_compounds_season.sql"
    ).read_text()

    # --- cost curve action space -----------------------------------------
    nc = q("""
        select count(*) total,
               count(*) filter (where next_compound is not null) with_next,
               count(distinct next_compound) distinct_next
        from int_pit_strategy_cost_curve
    """)[0]
    per_stint_next = q("""
        select max(k) from (
          select stint_id, horizon_scope, count(distinct next_compound) k
          from int_pit_strategy_cost_curve group by 1,2)
    """)[0][0]
    rec["cost_curve_action_space"] = {
        "rows": nc[0], "rows_with_next_compound": nc[1],
        "distinct_next_compound_values": nc[2],
        "max_next_compounds_offered_per_stint_scope": per_stint_next,
        "note": "1 means the table fixes next_compound to the realised choice; "
                "the DP's 'compound on stop' action is not enumerated here",
    }

    # --- horizon scopes ---------------------------------------------------
    rec["cost_curve_scopes"] = [
        {"scope": r[0], "rows": r[1], "stints": r[2]}
        for r in q("select horizon_scope, count(*), count(distinct stint_id) "
                   "from int_pit_strategy_cost_curve group by 1 order by 1")
    ]

    # --- what the DP state needs that is NOT here -------------------------
    have_pos = q("""
        select count(*) from information_schema.columns
        where table_name = 'fct_lap_residuals' and column_name = 'position'
    """)[0][0]
    rec["state_dimensions"] = {
        "lap": True, "compound": True, "tyre_age": True,
        "track_position_observed": bool(have_pos),
        "track_position_transition_kernel": False,
        "note": "position is recorded per lap in fct_lap_residuals, but nothing in the "
                "warehouse maps (stop at lap L) -> (position after the stop). That needs "
                "the whole field's pace and an overtaking model; neither exists.",
    }

    # --- the prediction mart ----------------------------------------------
    pf = pq.ParquetFile(str(MART))
    rec["mart"] = {
        "path": str(MART.relative_to(ROOT)),
        "rows": pf.metadata.num_rows,
        "columns": list(pf.schema_arrow.names),
    }
    mv = con.execute(
        f"select model_version, count(*), min(predicted_at), max(predicted_at) "
        f"from read_parquet('{MART}') group by 1"
    ).fetchall()
    rec["mart"]["versions"] = [
        {"version": r[0], "rows": r[1], "predicted_at_min": str(r[2]), "predicted_at_max": str(r[3])}
        for r in mv
    ]

    # --- can the ML degradation model be evaluated off-policy? ------------
    # A DP candidate L != actual needs old-tyre pace at ages never run (L > actual)
    # or new-tyre pace at ages never run (L < actual). Count how much of the
    # 'window' candidate grid is covered by a REAL scored lap on the right tyre.
    cov = q("""
        with span as (
            select stint_id, horizon_scope, max(horizon_laps) h,
                   max(stint_valid_laps) l_act
            from int_pit_strategy_cost_curve where horizon_scope = 'window'
            group by 1,2
        )
        select count(*) stints,
               sum(h) candidate_laps,
               sum(case when l_act between 1 and h then 1 else 0 end) with_actual_in_grid
        from span
    """)[0]
    rec["offpolicy_coverage"] = {
        "window_stints": cov[0],
        "window_candidates_total": cov[1],
        "stints_whose_actual_L_is_in_grid": cov[2],
        "candidates_fully_observed_per_stint": 1,
        "note": "Exactly ONE candidate per stint (L = the realised stop) has both arms "
                "run on real laps. Every other candidate needs one arm extrapolated "
                "past the age that tyre actually reached.",
    }

    OUT.write_text(json.dumps(rec, indent=2, default=str))
    print(json.dumps({k: rec[k] for k in ("findings",)}, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
