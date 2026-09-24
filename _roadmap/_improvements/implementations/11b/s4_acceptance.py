"""11b · s4 — the acceptance numbers, their intervals, and the pre-registered e-values.

    python3 _improvements/implementations/11b/s4_acceptance.py

Reads s2_stints_{dev,test}_full.parquet and s3_prereg.json, writes s4_results.json.

Everything is clustered on the RACE, never the lap and never the stint: laps are
not independent within a race and neither are stints (they share a car, a driver,
a track state and a caution path).  11a measured a 13x overstatement from using
the lap as the unit; the same correction is applied here by construction.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RNG = np.random.default_rng(20260916)
B = 2000
ARMS = ["seed", "model", "model_nodrift", "shadow_nodrift", "oracle_fit", "oracle"]


def race_boot_vec(v: np.ndarray, race_idx: np.ndarray, n_races: int,
                  b: int = B) -> tuple[float, float, float]:
    """Cluster bootstrap of a MEAN, resampling races with replacement.

    v is a per-stint quantity; race_idx maps each stint to its race. Implemented
    on per-race (sum, count) so the resample is a pair of index draws rather
    than a dataframe rebuild.
    """
    sums = np.bincount(race_idx, weights=v, minlength=n_races)
    cnts = np.bincount(race_idx, minlength=n_races).astype(float)
    obs = float(sums.sum() / cnts.sum())
    pick = RNG.integers(0, n_races, size=(b, n_races))
    draws = sums[pick].sum(axis=1) / cnts[pick].sum(axis=1)
    return obs, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def _race_index(df: pd.DataFrame) -> tuple[np.ndarray, int]:
    codes, uniq = pd.factorize(df.race_id)
    return codes, len(uniq)


def reproduction(df: pd.DataFrame) -> dict:
    idx, nr = _race_index(df)
    out = {}
    for arm in ARMS + ["production_argmin"]:
        col = f"L_{arm}" if arm != "production_argmin" else "L_production_argmin"
        if col not in df.columns:
            continue
        out[arm] = {}
        d = np.abs(df[col].to_numpy() - df.L_actual.to_numpy())
        for k in (0, 1, 2, 3):
            o, lo, hi = race_boot_vec((d <= k).astype(float), idx, nr)
            out[arm][f"within_{k}"] = {"rate": o, "ci95": [lo, hi]}
    return out


def policy_costs(df: pd.DataFrame) -> dict:
    """Mean per-stint cost on the held-out half-sample surface, and the pairwise
    differences with race-clustered CIs.  Regret differences ARE cost differences:
    the common minimum cancels."""
    idx, nr = _race_index(df)
    cols = {a: f"regret_{a}_x" for a in ARMS if f"regret_{a}_x" in df.columns}
    cols["actual"] = "regret_actual_x"
    levels = {}
    for a, c in cols.items():
        o, lo, hi = race_boot_vec(df[c].to_numpy(dtype=float), idx, nr)
        levels[a] = {"mean_regret_s": o, "ci95": [lo, hi]}
    pairs = [("seed", "model_nodrift"), ("seed", "shadow_nodrift"), ("seed", "model"),
             ("seed", "oracle_fit"), ("seed", "actual"), ("actual", "model_nodrift"),
             ("actual", "shadow_nodrift"), ("actual", "oracle_fit"),
             ("oracle_fit", "model_nodrift")]
    diffs = {}
    for a, b_ in pairs:
        if a not in cols or b_ not in cols:
            continue
        v = (df[cols[a]].to_numpy(dtype=float) - df[cols[b_]].to_numpy(dtype=float))
        o, lo, hi = race_boot_vec(v, idx, nr)
        diffs[f"{a}_minus_{b_}"] = {"seconds_per_stint": o, "ci95": [lo, hi]}
    return {"levels": levels, "differences": diffs}


def e_betting(win: np.ndarray, mu0: float, lam: float) -> float:
    return float(np.prod(1.0 + lam * (win - mu0)))


def e_shuffle(df: pd.DataFrame, col: str, k: int = 2, K: int = 999) -> dict:
    bucket = (df.H / 5).round().astype(int).to_numpy()
    dp = df[col].to_numpy()
    act = df.L_actual.to_numpy()
    obs = float(np.mean(np.abs(dp - act) <= k))
    rng = np.random.default_rng(20260916)
    ge = 0
    for _ in range(K):
        perm = act.copy()
        for b_ in np.unique(bucket):
            m = bucket == b_
            perm[m] = rng.permutation(act[m])
        if np.mean(np.abs(dp - perm) <= k) >= obs:
            ge += 1
    return {"observed_rate": obs, "n_perm_ge": ge, "K": K,
            "E": float((K + 1) / (1 + ge))}


def main() -> None:
    prereg = json.loads((HERE / "s3_prereg.json").read_text())
    lam = prereg["hypotheses"]["E1"]["lambda"]
    res: dict = {"prereg": str(HERE / "s3_prereg.json"), "halves": {}}

    for tag in ("dev", "test"):
        df = pd.read_parquet(HERE / f"s2_stints_{tag}_full.parquet")
        half = {
            "stints": int(len(df)), "races": int(df.race_id.nunique()),
            "circuits": int(df.circuit_key.nunique()),
            "seasons": sorted(int(x) for x in df.race_year.unique()),
            "instrument_check_production_argmin_matches_int_pit_strategy_value":
                float(np.mean(df.L_production_argmin == df.optimal_pit_lap_in_stint)),
            "reproduction": reproduction(df),
            "policy_cost": policy_costs(df),
        }
        # known-good screen: a green-flag stint ending (a real strategy call, not a
        # caution or a red flag) by a driver who finished in the points.
        kg = df[(df.end_regime == "green") & (df.final_position <= 10)]
        half["known_good"] = {
            "stints": int(len(kg)), "races": int(kg.race_id.nunique()),
            "screen": "end_regime == 'green' AND final_position <= 10",
            "reproduction": reproduction(kg) if len(kg) > 30 else None,
            "policy_cost": policy_costs(kg) if len(kg) > 30 else None,
        }
        res["halves"][tag] = half

    # ---- pre-registered e-values, on the TEST half only -------------------
    te = pd.read_parquet(HERE / "s2_stints_test_full.parquet")
    g = te.groupby("race_id")[[c for c in te.columns if c.startswith("regret_") and c.endswith("_x")]].mean()
    evals = {}
    for name, arm in (("E1", "model_nodrift"), ("E3", "shadow_nodrift")):
        col = f"regret_{arm}_x"
        if col not in g.columns:
            continue
        w = (g[col] < g["regret_seed_x"]).to_numpy(dtype=float)
        evals[name] = {"arm": arm, "races": int(len(w)), "win_rate": float(w.mean()),
                       "lambda": lam, "mu0": 0.5, "E": e_betting(w, 0.5, lam)}
    evals["E2"] = {"arm": "model_nodrift", **e_shuffle(te, "L_model_nodrift")}
    res["e_values_test"] = evals

    # ---- does the stochastic (SC-hazard) arm earn its place? --------------
    idx, nr = _race_index(te)
    stoch = {}
    for a in ARMS:
        cs, cd = f"regret_{a}_x", f"regret_{a}_det_x"
        if cs not in te.columns or cd not in te.columns:
            continue
        o, lo, hi = race_boot_vec(te[cd].to_numpy(float) - te[cs].to_numpy(float), idx, nr)
        stoch[a] = {
            "stochastic_mean_regret_s": float(te[cs].mean()),
            "deterministic_mean_regret_s": float(te[cd].mean()),
            "deterministic_minus_stochastic_s": o, "ci95": [lo, hi],
            "calls_changed_by_hazard": float(np.mean(te[f"L_{a}"] != te[f"L_{a}_det"])),
            "mean_lap_shift_later": float(np.mean(te[f"L_{a}"] - te[f"L_{a}_det"])),
        }
    res["stochastic_arm_test"] = {
        "caution_available_in_pct_of_stints": float(np.mean(te.caution_available > 0)),
        "mean_caution_gaps_per_stint": float(te.caution_available.mean()),
        "mean_hazard_per_lap": float(te.h.mean()),
        "arms": stoch,
    }

    # ---- sensitivities ----------------------------------------------------
    sens = {}
    for tag in ("test_persist", "test_r5", "test_r10"):
        p = HERE / f"s2_stints_{tag}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        cols = {a: f"regret_{a}_x" for a in ARMS + ["actual"] if f"regret_{a}_x" in d.columns}
        sens[tag] = {"stints": int(len(d)),
                     "mean_regret_s": {a: float(d[c].mean()) for a, c in cols.items()},
                     "reproduction_within_2": {
                         a: float(np.mean(np.abs(d[f"L_{a}"] - d.L_actual) <= 2))
                         for a in ARMS if f"L_{a}" in d.columns}}
    res["sensitivities"] = sens

    (HERE / "s4_results.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res["e_values_test"], indent=2))
    print(json.dumps(res["halves"]["test"]["policy_cost"], indent=2))


if __name__ == "__main__":
    main()
