"""int_constructor_car_fe_isolation.py · intermediate · grain: one row per (race_year, race_id, constructor_id) present in Ω.

Driver-isolation car term (WI-16a): the constructor×race FE fitted on the isolation panel, derived in the
warehouse on every build.

Previously a thin reader of data/fits/constructor_car_fe_isolation.parquet, written by a separate fitter run.
The fit now runs here, from int_driver_isolation_lap_panel, the same model the fitter used to read.
The parquet is no longer read.

FIT (identical to tasks/coefficients/fit_constructor_car_fe.py, which this model imports so there is one copy):
    per era (pre/post era_boundary):  mean_y_s ~ 1 | driver_id + constructor_race
    on driver-race means of the pre-cliff laps (ISOLATION_PANEL_QUERY), re-centred to a lap-weighted mean of
    zero inside each race. Negative = faster than the race's lap-weighted car.
    An island team gets car_term_source = 'unidentified', a singleton cell 'not_estimated'. Both have
    car_iso_s NULL, never 0.

Why a second car term, not int_constructor_car_fe: that one is fitted on pace_delta_s, before compound and
dirty air are taken out. The isolation ratings subtract the car from y_s, which has both removed already.
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
    fit_car_fe_isolation,
    load_isolation_panel,
)


def model(dbt, session):
    dbt.config(materialized='table', tags=['driver_isolation', 'constructor'])

    # ISOLATION_PANEL_QUERY names its input as a plain table, so register the dbt ref under that
    # name in a private in-memory DuckDB and run the fitter's own panel query against it.
    # dbt parses ref() arguments statically, so the name is written out as a literal.
    con = duckdb.connect()
    try:
        con.register('int_driver_isolation_lap_panel', dbt.ref('int_driver_isolation_lap_panel').df())
        lap_panel = load_isolation_panel(con)
    finally:
        con.close()

    out, note = fit_car_fe_isolation(lap_panel)

    out = out.assign(
        constructor_car_fe_isolation_id=(
            out.race_year.astype(str) + '_'
            + out.race_id.astype(str) + '_'
            + out.constructor_id.astype(str)
        ),
        race_year=out.race_year.astype('int32'),
        race_id=out.race_id.astype(str),
        constructor_id=out.constructor_id.astype(str),
        era=out.era.astype(str),
        n_laps=out.n_laps.astype('int32'),
        car_fe_raw_s=out.car_fe_raw_s.astype('float64'),
        car_iso_s=out.car_iso_s.astype('float64'),
        car_term_source=out.car_term_source.astype(str),
        race_components_n=out.race_components_n.astype('int32'),
        connectivity_note=note,
    )
    return out[[
        'constructor_car_fe_isolation_id', 'race_year', 'race_id', 'constructor_id', 'era',
        'n_laps', 'car_fe_raw_s', 'car_iso_s', 'car_term_source', 'race_components_n',
        'connectivity_note',
    ]]
