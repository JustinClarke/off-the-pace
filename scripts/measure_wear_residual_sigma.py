"""Phase C acceptance metric: per-stint wear-slope residual sigma.

The Phase C acceptance test (see _improvements/PLAN.md) requires that normalizing
lap pace for traffic reduces the scatter around each stint's fitted wear line.
This harness measures exactly that, mirroring survival.estimate_wear_gradient's
window and model choice so the number describes the fit the solver actually does
rather than a parallel re-implementation.

Per stint: restrict to the linear region (age_in_stint in [3, cutoff], where
cutoff = max(3, onset - 2) from the cliff seed), fit the same OLS the solver
fits, and take the residual standard error sqrt(SS_res / (n - k)). Aggregate
across stints.

Two comparisons, reported separately because they answer different questions:

  like-for-like  Same rows, y = lap_time_s vs y = normalized_pace_s. Isolates
                 the effect of normalization alone. Only available once
                 normalized_pace_s exists; single run, no baseline file needed.

  end-to-end     This run vs a stored baseline JSON. Reflects the real shipped
                 delta (lap population changes too, since Phase C relaxes the
                 valid-lap filter to green-flag). Requires capturing a baseline
                 BEFORE the solver change lands.

Pass the same --seed to both runs. The window cutoff is derived from cliff
onsets, which the Phase C refit itself moves; holding the seed fixed keeps the
comparison about pace normalization instead of about window drift.

Usage (PYTHONPATH=transform, same convention as the coefficients test suite):
  PYTHONPATH=transform .venv/bin/python scripts/measure_wear_residual_sigma.py \
      --label baseline
  PYTHONPATH=transform .venv/bin/python scripts/measure_wear_residual_sigma.py \
      --label phase_c \
      --seed transform/seeds_archive/compound_cliff_params_<baseline>.csv \
      --compare transform/analyses/gate_results/wear_sigma_baseline.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from tasks.coefficients.fit_compound_cliff import load_stint_data

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "dev.duckdb"
OUT = ROOT / "transform" / "analyses" / "gate_results"
SEED = ROOT / "transform" / "seeds" / "compound_cliff_params.csv"
SEASONS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

# Mirrors survival.estimate_wear_gradient: 3 points minimum for a 2-parameter
# fit, 4 before the 3-parameter wind model is worth attempting.
MIN_POINTS = 3
MIN_POINTS_WIND = 4


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except subprocess.CalledProcessError:
        return "unknown"


def _residual_sigma(linear_region: pd.DataFrame, y_col: str) -> float | None:
    """Residual standard error of the stint's wear fit, in seconds.

    Uses the wind-adjusted 3-parameter design when the solver would (wind
    present, enough points), else the 2-parameter age-only fit -- same branch
    condition as estimate_wear_gradient, so the residual describes that fit.
    """
    age = linear_region["age_in_stint"].to_numpy(dtype=float)
    y = linear_region[y_col].to_numpy(dtype=float)

    use_wind = (
        "wind_speed_ms" in linear_region.columns
        and len(linear_region) >= MIN_POINTS_WIND
        and linear_region["wind_speed_ms"].notna().all()
    )
    if use_wind:
        wind = linear_region["wind_speed_ms"].to_numpy(dtype=float)
        design = np.column_stack([np.ones_like(age), age, wind])
    else:
        design = np.column_stack([np.ones_like(age), age])

    dof = len(y) - design.shape[1]
    if dof <= 0:
        return None

    coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ coeffs
    return float(np.sqrt(float(np.sum(residuals**2)) / dof))


def _cutoffs(seed_path: Path) -> dict[tuple[str, str, int], int]:
    """Per (circuit, compound, season) linear-region cutoff from the cliff seed."""
    seed = pd.read_csv(seed_path)
    return {
        (r.circuit_key, r.compound_code, int(r.season)): max(
            3, int(r.compound_cliff_onset_laps) - 2
        )
        for r in seed.itertuples()
    }


def measure(
    stints_df: pd.DataFrame, cutoffs: dict, y_cols: list[str]
) -> dict[str, dict[str, float]]:
    """Per-stint residual sigma for each y column, over the identical row set.

    Every y column is measured on the same laps, so a like-for-like comparison
    is unaffected by population differences.
    """
    per_stint: dict[str, dict[str, float]] = {y: {} for y in y_cols}

    for stint_id, grp in stints_df.groupby("stint_id"):
        key = (
            grp["circuit_key"].iloc[0],
            grp["compound_code"].iloc[0],
            int(grp["race_year"].iloc[0]),
        )
        cutoff = cutoffs.get(key)
        if cutoff is None:
            continue

        window = grp[grp["age_in_stint"].between(3, cutoff)]
        # Require every y to be present on the same rows, so the comparison is
        # not quietly measuring different laps per column.
        usable = window[[y for y in y_cols]].notna().all(axis=1)
        window = window[usable]
        if len(window) < MIN_POINTS:
            continue

        for y in y_cols:
            sigma = _residual_sigma(window, y)
            if sigma is not None:
                per_stint[y][str(stint_id)] = sigma

    return per_stint


def _summarize(sigmas: dict[str, float]) -> dict:
    arr = np.array(list(sigmas.values()), dtype=float)
    if len(arr) == 0:
        return {"n_stints": 0}
    return {
        "n_stints": int(len(arr)),
        "median_sigma_s": round(float(np.median(arr)), 4),
        "mean_sigma_s": round(float(arr.mean()), 4),
        "p90_sigma_s": round(float(np.percentile(arr, 90)), 4),
        "pooled_sigma_s": round(float(np.sqrt((arr**2).mean())), 4),
    }


def _paired_delta(before: dict[str, float], after: dict[str, float]) -> dict:
    """Compare on the stints present in both runs -- population change alone
    can move a median, so the shared set is the honest read."""
    shared = sorted(set(before) & set(after))
    if not shared:
        return {"n_shared_stints": 0}
    b = np.array([before[s] for s in shared])
    a = np.array([after[s] for s in shared])
    delta = a - b
    return {
        "n_shared_stints": len(shared),
        "median_sigma_before_s": round(float(np.median(b)), 4),
        "median_sigma_after_s": round(float(np.median(a)), 4),
        "median_paired_delta_s": round(float(np.median(delta)), 4),
        "mean_paired_delta_s": round(float(delta.mean()), 4),
        "pct_stints_improved": round(float((delta < 0).mean() * 100), 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="name for this run (e.g. baseline)")
    ap.add_argument("--seed", type=Path, default=SEED, help="cliff seed for window cutoffs")
    ap.add_argument("--compare", type=Path, help="baseline JSON for an end-to-end delta")
    ap.add_argument("--duckdb", type=Path, default=DB)
    ap.add_argument("--seasons", type=int, nargs="+", default=SEASONS)
    args = ap.parse_args()

    # Resolve every path argument against the invoking cwd before the chdir
    # below, or a relative --seed/--compare silently resolves under transform/.
    args.seed = args.seed.resolve()
    args.duckdb = args.duckdb.resolve()
    if args.compare:
        args.compare = args.compare.resolve()

    # dev.duckdb's bronze views hold paths relative to transform/ ("../data/
    # bronze/..."), so the solver is always invoked as `cd transform && python
    # -m tasks.coefficients.fit_compound_cliff`. Match that cwd or every bronze
    # read fails to resolve.
    os.chdir(ROOT / "transform")

    con = duckdb.connect(str(args.duckdb), read_only=True)
    stints_df = load_stint_data(con, args.seasons)

    y_cols = ["lap_time_s"]
    if "normalized_pace_s" in stints_df.columns:
        y_cols.append("normalized_pace_s")

    cutoffs = _cutoffs(args.seed)
    per_stint = measure(stints_df, cutoffs, y_cols)

    result = {
        "label": args.label,
        "git_sha": _git_sha(),
        "seasons": args.seasons,
        "seed": str(args.seed.relative_to(ROOT)) if args.seed.is_relative_to(ROOT) else str(args.seed),
        "n_laps_loaded": int(len(stints_df)),
        "n_stints_loaded": int(stints_df["stint_id"].nunique()),
        "summary": {y: _summarize(per_stint[y]) for y in y_cols},
        "per_stint_sigma": per_stint,
    }

    if len(y_cols) == 2:
        result["like_for_like"] = _paired_delta(
            per_stint["lap_time_s"], per_stint["normalized_pace_s"]
        )

    if args.compare:
        prior = json.loads(args.compare.read_text())
        prior_sigmas = prior["per_stint_sigma"]["lap_time_s"]
        current = per_stint.get("normalized_pace_s") or per_stint["lap_time_s"]
        result["end_to_end"] = {
            "baseline_label": prior["label"],
            "baseline_git_sha": prior["git_sha"],
            **_paired_delta(prior_sigmas, current),
        }

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"wear_sigma_{args.label}.json"
    out_path.write_text(json.dumps(result, indent=2))

    for y in y_cols:
        print(f"\n{y}: {result['summary'][y]}")
    if "like_for_like" in result:
        print(f"\nlike-for-like (same laps, raw vs normalized): {result['like_for_like']}")
    if "end_to_end" in result:
        print(f"\nend-to-end (vs {args.compare.name}): {result['end_to_end']}")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
