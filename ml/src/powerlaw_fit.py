"""WI-17 shared power-law curve math: the beta grid, the two fit grains, the curve quantities.

The dbt models `int_stint_power_law_fit` and `int_cell_power_law_fit` are the fits of record
(the training targets). This module re-implements the same arithmetic in numpy so Step 0
(`powerlaw_ceiling.py`) can bootstrap it and `powerlaw.py` can grade held-out cells on the same
definitions. `ml/tests/test_powerlaw_export.py::test_cell_fit_matches_dbt` holds the two
implementations together.

Model, per unit (a stint, or a race x hardness-rank cell with one intercept per stint):

    y = c + alpha * age^beta          beta on BETA_GRID, (c, alpha) by OLS at each beta

The lap set is `int_power_law_lap` (slicks, the envelope mart's filters, tyre age 1-50) and y is
its `y_s` (the fuel-corrected lap time).

Two curve quantities are reported for every fit:

* ``delta(a) = alpha * a^beta``: seconds over the extrapolated age-0 pace, the WI's
  ``Δt(age)``. The age-0 level is never observed (the first clean lap on a tyre is age 2), so
  this carries the extrapolation below the data.
* ``incr(a) = alpha * (a^beta - FRESH_ANCHOR_AGE^beta)``: seconds over the fresh-tyre pace at
  ``FRESH_ANCHOR_AGE``. This is what the simulator draws: its fresh-tyre anchor
  (`ref_green_pace_s`) is the median of clean laps at tyre age <= 2, and those are almost all
  age 2 because the age-1 lap is the out-lap (6 of 139,855 lap-set laps are age 1).
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

# 0.20..3.00 in steps of 0.05, built from integers so the values are exact and match the
# dbt grid (`k / 20.0` for k in 4..60) bit for bit.
BETA_GRID: np.ndarray = np.arange(4, 61, dtype=np.float64) / 20.0
BETA_MIN, BETA_MAX = float(BETA_GRID[0]), float(BETA_GRID[-1])
LINEAR_INDEX = int(np.where(BETA_GRID == 1.0)[0][0])

# Ages the curve is graded at (WI-17 criterion 2) and the fresh-tyre anchor (see module doc).
EVAL_AGES: tuple[int, ...] = (5, 10, 15, 20)
FRESH_ANCHOR_AGE = 2

# Eligibility, as specced (per stint) and as probed (per cell).
STINT_MIN_LAPS, STINT_MIN_AGE_SPAN = 8, 7
CELL_STINT_MIN_LAPS = 5
CELL_MIN_STINTS, CELL_MIN_LAPS = 3, 40

LAP_QUERY = """
    SELECT lap_id, stint_id, race_id, race_year, driver_id, constructor_id, lap_number,
           lap_in_stint, age_in_stint AS age, compound_label, compound_code, hardness_era,
           compound_hardness_rank, circuit_id, y_s AS y
    FROM int_power_law_lap
"""


def load_laps(duckdb_path: str) -> pd.DataFrame:
    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        return con.execute(LAP_QUERY).df()
    finally:
        con.close()


def delta(alpha, beta, age):
    """alpha * age^beta: seconds over the extrapolated age-0 pace."""
    return np.asarray(alpha) * np.power(float(age), np.asarray(beta))


def incr(alpha, beta, age, anchor: int = FRESH_ANCHOR_AGE):
    """alpha * (age^beta - anchor^beta): seconds over the fresh-tyre pace at `anchor`."""
    b = np.asarray(beta)
    return np.asarray(alpha) * (np.power(float(age), b) - np.power(float(anchor), b))


def curve_quantities(alpha, beta) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {"alpha": np.asarray(alpha, float), "beta": np.asarray(beta, float)}
    for a in EVAL_AGES:
        out[f"delta_{a}"] = delta(alpha, beta, a)
        out[f"incr_{a}"] = incr(alpha, beta, a)
    return out


# ─── Per-stint fit: y = c + alpha * age^beta, profiled over the grid ──────────────────────────
@dataclass
class StintFit:
    c: float
    alpha: float
    beta: float
    r2: float
    r2_linear: float


def _stint_sums(age: np.ndarray, Y: np.ndarray):
    """Centred cross-products for every grid beta. Y may be (n,) or (n, reps)."""
    X = np.power(age[:, None], BETA_GRID[None, :])            # (n, G)
    xm = X.mean(axis=0)
    Xc = X - xm
    Y2 = Y if Y.ndim == 2 else Y[:, None]
    ym = Y2.mean(axis=0)
    Yc = Y2 - ym
    sxx = (Xc ** 2).sum(axis=0)                                # (G,)
    sxy = Xc.T @ Yc                                            # (G, R)
    syy = (Yc ** 2).sum(axis=0)                                # (R,)
    return xm, ym, sxx, sxy, syy


def fit_stint(age: np.ndarray, y: np.ndarray) -> StintFit | None:
    age = np.asarray(age, float)
    y = np.asarray(y, float)
    xm, ym, sxx, sxy, syy = _stint_sums(age, y)
    if syy[0] <= 0 or np.any(sxx <= 0):
        return None
    r2 = (sxy[:, 0] ** 2) / (sxx * syy[0])
    j = int(np.argmax(r2))                                     # first max -> smallest beta on ties
    alpha = sxy[j, 0] / sxx[j]
    return StintFit(c=float(ym[0] - alpha * xm[j]), alpha=float(alpha), beta=float(BETA_GRID[j]),
                    r2=float(r2[j]), r2_linear=float(r2[LINEAR_INDEX]))


def fit_stint_many(age: np.ndarray, Y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised over replicate columns of Y: returns (alpha[R], beta[R])."""
    xm, ym, sxx, sxy, syy = _stint_sums(np.asarray(age, float), np.asarray(Y, float))
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = (sxy ** 2) / (sxx[:, None] * syy[None, :])
    j = np.nanargmax(np.nan_to_num(r2, nan=-1.0), axis=0)
    cols = np.arange(sxy.shape[1])
    return sxy[j, cols] / sxx[j], BETA_GRID[j]


# ─── Pooled cell fit: stint intercepts + a shared (alpha, beta) ─────────────────────────────
@dataclass
class CellSums:
    """Per-stint within-stint sums for every grid beta; a cell fit is a weighted sum of these,
    so a stint-cluster bootstrap is just a reweighting."""
    sxx: np.ndarray   # (S, G)
    sxy: np.ndarray   # (S, G)
    syy: np.ndarray   # (S,)
    n: np.ndarray     # (S,)


def cell_sums(parts: list[tuple[np.ndarray, np.ndarray]]) -> CellSums:
    sxx, sxy, syy, n = [], [], [], []
    for age, y in parts:
        X = np.power(np.asarray(age, float)[:, None], BETA_GRID[None, :])
        Xc = X - X.mean(axis=0)
        yc = np.asarray(y, float) - np.mean(y)
        sxx.append((Xc ** 2).sum(axis=0))
        sxy.append(Xc.T @ yc)
        syy.append(float((yc ** 2).sum()))
        n.append(len(y))
    return CellSums(np.array(sxx), np.array(sxy), np.array(syy), np.array(n))


def fit_cell_from_sums(s: CellSums, w: np.ndarray | None = None) -> tuple[float, float, float]:
    """(alpha, beta, r2_within) for stint weights w (bootstrap counts; default all 1)."""
    w = np.ones(len(s.syy)) if w is None else w
    SXX = w @ s.sxx
    SXY = w @ s.sxy
    SYY = float(w @ s.syy)
    with np.errstate(divide="ignore", invalid="ignore"):
        sse = SYY - np.where(SXX > 0, SXY ** 2 / SXX, np.nan)
    j = int(np.nanargmin(sse))
    alpha = SXY[j] / SXX[j]
    r2 = 1.0 - sse[j] / SYY if SYY > 0 else np.nan
    return float(alpha), float(BETA_GRID[j]), float(r2)


def cell_parts(g: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    """The qualifying stints of one cell: >= CELL_STINT_MIN_LAPS laps and >= 2 distinct ages."""
    parts = []
    for _, s in g.groupby("stint_id", sort=True):
        if len(s) >= CELL_STINT_MIN_LAPS and s["age"].nunique() >= 2:
            parts.append((s["age"].to_numpy(float), s["y"].to_numpy(float)))
    return parts


def cell_eligible(parts) -> bool:
    return len(parts) >= CELL_MIN_STINTS and sum(len(p[1]) for p in parts) >= CELL_MIN_LAPS


def reliability(est: np.ndarray, boot_var: np.ndarray, trim: float = 0.05) -> float:
    """1 - mean(bootstrap sampling variance) / cross-unit variance of the estimates.

    The best R^2 any feature set could reach against these noisy targets. Units in the outer
    `trim` tails of the estimate distribution are dropped first (alpha is heavy-tailed when beta
    sits at the grid floor), matching the pre-flight probe. The cut is inclusive, so a quantity
    piled on the grid edges (beta) keeps its edge mass rather than losing it to the trim."""
    est = np.asarray(est, float)
    boot_var = np.asarray(boot_var, float)
    ok = np.isfinite(est) & np.isfinite(boot_var)
    est, boot_var = est[ok], boot_var[ok]
    if trim > 0 and len(est) > 20:
        lo, hi = np.quantile(est, [trim, 1 - trim])
        keep = (est >= lo) & (est <= hi)
        est, boot_var = est[keep], boot_var[keep]
    v = est.var()
    return float(1.0 - boot_var.mean() / v) if v > 0 else float("nan")
