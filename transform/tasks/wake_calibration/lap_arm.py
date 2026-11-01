"""
WC-10e lap-level arm (§9a), also the fallback, and F1 (§11).

Rules come from the signed discovery registration, wi/WC-10-discovery-preregistration-DRAFT.md (commit 6fd0330,
SHA-256 4d679bf6..., DD-WC20). THIS HAS NOT BEEN RUN ON REAL DATA. Library only: opens no file, writes nothing.

The lap arm has no car-behind term, so every quantity is race-internal and a bootstrap draw is the point fit
reweighted by race multiplicity (see design_a's module docstring). The lap-arm bracketed companion (X15) is a
DIAGNOSTIC and is not built here.

Owner rulings applied here (design_a.RULED_CHOICES): a lap prediction whose driver level (alpha) and field effect
(phi) lie in different connected components is dropped and counted (ruling 3, drops["disconnected"]); an
undefined Near_lap in any draw makes the F1 interval undefined, so F1 fails (ruling 4).

Amendment B2 (DD-WC23): a lap without tyre_life (t) does not enter step 1 (lap_free); the theta layout is computed
after that drop; dropped free and following laps are counted under drops["tyre_life_missing_free"] and
drops["tyre_life_missing"] (following laps: before B2 they vanished silently through isfinite(tau)).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tasks.wake_calibration import design_a as A
from tasks.wake_calibration import estimator as E

LAP_TRIM_S = 5.0  # §6f (iii)
LAP_MIN_FREE = 3  # §9a support: the driver-stint has >= 3 free laps
STINT_KEY = "lap_stint"  # (race, driver, stint), §9a


def lap_frame(p: pd.DataFrame, lap_times: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (race, driver, lap) with a braking pass row. Structural columns only, plus lap_time_s when
    `lap_times` (race_id, driver, lap, lap_time_s) is given.

    Scored (§9a): every braking corner of the race has an eligible pass (§5) on that lap, no pass of the lap is
    racecraft, and LapTime is present. Median gap over braking corners with free corners set to 3.0 s; free lap =
    every braking corner free; following lap = median in [0, 3.0)."""
    br = p[p["segment_basis"] == A.BRAKING_BASIS]
    nb = br.groupby("race_id")["corner_id"].nunique()
    e = br[br["eligible"]]
    gfill = np.where(e["free"].to_numpy(), A.FREE_GAP_S, e["gap_s"].to_numpy(dtype=float))
    e = e.assign(gfill=gfill)
    keys = ["race_id", "driver", "lap"]
    lap = e.groupby(keys).agg(n_elig=("corner_id", "nunique"), n_free=("free", "sum"), med=("gfill", "median"),
                              stint=("stint", "first"), compound=("compound", "first"), t=("t", "first"),
                              race_idx=("race_idx", "first")).reset_index()
    rc = br.groupby(keys)["racecraft"].any().rename("any_racecraft").reset_index()
    lap = lap.merge(rc, on=keys, how="left")
    lap["nb"] = lap["race_id"].map(nb).to_numpy()
    lap["struct_scored"] = (lap["n_elig"] == lap["nb"]) & ~lap["any_racecraft"].fillna(False).astype(bool)
    lap["free_lap"] = lap["n_free"] == lap["nb"]
    med = lap["med"].to_numpy(dtype=float)
    lap["following_lap"] = ~lap["free_lap"] & (med >= 0) & (med < A.FREE_GAP_S)
    lap["bin"] = np.where(lap["following_lap"], E.gap_bin(med), -1)
    lap[STINT_KEY] = lap["race_id"].astype(str) + "|" + lap["driver"].astype(str) + "|" + lap["stint"].astype(str)
    if lap_times is not None:
        lt = lap_times[["race_id", "driver", "lap", "lap_time_s"]].copy()
        lt["lap"] = lt["lap"].astype(int)
        if lt.duplicated(keys).any():
            raise A.EstimatorError("more than one lap time per (race, driver, lap)")
        lap = lap.merge(lt, on=keys, how="left")
        lap["scored"] = lap["struct_scored"] & np.isfinite(lap["lap_time_s"].to_numpy(dtype=float))
    return lap


def lap_free(sc: pd.DataFrame) -> np.ndarray:
    """Free scored laps that enter the lap-arm step 1: free, and tyre_life present (B2 ruling 1)."""
    return sc["free_lap"].to_numpy(dtype=bool) & A.tyre_ok(sc)


@dataclass
class LapArm:
    lap: pd.DataFrame  # the scored laps used, with A_tau (tau, no gamma) and valid
    tau: np.ndarray
    valid: np.ndarray
    bins: np.ndarray
    race_idx: np.ndarray
    drops: dict
    sweeps: int


def fit_lap_arm(lap: pd.DataFrame) -> LapArm:
    """§9a step 1 on free scored laps: LapTime = alpha[race, driver, stint] + phi[race, lap] + g(t; race, compound);
    phi under the §6c rule over distinct other free drivers on that lap; support >= 3 free laps; tau = LapTime -
    prediction for following scored laps."""
    sc = lap[lap["scored"]].reset_index(drop=True)
    free = lap_free(sc)  # B2: tyre_life required; the layout below is computed after this drop
    f = sc[free]
    lay = A.theta_layout(sc, free, race_key="race_id")
    lin, quad = A.theta_ids(lay, f["race_id"], f["compound"])
    a_codes, a_uni = pd.factorize(f[STINT_KEY])
    cell = pd.MultiIndex.from_frame(f[["race_id", "lap"]])
    f_codes, f_uni = pd.factorize(cell)
    sol = A.solve_fe(f["lap_time_s"].to_numpy(dtype=float), a_codes, f_codes, lin, quad, f["t"].to_numpy(dtype=float),
                     lay.n_params, f["race_idx"].to_numpy())
    alpha = pd.DataFrame({"y": sol.alpha[:, 0], "n": np.bincount(a_codes), "comp": sol.comp_alpha},
                         index=pd.Index(a_uni))
    phi = pd.DataFrame(list(f_uni), columns=["race_id", "lap"]).assign(
        y=sol.phi[:, 0], x=0.0, n=np.bincount(f_codes), comp=sol.comp_phi)
    fol = sc[sc["following_lap"]].reset_index(drop=True)
    W = A.phi_window_counts(f[["race_id", "lap", "driver"]], fol[["race_id", "lap", "driver"]], ["race_id"])
    py, _, p_ok, pc = A.window_mean(phi, fol, W, ["race_id"])
    a = alpha.reindex(fol[STINT_KEY].to_numpy())
    nfree = a["n"].fillna(0).to_numpy()
    lin_q, quad_q = A.theta_ids(lay, fol["race_id"], fol["compound"])
    th = sol.theta[:, 0]
    t = fol["t"].to_numpy(dtype=float)
    g = np.where(lin_q >= 0, th[np.clip(lin_q, 0, None)] * t, 0.0) + np.where(
        quad_q >= 0, th[np.clip(quad_q, 0, None)] * t * t, np.nan)
    tau = fol["lap_time_s"].to_numpy(dtype=float) - (a["y"].to_numpy(dtype=float) + py + g)
    t_ok = A.tyre_ok(fol)
    supported = nfree >= LAP_MIN_FREE
    has = t_ok & supported & p_ok & np.isfinite(tau)
    ok = A._component_check(has, a["comp"].to_numpy(dtype=float), pc)  # ruling 3: disconnected dropped, counted
    with np.errstate(invalid="ignore"):
        valid = ok & (np.abs(tau) <= LAP_TRIM_S)
    sc_free = sc["free_lap"].to_numpy(dtype=bool)
    drops = {"following_laps": int(len(fol)),
             A.TYRE_LIFE_MISSING: int((~t_ok).sum()),  # B2: counted first, as an entry condition
             "not_supported": int((t_ok & ~supported).sum()),
             "phi_unsupported": int((t_ok & supported & ~p_ok).sum()),
             "other_undefined": int((t_ok & supported & p_ok & ~np.isfinite(tau)).sum()),
             "disconnected": int((has & ~ok).sum()),
             "trimmed": int((ok & ~valid).sum()),
             "free_laps": int(sc_free.sum()),
             A.TYRE_LIFE_MISSING + "_free": int((sc_free & ~A.tyre_ok(sc)).sum())}
    return LapArm(lap=fol, tau=tau, valid=valid, bins=fol["bin"].to_numpy(), race_idx=fol["race_idx"].to_numpy(),
                  drops=drops, sweeps=sol.sweeps)


def lap_stats(arm: LapArm, w: np.ndarray | None = None) -> dict:
    """beta_lap by the 8 median-gap bins and Near_lap for one race weighting (point: all ones)."""
    w = np.ones(A.N_RACES) if w is None else np.asarray(w, dtype=float)
    wr = w[arm.race_idx] * arm.valid
    beta = A._bin_means(np.where(arm.valid, arm.tau, 0.0), np.clip(arm.bins, 0, None), wr)
    return {"lap|beta": beta, "lap|near": A._near(beta),
            "lap|n": np.bincount(np.clip(arm.bins, 0, None), weights=wr, minlength=A.N_BINS)}


def lap_draws(arm: LapArm, plan: A.Plan) -> list[dict]:
    return [lap_stats(arm, plan.weights[i]) for i in range(plan.weights.shape[0])]


def f1_verdict(lap_draw_list: list[dict], s3: dict) -> bool:
    """§11 F1: lower 95 % end of Near_lap > 0, and corner-level S3 passes in medium and slow. An undefined
    interval (any draw with Near_lap undefined, ruling 4) fails F1."""
    lo, _ = A.interval(lap_draw_list, "lap|near")
    return bool(lo > 0 and s3["medium"] and s3["slow"])
