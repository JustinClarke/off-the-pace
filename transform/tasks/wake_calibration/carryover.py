"""
WC-10e tyre carry-over theta_carry (registration §9b). Expected "—"; nothing here decides a tyre level (that is
confirmatory C5).

Rules come from the signed discovery registration, wi/WC-10-discovery-preregistration-DRAFT.md (commit 6fd0330,
DD-WC20). THIS HAS NOT BEEN RUN ON REAL DATA. Library only: opens no file, writes nothing.

§9b, as implemented (literal reading):
  - Close lap: a scored lap (§9a, lap_arm.lap_frame `scored`) with median gap < 1.0 s.
  - Episode: a maximal run of consecutive close laps in a stint (lap numbers l, l+1, ... all close; a lap that is
    not a close lap, scored or not, ends the run).
  - C_l: the number of close laps earlier in the stint (lap < l).
  - Fit on the free scored laps of driver-stints with >= 3 free laps:
        LapTime = alpha[race, driver, stint] + phi[race, lap] + g(tyre_life; race, compound)
                  + theta_carry * C_l + sum_{j=1..3} pi_j * 1{l is j laps before the stint's next episode} + e
    jointly by least squares. g is §6d with the class index dropped (design_a.theta_layout over the free laps, as
    the lap arm). alpha, phi and theta are race-internal; theta_carry and pi are pooled, so they are obtained by
    Frisch-Waugh-Lovell from per-race sufficient statistics of the fixed-effect residuals. A bootstrap draw is
    the same normal equations weighted by race multiplicity (exact, as in design_a's module docstring; every entry
    of a race is a separate copy, ruling 5). Intervals propagate undefined draws (ruling 4).
  - The episode-length tier fit replaces C_l by its three parts: close laps from episodes of 1-2, 3-4 and >= 5
    laps (every episode before a free lap is complete, so its length is known).
  - A regressor with no variation left after the fixed effects is reported "—, not identified" (never 0).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tasks.wake_calibration import design_a as A
from tasks.wake_calibration import lap_arm as L

CLOSE_LAP_GAP_S = 1.0  # §9b
CARRY_MIN_FREE = 3  # §9b: driver-stints with >= 3 free laps
PRE_TREND_LAPS = (1, 2, 3)  # §9b pi_1..pi_3
EPISODE_TIERS = ((1, 2), (3, 4), (5, None))  # §9b: 1-2, 3-4, >= 5 laps
TIER_NAMES = ("C_ep1-2", "C_ep3-4", "C_ep5+")
MAIN_TERMS = ("theta_carry", "pi_1", "pi_2", "pi_3")
TIER_TERMS = TIER_NAMES + ("pi_1", "pi_2", "pi_3")
SINGULAR_TOL = 1e-10


def carry_frame(lap: pd.DataFrame) -> pd.DataFrame:
    """Scored laps with the §9b labels: close, episode id and length, C_l, the tier parts and the pre-trend
    dummies. `lap` is lap_arm.lap_frame(p, lap_times) (needs `scored`)."""
    if "scored" not in lap.columns:
        raise A.EstimatorError("carry_frame needs lap_arm.lap_frame with lap times (`scored`)")
    sc = lap[lap["scored"]].sort_values([L.STINT_KEY, "lap"]).reset_index(drop=True).copy()
    med = sc["med"].to_numpy(dtype=float)
    sc["close_lap"] = med < CLOSE_LAP_GAP_S
    key = sc[L.STINT_KEY].to_numpy()
    lapn = sc["lap"].to_numpy(dtype=int)
    close = sc["close_lap"].to_numpy()
    # episode: consecutive lap numbers, all close, same stint
    new_ep = close & ~(np.r_[False, (key[1:] == key[:-1]) & (lapn[1:] == lapn[:-1] + 1) & close[:-1]])
    ep = np.where(close, np.cumsum(new_ep), 0)
    sc["episode"] = ep
    ep_len = pd.Series(ep[close]).value_counts()
    sc["episode_len"] = np.where(close, pd.Series(ep).map(ep_len).fillna(0).to_numpy(), 0).astype(int)
    # C_l and its tier parts: close laps strictly earlier in the stint
    g = sc.groupby(L.STINT_KEY, sort=False)
    sc["C"] = g["close_lap"].cumsum().to_numpy() - close.astype(int)
    for name, (lo, hi) in zip(TIER_NAMES, EPISODE_TIERS):
        inside = close & (sc["episode_len"].to_numpy() >= lo) & (
            True if hi is None else sc["episode_len"].to_numpy() <= hi)
        part = pd.Series(inside.astype(int)).groupby(key, sort=False).cumsum().to_numpy() - inside.astype(int)
        sc[name] = part
    # next episode start after l in the stint
    starts = sc.loc[new_ep, [L.STINT_KEY, "lap"]].rename(columns={"lap": "ep_start"})
    nxt = np.full(len(sc), np.nan)
    if len(starts):
        st = starts.groupby(L.STINT_KEY)["ep_start"].apply(lambda s: np.sort(s.to_numpy()))
        for i, (k, l_) in enumerate(zip(key, lapn)):
            arr = st.get(k)
            if arr is not None:
                j = np.searchsorted(arr, l_, side="right")
                if j < len(arr):
                    nxt[i] = arr[j]
    sc["laps_to_next_episode"] = nxt - lapn
    for j in PRE_TREND_LAPS:
        sc[f"pi_{j}"] = (sc["laps_to_next_episode"].to_numpy() == j).astype(float)
    nfree = sc.groupby(L.STINT_KEY)["free_lap"].transform("sum").to_numpy()
    sc["carry_fit"] = sc["free_lap"].to_numpy() & (nfree >= CARRY_MIN_FREE)
    return sc


@dataclass
class CarryFit:
    """Per-race sufficient statistics of the fixed-effect residuals, for the main and the tier model."""

    terms: dict  # model -> tuple of term names
    sxx: dict  # model -> N_RACES x k x k
    sxy: dict  # model -> N_RACES x k
    counts: dict
    sweeps: int


def fit_carry(sc: pd.DataFrame) -> CarryFit:
    """§9b: residualise LapTime and the regressors on alpha, phi and g (design_a.solve_fe, race blocks) over the
    free laps in the fit, then keep per-race cross-products."""
    f = sc[sc["carry_fit"]].reset_index(drop=True)
    if f.empty:
        raise A.EstimatorError("§9b: no free lap in a driver-stint with >= 3 free laps")
    free_all = sc["carry_fit"].to_numpy()
    lay = A.theta_layout(sc, free_all, race_key="race_id")
    lin, quad = A.theta_ids(lay, f["race_id"], f["compound"])
    a_codes, _ = pd.factorize(f[L.STINT_KEY])
    f_codes, _ = pd.factorize(pd.MultiIndex.from_frame(f[["race_id", "lap"]]))
    cols = ["lap_time_s", "C", *TIER_NAMES, *(f"pi_{j}" for j in PRE_TREND_LAPS)]
    Y = f[cols].to_numpy(dtype=float)
    sol = A.solve_fe(Y, a_codes, f_codes, lin, quad, f["t"].to_numpy(dtype=float), lay.n_params,
                     f["race_idx"].to_numpy())
    R = pd.DataFrame(sol.resid, columns=cols)
    ri = f["race_idx"].to_numpy()
    terms = {"main": MAIN_TERMS, "tier": TIER_TERMS}
    src = {"main": ["C", "pi_1", "pi_2", "pi_3"], "tier": [*TIER_NAMES, "pi_1", "pi_2", "pi_3"]}
    sxx, sxy = {}, {}
    y = R["lap_time_s"].to_numpy()
    for m, c in src.items():
        X = R[c].to_numpy()
        k = X.shape[1]
        xx = np.zeros((A.N_RACES, k, k))
        xy = np.zeros((A.N_RACES, k))
        np.add.at(xx, ri, X[:, :, None] * X[:, None, :])
        np.add.at(xy, ri, X * y[:, None])
        sxx[m], sxy[m] = xx, xy
    eps = sc.loc[sc["close_lap"], ["episode", "episode_len"]].drop_duplicates("episode")
    counts = {"scored_laps": int(len(sc)), "close_laps": int(sc["close_lap"].sum()),
              "episodes": int(len(eps)),
              **{f"episodes_{n[2:]}": int(((eps["episode_len"] >= lo) & (
                  True if hi is None else eps["episode_len"] <= hi)).sum())
                 for n, (lo, hi) in zip(TIER_NAMES, EPISODE_TIERS)},
              "free_laps_in_fit": int(len(f)), "stints_in_fit": int(f[L.STINT_KEY].nunique()),
              "free_laps_with_C_gt_0": int((f["C"] > 0).sum()),
              **{f"free_laps_pi_{j}": int(f[f"pi_{j}"].sum()) for j in PRE_TREND_LAPS},
              "races_in_fit": int(f["race_id"].nunique())}
    return CarryFit(terms=terms, sxx=sxx, sxy=sxy, counts=counts, sweeps=sol.sweeps)


def carry_coefficients(cf: CarryFit, w: np.ndarray | None = None) -> dict:
    """theta_carry, pi_1..pi_3 (main) and the tier thetas for one race weighting (point: all ones). A term with no
    residual variation is NaN ("—, not identified") and is left out of the solve."""
    w = np.ones(A.N_RACES) if w is None else np.asarray(w, dtype=float)
    out = {}
    for m, names in cf.terms.items():
        XX = np.tensordot(w, cf.sxx[m], axes=1)
        XY = w @ cf.sxy[m]
        ok = np.diag(XX) > SINGULAR_TOL
        beta = np.full(len(names), np.nan)
        if ok.any():
            sub = XX[np.ix_(ok, ok)]
            if np.linalg.matrix_rank(sub) == ok.sum():
                beta[ok] = np.linalg.solve(sub, XY[ok])
        for n, b in zip(names, beta):
            out[f"carry|{m}|{n}"] = float(b)
    return out


def carry_table(cf: CarryFit, plan: A.Plan) -> pd.DataFrame:
    """§13 item 5: point (full-sample fit), 95 % percentile interval over every draw of the plan, and counts."""
    pt = carry_coefficients(cf)
    draws = [carry_coefficients(cf, plan.weights[i]) for i in range(plan.weights.shape[0])]
    rows = []
    for key, v in pt.items():
        _, model, term = key.split("|")
        lo, hi = A.interval(draws, key) if np.isfinite(v) else (np.nan, np.nan)
        rows.append({"model": model, "term": term, "estimate_s": v, "lo95": lo, "hi95": hi,
                     "status": "ok" if np.isfinite(v) else "—, not identified", "draws": len(draws)})
    return pd.DataFrame(rows)
