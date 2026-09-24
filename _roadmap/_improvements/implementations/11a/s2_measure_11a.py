"""11a stage 2 - the out-of-sample test read.

Everything here was fixed by s1 before this script was first run. Four schemes are
applied to the held-out 2023-2024 half and scored on coverage, per-edge coverage and
interval width, marginally, per circuit and per stratum; then the two pre-registered
e-values and the variance decomposition that asks whether a circuit effect exists at all.

Outputs
-------
  s2_results.json     every headline number
  per_circuit.csv     coverage and width per circuit, per scheme, with race counts
  per_stratum.csv     compound x lap-in-stint band x circuit (01b's stratification)
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
MU_0, LAMBDA = 0.80, 2.5          # frozen in s1_prereg.json
N_PERM, N_BOOT, N_SPLIT_R = 999, 2000, 200
MIN_TEST_LAPS = 300               # R4's own screen, reproduced for comparability

# 01b's bands, verbatim.
BANDS = [(2, 5), (6, 10), (11, 15), (16, 20), (21, 30), (31, 10_000)]


def band_of(lap_in_stint: pd.Series) -> pd.Series:
    out = pd.Series("<2", index=lap_in_stint.index, dtype=object)
    for lo, hi in BANDS:
        out[(lap_in_stint >= lo) & (lap_in_stint <= hi)] = f"{lo}-{hi if hi < 9999 else '+'}"
    return out


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
    df["band"] = band_of(df["lap_in_stint"])
    return df.reset_index(drop=True)


# ─── The four schemes ────────────────────────────────────────────────────────────
def apply_schemes(cal: pd.DataFrame, tst: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return {scheme_name: test frame with lo/hi columns}."""
    pooled_sym = conformal_quantile(cal["s_sym"].to_numpy(), ALPHA)
    pooled_lo = conformal_quantile(cal["s_lo"].to_numpy(), ALPHA_EDGE)
    pooled_hi = conformal_quantile(cal["s_hi"].to_numpy(), ALPHA_EDGE)

    per_circuit = {}
    for ck, g in cal.groupby("circuit_key"):
        per_circuit[ck] = (
            conformal_quantile(g["s_sym"].to_numpy(), ALPHA),
            conformal_quantile(g["s_lo"].to_numpy(), ALPHA_EDGE),
            conformal_quantile(g["s_hi"].to_numpy(), ALPHA_EDGE),
        )

    # Cold start: a test circuit with no calibration history falls back to the pooled
    # quantile. This is not a formality - China and Las Vegas are exactly this case.
    fb = np.array([per_circuit.get(c, (pooled_sym, pooled_lo, pooled_hi))
                   for c in tst["circuit_key"]], dtype=float)
    m_sym, m_lo, m_hi = fb[:, 0], fb[:, 1], fb[:, 2]

    out = {}
    out["raw"] = tst.assign(lo=tst["q10"], hi=tst["q90"])
    out["pooled_sym"] = tst.assign(lo=tst["q10"] - pooled_sym, hi=tst["q90"] + pooled_sym)
    out["pooled_asym"] = tst.assign(lo=tst["q10"] - pooled_lo, hi=tst["q90"] + pooled_hi)
    out["mondrian_sym"] = tst.assign(lo=tst["q10"] - m_sym, hi=tst["q90"] + m_sym)
    out["mondrian_asym"] = tst.assign(lo=tst["q10"] - m_lo, hi=tst["q90"] + m_hi)
    return out, {"pooled_sym": pooled_sym, "pooled_lo": pooled_lo, "pooled_hi": pooled_hi}


def score(f: pd.DataFrame) -> dict:
    cov = ((f["y"] >= f["lo"]) & (f["y"] <= f["hi"])).to_numpy()
    return {
        "n": int(len(f)),
        "coverage": float(cov.mean()),
        "below_lo": float((f["y"] < f["lo"]).mean()),
        "above_hi": float((f["y"] > f["hi"]).mean()),
        "mean_width": float((f["hi"] - f["lo"]).mean()),
        "median_width": float((f["hi"] - f["lo"]).median()),
    }


def cluster_bootstrap_ci(f: pd.DataFrame, n_boot: int = N_BOOT) -> tuple[float, float]:
    """95% CI for coverage, resampling whole RACES. Laps are not independent; a
    row-level bootstrap here would report an interval several times too narrow."""
    cov = ((f["y"] >= f["lo"]) & (f["y"] <= f["hi"])).to_numpy()
    races = f["race_id"].to_numpy()
    uniq = np.unique(races)
    idx_by_race = {r: np.where(races == r)[0] for r in uniq}
    draws = np.empty(n_boot)
    for b in range(n_boot):
        pick = RNG.choice(uniq, size=len(uniq), replace=True)
        sel = np.concatenate([idx_by_race[r] for r in pick])
        draws[b] = cov[sel].mean()
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


# ─── E-values ────────────────────────────────────────────────────────────────────
def e1_betting(f: pd.DataFrame) -> float:
    """E = prod over races of [1 + lambda (mu0 - c_r)]. Frozen lambda from s1."""
    cov = (f["y"] >= f["lo"]) & (f["y"] <= f["hi"])
    per_race = f.assign(c=cov).groupby("race_id")["c"].mean()
    return float(np.prod(1.0 + LAMBDA * (MU_0 - per_race.to_numpy())))


def e2_shuffle_rank(f: pd.DataFrame, min_laps: int = MIN_TEST_LAPS) -> dict:
    """Shuffle-rank e-value on the worst-under-coverage statistic.

    The permutation reassigns circuit labels across the test RACES, preserving each
    circuit's race count and each race's own coverage rate. It therefore holds the
    race-level dependence structure fixed and varies only the thing under test: whether
    circuit identity is associated with coverage.
    """
    cov = ((f["y"] >= f["lo"]) & (f["y"] <= f["hi"])).to_numpy()
    race_of = f["race_id"].to_numpy()
    marginal = cov.mean()

    races = pd.DataFrame({"race_id": race_of, "cov": cov}).groupby("race_id").agg(
        n=("cov", "size"), k=("cov", "sum"))
    race_ids = races.index.to_numpy()
    n_r, k_r = races["n"].to_numpy(float), races["k"].to_numpy(float)
    label_of_race = f.groupby("race_id")["circuit_key"].first().reindex(race_ids).to_numpy()

    def stat(labels: np.ndarray) -> float:
        d = pd.DataFrame({"l": labels, "n": n_r, "k": k_r}).groupby("l").sum()
        d = d[d["n"] >= min_laps]
        if d.empty:
            return -np.inf
        return float((marginal - d["k"] / d["n"]).max())

    observed = stat(label_of_race)
    perm = np.array([stat(RNG.permutation(label_of_race)) for _ in range(N_PERM)])
    ge = int((perm >= observed).sum())
    return {"observed_max_under_coverage": observed,
            "n_perm_ge_observed": ge,
            "e_value": float((N_PERM + 1) / (1 + ge)),
            "perm_stat_median": float(np.median(perm)),
            "perm_stat_p95": float(np.percentile(perm, 95))}


# ─── Variance decomposition ──────────────────────────────────────────────────────
def circuit_variance_share(f: pd.DataFrame) -> dict:
    """How much of the per-race coverage spread is a CIRCUIT component?

    R4 screened circuits at n >= 300 LAPS. Laps within a race are dependent, so the
    effective n per circuit is its number of RACES. This is the reading that decides
    whether a Mondrian layer keyed on circuit has anything to calibrate against.
    """
    cov = (f["y"] >= f["lo"]) & (f["y"] <= f["hi"])
    per_race = f.assign(c=cov).groupby(["circuit_key", "race_id"])["c"].mean().reset_index()
    vc = C.variance_components(per_race["c"].to_numpy(),
                               per_race["circuit_key"].to_numpy())
    if vc is None:
        return {"available": False}
    return {"available": True, "n_race_units": vc.n, "n_circuits": vc.n_groups,
            "mean_races_per_circuit": vc.mean_rows_per_group,
            "sigma_b2_circuit": vc.sigma_b2, "sigma_w2_race_within_circuit": vc.sigma_w2,
            "icc_circuit_share": vc.share, "icc_naive_biased_up": vc.share_naive,
            "sd_per_race_coverage": vc.sd}


# ─── Exchangeability contrast: race-randomised split ─────────────────────────────
def race_randomised(df: pd.DataFrame, n_rep: int = N_SPLIT_R) -> dict:
    """Split R. Pool every out-of-sample season (2021-2024) and assign whole RACES at
    random to calibrate / test. This is the split whose exchangeability assumption is
    closest to satisfied; the temporal split's shortfall against it is the cost of the
    fact that seasons are not exchangeable."""
    races = df["race_id"].unique()
    acc = {k: [] for k in ["raw", "pooled_sym", "mondrian_sym", "mondrian_asym"]}
    spread = {k: [] for k in acc}
    for _ in range(n_rep):
        pick = RNG.permutation(races)
        half = len(pick) // 2
        cal = df[df["race_id"].isin(pick[:half])]
        tst = df[df["race_id"].isin(pick[half:])]
        schemes, _ = apply_schemes(cal, tst)
        for k in acc:
            f = schemes[k]
            c = (f["y"] >= f["lo"]) & (f["y"] <= f["hi"])
            acc[k].append(float(c.mean()))
            per_c = f.assign(c=c).groupby("circuit_key").agg(n=("c", "size"), m=("c", "mean"))
            per_c = per_c[per_c["n"] >= MIN_TEST_LAPS]
            spread[k].append(float(per_c["m"].max() - per_c["m"].min()))
    return {k: {"marginal_coverage_mean": float(np.mean(acc[k])),
                "marginal_coverage_sd": float(np.std(acc[k])),
                "per_circuit_spread_mean_pts": float(np.mean(spread[k]) * 100),
                "per_circuit_spread_sd_pts": float(np.std(spread[k]) * 100)}
            for k in acc}


def main() -> int:
    print("11a stage 2 - out-of-sample test read")
    df = load_panel()
    cal, tst = df[df["split"] == "calib"], df[df["split"] == "test"]
    print(f"  calib {len(cal):,} rows / {cal['race_id'].nunique()} races   "
          f"test {len(tst):,} rows / {tst['race_id'].nunique()} races")

    schemes, pooled_q = apply_schemes(cal, tst)
    print(f"  pooled conformal quantiles: sym {pooled_q['pooled_sym']:+.4f}  "
          f"lo {pooled_q['pooled_lo']:+.4f}  hi {pooled_q['pooled_hi']:+.4f}")

    results = {"item": "11a", "stage": "s2_measure",
               "pooled_conformal_quantiles": pooled_q, "schemes": {}}

    per_circuit_rows, per_stratum_rows = [], []
    for name, f in schemes.items():
        s = score(f)
        lo_ci, hi_ci = cluster_bootstrap_ci(f)
        s["coverage_ci95_race_clustered"] = [lo_ci, hi_ci]

        c = (f["y"] >= f["lo"]) & (f["y"] <= f["hi"])
        pc = f.assign(c=c, w=f["hi"] - f["lo"],
                      blo=f["y"] < f["lo"], ahi=f["y"] > f["hi"]).groupby("circuit_key").agg(
            n=("c", "size"), races=("race_id", "nunique"), coverage=("c", "mean"),
            below_lo=("blo", "mean"), above_hi=("ahi", "mean"), mean_width=("w", "mean"))
        pc_screen = pc[pc["n"] >= MIN_TEST_LAPS]
        s["per_circuit_n_ge_300"] = int(len(pc_screen))
        s["per_circuit_coverage_min"] = float(pc_screen["coverage"].min())
        s["per_circuit_coverage_max"] = float(pc_screen["coverage"].max())
        s["per_circuit_spread_pts"] = float(
            (pc_screen["coverage"].max() - pc_screen["coverage"].min()) * 100)
        s["per_circuit_worst_abs_dev_pts"] = float(
            (pc_screen["coverage"] - 0.80).abs().max() * 100)
        s["per_circuit_rmse_dev_pts"] = float(
            np.sqrt(((pc_screen["coverage"] - 0.80) ** 2).mean()) * 100)
        s["per_circuit_width_min"] = float(pc_screen["mean_width"].min())
        s["per_circuit_width_max"] = float(pc_screen["mean_width"].max())
        s["variance_decomposition"] = circuit_variance_share(f)

        for ck, r in pc.reset_index().iterrows():
            per_circuit_rows.append({"scheme": name, **r.to_dict()})

        st = f.assign(c=c, w=f["hi"] - f["lo"]).groupby(
            ["compound", "band", "circuit_key"]).agg(
            n=("c", "size"), coverage=("c", "mean"), mean_width=("w", "mean")).reset_index()
        st = st[st["n"] >= 30]
        s["per_stratum_n_ge_30"] = int(len(st))
        s["per_stratum_coverage_p10_p50_p90"] = [
            float(st["coverage"].quantile(q)) for q in (0.1, 0.5, 0.9)]
        s["per_stratum_rmse_dev_pts"] = float(
            np.sqrt(((st["coverage"] - 0.80) ** 2).mean()) * 100)
        for _, r in st.iterrows():
            per_stratum_rows.append({"scheme": name, **r.to_dict()})

        results["schemes"][name] = s
        print(f"  [{name:14s}] cov {s['coverage']:.4%}  "
              f"lo {s['below_lo']:.3%} hi {s['above_hi']:.3%}  "
              f"width {s['mean_width']:.3f}s  "
              f"circuit spread {s['per_circuit_spread_pts']:.1f}pts")

    pd.DataFrame(per_circuit_rows).to_csv(HERE / "per_circuit.csv", index=False)
    pd.DataFrame(per_stratum_rows).to_csv(HERE / "per_stratum.csv", index=False)

    # --- Pre-registered e-values ----------------------------------------------------
    prereg = json.loads((HERE / "s1_prereg.json").read_text())
    pre_circuits = prereg["e_value_E1_confirmatory"]["circuits"]
    raw = schemes["raw"]
    e1 = {}
    for ck in pre_circuits:
        sub = raw[raw["circuit_key"] == ck]
        e1[ck] = {"n": int(len(sub)), "races": int(sub["race_id"].nunique()),
                  "coverage": float(((sub["y"] >= sub["lo"]) &
                                     (sub["y"] <= sub["hi"])).mean()),
                  "e_value": e1_betting(sub)}
    pooled_sub = raw[raw["circuit_key"].isin(pre_circuits)]
    e1["__POOLED_PREREG__"] = {
        "n": int(len(pooled_sub)), "races": int(pooled_sub["race_id"].nunique()),
        "coverage": float(((pooled_sub["y"] >= pooled_sub["lo"]) &
                           (pooled_sub["y"] <= pooled_sub["hi"])).mean()),
        "e_value": e1_betting(pooled_sub)}
    results["E1_confirmatory"] = e1
    results["E2_scan"] = e2_shuffle_rank(raw)
    print(f"  E1: " + "  ".join(f"{k.split('_')[0]} E={v['e_value']:.3f} "
                                f"(cov {v['coverage']:.2%})" for k, v in e1.items()))
    print(f"  E2: observed max under-coverage "
          f"{results['E2_scan']['observed_max_under_coverage']:.4f}, "
          f"E={results['E2_scan']['e_value']:.2f}")

    # --- Exchangeability contrast ---------------------------------------------------
    print("  running race-randomised split (this is the slow part)...")
    results["split_R_race_randomised"] = race_randomised(df)
    results["split_T_temporal"] = {
        k: {"marginal_coverage": results["schemes"][k]["coverage"],
            "per_circuit_spread_pts": results["schemes"][k]["per_circuit_spread_pts"]}
        for k in ["raw", "pooled_sym", "mondrian_sym", "mondrian_asym"]}

    (HERE / "s2_results.json").write_text(json.dumps(results, indent=2, default=str))
    print("  wrote s2_results.json, per_circuit.csv, per_stratum.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
