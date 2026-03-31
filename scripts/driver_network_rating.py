"""Massey teammate-network driver rating (Metric 2).

Reads int_synthetic_teammate from data/dev.duckdb, chains all pairwise
teammate head-to-heads into a global Massey rating, and writes
data/marts/driver_network_rating.parquet.

Three rating sets (era column):
  all_time  – all seasons 2018–2024 pooled
  pre2022   – 2018–2021 (last-gen aero regs)
  post2022  – 2022–2024 (ground-effect regs)

Sign convention: positive rating = faster driver (matches raw proxy where
VER has the highest positive value; the field is anchored so Σrating = 0).

The Massey system uses ALL drivers for network propagation (including
one-race substitutes), but the output includes a `sufficient_sample`
flag (True when n_races ≥ 5) for consumers that want to filter outliers.

Usage:
  .venv/bin/python scripts/driver_network_rating.py
  .venv/bin/python scripts/driver_network_rating.py --db data/custom.duckdb
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
DEFAULT_DB = ROOT / "data" / "dev.duckdb"
OUT_PATH = ROOT / "data" / "marts" / "driver_network_rating.parquet"

MIN_RACES_THRESHOLD = 5


def _massey_solve(df: pd.DataFrame) -> pd.DataFrame:
    """Solve the weighted Massey system from pairwise driver comparisons.

    Each row in df is a per-(race_id, ego, teammate) comparison:
      delta = weighted-mean driver_skill_proxy_s (positive = ego faster)
      weight = total quality weight for that race-pair

    The Massey formulation finds ratings r such that:
      r[ego] - r[teammate] ≈ delta  (higher r = faster driver)

    The anchor Σr = 0 is applied by replacing the last equation of the
    Laplacian system, and the system is solved via numpy lstsq.

    Returns:
        DataFrame with driver_id, rating, rank (1 = fastest).
    """
    drivers = sorted(set(df["ego_driver_id"]) | set(df["teammate_driver_id"]))
    n = len(drivers)
    idx = {d: i for i, d in enumerate(drivers)}

    L = np.zeros((n, n))
    b = np.zeros(n)

    for _, row in df.iterrows():
        i = idx[row["ego_driver_id"]]
        j = idx[row["teammate_driver_id"]]
        w = float(row["weight"])
        d = float(row["delta"])
        L[i, i] += w
        L[j, j] += w
        L[i, j] -= w
        L[j, i] -= w
        b[i] += w * d
        b[j] -= w * d

    # Replace last equation with the anchor: sum(r) = 0
    L[-1, :] = 1.0
    b[-1] = 0.0

    r, _, _, _ = np.linalg.lstsq(L, b, rcond=None)

    result = pd.DataFrame({"driver_id": drivers, "rating": r})
    result = result.sort_values("rating", ascending=False).reset_index(drop=True)
    result["rank"] = range(1, n + 1)
    return result


def _race_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Count unique race appearances per driver (from both sides of the pair)."""
    all_appearances = pd.concat([
        df[["ego_driver_id", "race_id"]].rename(columns={"ego_driver_id": "driver_id"}),
        df[["teammate_driver_id", "race_id"]].rename(columns={"teammate_driver_id": "driver_id"}),
    ])
    counts = (
        all_appearances.drop_duplicates()
        .groupby("driver_id")["race_id"]
        .nunique()
        .rename("n_races")
        .reset_index()
    )
    return counts


def main(db_path: Path = DEFAULT_DB) -> None:
    con = duckdb.connect(str(db_path), read_only=True)

    # Aggregate to per-(race_id, ego, teammate): weighted mean delta + total weight.
    # race_id is the join key for race-count stats.
    agg = con.execute("""
        SELECT
            race_year,
            race_id,
            ego_driver_id,
            teammate_driver_id,
            SUM(pair_quality_weight * driver_skill_proxy_s)
                / NULLIF(SUM(pair_quality_weight), 0) AS delta,
            SUM(pair_quality_weight)                    AS weight
        FROM int_synthetic_teammate
        WHERE teammate_available_flag
          AND NOT strategic_divergence_flag
          AND pair_quality_weight > 0
        GROUP BY race_year, race_id, ego_driver_id, teammate_driver_id
    """).df()

    con.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    scopes = [
        ("all_time", agg),
        ("pre2022",  agg[agg["race_year"] < 2022].copy()),
        ("post2022", agg[agg["race_year"] >= 2022].copy()),
    ]

    results = []
    for scope, subset in scopes:
        if len(subset) == 0:
            continue
        rated = _massey_solve(subset)
        rated["era"] = scope
        race_cts = _race_counts(subset)
        rated = rated.merge(race_cts, on="driver_id", how="left")
        rated["n_races"] = rated["n_races"].fillna(0).astype(int)
        rated["sufficient_sample"] = rated["n_races"] >= MIN_RACES_THRESHOLD
        results.append(rated)

    out = pd.concat(results, ignore_index=True)
    out.to_parquet(OUT_PATH, index=False, compression="zstd")

    print(f"Written {len(out)} rows → {OUT_PATH}")
    for scope, _ in scopes:
        era_df = out[(out["era"] == scope) & out["sufficient_sample"]].sort_values("rank")
        print(f"\n=== {scope.upper()} TOP 15 (sufficient_sample only) ===")
        print(era_df.head(15)[["rank", "driver_id", "rating", "n_races"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    main(args.db)
