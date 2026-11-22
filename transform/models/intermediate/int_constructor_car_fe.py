"""int_constructor_car_fe.py · intermediate · grain: one row per (race_year, race_id, constructor_id).

De-biased constructor car pace (constructor x race fixed effect), derived in the warehouse on every build.

Previously this model was a thin reader of data/fits/constructor_car_fe.parquet, which a separate fitter
wrote on demand. The fit now runs here, from the same upstream models the fitter read:
int_lap_fuel_state, int_field_pace_curve, stg_laps, int_event_corrections, int_lap_rain_state (dry-lap rain state).
The parquet is no longer read by this model. The driver-isolation car term
(int_constructor_car_fe_isolation) still reads its own parquet.

FIT (identical to tasks/coefficients/fit_constructor_car_fe.py, which this model imports so there is one copy):
    pace_delta_s ~ 1 | driver_id + constructor_race
    on the clean lap panel (PANEL_QUERY: dry laps, correction_weight = 1.0), then re-centred so the
    WDC-winning constructor is at 0.0 in each year. Negative = faster than field.

Consumed only by int_driver_race_skill_loro.driver_skill_field_s, then int_driver_circuit_era_affinity.
"""
import sys
from pathlib import Path

import duckdb

# transform/ holds the `tasks` package. dbt runs a copy of this file from target/run/, so
# __file__ is not the source location: search up from the file and from the working
# directory (dbt is run from transform/) for the first folder that has tasks/coefficients.
def _find_transform_dir() -> Path:
    starts = [Path.cwd(), Path(__file__).resolve()]
    for start in starts:
        for p in [start, *start.parents]:
            if (p / "tasks" / "coefficients").is_dir():
                return p
    raise RuntimeError("cannot locate transform/tasks/coefficients from " + str(starts))


TRANSFORM_DIR = _find_transform_dir()
if str(TRANSFORM_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSFORM_DIR))

from tasks.coefficients.fit_constructor_car_fe import (  # noqa: E402
    PANEL_QUERY,
    fit_car_fe,
    load_panel,
)

def model(dbt, session):
    dbt.config(materialized='table', tags=['causal_decomposition', 'constructor'])

    # PANEL_QUERY names its inputs as plain tables, so register each dbt ref under its own name
    # in a private in-memory DuckDB and run the fitter's own panel query against it.
    # dbt parses ref() arguments statically, so the names are written out as literals.
    con = duckdb.connect()
    try:
        con.register('int_lap_fuel_state', dbt.ref('int_lap_fuel_state').df())
        con.register('int_field_pace_curve', dbt.ref('int_field_pace_curve').df())
        con.register('stg_laps', dbt.ref('stg_laps').df())
        con.register('int_event_corrections', dbt.ref('int_event_corrections').df())
        con.register('int_lap_rain_state', dbt.ref('int_lap_rain_state').df())
        panel = load_panel(con)
    finally:
        con.close()

    out = fit_car_fe(panel)

    out = out.assign(
        constructor_car_fe_id=(
            out.race_year.astype(str) + '_'
            + out.race_id.astype(str) + '_'
            + out.constructor_id.astype(str)
        ),
        race_year=out.race_year.astype('int32'),
        race_id=out.race_id.astype(str),
        constructor_id=out.constructor_id.astype(str),
        car_fe_s=out.car_fe_s.astype('float64'),
    )
    return out[['constructor_car_fe_id', 'race_year', 'race_id', 'constructor_id', 'car_fe_s']]
