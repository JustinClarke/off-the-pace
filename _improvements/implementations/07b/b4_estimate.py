"""07b estimator. Runs the pre-registered design written into
_improvements/work/07-causal-pit-timing.md (section "07b pre-registration",
2026-09-15) -- this script must not be edited to chase a result; every
specification here is named in that pre-registration.

Read-only against data/dev.duckdb (already baked into the cached panel parquet;
no further warehouse access here). Reuses ml/src/intervals.py::cluster_bootstrap
and ml/src/schema.py::RANDOM_STATE unmodified.
"""
import sys
sys.path.insert(0, "/Users/justin/github/off-the-pace")

import numpy as np
import pandas as pd
from scipy import stats

from ml.src import intervals as IV
from ml.src import schema as S

PANEL = "/Users/justin/github/off-the-pace/scratchpad/panel_07b_final.parquet"
rng_seed = S.RANDOM_STATE

panel = pd.read_parquet(PANEL)
panel["stint_max_lap"] = panel.groupby("stint_id")["lap_in_stint"].transform("max")
panel["D"] = (panel["lap_in_stint"] == panel["stint_max_lap"]).astype(int)
panel["Z"] = (panel["is_safety_car_lap"] | panel["is_vsc_lap"]).astype(int)

excl_redflag_only = panel["is_red_flag_lap"] & ~(panel["is_safety_car_lap"] | panel["is_vsc_lap"])
excl_track = panel["track_id"].isna()
pop1 = panel[~excl_redflag_only & ~excl_track].copy()
pop2 = pop1[pop1["deg_state_s"].notna()].copy()
pop3 = pop2[pop2["y_forward_n"] > 0].copy()
pop3["cell"] = (pop3["track_id"].astype(str) + "|" + pop3["era"].astype(str) + "|"
                + pop3["wet_race"].astype(str) + "|" + pop3["age_bin"].astype(str))
pop3 = pop3.reset_index(drop=True)

print(f"Headline analytic population: n={len(pop3)}, Z=1={pop3['Z'].sum()}, pit={pop3['D'].sum()}")

# ---------------------------------------------------------------------------
# Core estimator: FWL fixed-effects demeaning + Wald/2SLS ratio.
# ---------------------------------------------------------------------------
def fwl_wald(df: pd.DataFrame, z_col: str, extra_controls: list[str] | None = None,
             cell_col: str = "cell") -> dict:
    """Demean D, Y, Z (+ extra_controls) within `cell_col`, run first-stage and
    reduced-form OLS on the demeaned data (no intercept needed), return the Wald
    ratio (reduced form Z coef / first stage Z coef) plus both stage coefficients.
    """
    extra_controls = extra_controls or []
    cols = ["D", "y_forward_mean", z_col] + extra_controls
    g = df.groupby(cell_col)
    demeaned = {}
    for c in cols:
        cell_mean = g[c].transform("mean")
        demeaned[c] = (df[c] - cell_mean).to_numpy()

    X = np.column_stack([demeaned[z_col]] + [demeaned[c] for c in extra_controls])
    # first stage
    coef_d, *_ = np.linalg.lstsq(X, demeaned["D"], rcond=None)
    coef_y, *_ = np.linalg.lstsq(X, demeaned["y_forward_mean"], rcond=None)
    fs_z = coef_d[0]
    rf_z = coef_y[0]
    late = rf_z / fs_z if fs_z != 0 else np.nan
    return {"first_stage_z": float(fs_z), "reduced_form_z": float(rf_z), "late": float(late)}


def fwl_wald_arrays(D, Y, Z, cell, extra=None):
    """Same as fwl_wald but takes raw numpy arrays / a small dict of extra
    covariates, for use inside the bootstrap and permutation loops where
    building a DataFrame per draw would be slower."""
    df = pd.DataFrame({"D": D, "y_forward_mean": Y, "__Z__": Z, "cell": cell})
    extra_controls = []
    if extra:
        for k, v in extra.items():
            df[k] = v
            extra_controls.append(k)
    return fwl_wald(df, "__Z__", extra_controls=extra_controls, cell_col="cell")


# ---------------------------------------------------------------------------
# R0 -- headline
# ---------------------------------------------------------------------------
r0 = fwl_wald(pop3, "Z", extra_controls=["deg_state_s"])
print("\n=== R0 headline (FE(L4) + linear deg_state_s) ===")
print(r0)

# Cluster bootstrap CI, race-clustered, reusing ml/src/intervals.py unmodified.
D_arr = pop3["D"].to_numpy()
Y_arr = pop3["y_forward_mean"].to_numpy()
Z_arr = pop3["Z"].to_numpy()
deg_arr = pop3["deg_state_s"].to_numpy()
cell_arr = pop3["cell"].to_numpy()
race_arr = pop3["race_key"].to_numpy()

def score_r0(idx):
    return fwl_wald_arrays(D_arr[idx], Y_arr[idx], Z_arr[idx], cell_arr[idx],
                            extra={"deg_state_s": deg_arr[idx]})["late"]

print("\nRunning cluster_bootstrap (race-clustered, 400 resamples)...")
ci_r0 = IV.cluster_bootstrap(score_r0, race_arr, len(pop3), seed=rng_seed)
print(ci_r0)

# ---------------------------------------------------------------------------
# First-stage strength diagnostics (context, not the primary interval): OLS on
# demeaned data with cluster-robust SE clustered by race, via a simple manual
# cluster-robust variance (no extra dependency needed).
# ---------------------------------------------------------------------------
def cluster_robust_se(X, y, coef, clusters):
    resid = y - X @ coef
    XtX_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for c in np.unique(clusters):
        m = clusters == c
        Xg = X[m]
        ug = resid[m]
        score = Xg.T @ ug
        meat += np.outer(score, score)
    n_clusters = len(np.unique(clusters))
    n = X.shape[0]
    k = X.shape[1]
    correction = (n_clusters / (n_clusters - 1)) * ((n - 1) / (n - k))
    vcov = correction * XtX_inv @ meat @ XtX_inv
    return np.sqrt(np.diag(vcov))

g = pop3.groupby("cell")
D_tilde = (pop3["D"] - g["D"].transform("mean")).to_numpy()
Z_tilde = (pop3["Z"] - g["Z"].transform("mean")).to_numpy()
deg_tilde = (pop3["deg_state_s"] - g["deg_state_s"].transform("mean")).to_numpy()
X_fs = np.column_stack([Z_tilde, deg_tilde])
coef_fs, *_ = np.linalg.lstsq(X_fs, D_tilde, rcond=None)
se_fs = cluster_robust_se(X_fs, D_tilde, coef_fs, race_arr)
f_stat = (coef_fs[0] / se_fs[0]) ** 2
print(f"\nFirst-stage Z coefficient: {coef_fs[0]:.4f} (cluster-robust SE {se_fs[0]:.4f}, "
      f"race-clustered F={f_stat:.1f})")

# ---------------------------------------------------------------------------
# R1 -- unanimous-slice-only
# ---------------------------------------------------------------------------
popB = pop3[pop3["slice_unanimous"] == True].copy()
r1 = fwl_wald(popB, "Z", extra_controls=["deg_state_s"])
print(f"\n=== R1 unanimous-slice-only (n={len(popB)}, Z=1={popB['Z'].sum()}) ===")
print(r1)
D1, Y1, Z1, deg1, cell1, race1 = (popB[c].to_numpy() for c in
                                   ["D", "y_forward_mean", "Z", "deg_state_s", "cell", "race_key"])
ci_r1 = IV.cluster_bootstrap(
    lambda idx: fwl_wald_arrays(D1[idx], Y1[idx], Z1[idx], cell1[idx], {"deg_state_s": deg1[idx]})["late"],
    race1, len(popB), seed=rng_seed)
print(ci_r1)

# ---------------------------------------------------------------------------
# R2 -- conservative Z (already running at lap start; onset moments dropped)
# ---------------------------------------------------------------------------
popA = pop3[pop3["onset"] == 0].copy()
popA["Z_use"] = popA["Z_conservative"]
r2 = fwl_wald(popA, "Z_use", extra_controls=["deg_state_s"])
print(f"\n=== R2 conservative Z, onset dropped (n={len(popA)}, Z_use=1={popA['Z_use'].sum()}) ===")
print(r2)
D2, Y2, Z2, deg2, cell2, race2 = (popA[c].to_numpy() for c in
                                   ["D", "y_forward_mean", "Z_use", "deg_state_s", "cell", "race_key"])
ci_r2 = IV.cluster_bootstrap(
    lambda idx: fwl_wald_arrays(D2[idx], Y2[idx], Z2[idx], cell2[idx], {"deg_state_s": deg2[idx]})["late"],
    race2, len(popA), seed=rng_seed)
print(ci_r2)

# ---------------------------------------------------------------------------
# R3 -- quadratic deg_state_s
# ---------------------------------------------------------------------------
pop3["deg_state_s_sq"] = pop3["deg_state_s"] ** 2
r3 = fwl_wald(pop3, "Z", extra_controls=["deg_state_s", "deg_state_s_sq"])
print("\n=== R3 quadratic deg_state_s ===")
print(r3)

# ---------------------------------------------------------------------------
# R4 -- tercile-FE cross-check (closer to 07a's L5a cell structure)
# ---------------------------------------------------------------------------
pop3["deg_tercile"] = pd.qcut(pop3["deg_state_s"], 3, labels=["t1", "t2", "t3"])
pop3["cell_l5a"] = pop3["cell"] + "|" + pop3["deg_tercile"].astype(str)
g5 = pop3.groupby("cell_l5a")["Z"].agg(["sum", "count"])
g5["n0"] = g5["count"] - g5["sum"]
ident5 = g5[(g5["sum"] > 0) & (g5["n0"] > 0)]
print(f"\n=== R4 tercile-FE cross-check: {len(g5)} cells, {len(ident5)} identifying, "
      f"Z=1 mass in identifying: {ident5['sum'].sum()}/{g5['sum'].sum()} "
      f"({100*ident5['sum'].sum()/g5['sum'].sum():.1f}%) ===")
r4 = fwl_wald(pop3, "Z", extra_controls=[], cell_col="cell_l5a")
print(r4)

# ---------------------------------------------------------------------------
# Exclusion diagnostic: reduced form on D=0 subpopulation only.
# ---------------------------------------------------------------------------
pop_d0 = pop3[pop3["D"] == 0].copy()
g0 = pop_d0.groupby("cell")
Y0_tilde = (pop_d0["y_forward_mean"] - g0["y_forward_mean"].transform("mean")).to_numpy()
Z0_tilde = (pop_d0["Z"] - g0["Z"].transform("mean")).to_numpy()
deg0_tilde = (pop_d0["deg_state_s"] - g0["deg_state_s"].transform("mean")).to_numpy()
X0 = np.column_stack([Z0_tilde, deg0_tilde])
coef0, *_ = np.linalg.lstsq(X0, Y0_tilde, rcond=None)
se0 = cluster_robust_se(X0, Y0_tilde, coef0, pop_d0["race_key"].to_numpy())
t0 = coef0[0] / se0[0]
p0 = 2 * stats.t.sf(abs(t0), df=len(np.unique(pop_d0["race_key"])) - 1)
print(f"\n=== D=0 diagnostic (n={len(pop_d0)}): reduced-form Z coef on Y among non-pitters ===")
print(f"coef={coef0[0]:.4f}, cluster-robust SE={se0[0]:.4f}, t={t0:.2f}, p~{p0:.3f}")

# ---------------------------------------------------------------------------
# Falsification test: Y_placebo ~ Z, identical controls, identical population.
# ---------------------------------------------------------------------------
gph = pop3.groupby("cell")
Yp_tilde = (pop3["y_placebo_mean"] - gph["y_placebo_mean"].transform("mean")).to_numpy()
Zp_tilde = Z_tilde  # same demeaned Z as headline
degp_tilde = deg_tilde
Xp = np.column_stack([Zp_tilde, degp_tilde])
coefp, *_ = np.linalg.lstsq(Xp, Yp_tilde, rcond=None)
sep = cluster_robust_se(Xp, Yp_tilde, coefp, race_arr)
tp = coefp[0] / sep[0]
pp = 2 * stats.t.sf(abs(tp), df=len(np.unique(race_arr)) - 1)
print(f"\n=== FALSIFICATION TEST: Y_placebo ~ Z (n={len(pop3)}) ===")
print(f"coef={coefp[0]:.4f}, cluster-robust SE={sep[0]:.4f}, t={tp:.2f}, p~{pp:.3f}")

# ---------------------------------------------------------------------------
# Gate 7: within-cell permutation, Construction C.
# ---------------------------------------------------------------------------
print("\nRunning gate-7 permutation (999 within-cell shuffles of Z)...")
rng = np.random.default_rng(rng_seed)
cell_codes = pop3["cell"].to_numpy()
n = len(pop3)
perm_lates = np.empty(999)
# precompute index groups per cell for fast within-cell shuffles
cell_series = pd.Series(cell_codes)
idx_by_cell = cell_series.groupby(cell_series).indices  # dict: cell -> array of positions
D_np = pop3["D"].to_numpy()
Y_np = pop3["y_forward_mean"].to_numpy()
Z_np = pop3["Z"].to_numpy()
deg_np = pop3["deg_state_s"].to_numpy()
cell_np = pop3["cell"].to_numpy()

for b in range(999):
    z_shuffled = Z_np.copy()
    for _, positions in idx_by_cell.items():
        if len(positions) > 1:
            z_shuffled[positions] = rng.permutation(Z_np[positions])
    res = fwl_wald_arrays(D_np, Y_np, z_shuffled, cell_np, {"deg_state_s": deg_np})
    perm_lates[b] = res["late"]

obs_late = r0["late"]
all_stats = np.concatenate([np.abs(perm_lates), [np.abs(obs_late)]])
rank = int((all_stats >= np.abs(obs_late)).sum())  # rank of observed among K+1, ties inclusive
e_value = 1000.0 / rank
print(f"\nPermutation null: mean(|LATE_perm|)={np.abs(perm_lates).mean():.4f}, "
      f"sd={perm_lates.std():.4f}, range=[{perm_lates.min():.4f}, {perm_lates.max():.4f}]")
print(f"Observed |LATE|={abs(obs_late):.4f}, rank={rank}/1000, E={e_value:.2f}")

print("\nDONE")
