"""AX-05: query catalogue v1 - narrow qv_* views over the files the export just wrote.

Second export stage (finding 1): every view is built in an in-memory DuckDB with read_parquet over
the parquet the same run published, never from the warehouse, so a view is provably a subset of
published data. Observed measures only (HD4 A): every modelled column (components, residuals,
ratings, predictions, hazards, dirty-air prices, EB-shrunk priors) is left out and a deny-list
check fails the export if one slips in.

Writes:
  <out>/assistant/qv/<view>.parquet                       (small views)
  <out>/assistant/qv/<view>/<season>.parquet              (qv_laps)
  <out>/assistant/qv/<view>/<season>/<race_id>.parquet    (qv_teammate_corners)
  <out>/assistant/catalogue.json                          (views, ops, aggregates, limits, catalogue_version)

Hook: export_app_data._run_export_to calls export_query_views(...) after the last table export and
before the manifest. Tests: scripts/tests/test_assistant_query_views.py.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = 1
MAX_FILE_BYTES = 5 * 1024 * 1024

# Column names that must never appear in a qv_* view. The AX-05 list, the 2026-11-08 log additions
# (dirty_air_tax_se_s, cumulative_dirty_air_tax_race_s) and the AX-05 tightenings (any hazard column,
# EB-shrunk priors, the pit-loss prior, pit verdicts and optima, interval / SE columns, traffic channels).
DENY_PATTERNS: list[str] = [
    r"_component_s$", r"residual", r"rating", r"predicted", r"dirty_air", r"hazard",
    r"tyre_management_score", r"cliff_lap_in_stint", r"cumulative_dirty_air_tax_s", r"teammate_gap_s",
    r"dirty_air_tax_se_s", r"cumulative_dirty_air_tax_race_s",
    # AX-05 tightenings
    r"shrunk", r"pit_lane_loss", r"pit_loss", r"optimal", r"verdict", r"opportunity_cost",
    r"pit_decision_class", r"ci_low", r"ci_high", r"_se_s$", r"confidence", r"skill",
    r"air_state", r"share_lap", r"gap_ahead", r"anomaly", r"falloff", r"total_explained",
]

OPS: dict[str, dict] = {
    "eq": {"arity": "scalar", "sql": "="},
    "ne": {"arity": "scalar", "sql": "<>"},
    "lt": {"arity": "scalar", "sql": "<"},
    "lte": {"arity": "scalar", "sql": "<="},
    "gt": {"arity": "scalar", "sql": ">"},
    "gte": {"arity": "scalar", "sql": ">="},
    "in": {"arity": "list", "sql": "IN"},
    "between": {"arity": "pair", "sql": "BETWEEN"},
}
AGGREGATES: dict[str, str] = {
    "count": "COUNT(*) of the rows matched (use the view's count_name as col).",
    "avg": "Arithmetic mean of non-null values.",
    "median": "Median of non-null values.",
    "min": "Minimum.",
    "max": "Maximum.",
    "sum": "Sum; only on count-like measures.",
}
ORDERS = ["value_asc", "value_desc", "group_asc"]
LIMITS = {
    "max_filters": 6,
    "max_in_values": 20,
    "max_group_by": 2,
    "max_limit": 25,
    "max_string_length": 64,
    "timeout_ms": 3000,
    "thin_n": 5,
    "decimals": 3,
}

STR_OPS = ["eq", "ne", "in"]
INT_OPS = ["eq", "ne", "lt", "lte", "gt", "gte", "in", "between"]
BOOL_OPS = ["eq"]
STAT = ["avg", "median", "min", "max"]
COUNTLIKE = ["avg", "median", "min", "max", "sum"]


def dim(name: str, typ: str, description: str, ops: list[str] | None = None, group_by: bool = True) -> dict:
    default = {"string": STR_OPS, "integer": INT_OPS, "boolean": BOOL_OPS, "number": INT_OPS}[typ]
    return {"name": name, "role": "dimension", "type": typ, "ops": ops if ops is not None else default,
            "aggregates": [], "group_by": group_by, "description": description}


def meas(name: str, typ: str, description: str, aggregates: list[str] | None = None) -> dict:
    return {"name": name, "role": "measure", "type": typ, "ops": [], "aggregates": aggregates or STAT,
            "group_by": False, "description": description}


SEASON = dim("season", "integer", "Season (race_year).")
RACE = dim("race_id", "string", "Race id, <season>_<round> (e.g. 2024_8). Use list_values(domain: race).")
DRIVER = dim("driver_id", "string", "Three-letter driver code (e.g. LEC).")
CONSTRUCTOR = dim("constructor_id", "string", "Constructor id for that season.")

# Each view: sources (published tables the SQL reads), sql, partition ('season' | 'season_race' | None).
VIEWS: list[dict] = [
    {
        "name": "qv_laps",
        "grain": "driver x lap",
        "note": ("Green racing laps only: fct_lap_residuals is pre-filtered (no safety-car, VSC or red-flag "
                 "laps). Observed lap times, not fuel- or tyre-corrected. Major outlier laps are excluded "
                 "unless the request filters on is_major_outlier_lap."),
        "sources": ["fct_lap_residuals"],
        "partition": "season",
        "count_name": "laps",
        "required_filters": ["season"],
        "group_by_requires": {"lap_number": ["race_id"]},
        "default_filters": [{"col": "is_major_outlier_lap", "op": "eq", "val": False}],
        "max_seasons": 2,
        "sql": """
            SELECT race_year AS season, race_id, driver_id, constructor_id, compound, stint_id,
                   lap_number, CAST(lap_in_stint AS INTEGER) AS lap_in_stint, age_in_stint,
                   is_major_outlier_lap, lap_time_s
            FROM fct_lap_residuals
            ORDER BY season, race_id, driver_id, lap_number, lap_id
        """,
        "columns": [
            SEASON, RACE, DRIVER, CONSTRUCTOR,
            dim("compound", "string", "Tyre compound name (SOFT, MEDIUM, HARD, INTERMEDIATE, WET, and pre-2019 names)."),
            dim("stint_id", "string", "Stint id."),
            dim("lap_number", "integer", "Lap number in the race. Grouping by it requires a race_id filter."),
            dim("lap_in_stint", "integer", "Lap number within the stint (1 = first lap of the stint)."),
            dim("age_in_stint", "integer", "Tyre age in laps at that lap."),
            dim("is_major_outlier_lap", "boolean", "Major outlier lap flag (int_event_corrections). Excluded by default."),
            meas("lap_time_s", "number", "Observed lap time in seconds."),
        ],
    },
    {
        "name": "qv_stints",
        "grain": "stint",
        "note": ("One row per stint (fct_stint_features). Censored stints (ended by the flag or a retirement) "
                 "are not tyre-life observations: filter on is_censored_stint. mean_clean_pace_s is filled "
                 "only on sc_pit / vsc_pit runs."),
        "sources": ["fct_stint_features"],
        "partition": None,
        "count_name": "stints",
        "required_filters": ["season"],
        "group_by_requires": {},
        "default_filters": [],
        "max_seasons": None,
        "sql": """
            SELECT race_year AS season, race_id, driver_id, constructor_id, stint_id, compound,
                   stint_end_cause, is_censored_stint, reached_flag, short_stint_flag,
                   CAST(stint_length_laps AS INTEGER) AS stint_length_laps, starting_tyre_age_laps,
                   mean_clean_pace_s
            FROM fct_stint_features
            ORDER BY season, race_id, driver_id, stint_id
        """,
        "columns": [
            SEASON, RACE, DRIVER, CONSTRUCTOR,
            dim("stint_id", "string", "Stint id."),
            dim("compound", "string", "Tyre compound name."),
            dim("stint_end_cause", "string", "Why the stint ended: green_pit, sc_pit, vsc_pit, red, race_end, retirement."),
            dim("is_censored_stint", "boolean", "TRUE when the stint ended at the flag or in a retirement (no tyre-change decision)."),
            dim("reached_flag", "boolean", "TRUE race_end; FALSE green / SC / VSC tyre change; NULL on a red-flag change, a retirement or an unassigned stint."),
            dim("short_stint_flag", "boolean", "TRUE when the stint is under 3 laps."),
            meas("stint_length_laps", "integer", "Laps in the stint.", COUNTLIKE),
            meas("starting_tyre_age_laps", "integer", "Tyre age in laps at the start of the stint."),
            meas("mean_clean_pace_s", "number", "Mean fuel-corrected lap time over the run's clean laps; only on sc_pit / vsc_pit runs, else NULL."),
        ],
    },
    {
        "name": "qv_pit_stops",
        "grain": "pit stop",
        "note": ("One row per stint that ended in a pit stop (stint_end_cause green_pit / sc_pit / vsc_pit, or a "
                 "recorded actual_pit_lap). compound_after is the next stint's compound in stint order; NULL "
                 "after the last stint. actual_pit_lap is NULL where int_pit_strategy_value has no row for the "
                 "stint. No pit-lane loss: the published value is a venue prior, not this stop's time."),
        "sources": ["fct_stint_features", "int_pit_strategy_value"],
        "partition": None,
        "count_name": "stops",
        "required_filters": ["season"],
        "group_by_requires": {},
        "default_filters": [],
        "max_seasons": None,
        "sql": """
            WITH sf AS (
                SELECT *, TRY_CAST(regexp_extract(stint_id, '_(\\d+)$', 1) AS INTEGER) AS stint_number
                FROM fct_stint_features
            ), ordered AS (
                SELECT sf.*, LEAD(compound) OVER (
                    PARTITION BY race_id, driver_id ORDER BY stint_number NULLS LAST, stint_id
                ) AS compound_after
                FROM sf
            )
            SELECT o.race_year AS season, o.race_id, o.driver_id, o.constructor_id, o.stint_id,
                   o.stint_end_cause, o.compound AS compound_before, o.compound_after,
                   pv.actual_pit_lap
            FROM ordered AS o
            LEFT JOIN int_pit_strategy_value AS pv USING (stint_id)
            WHERE pv.actual_pit_lap IS NOT NULL OR o.stint_end_cause IN ('green_pit', 'sc_pit', 'vsc_pit')
            ORDER BY season, o.race_id, o.driver_id, o.stint_id
        """,
        "columns": [
            SEASON, RACE, DRIVER, CONSTRUCTOR,
            dim("stint_id", "string", "The stint the stop ended."),
            dim("stint_end_cause", "string", "green_pit, sc_pit, vsc_pit (or red / retirement with a recorded pit lap)."),
            dim("compound_before", "string", "Compound of the stint the stop ended."),
            dim("compound_after", "string", "Compound of the next stint; NULL after the last stint."),
            meas("actual_pit_lap", "integer", "Race lap of the stop; NULL where not recorded.", ["min", "max", "median", "avg"]),
        ],
    },
    {
        "name": "qv_driver_race",
        "grain": "driver x race",
        "note": ("Rows are the driver-races in mart_race_driver_summary, which carries only drivers with a paired "
                 "teammate lap (3,138 of about 3,275 driver-races). actual_finish_position and actual_dnf_cause "
                 "come from fct_ghost_race_finish self-scenario rows and are NULL where that table has none "
                 "(it keeps recombination_confidence >= 0.3); NULL is missing, never 0. timed_laps counts valid "
                 "timed laps, not classified laps completed."),
        "sources": ["mart_race_driver_summary", "fct_ghost_race_finish"],
        "partition": None,
        "count_name": "races",
        "required_filters": [],
        "group_by_requires": {},
        "default_filters": [],
        "max_seasons": None,
        "sql": """
            WITH actual AS (
                SELECT race_id, ego_driver_id AS driver_id,
                       MIN(actual_finish_position) AS actual_finish_position,
                       MIN(actual_dnf_cause) AS actual_dnf_cause
                FROM fct_ghost_race_finish
                WHERE is_self_scenario
                GROUP BY 1, 2
            )
            SELECT m.race_year AS season, m.race_id, m.circuit_id, m.driver_id, m.constructor_id,
                   m.has_dnf, a.actual_dnf_cause,
                   m.positions_gained, CAST(m.laps_completed AS INTEGER) AS timed_laps,
                   m.avg_lap_time_s, CAST(m.n_clean_laps AS INTEGER) AS n_clean_laps,
                   a.actual_finish_position
            FROM mart_race_driver_summary AS m
            LEFT JOIN actual AS a USING (race_id, driver_id)
            ORDER BY season, m.race_id, m.driver_id
        """,
        "columns": [
            SEASON, RACE,
            dim("circuit_id", "string", "Circuit id."),
            DRIVER, CONSTRUCTOR,
            dim("has_dnf", "boolean", "Did not finish."),
            dim("actual_dnf_cause", "string", "Retirement cause; NULL when finished or not available."),
            meas("positions_gained", "integer", "Grid position minus finish position.", COUNTLIKE),
            meas("timed_laps", "integer", "Valid timed laps in the race (not classified laps completed).", COUNTLIKE),
            meas("avg_lap_time_s", "number", "Mean observed lap time over valid laps (s)."),
            meas("n_clean_laps", "integer", "Clean (ml_eligible) laps in the race.", COUNTLIKE),
            meas("actual_finish_position", "integer", "Classified finish position; NULL where not available."),
        ],
    },
    {
        "name": "qv_race_laps",
        "grain": "race x lap",
        "note": "One row per race lap with its caution status (red flag > safety car > VSC > green).",
        "sources": ["race_caution_timeline"],
        "partition": None,
        "count_name": "laps",
        "required_filters": ["season"],
        "group_by_requires": {"lap_number": ["race_id"]},
        "default_filters": [],
        "max_seasons": None,
        "sql": """
            SELECT race_year AS season, race_id, circuit_slug, lap_number, caution_status, race_laps
            FROM race_caution_timeline
            ORDER BY season, race_id, lap_number
        """,
        "columns": [
            SEASON, RACE,
            dim("circuit_slug", "string", "Event slug (e.g. british_grand_prix)."),
            dim("lap_number", "integer", "Lap number."),
            dim("caution_status", "string", "green, vsc, safety_car, red_flag."),
            meas("race_laps", "integer", "Laps in the race (max lap number).", ["max", "min"]),
        ],
    },
    {
        "name": "qv_circuit_history",
        "grain": "circuit x season",
        "note": "Counts only, from int_sc_hazard_history. prior_* count earlier seasons at the event; 2018 has none.",
        "sources": ["int_sc_hazard_history"],
        "partition": None,
        "count_name": "rows",
        "required_filters": [],
        "group_by_requires": {},
        "default_filters": [],
        "max_seasons": None,
        "sql": """
            SELECT circuit_slug, season,
                   CAST(season_races_n AS INTEGER) AS season_races_n,
                   CAST(prior_races_n AS INTEGER) AS prior_races_n,
                   CAST(prior_racing_laps AS INTEGER) AS prior_racing_laps,
                   CAST(prior_sc_onsets AS INTEGER) AS prior_sc_onsets,
                   CAST(prior_vsc_onsets AS INTEGER) AS prior_vsc_onsets
            FROM int_sc_hazard_history
            ORDER BY circuit_slug, season
        """,
        "columns": [
            dim("circuit_slug", "string", "Event slug."),
            SEASON,
            meas("season_races_n", "integer", "Races at the event that season.", ["sum", "max"]),
            meas("prior_races_n", "integer", "Races at the event in earlier seasons.", ["sum", "max"]),
            meas("prior_racing_laps", "integer", "Racing laps at the event in earlier seasons.", ["sum", "max"]),
            meas("prior_sc_onsets", "integer", "Safety-car deployments at the event in earlier seasons.", ["sum", "max"]),
            meas("prior_vsc_onsets", "integer", "VSC deployments at the event in earlier seasons.", ["sum", "max"]),
        ],
    },
    {
        "name": "qv_teammate_corners",
        "grain": "teammate pair x corner x lap",
        "note": ("Teammate pairs only (same constructor in that race, driver_a < driver_b). Deltas are "
                 "driver_a minus driver_b and NULL where either side is missing, never 0 (CO-22). One race per "
                 "request: race_id must be a single eq filter."),
        "sources": ["fct_telemetry_deltas", "fct_lap_residuals"],
        "partition": "season_race",
        "count_name": "corners",
        "required_filters": ["season", "race_id"],
        "group_by_requires": {},
        "default_filters": [],
        "max_seasons": 1,
        "sql": """
            WITH con AS (
                SELECT DISTINCT race_id, driver_id, constructor_id FROM fct_lap_residuals
            )
            SELECT td.race_year AS season, td.race_id, td.track_id AS circuit_slug, a.constructor_id,
                   td.driver_a, td.driver_b, td.corner_name, td.lap_number,
                   td.braking_point_delta_m, td.v_min_delta_kph, td.throttle_point_delta_m
            FROM fct_telemetry_deltas AS td
            JOIN con AS a ON a.race_id = td.race_id AND a.driver_id = td.driver_a
            JOIN con AS b ON b.race_id = td.race_id AND b.driver_id = td.driver_b
            WHERE a.constructor_id = b.constructor_id
            ORDER BY season, td.race_id, td.driver_a, td.driver_b, td.corner_name, td.lap_number
        """,
        "columns": [
            SEASON,
            dim("race_id", "string", "Race id; a single eq filter is required.", ["eq"]),
            dim("circuit_slug", "string", "Event slug."),
            CONSTRUCTOR,
            dim("driver_a", "string", "First driver of the pair (alphabetically smaller code)."),
            dim("driver_b", "string", "Second driver of the pair."),
            dim("corner_name", "string", "Named corner (e.g. Turn_1)."),
            dim("lap_number", "integer", "Lap number."),
            meas("braking_point_delta_m", "number", "driver_a minus driver_b braking point (m); positive = driver_a brakes later.", ["avg", "median"]),
            meas("v_min_delta_kph", "number", "driver_a minus driver_b minimum corner speed (km/h); positive = driver_a carries more speed.", ["avg", "median"]),
            meas("throttle_point_delta_m", "number", "driver_a minus driver_b throttle-application point (m); positive = driver_a gets on power later.", ["avg", "median"]),
        ],
    },
    {
        "name": "qv_circuits",
        "grain": "circuit (event slug)",
        "note": "Reference facts only (dim_circuits); modelled indices and fuel constants are left out.",
        "sources": ["dim_circuits"],
        "partition": None,
        "count_name": "circuits",
        "required_filters": [],
        "group_by_requires": {},
        "default_filters": [],
        "max_seasons": None,
        "sql": """
            SELECT circuit_key, circuit_id, circuit_name, lap_length_km, corner_count, era_start_year
            FROM dim_circuits
            ORDER BY circuit_key
        """,
        "columns": [
            dim("circuit_key", "string", "Event slug (matches circuit_slug elsewhere)."),
            dim("circuit_id", "string", "Physical venue id."),
            dim("circuit_name", "string", "Venue name."),
            meas("lap_length_km", "number", "Lap length (km)."),
            meas("corner_count", "integer", "Number of corners."),
            meas("era_start_year", "integer", "First year of the current layout.", ["min", "max"]),
        ],
    },
    {
        "name": "qv_compounds",
        "grain": "circuit x season x compound",
        "note": ("Keys of dim_compounds_season only: which compounds have a profile for each event and season. "
                 "The fitted compound parameters are modelled and left out. Not a list of compounds actually run."),
        "sources": ["dim_compounds_season"],
        "partition": None,
        "count_name": "compounds",
        "required_filters": [],
        "group_by_requires": {},
        "default_filters": [],
        "max_seasons": None,
        "sql": """
            SELECT season, circuit_key, compound_code
            FROM dim_compounds_season
            ORDER BY season, circuit_key, compound_code
        """,
        "columns": [
            SEASON,
            dim("circuit_key", "string", "Event slug."),
            dim("compound_code", "string", "Compound name."),
        ],
    },
]

PARQUET_TYPE = {"VARCHAR": "string", "INTEGER": "integer", "BIGINT": "integer", "SMALLINT": "integer",
                "DOUBLE": "number", "FLOAT": "number", "BOOLEAN": "boolean"}


def denied_columns(names: list[str]) -> list[str]:
    return [n for n in names if any(re.search(p, n) for p in DENY_PATTERNS)]


def public_view(v: dict) -> dict:
    """The catalogue entry (no SQL, no source plumbing)."""
    keys = ["name", "grain", "note", "count_name", "required_filters", "group_by_requires",
            "default_filters", "max_seasons", "columns"]
    out = {k: v[k] for k in keys}
    out["partition_key"] = "season" if v["partition"] else None
    out["sub_partition_key"] = "race_id" if v["partition"] == "season_race" else None
    return out


def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_catalogue(views: list[dict], seasons: list[int]) -> dict:
    cat = {
        "schema_version": SCHEMA_VERSION,
        "seasons": seasons,
        "ops": {k: {"arity": v["arity"]} for k, v in OPS.items()},
        "aggregates": AGGREGATES,
        "orders": ORDERS,
        "limits": LIMITS,
        "views": [public_view(v) for v in views],
    }
    cat["catalogue_version"] = hashlib.sha256(canonical_bytes(cat)).hexdigest()
    return cat


def _register_sources(conn, entries: list[dict], out_root: Path, names: set[str]) -> None:
    by_name = {e["name"]: e for e in entries}
    for name in sorted(names):
        if name not in by_name:
            raise KeyError(f"source table {name} was not exported in this run")
        e = by_name[name]
        rel = e["path"].removeprefix("/data/")
        p = out_root / rel
        files = sorted(p.rglob("*.parquet")) if p.is_dir() else [p]
        lst = ", ".join("'" + str(f).replace("'", "''") + "'" for f in files)
        conn.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet([{lst}], union_by_name=true)")


def _copy(conn, sql: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    conn.execute(f"COPY ({sql}) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def _check_columns(conn, view: dict, relation: str) -> None:
    desc = conn.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
    names = [r[0] for r in desc]
    bad = denied_columns(names)
    if bad:
        raise ValueError(f"{view['name']}: denied (modelled) columns {bad}")
    declared = [c["name"] for c in view["columns"]]
    if names != declared:
        raise ValueError(f"{view['name']}: parquet columns {names} != catalogue columns {declared}")
    for (name, typ, *_), col in zip(desc, view["columns"]):
        if PARQUET_TYPE.get(typ) != col["type"]:
            raise ValueError(f"{view['name']}.{name}: parquet type {typ} != catalogue type {col['type']}")


def export_query_views(out_root: Path, entries: list[dict], size_report: list,
                       views: list[dict] | None = None, progress=print,
                       src_root: Path | None = None) -> list[dict]:
    """Build every qv_* view from the files already written under out_root; return manifest entries.

    src_root (tests only) reads the published sources from another export root."""
    import duckdb

    views = views if views is not None else VIEWS
    out_root = Path(out_root)
    src_root = Path(src_root) if src_root is not None else out_root
    qv_dir = out_root / "assistant" / "qv"
    conn = duckdb.connect()
    conn.execute("SET threads=1")  # deterministic row-group layout (determinism test compares sha256)
    conn.execute("SET TimeZone='UTC'")
    _register_sources(conn, entries, src_root, {s for v in views for s in v["sources"]})

    new_entries: list[dict] = []
    all_seasons: set[int] = set()
    for v in views:
        name = v["name"]
        conn.execute(f"CREATE OR REPLACE TEMP TABLE {name} AS {v['sql']}")
        _check_columns(conn, v, name)
        if any(c["name"] == "season" for c in v["columns"]):
            all_seasons |= {r[0] for r in conn.execute(f"SELECT DISTINCT season FROM {name} WHERE season IS NOT NULL").fetchall()}
        order = "ALL"  # total order over every column: byte-stable files on re-run
        total = 0
        if v["partition"] is None:
            out = qv_dir / f"{name}.parquet"
            _copy(conn, f"SELECT * FROM {name} ORDER BY {order}", out)
            total = out.stat().st_size
            _gate(out, name)
            entry = {"name": name, "path": f"/data/{out.relative_to(out_root)}", "partitioned": False}
            detail = f"{total/1024:.1f} KB"
        else:
            part_dir = qv_dir / name
            partitions = []
            seasons = [r[0] for r in conn.execute(f"SELECT DISTINCT season FROM {name} ORDER BY 1").fetchall()]
            biggest = 0
            for s in seasons:
                if v["partition"] == "season":
                    out = part_dir / f"{s}.parquet"
                    _copy(conn, f"SELECT * FROM {name} WHERE season = {int(s)} ORDER BY {order}", out)
                    _gate(out, name)
                    total += out.stat().st_size
                    biggest = max(biggest, out.stat().st_size)
                    partitions.append({"value": s, "path": f"/data/{out.relative_to(out_root)}"})
                else:
                    year_dir = part_dir / str(s)
                    subs = []
                    races = [r[0] for r in conn.execute(
                        f"SELECT DISTINCT race_id FROM {name} WHERE season = ? ORDER BY 1", [s]).fetchall()]
                    for rid in races:
                        if not re.fullmatch(r"\d{4}_\d{1,2}", rid):
                            raise ValueError(f"{name}: unexpected race_id {rid!r}")
                        out = year_dir / f"{rid}.parquet"
                        _copy(conn, f"SELECT * FROM {name} WHERE season = {int(s)} AND race_id = '{rid}' ORDER BY {order}", out)
                        _gate(out, name)
                        total += out.stat().st_size
                        biggest = max(biggest, out.stat().st_size)
                        subs.append({"value": rid, "path": f"/data/{out.relative_to(out_root)}"})
                    partitions.append({"value": s, "path": f"/data/{year_dir.relative_to(out_root)}", "subPartitions": subs})
            entry = {"name": name, "path": f"/data/{part_dir.relative_to(out_root)}", "partitioned": True,
                     "partitionKey": "season", "partitions": partitions}
            detail = f"{len(partitions)} partitions, {total/1024:.1f} KB total, largest file {biggest/1024:.1f} KB"
        rows = conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        size_report.append((name, total))
        progress(f"  {name}  →  assistant/qv  ({rows} rows; {detail})")
        new_entries.append(entry)
    conn.close()

    cat = build_catalogue(views, sorted(int(s) for s in all_seasons))
    cat_path = out_root / "assistant" / "catalogue.json"
    cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    progress(f"  catalogue.json  →  assistant/catalogue.json  ({len(cat['views'])} views, version {cat['catalogue_version'][:12]})")
    return new_entries


def _gate(path: Path, name: str) -> None:
    if path.stat().st_size > MAX_FILE_BYTES:  # read at call time so tests can lower it
        raise ValueError(f"SIZE GATE: {name} {path.name} is {path.stat().st_size/1024**2:.2f} MB > 5 MB")
