"""
Survival-analysis helpers for tyre cliff parameter estimation.

The key insight: F1 teams pit *before* the cliff, so most stints are
right-censored at the voluntary pit lap. Naïve OLS treats every pit as
"we observed degradation up to here"   which systematically underestimates
cliff_onset_laps because drivers pit early *precisely to avoid the cliff*.

We model "time to cliff event" as a survival problem:
   -Event: lap where pace drops > threshold vs trailing median (cliff occurred)
   -Censored: stint ended without observing that drop (voluntary pit, or lap 1)

The hazard function's median (lap where ~50% of stints would cliff if left alone)
gives an unbiased estimate of cliff_onset_laps.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd


CLIFF_DETECTION_THRESHOLD_S = 0.5
CLIFF_MIN_CONTINUATION_LAPS = 2
TRAILING_WINDOW = 5

# Genuine tyre failures (vs. mechanical/collision/other retirements) are true
# survival events, not censoring -- the tyre didn't survive to be censored.
# Mechanical (Engine/Gearbox/Brakes/Hydraulics/...), Collision/Accident, and
# ambiguous ("Retired") stay censored: default `observed=0` unless a pace-based
# cliff was independently detected already covers that case.
TYRE_FAILURE_STATUS_PATTERN = re.compile(r"puncture|tyre|wheel", re.IGNORECASE)


def is_tyre_failure(status: object) -> bool:
    """True if a DNF status string indicates a genuine tyre/wheel failure."""
    return isinstance(status, str) and bool(TYRE_FAILURE_STATUS_PATTERN.search(status))


def detect_cliff_lap(
    lap_times: pd.Series,
    age_in_stint: pd.Series,
) -> int | None:
    """
    Return the age_in_stint (tyre-life lap) at which the cliff is detected,
    or None if not observed.

    Keyed on age_in_stint, not lap_in_stint: compound_cliff_onset_laps is
    compared against age_in_stint downstream (int_compound_cliff_predicted's
    hockey-stick formula), and age_in_stint is the tyre's true physical
    odometer (continuous across SC/VSC gaps, and can exceed lap_in_stint when
    the set was scrubbed in qualifying) while lap_in_stint only counts laps
    within this race stint.

    A cliff is detected when lap_time exceeds the trailing 5-lap median by
    CLIFF_DETECTION_THRESHOLD_S for at least CLIFF_MIN_CONTINUATION_LAPS consecutive laps.
    This guards against one-off track-limits events or lock-ups.
    """
    df = pd.DataFrame({"t": lap_times.values, "age": age_in_stint.values}).sort_values("age")
    if len(df) < TRAILING_WINDOW + CLIFF_MIN_CONTINUATION_LAPS:
        return None

    df["trailing_med"] = (
        df["t"]
        .rolling(window=TRAILING_WINDOW, min_periods=3)
        .median()
        .shift(1)
    )
    df["spike"] = df["t"]-df["trailing_med"] > CLIFF_DETECTION_THRESHOLD_S

    # Need CLIFF_MIN_CONTINUATION_LAPS consecutive spikes
    streak = 0
    for _, row in df.dropna(subset=["trailing_med"]).iterrows():
        if row["spike"]:
            streak += 1
            if streak >= CLIFF_MIN_CONTINUATION_LAPS:
                # Return the first lap of the streak (not the confirmation lap)
                return int(row["age"])-(streak-1)
        else:
            streak = 0
    return None


def build_survival_dataset(
    stints_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Given a DataFrame of stints (one row per lap), build the per-stint survival table:
        stint_id, circuit_key, compound_code, race_year,
        duration (= age_in_stint at which event/censoring occurred),
        observed (= 1 if cliff detected OR a genuine tyre failure ended the
        stint, 0 if censored -- voluntary pit, non-tyre DNF, or still running),
        avg_track_temp_c, forced_stop (= 1 if DNF/SC/damage retirement),
        is_fresh_tyre (= whether the stint started on a fresh tyre set; carried
        through as a covariate for scrubbed stints rather than dropping them),
        tyre_failure (= 1 if this stint ended in a Puncture/Wheel/Tyre DNF)

    Expects columns: stint_id, age_in_stint, lap_time_s, circuit_key,
                     compound_code, race_year, track_temp_c, forced_stop_flag.
    is_fresh_tyre and dnf_status are optional (default to True / not-a-failure
    if absent, e.g. synthetic tests).
    """
    records = []
    for stint_id, grp in stints_df.groupby("stint_id"):
        grp = grp.sort_values("age_in_stint")
        if len(grp) < 3:
            continue

        cliff_lap = detect_cliff_lap(grp["lap_time_s"], grp["age_in_stint"])
        # The retirement status (if any) applies to the driver's last lap of the
        # race, which for a retiring stint is this group's last (chronologically
        # latest) row.
        tyre_failure = "dnf_status" in grp.columns and is_tyre_failure(grp["dnf_status"].iloc[-1])

        if cliff_lap is not None:
            duration = cliff_lap
            observed = 1
        elif tyre_failure:
            # Sudden failure (e.g. a puncture) often doesn't produce the two
            # consecutive slow laps detect_cliff_lap requires -- without this,
            # a real tyre-failure event would be misclassified as censored.
            duration = int(grp["age_in_stint"].max())
            observed = 1
        else:
            duration = int(grp["age_in_stint"].max())
            observed = 0

        records.append(
            {
                "stint_id": stint_id,
                "circuit_key": grp["circuit_key"].iloc[0],
                "compound_code": grp["compound_code"].iloc[0],
                "race_year": int(grp["race_year"].iloc[0]),
                "duration": duration,
                "observed": observed,
                "avg_track_temp_c": float(grp["track_temp_c"].mean()),
                "avg_wind_speed_ms": (
                    float(grp["wind_speed_ms"].mean())
                    if "wind_speed_ms" in grp and grp["wind_speed_ms"].notna().any()
                    else None
                ),
                "forced_stop": int(grp["forced_stop_flag"].iloc[0]),
                "is_fresh_tyre": bool(grp["is_fresh_tyre"].iloc[0]) if "is_fresh_tyre" in grp else True,
                "tyre_failure": int(tyre_failure),
            }
        )

    return pd.DataFrame(records)


def fit_cliff_onset_median(
    survival_df: pd.DataFrame,
    min_stints: int = 10,
) -> float | None:
    """
    Estimate the median cliff-onset lap from a per-stint survival dataset.

    Uses the Kaplan-Meier estimator (nonparametric). Falls back to the
    observed mean if there are too few events to fit reliably.

    Returns None if insufficient data.
    """
    if len(survival_df) < min_stints:
        return None

    try:
        from lifelines import KaplanMeierFitter  # type: ignore
        kmf = KaplanMeierFitter()
        kmf.fit(
            durations=survival_df["duration"],
            event_observed=survival_df["observed"],
            label="cliff_onset",
        )
        median = kmf.median_survival_time_
        if np.isnan(median) or np.isinf(median):
            # KM never crosses 0.5   cliff doesn't typically happen for this compound
            # Use the 75th percentile of observed cliffs as a proxy
            cliffed = survival_df[survival_df["observed"] == 1]["duration"]
            return float(cliffed.quantile(0.75)) if len(cliffed) > 3 else None
        return float(median)
    except ImportError:
        # lifelines not installed   fall back to simple mean of observed cliffs
        cliffed = survival_df[survival_df["observed"] == 1]["duration"]
        return float(cliffed.mean()) if len(cliffed) >= min_stints // 2 else None


def estimate_cliff_severity(
    stints_df: pd.DataFrame,
    cliff_onset_laps: float,
) -> float | None:
    """
    Estimate cliff_severity_s (seconds of pace loss at onset + 5 laps post-cliff).

    Uses only uncensored stints (observed cliff or forced stop) where we actually
    see post-cliff laps. Computes the average lap-time delta between
    [onset, onset+5] vs [onset-5, onset-1], windowed on age_in_stint (tyre-life
    laps) to match the units cliff_lap is detected in.
    """
    records = []
    for _stint_id, grp in stints_df.groupby("stint_id"):
        grp = grp.sort_values("age_in_stint").reset_index(drop=True)
        cliff_lap = detect_cliff_lap(grp["lap_time_s"], grp["age_in_stint"])
        if cliff_lap is None:
            continue

        pre = grp[grp["age_in_stint"].between(cliff_lap-5, cliff_lap-1)]["lap_time_s"]
        post = grp[grp["age_in_stint"].between(cliff_lap, cliff_lap + 5)]["lap_time_s"]

        if len(pre) >= 2 and len(post) >= 2:
            records.append(float(post.mean()-pre.mean()))

    if not records:
        return None
    # Winsorise to 1.5s/lap   an unbounded mean lets one stint's post-cliff
    # laps (backmarker traffic, a slow puncture) dwarf real car pace in the
    # ghost cliff term. Cap before trimming so the trim's own percentiles
    # aren't skewed by the same outliers.
    arr = np.clip(np.array(records), None, 1.5)
    p10, p90 = np.percentile(arr, [10, 90])
    trimmed = arr[(arr >= p10) & (arr <= p90)]
    return float(trimmed.mean()) if len(trimmed) > 0 else float(arr.mean())


def _fit_wear_slope_with_wind(linear_region: pd.DataFrame) -> tuple[float, float]:
    """
    OLS lap_time_s ~ intercept + age_in_stint + wind_speed_ms, returning the
    age_in_stint coefficient (wear slope net of wind) and R^2. Wind adds drag
    that inflates lap time independent of tyre wear; without netting it out,
    a windy stint's wear_gradient estimate is biased high.
    """
    age = linear_region["age_in_stint"].to_numpy(dtype=float)
    wind = linear_region["wind_speed_ms"].to_numpy(dtype=float)
    y = linear_region["lap_time_s"].to_numpy(dtype=float)
    design = np.column_stack([np.ones_like(age), age, wind])
    coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ coeffs
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(coeffs[1]), r_squared


def estimate_wear_gradient(
    stints_df: pd.DataFrame,
    cliff_onset_laps: float,
) -> float | None:
    """
    Estimate compound_wear_gradient (s/lap) from the linear portion of the wear curve.

    Fits a linear regression on tyre-life laps 3 to min(cliff_onset-2, max_age-2)
    to capture the steady-state degradation before the cliff accelerates, windowed
    on age_in_stint so an SC/VSC gap (already excluded from this row set by the
    caller) doesn't compress the fitted x-spacing and inflate the slope.
    Uses uncensored stints only (forced stop or observed cliff) to avoid the selection
    bias of voluntary pits cutting short the measurable degradation range.

    When wind_speed_ms is available (and the window has enough points to fit a
    3-parameter model), nets wind out via multivariate OLS so a windy stint's
    aero drag doesn't get misread as tyre wear; otherwise falls back to the
    simple age_in_stint-only regression.
    """
    from scipy import stats  # type: ignore

    slopes = []
    cutoff = max(3, int(cliff_onset_laps)-2)
    has_wind = "wind_speed_ms" in stints_df.columns

    for _stint_id, grp in stints_df.groupby("stint_id"):
        grp = grp.sort_values("age_in_stint").reset_index(drop=True)
        linear_region = grp[
            grp["age_in_stint"].between(3, cutoff) &
            grp["lap_time_s"].notna()
        ]
        if len(linear_region) < 3:
            continue

        if has_wind and len(linear_region) >= 4 and linear_region["wind_speed_ms"].notna().all():
            slope, r_squared = _fit_wear_slope_with_wind(linear_region)
        else:
            result = stats.linregress(
                linear_region["age_in_stint"].values,
                linear_region["lap_time_s"].values,
            )
            slope, r_squared = result.slope, result.rvalue ** 2

        # Only accept positive slopes (pace genuinely deteriorating)
        if slope > 0 and r_squared > 0.1:
            slopes.append(slope)

    if not slopes:
        return None
    arr = np.array(slopes)
    p10, p90 = np.percentile(arr, [10, 90])
    trimmed = arr[(arr >= p10) & (arr <= p90)]
    return float(trimmed.mean()) if len(trimmed) > 0 else float(arr.mean())
