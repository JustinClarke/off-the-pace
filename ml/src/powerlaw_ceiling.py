"""WI-17 Step 0: can (alpha, beta) be predicted at all? Read-only identification check.

Re-runs the pre-flight probe on the final lap set (`int_power_law_lap`) and reports the
**reliability ceiling** -- 1 - mean(bootstrap sampling variance) / cross-unit variance, i.e.
the best R^2 any feature set could reach against these noisy targets -- for alpha, beta and the
curve at ages 5, 10, 15 and 20, for three fit grains:

  stint       y = c + alpha * age^beta per stint (>= 8 laps, age span >= 7); residual bootstrap.
  cell        race x hardness-rank cell, one intercept per stint and a shared (alpha, beta);
              stint-cluster bootstrap.
  cell+lapFE  the cell fit with a (race, lap) fixed effect alongside the stint intercepts, all
              of a race's cells fitted jointly (Frisch-Waugh: both fixed effects projected out
              exactly, then (alpha_k, beta_k) profiled on the grid jointly across the race's
              ranks); stint-cluster bootstrap within each cell.

The curve is reported two ways (see powerlaw_fit): `delta_a` over the extrapolated age-0 pace
(the WI's wording) and `incr_a` over the fresh-tyre pace at age 2 (what the simulator draws).

`--with-rubber` repeats the stint and cell grains on the pre-flight target
(weight_corrected_lap_time - rubber_component_s) for comparison. That read is a measurement
only; nothing trains on it.

CLI:
  python -m ml.src.powerlaw_ceiling                  # prints the table, writes the JSON report
  python -m ml.src.powerlaw_ceiling --reps 40 --with-rubber
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ml.src import powerlaw_fit as PF
from ml.src import schema as S

REPORT_PATH = Path("ml/artefacts/powerlaw_ceiling.json")
N_BOOT = 40
STOP_BELOW = 0.3     # WI-17 Step 0: every ceiling below this -> the item closes as a measured "no"
QUANTITIES = ["alpha", "beta"] + [f"delta_{a}" for a in PF.EVAL_AGES] + [f"incr_{a}" for a in PF.EVAL_AGES]


def _q(x) -> list[float]:
    return [round(float(v), 3) for v in np.quantile(x, [0.1, 0.25, 0.5, 0.75, 0.9])]


def _ceilings(est: dict[str, np.ndarray], var: dict[str, np.ndarray]) -> dict[str, float]:
    return {k: round(PF.reliability(est[k], var[k]), 3) for k in QUANTITIES}


def _medians(est: dict[str, np.ndarray]) -> dict[str, float]:
    """Median point estimate per quantity: the level check. A ceiling measures precision
    only, so a grain that is precise about the wrong quantity shows up here, not there."""
    return {k: round(float(np.nanmedian(est[k])), 3) for k in QUANTITIES}


def _boot_moments(alphas: np.ndarray, betas: np.ndarray) -> dict[str, float]:
    qs = PF.curve_quantities(alphas, betas)
    return {k: float(np.var(qs[k])) for k in QUANTITIES}


# ─── grain 1: per stint ──────────────────────────────────────────────────────────────────────
def stint_grain(laps: pd.DataFrame, reps: int, rng: np.random.Generator) -> dict:
    est = {k: [] for k in QUANTITIES}
    var = {k: [] for k in QUANTITIES}
    r2, r2_lin, n_laps = [], [], []
    for _, g in laps.groupby("stint_id", sort=True):
        if len(g) < PF.STINT_MIN_LAPS:
            continue
        age = g["age"].to_numpy(float)
        y = g["y"].to_numpy(float)
        if np.ptp(age) < PF.STINT_MIN_AGE_SPAN:
            continue
        fit = PF.fit_stint(age, y)
        if fit is None:
            continue
        r2.append(fit.r2)
        r2_lin.append(fit.r2_linear)
        n_laps.append(len(y))
        fitted = fit.c + fit.alpha * age ** fit.beta
        resid = y - fitted
        Ystar = fitted[:, None] + rng.choice(resid, size=(len(y), reps), replace=True)
        ba, bb = PF.fit_stint_many(age, Ystar)
        point = PF.curve_quantities(fit.alpha, fit.beta)
        moments = _boot_moments(ba, bb)
        for k in QUANTITIES:
            est[k].append(float(point[k]))
            var[k].append(moments[k])
    est = {k: np.array(v) for k, v in est.items()}
    var = {k: np.array(v) for k, v in var.items()}
    r2, r2_lin, n_laps = map(np.array, (r2, r2_lin, n_laps))
    return {
        "n_units": int(len(r2)),
        "r2_quantiles_p10_p25_p50_p75_p90": _q(r2),
        "share_r2_ge_0_85": round(float((r2 >= 0.85).mean()), 3),
        "share_r2_ge_0_85_by_laps": {
            f"{lo}-{hi}": round(float((r2[(n_laps >= lo) & (n_laps < hi)] >= 0.85).mean()), 3)
            for lo, hi in [(8, 15), (15, 25), (25, 60)]},
        "median_r2_gain_over_line": round(float(np.median(r2 - r2_lin)), 4),
        "share_beta_at_grid_edge": round(float(np.isin(est["beta"], [PF.BETA_MIN, PF.BETA_MAX]).mean()), 3),
        "ceiling": _ceilings(est, var),
        "median_estimate": _medians(est),
    }


# ─── grain 2: race x hardness-rank cell ──────────────────────────────────────────────────────
def cell_grain(laps: pd.DataFrame, reps: int, rng: np.random.Generator) -> tuple[dict, pd.DataFrame]:
    est = {k: [] for k in QUANTITIES}
    var = {k: [] for k in QUANTITIES}
    rows = []
    ranked = laps[laps["compound_hardness_rank"].notna()]
    for (race, rank), g in ranked.groupby(["race_id", "compound_hardness_rank"], sort=True):
        parts = PF.cell_parts(g)
        if not PF.cell_eligible(parts):
            continue
        sums = PF.cell_sums(parts)
        alpha, beta, r2w = PF.fit_cell_from_sums(sums)
        S_ = len(parts)
        W = rng.multinomial(S_, np.full(S_, 1.0 / S_), size=reps).astype(float)
        ba, bb = np.empty(reps), np.empty(reps)
        for r in range(reps):
            ba[r], bb[r], _ = PF.fit_cell_from_sums(sums, W[r])
        point = PF.curve_quantities(alpha, beta)
        moments = _boot_moments(ba, bb)
        for k in QUANTITIES:
            est[k].append(float(point[k]))
            var[k].append(moments[k])
        rows.append({"race_id": race, "rank": int(rank), "n_stints": S_,
                     "n_laps": int(sum(len(p[1]) for p in parts)),
                     "alpha": alpha, "beta": beta, "r2_within": r2w})
    est = {k: np.array(v) for k, v in est.items()}
    var = {k: np.array(v) for k, v in var.items()}
    cells = pd.DataFrame(rows)
    return {
        "n_units": int(len(cells)),
        "r2_within_quantiles_p10_p25_p50_p75_p90": _q(cells["r2_within"]),
        "share_beta_at_grid_edge": round(float(cells["beta"].isin([PF.BETA_MIN, PF.BETA_MAX]).mean()), 3),
        "share_alpha_negative": round(float((cells["alpha"] < 0).mean()), 3),
        "ceiling": _ceilings(est, var),
        "median_estimate": _medians(est),
    }, cells


# ─── grain 3: cell + (race, lap) fixed effect, a race's cells fitted jointly ────────────────
def _race_design(stint_idx: np.ndarray, lap_idx: np.ndarray) -> np.ndarray:
    n = len(stint_idx)
    D = np.zeros((n, stint_idx.max() + 1 + lap_idx.max() + 1))
    D[np.arange(n), stint_idx] = 1.0
    D[np.arange(n), stint_idx.max() + 1 + lap_idx] = 1.0
    return D


def _fit_race_lapfe(age, y, stint_idx, lap_idx, rank_idx, K):
    """Joint (alpha_k, beta_k) for a race's K ranks with stint and lap FEs projected out.

    Returns (alpha[K], beta[K], surviving_share[K] at the chosen beta, surviving_share[K] at
    beta = 1) where surviving_share is the fraction of the regressor's within-stint variance
    left after the lap FE is also removed -- 0 means the curve is not identified at all."""
    G = len(PF.BETA_GRID)
    X = np.zeros((len(y), K * G))
    powers = np.power(age[:, None], PF.BETA_GRID[None, :])
    for k in range(K):
        m = rank_idx == k
        X[m, k * G:(k + 1) * G] = powers[m]
    D = _race_design(stint_idx, lap_idx)
    M = np.column_stack([y, X])
    coef, *_ = np.linalg.lstsq(D, M, rcond=None)
    R = M - D @ coef
    yt, Xt = R[:, 0], R[:, 1:]
    # within-stint only (for the surviving-variance diagnostic)
    Ds = D[:, : stint_idx.max() + 1]
    cs, *_ = np.linalg.lstsq(Ds, X, rcond=None)
    Xw = X - Ds @ cs
    gram = Xt.T @ Xt
    bvec = Xt.T @ yt
    syy = float(yt @ yt)
    combos = np.stack(np.meshgrid(*[np.arange(G)] * K, indexing="ij"), axis=-1).reshape(-1, K)
    idx = combos + (np.arange(K) * G)[None, :]
    A = gram[idx[:, :, None], idx[:, None, :]]                     # (C, K, K)
    b = bvec[idx]                                                  # (C, K)
    # Conditioning screen: the Hadamard ratio det(A) / prod(diag(A)) is 1 for orthogonal
    # regressors and 0 for collinear ones (all ranks at beta = 1 is exactly singular -- see
    # the note in lapfe_grain). Cheaper than a per-combo SVD across ~185k combos.
    diag = np.einsum("ckk->ck", A)
    with np.errstate(all="ignore"):
        had = np.linalg.det(A) / np.prod(diag, axis=1)
    ok = np.isfinite(had) & (had > 1e-10) & np.all(diag > 1e-12, axis=1)
    sse = np.full(len(combos), np.inf)
    sol = np.zeros_like(b)
    if ok.any():
        sol[ok] = np.linalg.solve(A[ok], b[ok][..., None])[..., 0]
        sse[ok] = syy - np.einsum("ck,ck->c", sol[ok], b[ok])
    j = int(np.argmin(sse))
    alphas, betas = sol[j], PF.BETA_GRID[combos[j]]
    surv, surv_lin = np.empty(K), np.empty(K)
    for k in range(K):
        cj = k * G + combos[j, k]
        cl = k * G + PF.LINEAR_INDEX
        surv[k] = (Xt[:, cj] @ Xt[:, cj]) / max(Xw[:, cj] @ Xw[:, cj], 1e-12)
        surv_lin[k] = (Xt[:, cl] @ Xt[:, cl]) / max(Xw[:, cl] @ Xw[:, cl], 1e-12)
    return alphas, betas, surv, surv_lin


def lapfe_grain(laps: pd.DataFrame, reps: int, rng: np.random.Generator) -> dict:
    est = {k: [] for k in QUANTITIES}
    var = {k: [] for k in QUANTITIES}
    surv_all, surv_lin_all, k_per_race = [], [], []
    ranked = laps[laps["compound_hardness_rank"].notna()]
    for race, rg in ranked.groupby("race_id", sort=True):
        cells = []
        for rank, g in rg.groupby("compound_hardness_rank", sort=True):
            stints = [s for _, s in g.groupby("stint_id", sort=True)
                      if len(s) >= PF.CELL_STINT_MIN_LAPS and s["age"].nunique() >= 2]
            if len(stints) >= PF.CELL_MIN_STINTS and sum(len(s) for s in stints) >= PF.CELL_MIN_LAPS:
                cells.append(stints)
        K = len(cells)
        if K == 0:
            continue
        k_per_race.append(K)

        def assemble(choice):
            ages, ys, sidx, lnum, ridx = [], [], [], [], []
            sid = 0
            for k, stints in enumerate(cells):
                for i in choice[k]:
                    s = stints[i]
                    ages.append(s["age"].to_numpy(float))
                    ys.append(s["y"].to_numpy(float))
                    lnum.append(s["lap_number"].to_numpy(int))
                    sidx.append(np.full(len(s), sid))
                    ridx.append(np.full(len(s), k))
                    sid += 1
            lap = np.concatenate(lnum)
            _, lap_idx = np.unique(lap, return_inverse=True)
            return (np.concatenate(ages), np.concatenate(ys), np.concatenate(sidx), lap_idx,
                    np.concatenate(ridx))

        full = [np.arange(len(c)) for c in cells]
        a0, b0, surv, surv_lin = _fit_race_lapfe(*assemble(full), K)
        surv_all.extend(surv.tolist())
        surv_lin_all.extend(surv_lin.tolist())
        ba = np.empty((reps, K))
        bb = np.empty((reps, K))
        for r in range(reps):
            choice = [rng.integers(0, len(c), len(c)) for c in cells]
            ba[r], bb[r], _, _ = _fit_race_lapfe(*assemble(choice), K)
        for k in range(K):
            point = PF.curve_quantities(a0[k], b0[k])
            moments = _boot_moments(ba[:, k], bb[:, k])
            for q in QUANTITIES:
                est[q].append(float(point[q]))
                var[q].append(moments[q])
    est = {k: np.array(v) for k, v in est.items()}
    var = {k: np.array(v) for k, v in var.items()}
    surv_all, surv_lin_all = np.array(surv_all), np.array(surv_lin_all)
    return {
        "n_units": int(len(est["alpha"])),
        "ranks_per_race": {str(k): int(v) for k, v in zip(*np.unique(k_per_race, return_counts=True))},
        "share_beta_at_grid_edge": round(float(np.isin(est["beta"], [PF.BETA_MIN, PF.BETA_MAX]).mean()), 3),
        "identification": {
            "surviving_share_of_within_stint_variance_at_chosen_beta_p10_p50_p90":
                [round(float(v), 4) for v in np.quantile(surv_all, [0.1, 0.5, 0.9])],
            "surviving_share_at_beta_1_p10_p50_p90":
                [round(float(v), 4) for v in np.quantile(surv_lin_all, [0.1, 0.5, 0.9])],
            "note": ("Within a stint, tyre age and lap number rise together one for one, so a "
                     "straight-line age term lies in the span of the stint and (race, lap) fixed "
                     "effects. Only curvature, and differences between a race's ranks, survive."),
        },
        "ceiling": _ceilings(est, var),
        "median_estimate": _medians(est),
    }


def with_rubber(laps: pd.DataFrame, duckdb_path: str) -> pd.DataFrame:
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        rub = con.execute("SELECT lap_id, COALESCE(rubber_component_s, 0) AS rubber "
                          "FROM int_lap_residual_decomposed").df()
    finally:
        con.close()
    out = laps.merge(rub, on="lap_id", how="left")
    out["y"] = out["y"] - out["rubber"].fillna(0.0)
    return out.drop(columns="rubber")


def verdict(report: dict) -> dict:
    ceilings = {f"{grain}.{q}": v for grain, blk in report["grains"].items()
                for q, v in blk["ceiling"].items()}
    best = max(ceilings.items(), key=lambda kv: kv[1] if np.isfinite(kv[1]) else -9)
    curve_best = {g: max(v for q, v in blk["ceiling"].items() if q.startswith(("delta_", "incr_")))
                  for g, blk in report["grains"].items()}
    return {"all_below_stop_threshold": bool(all(v < STOP_BELOW for v in ceilings.values()
                                                 if np.isfinite(v))),
            "stop_threshold": STOP_BELOW,
            "best": {"quantity": best[0], "ceiling": best[1]},
            "best_curve_ceiling_by_grain": curve_best}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duckdb", default=S.DUCKDB_PATH)
    ap.add_argument("--reps", type=int, default=N_BOOT)
    ap.add_argument("--with-rubber", action="store_true",
                    help="also measure the pre-flight target (y - rubber_component_s)")
    ap.add_argument("--skip-lapfe", action="store_true", help="skip the (race, lap) FE variant")
    ap.add_argument("--out", default=str(REPORT_PATH))
    args = ap.parse_args()

    laps = PF.load_laps(args.duckdb)
    report: dict = {"lap_set": "int_power_law_lap", "target": "y_s = weight_corrected_lap_time",
                    "n_laps": int(len(laps)), "reps": args.reps, "random_state": S.RANDOM_STATE,
                    "fresh_anchor_age": PF.FRESH_ANCHOR_AGE, "grains": {}}
    rng = np.random.default_rng(S.RANDOM_STATE)
    t = time.time()
    report["grains"]["stint"] = stint_grain(laps, args.reps, rng)
    print(f"stint grain done ({time.time() - t:.0f}s)")
    blk, _ = cell_grain(laps, args.reps, rng)
    report["grains"]["cell"] = blk
    print(f"cell grain done ({time.time() - t:.0f}s)")
    if not args.skip_lapfe:
        report["grains"]["cell_lapfe"] = lapfe_grain(laps, args.reps, rng)
        print(f"cell+lapFE grain done ({time.time() - t:.0f}s)")
    report["verdict"] = verdict(report)
    if args.with_rubber:
        lr = with_rubber(laps, args.duckdb)
        rng2 = np.random.default_rng(S.RANDOM_STATE)
        rub = {"stint": stint_grain(lr, args.reps, rng2)}
        rub["cell"], _ = cell_grain(lr, args.reps, rng2)
        report["sensitivity_y_minus_rubber"] = rub
        print(f"rubber sensitivity done ({time.time() - t:.0f}s)")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"\nreliability ceiling (best R^2 any feature set can reach), {args.reps} bootstrap reps")
    grains = list(report["grains"])
    print(f"{'quantity':10s}" + "".join(f"{g:>12s}" for g in grains))
    for q in QUANTITIES:
        print(f"{q:10s}" + "".join(f"{report['grains'][g]['ceiling'][q]:>12.3f}" for g in grains))
    if "sensitivity_y_minus_rubber" in report:
        print("\n  y - rubber (pre-flight target):")
        for q in QUANTITIES:
            print(f"{q:10s}" + "".join(
                f"{report['sensitivity_y_minus_rubber'][g]['ceiling'][q]:>12.3f}" for g in ("stint", "cell")))
    print(json.dumps(report["verdict"], indent=1))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
