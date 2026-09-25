"""
Fit compound cliff parameters from historical stint data.

Reads from dev.duckdb (dbt-built warehouse). Writes fitted params to
seeds/_pending/compound_cliff_params_pending.csv for human review.

Usage:
    python -m tasks.coefficients.fit_compound_cliff
    python -m tasks.coefficients.fit_compound_cliff --dry-run
    python -m tasks.coefficients.fit_compound_cliff --seasons 2022 2023 2024
    python -m tasks.coefficients.fit_compound_cliff --circuits bahrain_grand_prix

    python -m tasks.coefficients.fit_compound_cliff --fill-gaps

The fitter operates per (circuit_key, compound_code, season) group.
Groups with fewer than MIN_STINTS stints fall back to a fit on the venue's
stints pooled across every season, then to compound-class defaults.

Provenance is recorded per parameter, not per cell. fit_source says which tier
the cell's fit was attempted at; onset_source, gradient_source and
severity_source say where each number actually came from, because a tier that
ran can still hand back no usable estimate for one parameter, and that
parameter then holds the class default. See PARAM_SOURCES.

--fill-gaps does not fit anything. It adds a row for every
(circuit_key, compound_code, season) the warehouse's valid laps need but the
live seed lacks -- the latest earlier season's cell for the same venue and
compound, else the class default -- so a new season's missing cells are
carried forward explicitly instead of being priced from nothing downstream.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .provenance import build_provenance
from .seed_writer import SEEDS_DIR, write_pending
from .survival import (
    build_survival_dataset,
    estimate_cliff_severity,
    estimate_wear_gradient,
    fit_cliff_onset_median,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
SEED_NAME = "compound_cliff_params"

MIN_STINTS = 8

# Compound-class defaults when data is insufficient.
# Values are conservative (later onset, milder severity) to avoid overcorrecting.
# Severities capped at 1.5 (matching estimate_cliff_severity's winsorization) so
# a default never itself breaches the assert_cliff_seed_severity_bounded gate;
# relative compound ordering (soft > wet > medium > intermediate > hard) is
# otherwise unchanged from the original values.
COMPOUND_DEFAULTS = {
    "SOFT":         {"cliff_onset_laps": 22, "cliff_severity": 1.50, "wear_gradient": 0.070, "grip_peak": 1.03},
    "MEDIUM":       {"cliff_onset_laps": 33, "cliff_severity": 1.40, "wear_gradient": 0.040, "grip_peak": 1.00},
    "HARD":         {"cliff_onset_laps": 50, "cliff_severity": 1.20, "wear_gradient": 0.022, "grip_peak": 0.97},
    "INTERMEDIATE": {"cliff_onset_laps": 25, "cliff_severity": 1.30, "wear_gradient": 0.055, "grip_peak": 0.98},
    "WET":          {"cliff_onset_laps": 20, "cliff_severity": 1.45, "wear_gradient": 0.080, "grip_peak": 0.95},
    # Pre-2019 legacy names (2018 only): softer than SOFT in Pirelli's
    # naming order (HARD < MEDIUM < SOFT < SUPERSOFT < ULTRASOFT < HYPERSOFT).
    # Extrapolated from the SOFT row along that same ordering -- more grip,
    # faster wear, earlier onset. Severity is already at the 1.5 winsorization
    # cap for SOFT, so these cap there too rather than exceeding it.
    "SUPERSOFT":    {"cliff_onset_laps": 18, "cliff_severity": 1.50, "wear_gradient": 0.085, "grip_peak": 1.05},
    "ULTRASOFT":    {"cliff_onset_laps": 14, "cliff_severity": 1.50, "wear_gradient": 0.100, "grip_peak": 1.07},
    "HYPERSOFT":    {"cliff_onset_laps": 10, "cliff_severity": 1.50, "wear_gradient": 0.115, "grip_peak": 1.09},
}

# Where one fitted parameter's number came from. A class default stays
# "class_default" wherever the number travels -- including when a later season
# carries the cell forward -- so a default can never be relabelled as measured
# one step downstream.
#   fitted                 estimated from this cell's own (venue, compound,
#                          season) stints
#   cross_season_fallback  estimated from the venue's stints pooled across
#                          every season (too few in this season alone)
#   class_default          COMPOUND_DEFAULTS (or a compound-class value noted
#                          in the row): no usable estimate for this venue
#   carried_forward        copied unchanged from an earlier season's cell, where
#                          it was fitted or cross-season estimated
PARAM_SOURCES = ("fitted", "cross_season_fallback", "class_default", "carried_forward")

# The parameter source each fit tier implies when its estimator returns a
# usable number.
_TIER_PARAM_SOURCE = {
    "cox_km_survival": "fitted",
    "cross_season_fallback": "cross_season_fallback",
    "compound_class_default": "class_default",
}

_PARAM_SOURCE_COLUMNS = ("onset_source", "gradient_source", "severity_source")

# The seed's column order.
SEED_COLUMNS = [
    "circuit_key", "compound_code", "season",
    "compound_grip_peak", "compound_wear_gradient",
    "compound_optimal_temp_low", "compound_optimal_temp_high",
    "compound_cliff_onset_laps", "compound_cliff_severity",
    "fit_date", "data_window", "fit_method", "git_sha", "fit_timestamp",
    "fit_source", *_PARAM_SOURCE_COLUMNS,
    "n_stints", "notes",
]

OPTIMAL_TEMP_RANGES = {
    "SOFT":         (82, 108),
    "MEDIUM":       (78, 105),
    "HARD":         (76, 108),
    "INTERMEDIATE": (15,  50),
    "WET":          (10,  40),
    # Same slick rubber family as SOFT; no independent evidence for a
    # different operating window, so inherit SOFT's.
    "SUPERSOFT":    (82, 108),
    "ULTRASOFT":    (82, 108),
    "HYPERSOFT":    (82, 108),
}


def load_stint_data(con: duckdb.DuckDBPyConnection, seasons: list[int]) -> pd.DataFrame:
    """
    Build the per-lap stint dataset from dev.duckdb.

    Joins int_stint_geometry + stg_laps + stg_weather + stg_events +
    stg_results + int_lap_normalized_pace + int_lap_fuel_state. Filters to
    green-flag, non-SC, non-pit laps with a known tyre age on the dry and wet
    compounds -- see the WHERE clause for why that is green-flag rather than
    is_valid_lap.

    fuel_corrected_pace_s is the series the curve is fitted on: lap time with
    the dirty-air cost AND the fuel burn removed. The residual decomposition
    subtracts fuel separately (fuel_component_s), so a curve fitted on pace that
    still carries the burn would price wear net of ~0.05 s/lap of fuel gain.
    normalized_pace_s (dirty air removed, fuel left in) is kept for inspection
    and for scripts/measure_wear_residual_sigma.py.
    """
    season_filter = ", ".join(str(s) for s in seasons)
    query = f"""
        SELECT
            sg.stint_id,
            sg.lap_id,
            sg.race_year,
            sg.race_id,
            sg.driver_id,
            sg.lap_in_stint,
            sg.age_in_stint,
            -- compound_code in int_stint_geometry is NULL; source from stg_laps
            l.compound                          AS compound_code,
            sg.stint_length_actual,
            -- stg_laps.circuit_key is the raw race_id ("YYYY_N"); resolve to friendly
            -- name via race_to_track (both race_id columns are VARCHAR "YYYY_N"; the
            -- fallback is defensive only -- race_to_track's one gap, 2018_14, was
            -- filled by WI-05/F8 and assert_race_to_track_covers_all_races keeps it
            -- complete)
            COALESCE(rtt.track_id, l.circuit_key) AS circuit_key,
            -- Physical-venue id (dim_circuits collapses renamed-event/double-header
            -- keys, e.g. mexican_grand_prix + mexico_city_grand_prix, onto one venue).
            -- Used only to pool the cross-season fallback; the emitted seed still
            -- keys on circuit_key (event slug) so int_compound_cliff_predicted's
            -- join to race_to_track.track_id keeps working.
            dc.circuit_id AS circuit_id,
            l.lap_time_s,
            l.is_valid_lap,
            l.is_safety_car_lap,
            l.is_vsc_lap,
            l.is_pit_lap,
            l.is_fresh_tyre,
            -- Phase C: pace with the dirty-air cost removed, so
            -- traffic-compromised laps stay usable instead of being discarded.
            -- COALESCE keeps the column complete for laps int_lap_air_state
            -- does not cover, so a missing air state degrades to raw lap time
            -- rather than dropping the lap from the fit.
            COALESCE(np.normalized_pace_s, l.lap_time_s) AS normalized_pace_s,
            -- The fitted series: the same pace with the fuel burn removed too,
            -- by the fuel model's own weight_penalty_s (the correction
            -- int_lap_fuel_state applies to weight_corrected_lap_time). That
            -- model prices valid laps only, so a green-flag lap it skipped
            -- (inaccurate timing: 0.8% of rows, nearly all 2018) is priced
            -- from the same race's constants with the same formula -- linear
            -- burn from the regulatory limit over the scheduled distance.
            -- NULL, never 0, if the race has no fuel row: an unpriced lap must
            -- not be fitted as if it carried no fuel.
            COALESCE(np.normalized_pace_s, l.lap_time_s) - COALESCE(
                fs.weight_penalty_s,
                CASE WHEN rf.race_id IS NOT NULL THEN
                    GREATEST(
                        rf.initial_fuel_kg
                        - rf.fuel_consumption_rate_kg_per_lap * (l.lap_number - 1),
                        0.0
                    ) * dc.weight_penalty_factor
                END
            ) AS fuel_corrected_pace_s,
            COALESCE(w.track_temp_c, 30.0)     AS track_temp_c,
            COALESCE(w.rainfall_flag, FALSE)    AS rainfall_flag,
            w.wind_speed_ms,
            -- A forced stop is a DNF or retirement (driver didn't choose to pit)
            COALESCE(
                (SELECT TRUE FROM stg_events e
                 WHERE e.driver_id = sg.driver_id
                   AND e.race_id = sg.race_id
                   AND e.event_type = 'DNF'
                 LIMIT 1),
                FALSE
            ) AS forced_stop_flag,
            -- Raw retirement status string, attached only to the driver's last
            -- stint of the race (NULL for earlier stints that ended in a
            -- voluntary pit, and for classified/finished drivers) -- otherwise
            -- a driver with 2+ stints before retiring would have every prior,
            -- completed stint wrongly tagged with the eventual failure.
            CASE WHEN sg.stint_number = (
                SELECT MAX(sg2.stint_number) FROM int_stint_geometry sg2
                WHERE sg2.driver_id = sg.driver_id AND sg2.race_id = sg.race_id
            ) THEN (
                SELECT r.status FROM stg_results r
                WHERE r.driver_id = sg.driver_id
                  AND r.race_id = sg.race_id
                  AND r.is_dnf
                LIMIT 1
            ) END AS dnf_status
        FROM int_stint_geometry sg
        JOIN stg_laps l ON sg.lap_id = l.lap_id
        LEFT JOIN stg_weather w ON sg.lap_id = w.lap_id
        LEFT JOIN race_to_track rtt
          ON l.race_id = rtt.race_id
        LEFT JOIN dim_circuits dc
          ON rtt.track_id = dc.circuit_key
        LEFT JOIN int_lap_normalized_pace np ON sg.lap_id = np.lap_id
        LEFT JOIN int_lap_fuel_state fs ON sg.lap_id = fs.lap_id
        LEFT JOIN (
            -- Race-level constants, identical on every row of a race.
            SELECT
                race_id,
                MAX(initial_fuel_kg) AS initial_fuel_kg,
                MAX(fuel_consumption_rate_kg_per_lap) AS fuel_consumption_rate_kg_per_lap
            FROM int_lap_fuel_state
            GROUP BY race_id
        ) rf ON l.race_id = rf.race_id
        WHERE sg.race_year IN ({season_filter})
          -- A NULL tyre age is unknown, not a value: int_stint_geometry NULLs
          -- it (and the compound) on stints whose bronze boundaries contradict
          -- the pit record (stg_lap_tyre_qa's quarantine). Those laps cannot be
          -- placed on a wear curve; the survival step also cannot run on them.
          AND sg.age_in_stint IS NOT NULL
          AND l.compound IN (
              'SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET',
              -- Pre-2019 legacy naming, 2018 only (see COMPOUND_DEFAULTS).
              'SUPERSOFT', 'ULTRASOFT', 'HYPERSOFT'
          )
          -- Phase C: green-flag laps, not is_valid_lap. The dropped condition
          -- is is_accurate only -- every other component of is_valid_lap is
          -- restated below (SC/VSC via the two flags, which between them cover
          -- the same TrackStatus digits 4-7; pit; deleted; lap 1; timed).
          -- FastF1 marks a lap inaccurate for reasons that are pace-relevant
          -- but not pace-invalidating once normalized, which is exactly the
          -- population this phase is trying to recover. Deleted laps
          -- (track-limits) stay out: those times are void, not compromised.
          -- Lap 1 stays out: a standing start is not a pace signal.
          AND l.is_safety_car_lap = FALSE
          AND l.is_vsc_lap = FALSE
          AND l.is_pit_lap = FALSE
          AND NOT l.is_deleted
          AND l.lap_number > 1
          AND l.lap_time_s > 0
          AND l.lap_time_s < 200
    """
    log.info("Loading stint lap data for seasons %s...", seasons)
    df = con.execute(query).df()
    log.info("Loaded %d lap rows from %d stints", len(df), df["stint_id"].nunique())
    return df


def fresh_tyre_only(stints_df: pd.DataFrame) -> pd.DataFrame:
    """
    Restrict to fresh-tyre laps for baseline compound wear-curve fitting.

    Scrubbed (non-fresh) tyres degrade from a different starting point, which
    would bias the steady-state wear_gradient regression. They stay in the
    survival dataset (cliff-onset/severity) as a covariate rather than being
    dropped from the fitter entirely -- only the baseline curve fit excludes
    them. Missing column (e.g. synthetic test fixtures) defaults to keeping
    all rows.
    """
    if "is_fresh_tyre" not in stints_df.columns:
        return stints_df
    return stints_df[stints_df["is_fresh_tyre"] == True]  # noqa: E712 -- NaN-safe, unlike .astype(bool)


def fit_group(
    stints_df: pd.DataFrame,
    circuit_key: str,
    compound_code: str,
    season: int,
    fallback_df: pd.DataFrame | None = None,
) -> dict:
    """
    Fit cliff parameters for a single (circuit_key, compound_code, season) group.

    Tiers: this season's stints (>= MIN_STINTS), else the venue's stints pooled
    across every season (fallback_df, >= MIN_STINTS), else the compound-class
    defaults. Within a tier that ran, any parameter whose estimator returns
    nothing or an out-of-range value takes the class default, and that is
    recorded against the parameter itself (onset_source / gradient_source /
    severity_source) -- notes never claim "fitted" for a cell holding a default.

    Returns a result dict with all columns needed for the seed CSV.
    """
    defaults = COMPOUND_DEFAULTS.get(compound_code, COMPOUND_DEFAULTS["MEDIUM"])
    opt_temp_low, opt_temp_high = OPTIMAL_TEMP_RANGES.get(compound_code, (78, 108))

    group_df = stints_df[
        (stints_df["circuit_key"] == circuit_key) &
        (stints_df["compound_code"] == compound_code) &
        (stints_df["race_year"] == season)
    ]

    # Fit on fuel-corrected pace when the warehouse supplies it, then on
    # dirty-air-normalized pace, then raw lap time (synthetic fixtures, or an
    # older warehouse). Resolved once here so onset, severity and gradient are
    # all fitted on the same series -- mixing them would make cliff onset and
    # severity incomparable, and the cliff term downstream de-double-counts
    # severity against span * wear_gradient, which only cancels cleanly when
    # both were measured with the fuel burn in or out together.
    pace_col = next(
        (c for c in ("fuel_corrected_pace_s", "normalized_pace_s") if c in stints_df.columns),
        "lap_time_s",
    )

    survival_df = (
        build_survival_dataset(group_df, pace_col=pace_col) if len(group_df) > 0 else pd.DataFrame()
    )
    season_n_stints = len(survival_df)
    cross_survival = (
        build_survival_dataset(fallback_df, pace_col=pace_col)
        if fallback_df is not None and len(fallback_df) > 0
        else pd.DataFrame()
    )
    fit_notes = ""

    if season_n_stints >= MIN_STINTS:
        cliff_onset = fit_cliff_onset_median(survival_df)
        cliff_severity = estimate_cliff_severity(
            group_df, cliff_onset or defaults["cliff_onset_laps"], pace_col=pace_col
        )
        wear_gradient = estimate_wear_gradient(
            fresh_tyre_only(group_df), cliff_onset or defaults["cliff_onset_laps"], pace_col=pace_col
        )
        source = "cox_km_survival"
        used_n_stints = season_n_stints
    elif len(cross_survival) >= MIN_STINTS:
        # Cross-season fallback: all seasons for this circuit+compound. Gated
        # and reported on cross_survival (actual stints), not fallback_df
        # (lap rows) -- a handful of long stints would otherwise clear
        # MIN_STINTS on lap count alone while providing far fewer real stints.
        cliff_onset = fit_cliff_onset_median(cross_survival)
        cliff_severity = estimate_cliff_severity(
            fallback_df, cliff_onset or defaults["cliff_onset_laps"], pace_col=pace_col
        )
        wear_gradient = estimate_wear_gradient(
            fresh_tyre_only(fallback_df), cliff_onset or defaults["cliff_onset_laps"], pace_col=pace_col
        )
        source = "cross_season_fallback"
        used_n_stints = len(cross_survival)
        fit_notes = f"insufficient season stints ({season_n_stints}); used {used_n_stints} cross-season stints"
        log.warning(
            "%s / %s / %d: only %d stints, falling back to cross-season (%s)",
            circuit_key, compound_code, season, season_n_stints, fit_notes,
        )
    else:
        cliff_onset = None
        cliff_severity = None
        wear_gradient = None
        source = "compound_class_default"
        used_n_stints = season_n_stints
        fit_notes = f"insufficient data ({season_n_stints} stints); used class defaults"
        log.warning(
            "%s / %s / %d: using class defaults (%s)",
            circuit_key, compound_code, season, fit_notes,
        )

    # Clamp to physically plausible ranges   survival/regression can produce
    # outliers for thin groups; fall back to defaults when out of range. Each
    # fallback is recorded against its own parameter: the tier's source holds
    # only for a parameter whose estimator actually returned a usable number.
    tier_param_source = _TIER_PARAM_SOURCE[source]

    onset_defaulted = not cliff_onset
    onset_val = float(cliff_onset or defaults["cliff_onset_laps"])
    onset_val = max(5.0, min(100.0, onset_val))

    severity_val = float(cliff_severity or defaults["cliff_severity"])
    severity_defaulted = not cliff_severity or severity_val < 0.1 or severity_val > 1.5
    if severity_defaulted:
        severity_val = defaults["cliff_severity"]

    gradient_val = float(wear_gradient or defaults["wear_gradient"])
    gradient_defaulted = not wear_gradient or gradient_val < 0.005 or gradient_val > 0.300
    if gradient_defaulted:
        gradient_val = defaults["wear_gradient"]

    param_sources = {
        "onset_source": "class_default" if onset_defaulted else tier_param_source,
        "gradient_source": "class_default" if gradient_defaulted else tier_param_source,
        "severity_source": "class_default" if severity_defaulted else tier_param_source,
    }
    defaulted = [
        name for name, key in (("onset", "onset_source"), ("gradient", "gradient_source"),
                               ("severity", "severity_source"))
        if param_sources[key] == "class_default"
    ]
    if source == "compound_class_default" or not defaulted:
        notes = fit_notes or f"fitted from {used_n_stints} stints via {source}"
    else:
        # A tier ran but could not measure every parameter. Say so, and never
        # with the "fitted from" wording a fully measured cell carries.
        head = fit_notes or f"{used_n_stints} stints via {source}"
        notes = f"{head}; no usable estimate for {', '.join(defaulted)}: class default used"

    return {
        "circuit_key": circuit_key,
        "compound_code": compound_code,
        "season": season,
        "compound_grip_peak": defaults["grip_peak"],
        "compound_wear_gradient": round(gradient_val, 4),
        "compound_optimal_temp_low": opt_temp_low,
        "compound_optimal_temp_high": opt_temp_high,
        "compound_cliff_onset_laps": round(onset_val, 1),
        "compound_cliff_severity": round(severity_val, 2),
        "fit_source": source,
        **param_sources,
        "n_stints": used_n_stints,
        "notes": notes,
    }


def run_fit(
    seasons: list[int],
    circuits: list[str] | None,
    dry_run: bool,
) -> pd.DataFrame:
    log.info("Connecting to %s", DB_PATH)
    con = duckdb.connect(str(DB_PATH), read_only=True)

    stints_df = load_stint_data(con, seasons)

    if circuits:
        stints_df = stints_df[stints_df["circuit_key"].isin(circuits)]
        log.info("Filtered to %d circuits: %s", len(circuits), circuits)

    groups = (
        stints_df.groupby(["circuit_key", "compound_code", "race_year"])
        .size()
        .reset_index(name="n_laps")
    )
    log.info("Fitting %d circuit/compound/season groups...", len(groups))

    # circuit_key -> circuit_id (physical venue), for cross-season pooling below.
    # A circuit_key absent from dim_circuits (a race missing from race_to_track,
    # as 2018_14 was until WI-05/F8) has no circuit_id and pools on itself only.
    circuit_id_by_key = (
        stints_df.dropna(subset=["circuit_id"])
        .drop_duplicates("circuit_key")
        .set_index("circuit_key")["circuit_id"]
    )

    results = []
    for _, row in groups.iterrows():
        circuit_key = row["circuit_key"]
        compound_code = row["compound_code"]
        season = int(row["race_year"])

        # Cross-season fallback pool: keyed on the physical venue
        # (dim_circuits.circuit_id), not the event slug, so renamed-event and
        # double-header keys (mexican_grand_prix / mexico_city_grand_prix,
        # austrian_grand_prix / styrian_grand_prix, etc.) share history instead
        # of each falling to compound_class_default in isolation.
        circuit_id = circuit_id_by_key.get(circuit_key)
        if circuit_id is not None:
            cross_df = stints_df[
                (stints_df["circuit_id"] == circuit_id) &
                (stints_df["compound_code"] == compound_code)
            ]
        else:
            cross_df = stints_df[
                (stints_df["circuit_key"] == circuit_key) &
                (stints_df["compound_code"] == compound_code)
            ]

        result = fit_group(stints_df, circuit_key, compound_code, season, fallback_df=cross_df)
        results.append(result)
        log.info(
            "  %-35s %-12s %d  onset=%.1f  severity=%.2f  gradient=%.4f  [%s]",
            circuit_key, compound_code, season,
            result["compound_cliff_onset_laps"],
            result["compound_cliff_severity"],
            result["compound_wear_gradient"],
            result["fit_source"],
        )

    out_df = pd.DataFrame(results)

    prov = build_provenance(
        fit_method="km_survival_v1",
        season_min=min(seasons),
        season_max=max(seasons),
    )
    for k, v in prov.items():
        out_df[k] = v

    out_df = out_df[[c for c in SEED_COLUMNS if c in out_df.columns]]
    out_df = out_df.sort_values(["circuit_key", "compound_code", "season"])

    return out_df


def load_needed_cells(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Every (circuit_key, compound_code, season) the warehouse prices.

    The same population int_compound_cliff_predicted joins to the seed: valid
    laps of int_stint_geometry with a known compound, keyed through
    race_to_track. assert_compound_params_cover_mart checks the same set.
    """
    return con.execute("""
        SELECT DISTINCT
            rtt.track_id AS circuit_key,
            g.compound_in_stint AS compound_code,
            g.race_year AS season
        FROM int_stint_geometry g
        JOIN race_to_track rtt ON g.race_id = rtt.race_id
        WHERE g.is_valid_lap AND g.compound_in_stint IS NOT NULL
    """).df()


def fill_coverage_gaps(seed_df: pd.DataFrame, needed: pd.DataFrame) -> pd.DataFrame:
    """
    Rows for every needed (circuit_key, compound_code, season) cell the seed lacks.

    Nothing is fitted. The hierarchy, applied per missing cell:
      1. venue history -- the latest EARLIER season's cell for the same
         circuit_key and compound, copied unchanged. Earlier only, so a filled
         cell never carries information from its own season or a later one.
      2. class default -- COMPOUND_DEFAULTS, when the venue has never had one.
    Per-parameter provenance follows the number: a copied parameter is
    "carried_forward" unless the source cell itself held a class default there,
    in which case it stays "class_default".

    Returns only the new rows, in SEED_COLUMNS order.
    """
    have = set(zip(seed_df["circuit_key"], seed_df["compound_code"], seed_df["season"].astype(int)))
    gaps = sorted(
        {(k, c, int(s)) for k, c, s in zip(needed["circuit_key"], needed["compound_code"], needed["season"])}
        - have
    )
    rows = []
    for circuit_key, compound_code, season in gaps:
        history = seed_df[
            (seed_df["circuit_key"] == circuit_key)
            & (seed_df["compound_code"] == compound_code)
            & (seed_df["season"].astype(int) < season)
        ]
        if len(history):
            src = history.loc[history["season"].astype(int).idxmax()]
            src_season = int(src["season"])
            row = {c: src[c] for c in SEED_COLUMNS if c in src.index}
            row.update({
                "season": season,
                "fit_source": f"carried_forward_{src_season}",
                **{
                    col: "class_default" if src[col] == "class_default" else "carried_forward"
                    for col in _PARAM_SOURCE_COLUMNS
                },
                "notes": (
                    f"No {season} cell for this venue and compound: the {src_season} cell "
                    f"(the latest earlier season with one; fit_source {src['fit_source']}) "
                    "carried forward unchanged. Parameters that were class defaults there "
                    "stay marked class_default. data_window/fit_method are the source fit's."
                ),
            })
        else:
            if compound_code not in COMPOUND_DEFAULTS:
                # No class default to fall back to: leave the gap, and let
                # assert_compound_params_cover_mart refuse the build on it.
                log.error("%s / %s / %d: no seed history and no class default for this compound",
                          circuit_key, compound_code, season)
                continue
            defaults = COMPOUND_DEFAULTS[compound_code]
            opt_temp_low, opt_temp_high = OPTIMAL_TEMP_RANGES[compound_code]
            row = {
                "circuit_key": circuit_key,
                "compound_code": compound_code,
                "season": season,
                "compound_grip_peak": defaults["grip_peak"],
                "compound_wear_gradient": defaults["wear_gradient"],
                "compound_optimal_temp_low": opt_temp_low,
                "compound_optimal_temp_high": opt_temp_high,
                "compound_cliff_onset_laps": float(defaults["cliff_onset_laps"]),
                "compound_cliff_severity": defaults["cliff_severity"],
                "fit_method": "km_survival_v1",
                "data_window": f"{int(seed_df['season'].min())}_to_{season - 1}",
                "fit_source": "compound_class_default",
                **{col: "class_default" for col in _PARAM_SOURCE_COLUMNS},
                "n_stints": 0,
                "notes": (
                    f"No {season} cell and no earlier season's cell for this venue and "
                    "compound to carry forward: compound-class defaults (COMPOUND_DEFAULTS)."
                ),
            }
        rows.append(row)

    out = pd.DataFrame(rows, columns=SEED_COLUMNS)
    if len(out):
        # When and at which commit the rows were written. data_window and
        # fit_method stay per row (above): they describe the numbers, not
        # this write.
        stamp = build_provenance(
            fit_method="km_survival_v1",
            season_min=int(seed_df["season"].min()),
            season_max=int(out["season"].max()),
        )
        for k in ("fit_date", "git_sha", "fit_timestamp"):
            out[k] = stamp[k]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit compound cliff parameters from F1 stint data.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing output.")
    parser.add_argument(
        "--seasons", nargs="+", type=int,
        default=list(range(2018, 2025)),
        help="Seasons to fit (default: 2018-2024).",
    )
    parser.add_argument(
        "--circuits", nargs="+", default=None,
        help="Limit fit to these circuit_keys (default: all).",
    )
    parser.add_argument(
        "--fill-gaps", action="store_true",
        help="Fit nothing: write the live seed plus a carried-forward / class-default row "
             "for every cell the warehouse's valid laps need but the seed lacks.",
    )
    args = parser.parse_args(argv)

    if args.fill_gaps:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        live = pd.read_csv(SEEDS_DIR / f"{SEED_NAME}.csv")
        added = fill_coverage_gaps(live, load_needed_cells(con))
        for _, r in added.iterrows():
            log.info("  + %-35s %-12s %d  [%s]", r["circuit_key"], r["compound_code"],
                     r["season"], r["fit_source"])
        log.info("%d gap rows.", len(added))
        if args.dry_run or not len(added):
            return 0
        write_pending(pd.concat([live, added], ignore_index=True)[SEED_COLUMNS], SEED_NAME)
        log.info("Done. Pending seed written. Review then run: make coefficients-promote")
        return 0

    if args.dry_run:
        log.info("DRY RUN   will connect to duckdb and show plan without writing output.")
        log.info("Seasons: %s", args.seasons)
        log.info("Circuits: %s", args.circuits or "all")
        con = duckdb.connect(str(DB_PATH), read_only=True)
        stints_df = load_stint_data(con, args.seasons)
        if args.circuits:
            stints_df = stints_df[stints_df["circuit_key"].isin(args.circuits)]
        groups = stints_df.groupby(["circuit_key", "compound_code", "race_year"]).size()
        log.info("Would fit %d groups across %d unique circuits.", len(groups), stints_df["circuit_key"].nunique())
        log.info("Output: seeds/_pending/%s_pending.csv", SEED_NAME)
        return 0

    out_df = run_fit(
        seasons=args.seasons,
        circuits=args.circuits,
        dry_run=args.dry_run,
    )

    write_pending(out_df, SEED_NAME)
    log.info("Done. Pending seed written. Review then run: make coefficients-promote")
    return 0


if __name__ == "__main__":
    sys.exit(main())
