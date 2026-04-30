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

import numpy as np
import pandas as pd


CLIFF_DETECTION_THRESHOLD_S = 0.5
CLIFF_MIN_CONTINUATION_LAPS = 2
TRAILING_WINDOW = 5


def detect_cliff_lap(
    lap_times: pd.Series,
    lap_in_stint: pd.Series,
) -> int | None:
    """
    Return the lap_in_stint at which the cliff is detected, or None if not observed.

    A cliff is detected when lap_time exceeds the trailing 5-lap median by
    CLIFF_DETECTION_THRESHOLD_S for at least CLIFF_MIN_CONTINUATION_LAPS consecutive laps.
    This guards against one-off track-limits events or lock-ups.
    """
    df = pd.DataFrame({"t": lap_times.values, "lap": lap_in_stint.values}).sort_values("lap")
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
                return int(row["lap"])-(streak-1)
        else:
            streak = 0
    return None


def build_survival_dataset(
    stints_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Given a DataFrame of stints (one row per lap), build the per-stint survival table:
        stint_id, circuit_key, compound_code, race_year,
        duration (= lap at which event/censoring occurred),
        observed (= 1 if cliff detected, 0 if censored),
        avg_track_temp_c, forced_stop (= 1 if DNF/SC/damage retirement)

    Expects columns: stint_id, lap_in_stint, lap_time_s, circuit_key,
                     compound_code, race_year, track_temp_c, forced_stop_flag
    """
    records = []
    for stint_id, grp in stints_df.groupby("stint_id"):
        grp = grp.sort_values("lap_in_stint")
        if len(grp) < 3:
            continue

        cliff_lap = detect_cliff_lap(grp["lap_time_s"], grp["lap_in_stint"])

        if cliff_lap is not None:
            duration = cliff_lap
            observed = 1
        else:
            duration = int(grp["lap_in_stint"].max())
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
                "forced_stop": int(grp["forced_stop_flag"].iloc[0]),
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
    [onset, onset+5] vs [onset-5, onset-1].
    """
    records = []
    for _stint_id, grp in stints_df.groupby("stint_id"):
        grp = grp.sort_values("lap_in_stint").reset_index(drop=True)
        cliff_lap = detect_cliff_lap(grp["lap_time_s"], grp["lap_in_stint"])
        if cliff_lap is None:
            continue

        pre = grp[grp["lap_in_stint"].between(cliff_lap-5, cliff_lap-1)]["lap_time_s"]
        post = grp[grp["lap_in_stint"].between(cliff_lap, cliff_lap + 5)]["lap_time_s"]

        if len(pre) >= 2 and len(post) >= 2:
            records.append(float(post.mean()-pre.mean()))

    if not records:
        return None
    # Trim outliers (top/bottom 10%) before averaging
    arr = np.array(records)
    p10, p90 = np.percentile(arr, [10, 90])
    trimmed = arr[(arr >= p10) & (arr <= p90)]
    return float(trimmed.mean()) if len(trimmed) > 0 else float(arr.mean())


def estimate_wear_gradient(
    stints_df: pd.DataFrame,
    cliff_onset_laps: float,
) -> float | None:
    """
    Estimate compound_wear_gradient (s/lap) from the linear portion of the wear curve.

    Fits a linear regression on laps 3 to min(cliff_onset-2, max_lap-2) to capture
    the steady-state degradation before the cliff accelerates.
    Uses uncensored stints only (forced stop or observed cliff) to avoid the selection
    bias of voluntary pits cutting short the measurable degradation range.
    """
    from scipy import stats  # type: ignore

    slopes = []
    cutoff = max(3, int(cliff_onset_laps)-2)

    for _stint_id, grp in stints_df.groupby("stint_id"):
        grp = grp.sort_values("lap_in_stint").reset_index(drop=True)
        linear_region = grp[
            grp["lap_in_stint"].between(3, cutoff) &
            grp["lap_time_s"].notna()
        ]
        if len(linear_region) < 3:
            continue

        result = stats.linregress(
            linear_region["lap_in_stint"].values,
            linear_region["lap_time_s"].values,
        )
        # Only accept positive slopes (pace genuinely deteriorating)
        if result.slope > 0 and result.rvalue ** 2 > 0.1:
            slopes.append(result.slope)

    if not slopes:
        return None
    arr = np.array(slopes)
    p10, p90 = np.percentile(arr, [10, 90])
    trimmed = arr[(arr >= p10) & (arr <= p90)]
    return float(trimmed.mean()) if len(trimmed) > 0 else float(arr.mean())
