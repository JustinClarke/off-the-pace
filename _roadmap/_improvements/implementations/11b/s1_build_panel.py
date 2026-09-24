"""11b · s1 — build the DP panel.

One row per (stint, candidate pit lap) for the 'window' horizon, carrying

  * the SEED cost surface, lifted verbatim from int_pit_strategy_cost_curve
    (old/new cumulative wear, compound baseline delta, pit loss, SC discount);
  * the REALISED unmodelled-degradation path  delta*(u) = rho(u) - rho(1),
    where rho = fct_lap_residuals.driver_skill_residual_s, i.e. lap time with
    field pace, fuel, the SEED compound curve, rubber, ambient, constructor and
    dirty air already removed;
  * the MODEL path delta_hat(u), telescoped from the v11 p50 forecast of
    next_5_lap_cumulative_jump_s in data/marts/mart_degradation_predictions.parquet;
  * the realised per-lap caution flags over the horizon.

WHY delta AND NOT "the degradation forecast".  int_lap_residual_decomposed
subtracts int_compound_cliff_predicted.expected_compound_pace_s -- the SEEDED
compound polynomial -- before forming driver_skill_residual_s.  The ML target is
therefore the seed's RESIDUAL, not total tyre degradation, and a per-lap running
cost is seed(age) + rho(age).  The level rho(1) multiplies the whole horizon and
cancels out of the argmin, so only delta matters.  See the RESULT section of
work/11-parallel-surfaces.md.

Read-only.  Writes panel.parquet + s1_manifest.json alongside this file.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DB = ROOT / "data" / "dev.duckdb"
MART = ROOT / "data" / "marts" / "mart_degradation_predictions.parquet"

HORIZON_K = 5          # next_5_lap_cumulative_jump_s
TRI_K = HORIZON_K * (HORIZON_K + 1) // 2   # 15 = sum_{j=1..5} j


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB), read_only=True)


def build() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    con = _con()

    # --- valid-lap index per driver-race, exactly as the cost curve builds it
    con.execute(f"""
        create or replace temp view dl as
        select sg.stint_id, sg.lap_id, sg.race_year, sg.race_id, sg.driver_id,
               sg.lap_number, sg.age_in_stint, sg.compound_in_stint as compound,
               row_number() over (partition by sg.race_year, sg.race_id, sg.driver_id
                                  order by sg.lap_number) as driver_lap_idx,
               row_number() over (partition by sg.stint_id order by sg.lap_number) as u
        from int_stint_geometry sg
        where sg.is_valid_lap = true
    """)
    con.execute("""
        create or replace temp view spans as
        select stint_id, race_year, race_id, driver_id,
               min(driver_lap_idx) as first_idx, max(driver_lap_idx) as last_idx,
               count(*) as n_valid
        from dl group by 1,2,3,4
    """)
    con.execute("""
        create or replace temp view succ as
        select stint_id, race_year, race_id, driver_id, first_idx, last_idx, n_valid,
               lead(stint_id) over (partition by race_year, race_id, driver_id
                                    order by first_idx) as next_stint_id
        from spans
    """)

    # --- per-lap path for every stint: rho, model forecast, caution flags
    laps = con.execute(f"""
        select dl.stint_id, dl.u, dl.lap_id, dl.lap_number, dl.age_in_stint,
               r.driver_skill_residual_s as rho,
               r.is_safety_car_lap or r.is_vsc_lap as caution,
               f.next_5_lap_cumulative_jump_s as j_real,
               m.predicted_degradation_jump_s as j_hat,
               m.predicted_degradation_jump_p10_s as j_hat_p10,
               m.predicted_degradation_jump_p90_s as j_hat_p90,
               d.drift_s_per_lap as drift
        from dl
        join fct_lap_residuals r on dl.lap_id = r.lap_id
        left join fct_cliff_prediction_features f on dl.lap_id = f.lap_id
        left join read_parquet('{MART}') m on dl.lap_id = m.lap_id
        left join int_lap_residual_stint_detrend d on dl.stint_id = d.stint_id
        order by dl.stint_id, dl.u
    """).df()

    # --- the seed cost surface, verbatim from the production table
    cc = con.execute("""
        select c.stint_id, c.race_year, c.race_id, c.driver_id, c.horizon_laps,
               c.stint_valid_laps, c.candidate_pit_lap_offset as L, c.laps_on_new_set,
               c.compound, c.next_compound, c.candidate_lap_number,
               c.old_wear_cost_s, c.new_wear_cost_s, c.baseline_cost_s,
               c.pit_lane_loss_s, c.sc_hazard_per_lap, c.sc_probability,
               c.pit_discount_factor, c.pit_cost_s, c.wear_cost_s, c.total_cost_s
        from int_pit_strategy_cost_curve c
        where c.horizon_scope = 'window'
    """).df()

    # --- stint-level metadata
    meta = con.execute("""
        select s.stint_id, s.race_year, s.race_id, s.driver_id, s.next_stint_id,
               s.n_valid as n_old, rtt.track_id as circuit_key,
               er.end_regime, er.stint_end_cause,
               psv.actual_pit_lap, psv.optimal_pit_lap, psv.optimal_pit_lap_in_stint,
               psv.strategy_verdict, psv.opportunity_cost_s
        from succ s
        join race_to_track rtt on s.race_id = rtt.race_id
        left join int_stint_end_regime er on s.stint_id = er.stint_id
        left join int_pit_strategy_value psv on s.stint_id = psv.stint_id
        where s.next_stint_id is not null
    """).df()

    # --- final finishing position per driver-race (for the 'known-good' screen)
    fin = con.execute("""
        select race_year, race_id, driver_id,
               arg_max(position, lap_number) as final_position
        from fct_lap_residuals group by 1,2,3
    """).df()
    meta = meta.merge(fin, on=["race_year", "race_id", "driver_id"], how="left")

    manifest = {
        "cost_curve_window_rows": int(len(cc)),
        "cost_curve_window_stints": int(cc.stint_id.nunique()),
        "lap_rows": int(len(laps)),
        "lap_rows_with_model_forecast": int(laps.j_hat.notna().sum()),
        "lap_rows_with_realised_target": int(laps.j_real.notna().sum()),
        "lap_rows_with_rho": int(laps.rho.notna().sum()),
        "stints_with_successor": int(len(meta)),
        "horizon_k": HORIZON_K,
        "triangular_constant": TRI_K,
    }
    return cc, laps, meta, manifest


def main() -> None:
    cc, laps, meta, manifest = build()
    laps.to_parquet(HERE / "panel_laps.parquet", index=False)
    cc.to_parquet(HERE / "panel_seed_surface.parquet", index=False)
    meta.to_parquet(HERE / "panel_meta.parquet", index=False)
    (HERE / "s1_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
