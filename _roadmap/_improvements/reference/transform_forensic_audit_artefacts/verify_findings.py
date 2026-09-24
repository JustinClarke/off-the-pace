"""Status board for every transform-audit finding (round 1: F1-F21, round 2: F22-F37,
round 3: F38-F49).

Run from anywhere, read-only against data/dev.duckdb (override with OTP_DB=...):

    .venv/bin/python _improvements/reference/transform_forensic_audit_artefacts/verify_findings.py
    .venv/bin/python .../verify_findings.py F22 F23a        # only these

Each check measures the defect directly (a count, a share, or a code/text fact) and prints
PRESENT or CLEARED plus the measured value, so a fix can be confirmed the moment it builds.
A check that cannot run prints ERROR with the reason instead of crashing the board.
"PRESENT" after a deliberate ruling (e.g. a declared exemption) is expected: say so in the
ruling and retire the check here, rather than letting the board go quietly red.

The full evidence for each finding is in transform_forensic_audit_report.md (F1-F21),
transform_forensic_audit_report_round2.md (F22-F37) and transform_forensic_audit_report_round3.md
(F38-F49); probes are in this folder, round2/ and round3/.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent / "round2"))
from _db import REPO, con  # noqa: E402


def text(rel: str) -> str:
    return (REPO / rel).read_text()


@dataclass
class Check:
    id: str
    title: str
    measure: Callable[[object], object]   # connection -> value
    present: Callable[[object], bool]     # value -> defect still present?
    cleared_means: str


def sql(q: str) -> Callable[[object], object]:
    return lambda c: c.execute(q).fetchone()[0]


def _compound_defaults() -> dict:
    """COMPOUND_DEFAULTS read from fit_compound_cliff.py's source (no import: the module
    configures logging on import)."""
    import ast
    tree = ast.parse(text("transform/tasks/coefficients/fit_compound_cliff.py"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "COMPOUND_DEFAULTS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise LookupError("COMPOUND_DEFAULTS not found")


# ── Round 2 shared SQL ───────────────────────────────────────────────────────────
STINT_BOUNDARY_SQL = r"""
with seq as (
  select g.race_year, g.race_id, g.driver_id, g.lap_number, g.stint_number, g.is_red_flag_lap,
    lag(g.stint_number) over w prev_stint, lag(g.is_red_flag_lap) over w prev_red,
    exists (select 1 from stg_pits p where p.race_year = g.race_year and p.race_id = g.race_id
            and p.driver_id = g.driver_id and p.pit_in_lap_number = g.lap_number - 1) prev_is_in_lap
  from int_stint_geometry g
  window w as (partition by g.race_year, g.race_id, g.driver_id order by g.lap_number)),
per_race as (
  select race_id, count(*) filter (where prev_stint is not null and stint_number is not null
      and stint_number <> prev_stint and not prev_is_in_lap and not coalesce(prev_red, false)
      and not is_red_flag_lap) b
  from seq group by 1)
select count(*) from per_race where b >= 5"""

FUEL_INITIAL_SQL = r"""
with r as (
  select f.race_year, f.race_id,
    max(f.fuel_mass_kg + d.fuel_consumption_rate_kg_per_lap * (f.lap_number - 1)) initial_kg,
    max(f.fuel_mass_kg / nullif(d.fuel_consumption_rate_kg_per_lap, 0) + f.lap_number - 1) implied_race_laps
  from int_lap_fuel_state f join race_to_track rt using (race_id)
  join dim_circuits d on d.circuit_key = rt.track_id group by all)
select {expr} from r"""

CHECKS: list[Check] = [
    # ── Round 1 ─────────────────────────────────────────────────────────────────
    Check("F1", "pace_delta_s fabricated as 0 where the field curve is missing",
          sql("select count(*) from int_lap_residual_decomposed where base_track_pace_s is null and pace_delta_s is not null"),
          lambda v: v > 0, "0 laps carry a pace_delta_s without a measured base"),
    Check("F2", "compound seed cells fitted on their own (single-race) season",
          sql("select count(*) from dim_compounds_season where season <= 2024 and notes like 'fitted from % via cox_km_survival'"),
          lambda v: v > 0, "no cell's fit population includes its own season (needs fit provenance, round-1 T3)"),
    Check("F3", "browser reads manifest.input.n_features / feature_order, which v14 lacks",
          lambda c: ("n_features" not in json.loads(text("app/public/models/manifest.json"))["input"])
          and bool(re.search(r"input\.(n_features|feature_order)", text("app/src/ml/featureVector.ts"))),
          lambda v: v, "featureVector.ts reads models[i].feature_order (or the manifest carries the keys)"),
    Check("F4", "holdout resolves to MAX(race_year)+1, a season with no rows",
          lambda c: ("MAX(race_year) + 1" in text("ml/src/features.py"),
                     c.execute("select count(*) from fct_cliff_prediction_features where race_year = "
                               "(select max(race_year) + 1 from fct_cliff_prediction_features)").fetchone()[0]),
          lambda v: v[0] and v[1] == 0, "a declared holdout season with rows"),
    Check("F5", "one global theta_air across all seasons (ingesting a season relabels history)",
          sql("select count(distinct round(dirty_air_tax_s, 9)) filter (where dirty_air_tax_s > 0) from int_dirty_air_tax_component"),
          lambda v: v == 1, "theta windowed/frozen per version (more than one per-lap tax value, or a declared freeze)"),
    Check("F6", "fuel counts laps from the last VALID lap (reaches the race ending)",
          lambda c: c.execute(FUEL_INITIAL_SQL.format(expr="count(*)") + r"""
             where implied_race_laps + 0.5 < (select max(lap_number) from stg_laps s where s.race_id = r.race_id)""").fetchone()[0],
          lambda v: v > 0, "every race's implied fuel lap count equals its full lap count"),
    Check("F7", "latest-season rows with no seed cell (fabricated cliff features/labels)",
          sql("""select count(*) from fct_cliff_prediction_features
                 where race_year = (select max(race_year) from fct_cliff_prediction_features)
                   and compound in ('SOFT','MEDIUM','HARD') and compound_cliff_onset_laps is null"""),
          lambda v: v > 0, "every slick row has a seed cell"),
    Check("F8", "races missing from race_to_track (dropped by INNER JOIN)",
          sql("select count(distinct race_id) from stg_laps where race_id not in (select race_id from race_to_track)"),
          lambda v: v > 0, "0 races missing"),
    Check("F10", "qualifying chain reads race-day int_track_evolution",
          lambda c: "int_track_evolution" in text("transform/models/intermediate/int_lap_residual_decomposed_qualifying.sql"),
          lambda v: v, "no race-side ref in the qualifying decomposition"),
    Check("F11a", "features --check writes ml/models/encoders.json",
          lambda c: bool(re.search(r"persist_encoders\s*=\s*True", text("ml/src/features.py"))),
          lambda v: v, "the audit CLI never persists encoders"),
    Check("F11b", "latest-season slick laps with NULL compound_code (failing dbt test)",
          sql("""select count(*) from int_stint_geometry where race_year = (select max(race_year) from int_stint_geometry)
                 and compound_in_stint in ('SOFT','MEDIUM','HARD') and compound_code is null"""),
          lambda v: v > 0, "tyre_allocations covers the latest season"),
    Check("F12", "2018 excess share of rows with no car telemetry (fabricated free air)",
          sql("""select avg(case when gap_ahead_min_s is null then 1.0 else 0 end) filter (where race_year = 2018)
                      - avg(case when gap_ahead_min_s is null then 1.0 else 0 end) filter (where race_year > 2018)
                 from fct_cliff_prediction_features where is_training_eligible"""),
          lambda v: v > 0.02, "2018 no-telemetry rows NULL rather than free-air (or share in line with other seasons)"),
    Check("F13", "dim_events.race_id loaded as an integer-like string",
          sql(r"select count(*) from dim_events where race_id not like '%\_%' escape '\'"),
          lambda v: v > 0, "race_id typed VARCHAR in the seed config"),
    Check("F14", "disqualified drivers read as classified",
          sql("select count(*) from stg_results where status = 'Disqualified' and is_classified"),
          lambda v: v > 0, "0"),
    Check("F16", "per-season outputs picking an arbitrary constructor (ANY_VALUE)",
          sql("""select count(*) from mart_corner_skill_driver m join
                 (select race_year, driver_id from stg_results group by all having count(distinct constructor_id) > 1) x
                 using (race_year, driver_id)"""),
          lambda v: v > 0, "multi-team driver-seasons split or flagged"),
    Check("F17", "constructors falling to unknown_pu",
          sql("select count(*) from dim_constructors where pu_family = 'unknown_pu'"),
          lambda v: v > 0, "0"),
    Check("F18", "2020_1 lap numbering short of the 71-lap race",
          sql("select max(lap_number) from stg_laps where race_id = '2020_1'"),
          lambda v: v is not None and v < 71, "71 laps (re-pulled or declared)"),
    Check("F19", "raw_laps declares session_type, which bronze lacks",
          lambda c: bool(re.search(r"raw_laps\n(?:.*\n){0,12}?\s*- name: session_type", text("transform/models/staging/src_formula1.yml"))),
          lambda v: v, "column removed from the contract (or populated)"),
    Check("F20", "doc drift in the ML mart header",
          lambda c: "42nd feature" in text("transform/models/marts/fct_cliff_prediction_features.sql"),
          lambda v: v, "stale header lines removed"),
    Check("F21", "offline fits stop before the latest ingested season",
          lambda c: sorted({w for p in (REPO / "data/fits").glob("*.parquet")
                            for w in __import__("pyarrow.parquet", fromlist=["x"]).read_table(p, columns=["data_window"])
                            .column("data_window").to_pylist()}),
          lambda v: any(w.endswith("2024") for w in v), "data_window reaches the latest season"),

    # ── Round 2 ─────────────────────────────────────────────────────────────────
    Check("F22", "rubber/ambient subtracted twice (already inside base_track_pace_s)",
          lambda c: c.execute(r"""
            with rm as (select race_year, race_id, avg(track_state_index_s) mp from int_track_evolution group by all)
            select max(abs(r.base_track_pace_s - (rm.mp + e.rubber_component_s + e.ambient_component_s + e.unexplained_residual_s))),
                   avg(abs(r.driver_skill_residual_s - (r.pace_delta_s - r.fuel_component_s - coalesce(r.compound_component_s, 0)
                          - r.constructor_component_s - r.dirty_air_tax_s)))
            from int_lap_residual_decomposed r join int_track_evolution e using (race_year, race_id, lap_number)
            join rm using (race_year, race_id) where r.pace_delta_s is not null""").fetchone(),
          lambda v: v[0] < 1e-6 and v[1] > 1e-6,
          "either the base stops containing rubber/ambient, or the residual stops subtracting them"),
    Check("F23a", "theta_air calibration panel contains fabricated-base laps",
          sql("""select count(*) from int_dirty_air_tax_component d join int_lap_residual_decomposed r using (lap_id)
                 where r.base_track_pace_s is null"""),
          lambda v: v > 0, "0 (follows from fixing F1: partial residual becomes NULL there)"),
    Check("F23b", "laps behind a car billed 0 s dirty air because they were downweighted/wet",
          sql(r"""with lag as (select g.lap_id, lag(coalesce(a.dirty_air_share_lap, 0.0), 1, 0.0)
                    over (partition by g.stint_id order by g.lap_in_stint) s
                    from int_stint_geometry g left join int_lap_air_state a using (lap_id))
                  select count(*) from int_lap_residual_decomposed r join lag using (lap_id)
                  left join int_dirty_air_tax_component d using (lap_id) where d.lap_id is null and lag.s > 0"""),
          lambda v: v > 0, "tax applied to every spine lap; the panel filter only governs estimation"),
    Check("F24", "races whose bronze stint numbering ignores the pit stops",
          sql(STINT_BOUNDARY_SQL), lambda v: v > 0,
          "0 races with >= 5 stint boundaries lacking a pit stop (stints rebuilt from pits, or races quarantined)"),
    Check("F25", "2018 stint-1 laps with lap_in_stint one short (lap 1 unassigned)",
          sql("""select count(*) from int_stint_geometry where race_year = 2018 and stint_number = 1
                 and lap_number = 2 and lap_in_stint = 1"""),
          lambda v: v > 0, "lap 2 of stint 1 has lap_in_stint 2 in every race"),
    Check("F26", "races flagged mostly raining with no intermediate/wet tyre used",
          sql(r"""select count(*) from (
                    select l.race_id, avg(case when r.rainfall_flag then 1.0 else 0 end) rain,
                           avg(case when l.compound in ('INTERMEDIATE','WET') then 1.0 else 0 end) wet
                    from stg_laps l join int_lap_residual_decomposed r using (lap_id) group by 1)
                  where rain > 0.5 and wet < 0.05"""),
          lambda v: v > 0, "0 (wet flag derived from, or cross-checked against, tyre usage)"),
    Check("F27", "Wet-Race Specialist averages a skill that excludes every rain lap",
          lambda c: "race_wet_flag" in text("app/src/features/wet-race-specialist/queries.ts")
          and "lf.is_rain_lap = FALSE" in text("transform/models/marts/fct_driver_skill_features.sql"),
          lambda v: v, "wet skill computed on wet laps (or the page redefined)"),
    Check("F28", "Quali-vs-Race subtracts a positive=faster proxy from a negative=faster residual",
          lambda c: "AVG(f.driver_skill_proxy_mean_s)" in text("app/src/features/quali-vs-race-skill/queries.ts"),
          lambda v: v, "both sides on one sign convention and one reference frame"),
    Check("F29", "Blind-Test Scoreboard: 5-lap prediction vs 1-lap actual",
          lambda c: "next_lap_degradation_jump_s   AS actual_degradation_jump_s" in
          text("app/src/features/blind-test-scoreboard/queries.ts"),
          lambda v: v, "actual = the trained target (next_5_lap_cumulative_jump_s)"),
    Check("F30", "Tyre-Cliff Survival KM event is the seed rule itself",
          lambda c: "BOOL_OR(cliff_onset_passed)" in text("app/src/features/tyre-cliff-survival/queries.ts"),
          lambda v: v, "event from an observed pace cliff, not age > seed onset"),
    Check("F31", "pit-ended stints whose stop is lost (verdict NULL, cost 0)",
          sql("""select count(*) from int_pit_strategy_value pv join int_stint_end_regime e using (stint_id)
                 where e.stint_end_cause in ('green_pit','sc_pit','vsc_pit','red') and pv.actual_pit_lap is null"""),
          lambda v: v > 0, "0"),
    Check("F32", "races whose modelled starting fuel exceeds the FIA maximum",
          lambda c: c.execute(FUEL_INITIAL_SQL.format(expr="count(*)") +
                              " where initial_kg > case when race_year = 2018 then 105 else 110 end").fetchone()[0],
          lambda v: v > 0, "0"),
    Check("F33", "2018 qualifying laps dropped by the IsAccurate gate",
          sql("""select avg(case when is_accurate then 1.0 else 0 end) from stg_laps_qualifying
                 where race_year = 2018 and lap_time_s is not null and not is_pit_lap"""),
          lambda v: v < 0.9 and "AND is_accurate" in text("transform/models/staging/stg_laps_qualifying.sql"),
          "gate no longer drops accurate-in-fact 2018 quali laps"),
    Check("F34", "dbt tests that cannot fail (placeholders + pass-by-construction)",
          lambda c: sum(bool(re.search(r"SELECT\s+1\s+WHERE\s+FALSE", p.read_text(), re.I))
                        for p in (REPO / "transform/tests").glob("*.sql")) + (
              "WHERE dirty_air_tax_s < 0" in text("transform/tests/assert_aero_penalty_negative.sql"))
          + ("rubber_component_s > prev_rubber_component_s" in text("transform/tests/assert_track_evolution_monotone.sql")),
          lambda v: v > 0, "placeholders deleted or wired up; clamped quantities tested before the clamp"),
    Check("F35", "circuit x constructor interaction added on top of a per-race constructor level",
          lambda c: "cci.circuit_constructor_interaction_s" in text("transform/models/intermediate/int_lap_residual_decomposed.sql"),
          lambda v: v, "interaction dropped from the lap residual (or structural pace made seasonal)"),
    Check("F36", "Lap Waterfall / Race Lost add track_unexplained_s to the reconstructed delta",
          lambda c: "COALESCE(AVG(track_unexplained_s), 0)  AS pace_delta_s" in text("app/src/features/lap-waterfall/queries.ts"),
          lambda v: v, "delta = explained + skill"),
    Check("F37", "home page: circuits counted from dim_circuits rows; model count from *_v1.onnx",
          lambda c: ('SELECT COUNT(*) FROM dim_circuits' in text("scripts/export_app_data.py"),
                     '"*_v1.onnx"' in text("scripts/export_app_data.py")),
          lambda v: v[0] or v[1], "counts derived from raced venues and the shipped version's card"),

    # ── Round 3 ─────────────────────────────────────────────────────────────────
    # Full evidence: transform_forensic_audit_report_round3.md and round3/r3_*.py.
    Check("F38", "field base is fuel-neutral but not compound-neutral (residual carries -field compound cost)",
          # Mean residual on laps with a measured base: -1.96 s as built, +0.33 s against a
          # compound-neutral base (round3/r3_compound_in_field_base.py Part 2). F1/F22 fixes do not move it.
          lambda c: round(c.execute("select avg(driver_skill_residual_s) from int_lap_residual_decomposed "
                                    "where base_track_pace_s is not null").fetchone()[0], 3),
          lambda v: v < -1.0,
          "base built from compound-corrected laps (or the residual subtracts own-minus-field compound); "
          "mean residual on measured laps near 0, not ~-2 s"),
    Check("F39", "NULL tyre age becomes the 10 s wear cap (DuckDB LEAST skips NULL)",
          sql("""select count(*) from int_lap_residual_decomposed r join int_compound_cliff_predicted c using (lap_id)
                 where r.age_in_stint is null and c.compound_wear_s >= 10.0"""),
          lambda v: v > 0, "0 (NULL age gives a NULL compound term)"),
    Check("F40", "equal-car rating = own P20 minus teammate MEDIAN (pairs sum to ~-1.8 s, not 0)",
          lambda c: c.execute("""select round(avg(s), 3), count(*) filter (where both_neg) from (
                select sum(driver_skill_loro_s) s, bool_and(driver_skill_loro_s < 0) both_neg from int_driver_race_skill_loro
                where driver_skill_loro_s is not null group by race_year, race_id, constructor_id having count(*) = 2)""").fetchone(),
          lambda v: v[0] < -0.5, "two-driver cars' ratings sum to ~0 (same statistic on both sides)"),
    Check("F41a", "seed cells noted 'fitted via cox_km_survival' that carry class-default parameters",
          lambda c: c.execute(
              "select count(*) from dim_compounds_season s join (select * from (values " +
              ",".join(f"('{k}',{v['cliff_onset_laps']},{v['cliff_severity']},{v['wear_gradient']})"
                       for k, v in _compound_defaults().items()) +
              ") t(cc, o, sv, g)) d on d.cc = s.compound_code where s.notes like 'fitted from % via cox_km_survival' and "
              "(abs(s.compound_cliff_onset_laps - d.o) < 1e-9 or abs(s.compound_cliff_severity - d.sv) < 1e-9 "
              "or abs(s.compound_wear_gradient - d.g) < 1e-9)").fetchone()[0],
          lambda v: v > 0, "every defaulted parameter is labelled as a default in fit_source/notes (per parameter)"),
    Check("F41b", "wear gradient fitted on lap times that still contain the fuel burn",
          lambda c: "COALESCE(np.normalized_pace_s, l.lap_time_s) AS normalized_pace_s"
          in text("transform/tasks/coefficients/fit_compound_cliff.py")
          and "weight_corrected" not in text("transform/tasks/coefficients/fit_compound_cliff.py"),
          lambda v: v, "estimate_wear_gradient receives fuel-corrected pace"),
    Check("F42a", "unitless compound_grip_peak (0.95-1.09) added to expected_compound_pace_s as seconds",
          lambda c: ("COALESCE(compound_grip_peak, 0.0)" in text("transform/models/intermediate/int_compound_cliff_predicted.sql"),
                     c.execute("select min(compound_grip_peak), max(compound_grip_peak) from dim_compounds_season").fetchone()),
          lambda v: v[0], "grip removed from the pace sum, or replaced by a fitted per-compound offset in seconds"),
    Check("F42b", "temperature term never fires on a slick lap with a seed cell (track temp vs tyre window)",
          sql("""select count(*) filter (where c.ambient_temp_delta > 0) from int_compound_cliff_predicted c
                 join race_to_track rt on rt.race_id = c.race_id
                 join dim_compounds_season s on s.circuit_key = rt.track_id and s.season = c.race_year and s.compound_code = c.compound
                 where c.compound in ('SOFT','MEDIUM','HARD')"""),
          lambda v: v == 0, "the term is fitted against a temperature on the same scale (or dropped)"),
    Check("F43", "int_lap_proximity keeps pit-lane crossings in the car-ahead ordering",
          lambda c: not re.search(r"stg_pits|pit_in_time|pit_lane|is_pit", text("transform/models/intermediate/int_lap_proximity.sql")),
          lambda v: v, "crossings between pit-in and pit-out excluded (re-run round3/r3_proximity_pitlane_car_ahead.py: 0 changed laps)"),
    Check("F44", "Driver Circuit Affinity draws the absolute rating as 'vs own average' (share of cells green)",
          lambda c: (round(c.execute("select avg(case when shrunk_affinity_s < 0 then 1.0 else 0 end) "
                                     "from int_driver_circuit_affinity where n_obs >= 2").fetchone()[0], 3),
                     "a.shrunk_affinity_s," in text("app/src/features/driver-circuit-affinity/queries.ts")),
          lambda v: v[0] > 0.9 and v[1], "page draws shrunk_affinity_s minus the driver's global mean (about half the cells green)"),
    Check("F45", "era offset reverses the between-era field-mean gap (pre - post, before vs after)",
          lambda c: c.execute("""select round(max(u) filter (where pre) - max(u) filter (where not pre), 4),
                  round(max(a) filter (where pre) - max(a) filter (where not pre), 4) from (
                  select season < 2022 pre, avg(shrunk_residual_s) u, avg(era_adjusted_rating) a
                  from int_era_normalized_driver_rating group by 1)""").fetchone(),
          lambda v: v[0] * v[1] < 0 or abs(v[1]) > abs(v[0]),
          "no offset on a teammate-relative rating, or one that shrinks the field-mean gap"),
    Check("F46", "Hidden Performance: false self-scenario identity text; rank on fuel-inclusive mean",
          lambda c: ("predicted finish equals actual finish" in text("app/src/features/hidden-performance/methodology.tsx"),
                     "ORDER BY predicted_mean_lap_s ASC" in text("transform/models/marts/fct_ghost_race_finish.sql")),
          lambda v: v[0] or v[1], "text removed and rank keyed on predicted_mean_residual_pace_s"),
    Check("F47", "push_residual built on raw lap time (fuel burn read as pushing): share 'pushing' at lap_in_stint > 20",
          lambda c: ("SELECT lap_id, lap_time_s\n    FROM {{ ref('stg_laps') }}" in text("transform/models/intermediate/int_lap_thermal_proxy.sql"),
                     round(c.execute("""select avg(case when t.push_residual > 0 then 1.0 else 0 end)
                         from fct_cliff_prediction_features f join int_lap_thermal_proxy t using (lap_id)
                         where f.is_training_eligible and f.lap_in_stint > 20 and t.push_residual is not null""").fetchone()[0], 3)),
          lambda v: v[0], "baseline and residual on fuel-corrected lap time (share pushing late in stints ~0.3, not ~0.68)"),
    Check("F48", "S2 gap < 1 s with DRS coded 'drs_train' (dirty_air_share 0) while 1.0-1.5 s is dirty air",
          lambda c: "WHEN gap_median_s < 1.0 AND drs_active = 1 THEN 'drs_train'"
          in text("transform/models/intermediate/int_lap_air_state.sql"),
          lambda v: v, "share monotone in gap: S2 < 1.5 s counts as dirty air whatever DRS did"),
    Check("F49", "surface/bulk ratio capped at 0.5 by construction; 'surface_driven' (>0.65) unreachable",
          lambda c: c.execute("""select round(max(surface_bulk_ratio), 3), count(*) filter (where degradation_source = 'surface_driven')
                                 from int_tyre_surface_vs_bulk_decoupling""").fetchone(),
          lambda v: v[0] <= 0.5 and v[1] == 0, "loads normalised so the ratio can span its classes (or the class removed)"),
]


def main(argv: list[str]) -> int:
    wanted = set(argv)
    c = con()
    rows, n_present = [], 0
    for ch in CHECKS:
        if wanted and ch.id not in wanted:
            continue
        try:
            v = ch.measure(c)
            status = "PRESENT" if ch.present(v) else "CLEARED"
        except Exception as e:  # a broken check must not hide the rest of the board
            v, status = f"{type(e).__name__}: {str(e).splitlines()[0][:70]}", "ERROR"
        n_present += status == "PRESENT"
        if isinstance(v, float):
            v = round(v, 4)
        elif isinstance(v, tuple):
            v = tuple(float(f"{x:.4g}") if isinstance(x, float) else x for x in v)
        rows.append((ch.id, status, str(v)[:60], ch.title))
    w = max(len(r[2]) for r in rows)
    for r in rows:
        print(f"{r[0]:5s} {r[1]:8s} {r[2]:<{w}s}  {r[3]}")
    print(f"\n{n_present} present / {len(rows)} checked  "
          f"(manual-only findings not on this board: F9, F15 -- see the reports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
