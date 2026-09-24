"""11a stage 3 - can the Mondrian layer be rescued, and at what data volume?

s2 found the raw Mondrian scheme strictly dominated: worse per-circuit coverage than
doing nothing, at 13% more width. But the variance decomposition also found the circuit
component is 22% of per-race coverage variance - small, not zero. So the honest question
is not "does Mondrian work" but "is it starved, and what would feed it".

Two arms:

  A. SHRUNK MONDRIAN. Partial pooling of the per-circuit conformal quantile toward the
     pooled one, with the weight implied by a variance decomposition of the per-race
     conformal quantiles measured on CALIBRATION data only:
         w_c = sigma_b^2 / (sigma_b^2 + sigma_w^2 / n_races_c)
         Q_c = w_c * Q_circuit_c + (1 - w_c) * Q_pooled
     This is a James-Stein/BLUP weight, not a conformal one. It BREAKS the finite-sample
     distribution-free guarantee - the shrunk value is no longer an order statistic of the
     calibration scores - and is reported as a heuristic recalibration, never as certified
     coverage. Stated because that distinction is the whole epistemic value of the method.

  B. CALIBRATION-VOLUME SWEEP. Vary the share of races given to calibration and watch
     whether the Mondrian penalty closes as races-per-circuit grows. If it closes, the
     finding is "starved"; if it does not, the finding is "absent".

Outputs
-------
  s3_results.json   shrinkage arm + sweep
  sweep.csv         per-volume, per-scheme conditional-coverage error
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.src import ceiling as C
from ml.src import schema as S

HERE = Path(__file__).resolve().parent
TARGET = S.DEGRADATION_TARGET
RNG = np.random.default_rng(S.RANDOM_STATE)

ALPHA, ALPHA_EDGE = 0.20, 0.10
MIN_TEST_LAPS = 300
N_REP = 200
CALIB_SHARES = [0.25, 0.40, 0.50, 0.65, 0.80]


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    n = len(scores)
    if n == 0:
        return float("inf")
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    return float("inf") if k > n else float(np.sort(scores)[k - 1])


def load_panel() -> pd.DataFrame:
    df = pd.read_parquet(HERE / "panel_shadow.parquet")
    df = df[df["is_training_eligible"].astype(bool) & df[TARGET].notna()].copy()
    df["y"] = df[TARGET].astype(float)
    df["s_lo"] = df["q10"] - df["y"]
    df["s_hi"] = df["y"] - df["q90"]
    df["s_sym"] = np.maximum(df["s_lo"], df["s_hi"])
    return df.reset_index(drop=True)


def shrinkage_weights(cal: pd.DataFrame) -> tuple[dict[str, float], dict]:
    """w_c per circuit, from a variance decomposition of PER-RACE conformal quantiles.

    The decomposition is run on calibration data only - it is part of the fit, not part
    of the evaluation.
    """
    per_race_q = (cal.groupby(["circuit_key", "race_id"])["s_sym"]
                  .apply(lambda s: conformal_quantile(s.to_numpy(), ALPHA))
                  .reset_index())
    per_race_q = per_race_q[np.isfinite(per_race_q["s_sym"])]
    vc = C.variance_components(per_race_q["s_sym"].to_numpy(),
                               per_race_q["circuit_key"].to_numpy())
    if vc is None or vc.sigma_b2 <= 0:
        return {}, {"available": False,
                    "note": "between-circuit component estimated at or below zero "
                            "-> full shrinkage to pooled is the implied answer"}
    n_races = cal.groupby("circuit_key")["race_id"].nunique()
    w = {ck: float(vc.sigma_b2 / (vc.sigma_b2 + vc.sigma_w2 / max(int(n), 1)))
         for ck, n in n_races.items()}
    info = {"available": True, "sigma_b2_quantile": vc.sigma_b2,
            "sigma_w2_quantile": vc.sigma_w2, "icc_quantile": vc.share,
            "mean_weight": float(np.mean(list(w.values()))) if w else None,
            "min_weight": float(np.min(list(w.values()))) if w else None,
            "max_weight": float(np.max(list(w.values()))) if w else None}
    return w, info


def build(cal: pd.DataFrame, tst: pd.DataFrame, weights: dict[str, float] | None):
    pooled_sym = conformal_quantile(cal["s_sym"].to_numpy(), ALPHA)
    per_circuit = {ck: conformal_quantile(g["s_sym"].to_numpy(), ALPHA)
                   for ck, g in cal.groupby("circuit_key")}

    def q_for(ck: str, shrunk: bool) -> float:
        q = per_circuit.get(ck)
        if q is None or not np.isfinite(q):
            return pooled_sym                       # cold start
        if not shrunk:
            return q
        w = (weights or {}).get(ck, 0.0)
        return w * q + (1.0 - w) * pooled_sym

    out = {}
    out["raw"] = tst.assign(lo=tst["q10"], hi=tst["q90"])
    out["pooled"] = tst.assign(lo=tst["q10"] - pooled_sym, hi=tst["q90"] + pooled_sym)
    for name, shrunk in (("mondrian", False), ("mondrian_shrunk", True)):
        m = np.array([q_for(c, shrunk) for c in tst["circuit_key"]], dtype=float)
        out[name] = tst.assign(lo=tst["q10"] - m, hi=tst["q90"] + m)
    return out


def conditional_error(f: pd.DataFrame) -> dict:
    """The quantity 11a exists to reduce: dispersion of per-circuit coverage about
    nominal. RMSE about 0.80 is the headline; spread is reported beside it because R4
    quoted a spread."""
    c = (f["y"] >= f["lo"]) & (f["y"] <= f["hi"])
    pc = f.assign(c=c).groupby("circuit_key").agg(n=("c", "size"), m=("c", "mean"))
    pc = pc[pc["n"] >= MIN_TEST_LAPS]
    if pc.empty:
        return {}
    return {"marginal_coverage": float(c.mean()),
            "per_circuit_rmse_dev_pts": float(np.sqrt(((pc["m"] - 0.80) ** 2).mean()) * 100),
            "per_circuit_spread_pts": float((pc["m"].max() - pc["m"].min()) * 100),
            "mean_width": float((f["hi"] - f["lo"]).mean()),
            "n_circuits": int(len(pc))}


def main() -> int:
    print("11a stage 3 - shrinkage and calibration-volume sweep")
    df = load_panel()

    # --- Arm A: shrinkage on the declared temporal split ----------------------------
    cal, tst = df[df["split"] == "calib"], df[df["split"] == "test"]
    weights, info = shrinkage_weights(cal)
    print(f"  shrinkage weights: {info}")
    schemes = build(cal, tst, weights)
    arm_a = {name: conditional_error(f) for name, f in schemes.items()}
    for k, v in arm_a.items():
        print(f"  [T {k:16s}] cov {v['marginal_coverage']:.4%}  "
              f"per-circuit RMSE {v['per_circuit_rmse_dev_pts']:.2f}pts  "
              f"spread {v['per_circuit_spread_pts']:.1f}pts  "
              f"width {v['mean_width']:.3f}s")

    # --- Arm B: calibration-volume sweep, race-randomised ---------------------------
    races = df["race_id"].unique()
    rows = []
    for share in CALIB_SHARES:
        n_cal = max(2, int(round(len(races) * share)))
        acc = {}
        for _ in range(N_REP):
            pick = RNG.permutation(races)
            c_df = df[df["race_id"].isin(pick[:n_cal])]
            t_df = df[df["race_id"].isin(pick[n_cal:])]
            if t_df.empty:
                continue
            w, _ = shrinkage_weights(c_df)
            for name, f in build(c_df, t_df, w).items():
                e = conditional_error(f)
                if e:
                    acc.setdefault(name, []).append(e)
        races_per_circuit = n_cal / df["circuit_key"].nunique()
        for name, lst in acc.items():
            rows.append({
                "calib_share": share, "calib_races": n_cal,
                "mean_calib_races_per_circuit": races_per_circuit, "scheme": name,
                "per_circuit_rmse_dev_pts": float(np.mean([x["per_circuit_rmse_dev_pts"] for x in lst])),
                "per_circuit_spread_pts": float(np.mean([x["per_circuit_spread_pts"] for x in lst])),
                "marginal_coverage": float(np.mean([x["marginal_coverage"] for x in lst])),
                "mean_width": float(np.mean([x["mean_width"] for x in lst])),
            })
        print(f"  share {share:.2f} ({n_cal} races, {races_per_circuit:.1f}/circuit): " +
              "  ".join(f"{r['scheme']} {r['per_circuit_rmse_dev_pts']:.2f}"
                        for r in rows if r["calib_share"] == share))

    sweep = pd.DataFrame(rows)
    sweep.to_csv(HERE / "sweep.csv", index=False)

    out = {"item": "11a", "stage": "s3_shrinkage_sweep",
           "shrinkage_info": info, "arm_A_temporal_split": arm_a,
           "arm_B_sweep": rows,
           "guarantee_note": "the shrunk scheme is a heuristic recalibration, NOT a "
                             "conformal one - the shrunk value is not an order "
                             "statistic of the calibration scores, so the finite-sample "
                             "distribution-free coverage guarantee does not apply to it"}
    (HERE / "s3_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("  wrote s3_results.json, sweep.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
