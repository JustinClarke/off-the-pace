"""
WC-10e design A (discovery, 2022-23): the free-air imputation estimator, the cross-fitted pass class, the bracketed
companion, switches S1-S3, the bootstrap and the go/no-go line. The lap arm and F1 are in lap_arm.py.

Rules come from the signed discovery registration, wi/WC-10-discovery-preregistration-DRAFT.md (commit 6fd0330,
SHA-256 4d679bf6..., DD-WC20). Section numbers (§) point into it. Every constant below is copied from it.

THIS HAS NOT BEEN RUN ON REAL DATA. It is a library of functions on DataFrames: it opens no file (wc10_io.py
loads, under the seal and the ledger) and writes nothing.

Open choices. The registration left five choices open; the owner ruled all five (see OPEN_CHOICES, which records
the ruled values). The code implements only the ruled behaviour. `preflight()` refuses (OpenChoicesUnset) while
any value is None or differs from the ruling, and wc10_io.Ledger.run_start calls it, so RUN START cannot be
written with an open choice.

How the bootstrap is computed (§10). Every quantity of the chain except gamma_k (the car-behind coefficient,
pooled per corner class) is race-internal: alpha groups, phi cells, theta cells, the phi windows, trims, the
bracket, the pass class (via alpha-bar, which averages within a race) all live inside one race. A circuit drawn
twice enters as two separate copies, so its races' fits are identical copies; a race drawn twice within one copy
is, by ruling 5, also a separate copy (its groups, cells and classes are copies, and sigma's degrees of freedom
count its parameters once per entry). The whole-chain refit of a draw is therefore exactly: gamma_k by
race-weighted Frisch-Waugh-Lovell from per-race sufficient statistics, every coefficient as (y-part - gamma_k
x-part), sigma_k with the §6b degrees of freedom of the drawn data (n, RSS and parameters all weighted by
multiplicity), then every trim, class and average recomputed with race weights. This is an algebraic identity
with refitting the replicated data (up to the convergence tolerance), not an approximation; tests check it
against a literal refit on synthetic data with circuit copies and duplicate races.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from tasks.wake_calibration import estimator as E
from tasks.wake_calibration import wc10_io as IO

# --------------------------------------------------------------------------- fixed numbers (§0b)

CLASSES = ("fast", "medium", "slow")  # print order
BRAKING_BASIS = E.BRAKING_BASIS
GAP_EDGES = E.GAP_EDGES  # the registered 8 bins, [lower, upper)
N_BINS = E.N_BINS
NEAR_BINS = (2, 3)  # 0.5-0.75, 0.75-1.0
FAR_BINS = (6, 7)  # 2.0-2.5, 2.5-3.0
FREE_GAP_S = 3.0  # §5 free: clear_ahead or gap_s >= 3.0
CLOSE_GAP_S = 1.0  # §5 close
MIN_FREE_SUPPORT = 2  # §6a
PHI_MIN_DRIVERS = 3  # §6c
PHI_WINDOWS = (0, 1, 2)  # §6c
THIN_MIN_DRIVERS = 3  # §6d
TRIM_FREE = {"seg_time_s": 2.0, "min_speed_kph": 40.0, "exit_speed_kph": 40.0}  # §6f (i)
TRIM_EFFECT = {"seg_time_s": 2.0, "min_speed_kph": 40.0, "exit_speed_kph": 40.0}  # §6f (ii)
SIGN = {"seg_time_s": 1.0, "min_speed_kph": -1.0, "exit_speed_kph": -1.0}  # §6e: positive = loss
OUTCOMES = ("seg_time_s", "min_speed_kph", "exit_speed_kph")
TIME, MINSPEED = "seg_time_s", "min_speed_kph"
HELD_UP_SE_MULT = 2.0  # §6h
BRACKET_LAPS = 5  # §8a
GAP_CHANGE_S = 0.10  # §8d
TIER_EDGES = (0.20, 0.50, 0.80)  # §8b
CONV_TOL = 1e-10  # §6b
MAX_SWEEPS = 10_000  # §6b

S2_TOL_FRAC = 0.25  # §11 S2
S2_PACE_FLOOR = 0.020
S2_AERO_FLOOR = 0.75
S2_AGREE_MIN = 500
S2_DISAGREE_MIN = 100
S2_CELL_MIN_ONE_SIDED = 20
S3_TOL_FRAC = 0.25  # §11 S3
S3_FLOOR = 0.010
S3_MIN_FREE = 3
S3_MIN_SPAN = 8

N_BOOT = 1000  # §10
SEED = 20261029
CI95 = (2.5, 97.5)
CI90 = (5.0, 95.0)
CI80 = (10.0, 90.0)

HELD_UP, DIRTY_AIR, UNKNOWN, RACECRAFT = "held_up", "dirty_air", "unknown", "racecraft"
AGREE, DISAGREE, INCONCLUSIVE = "AGREE", "DISAGREE", "INCONCLUSIVE"
GAP_CHANGES = ("shrinking", "arrived_from_free", "steady", "growing", "unknown")  # §11 S2 cells
S2_TIERS = ("<0.20", "0.20-0.50", ">=0.50")

# Appendix A: the fixed bootstrap lists (circuits bytewise on the NFC key; races bytewise on race_id).
APPENDIX_A = {
    "Austin": ("2022_19", "2023_18"), "Baku": ("2022_8", "2023_4"), "Barcelona": ("2022_6", "2023_7"),
    "Budapest": ("2022_13", "2023_11"), "Imola": ("2022_4",), "Jeddah": ("2022_2", "2023_2"),
    "Las Vegas": ("2023_21",), "Le Castellet": ("2022_12",), "Lusail": ("2023_17",),
    "Marina Bay": ("2022_17", "2023_15"), "Melbourne": ("2022_3", "2023_3"), "Mexico City": ("2022_20", "2023_19"),
    "Miami": ("2022_5", "2023_5"), "Monaco": ("2022_7", "2023_6"), "Montréal": ("2022_9", "2023_8"),
    "Monza": ("2022_16", "2023_14"), "Sakhir": ("2022_1", "2023_1"), "Silverstone": ("2022_10", "2023_10"),
    "Spa-Francorchamps": ("2022_14", "2023_12"), "Spielberg": ("2022_11", "2023_9"), "Suzuka": ("2023_16",),
    "São Paulo": ("2022_21", "2023_20"), "Yas Island": ("2022_22", "2023_22"), "Zandvoort": ("2022_15", "2023_13"),
}
CIRCUITS = sorted((unicodedata.normalize("NFC", c) for c in APPENDIX_A), key=lambda c: c.encode())
RACES = [r for c in CIRCUITS for r in sorted(APPENDIX_A[c], key=lambda r: r.encode())]  # global race order
RACE_INDEX = {r: i for i, r in enumerate(RACES)}
N_RACES = len(RACES)

# Open choices left by the registration, as ruled by the owner (pre-result). The code implements only these values;
# preflight() refuses RUN START while any value is None or differs from RULED_CHOICES.
RULED_CHOICES: dict[str, str] = {
    # Ruling 1. §5 says racecraft is "out of every fit"; §6a/§6b define step 1 on free passes without naming
    # racecraft. A free pass (gap >= 3 or clear ahead) can still be flagged racecraft by the C5 leader-change rule.
    # "drop": racecraft free passes leave step 1 (and so support, bracket, phi counts), and are counted.
    "racecraft_free_passes": "drop",
    # Ruling 2. §6h: alpha-bar[r, m, c'] at another corner c' of the class has no group left after excluding both
    # stints. "skip_corner": that c' contributes neither to o nor to N (counted); if too few corners remain, the
    # existing N_F < 2 / N_L < 2 rule makes the pass unknown.
    "alpha_bar_empty_other_corner": "skip_corner",
    # Ruling 3. A prediction whose alpha group (driver level) and phi cell(s) (field effect) lie in different
    # connected components of the alpha-phi graph is not identified. "drop": dropped and counted (lap arm too).
    "disconnected_prediction": "drop",
    # Ruling 4. §10 percentile intervals when a draw leaves a statistic undefined (an empty bin or cell in that
    # draw). "propagate": the interval is undefined; no draw is skipped or redrawn; the go/no-go line prints the
    # number of undefined draws; an undefined S2 interval is INCONCLUSIVE.
    "undefined_draws": "propagate",
    # Ruling 5. §10 "A race drawn twice within one copy counts twice." "separate_copy": like a circuit copy, the
    # race enters as a separate copy; sigma's degrees of freedom count its parameters once per entry.
    "duplicate_race_in_copy": "separate_copy",
}
OPEN_CHOICES: dict[str, str | None] = dict(RULED_CHOICES)


class EstimatorError(ValueError):
    """A registered rule cannot be applied to the data given (never silently patched)."""


class OpenChoicesUnset(EstimatorError):
    """Preflight: an open choice is None or differs from the owner's ruling, so RUN START is refused."""


def preflight(choices: dict | None = None) -> None:
    """Refuse RUN START while any open choice is None (or not the ruled value, the only one implemented)."""
    choices = OPEN_CHOICES if choices is None else choices
    unset = sorted(k for k in RULED_CHOICES if choices.get(k) is None)
    if unset:
        raise OpenChoicesUnset(f"RUN START refused: open choice(s) not set: {unset}")
    other = sorted(k for k in RULED_CHOICES if choices[k] != RULED_CHOICES[k])
    if other:
        raise OpenChoicesUnset(f"RUN START refused: open choice(s) differ from the owner's ruling: {other}")


# --------------------------------------------------------------------------- pass sets (§5, §8b, §8d)


def prepare(structure: pd.DataFrame) -> pd.DataFrame:
    """Structure columns (wc10_io.load_structure) plus the §5 pass sets and the fixed per-pass labels. No outcome
    column is used. Racecraft is computed on all rows, as WC-03 prepare_passes did (§5)."""
    p = structure.reset_index(drop=True).copy()
    IO.check_season_column(p, "structure frame")
    p["row"] = np.arange(len(p))
    p["racecraft"] = E.racecraft(p).to_numpy(dtype=bool)
    gap = p["gap_s"].to_numpy(dtype=float)
    yielding = E.is_yielding(p["tag"]).to_numpy()
    elig = ((p["segment_basis"] == BRAKING_BASIS).to_numpy() & p["reason"].isna().to_numpy() & ~yielding
            & p["stint"].notna().to_numpy() & p["compound"].notna().to_numpy())
    clear = p["clear_ahead"].fillna(False).astype(bool).to_numpy()
    with np.errstate(invalid="ignore"):
        free = elig & (clear | (gap >= FREE_GAP_S))
        following = elig & ~free & (gap >= 0) & (gap < FREE_GAP_S)
    p["eligible"], p["free"], p["following"] = elig, free, following
    p["close"] = following & (gap < CLOSE_GAP_S)
    p["bin"] = np.where(following, E.gap_bin(gap), -1)
    p["lap"] = p["lap"].astype(int)
    p["stint_key"] = (p["race_id"].astype(str) + "|" + p["driver"].astype(str) + "|"
                      + p["stint"].astype(str) + "|" + p["compound"].astype(str))
    p["group"] = p["stint_key"] + "|" + p["corner_id"].astype(str)
    p["behind"] = p["behind_1s"].fillna(False).astype(bool).astype(float)
    p["t"] = p["tyre_life"].astype(float)
    # §8b: stint close share over eligible braking passes, racecraft included; a negative gap is not close.
    share = p.loc[elig].groupby("stint_key")["close"].mean()
    s = p["stint_key"].map(share).to_numpy(dtype=float)
    p["close_share"] = s
    p["tier"] = np.select([s < TIER_EDGES[0], s < TIER_EDGES[1], s < TIER_EDGES[2], s >= TIER_EDGES[2]],
                          ["<0.20", "0.20-0.50", "0.50-0.80", ">=0.80"], default="")
    p["s2_tier"] = np.select([s < TIER_EDGES[0], s < TIER_EDGES[1], s >= TIER_EDGES[1]], list(S2_TIERS), default="")
    p["extrapolated"] = s >= TIER_EDGES[2]
    p["gap_change"] = gap_change(p)
    # race index into Appendix A; every eligible row must sit in a listed race (§10)
    p["race_idx"] = p["race_id"].map(RACE_INDEX).fillna(-1).astype(int)
    bad = sorted(set(p.loc[elig & (p["race_idx"].to_numpy() < 0), "race_id"]))
    if bad:
        raise EstimatorError(f"eligible pass(es) in race(s) outside Appendix A: {bad[:5]}")
    return p


def gap_change(p: pd.DataFrame) -> np.ndarray:
    """§8d / §11 S2 cells: unknown (previous pass missing or excluded), arrived_from_free (previous lap free),
    shrinking (< -0.10 s), growing (> +0.10 s), steady. Checked in that order, as the registered count script d05
    (counts_d/scripts/d05_review2_counts.py) did. For §8d's X3, arrived_from_free counts as shrinking."""
    prev = p["prev_lap_gap_s"].to_numpy(dtype=float)
    pclear = p["prev_lap_clear_ahead"].astype("boolean").fillna(False).to_numpy(dtype=bool)
    with np.errstate(invalid="ignore"):
        pfree = pclear | (prev >= FREE_GAP_S)
        d = p["gap_s"].to_numpy(dtype=float) - prev
        unknown = p["prev_lap_reason"].notna().to_numpy() | (np.isnan(prev) & ~pfree)
        return np.select([unknown, pfree, d < -GAP_CHANGE_S, d > GAP_CHANGE_S],
                         ["unknown", "arrived_from_free", "shrinking", "growing"], default="steady")


def free_set(p: pd.DataFrame, y: pd.Series, outcome: str) -> np.ndarray:
    """Free passes entering step 1 for one outcome: free, outcome not null, trim (i) against the group's
    free-pass median (§6f), racecraft free passes dropped (ruling 1; counted by racecraft_free_dropped)."""
    yv = y.to_numpy(dtype=float)
    base = p["free"].to_numpy() & np.isfinite(yv) & ~p["racecraft"].to_numpy(dtype=bool)
    med = pd.Series(yv[base]).groupby(p["group"].to_numpy()[base]).median()
    m = p["group"].map(med).to_numpy(dtype=float)
    with np.errstate(invalid="ignore"):
        return base & (np.abs(yv - m) <= TRIM_FREE[outcome])


def racecraft_free_dropped(p: pd.DataFrame, y: pd.Series) -> int:
    """Ruling 1 count: free passes with the outcome present that are racecraft, so left out of step 1."""
    return int((p["free"].to_numpy() & np.isfinite(y.to_numpy(dtype=float))
                & p["racecraft"].to_numpy(dtype=bool)).sum())


# --------------------------------------------------------------------------- the fixed structure sets (§6a)


@dataclass
class Structure:
    """Support, bracket, phi windows, the theta layout (reference compound, thin cells): fixed once from the
    seg_time_s free-pass trim and reused for every outcome (§6a)."""

    free_time: np.ndarray  # bool per row
    n_free_group: np.ndarray  # free passes in the row's group (time set)
    supported: np.ndarray  # following and group >= 2 free
    W: np.ndarray  # phi window per following row (-1 = phi-unsupported, -2 = not a following row)
    lap_b: np.ndarray  # nearest earlier free lap within 5 (NaN if none)
    lap_a: np.ndarray  # nearest later free lap within 5
    bracketed: np.ndarray
    theta: dict  # class -> ThetaLayout
    free_rows_time: pd.DataFrame  # (race_id, corner_id, lap, driver) of time-set free passes


@dataclass
class ThetaLayout:
    """§6d per class: (race_id, compound) -> (lin id or -1, quad id); default per race = the reference curve."""

    table: pd.DataFrame
    default_quad: dict
    n_params: int


def phi_window_counts(free_rows: pd.DataFrame, queries: pd.DataFrame, keys: list[str]) -> np.ndarray:
    """§6c: W = 0, 1 or 2, the smallest window whose free passes come from >= 3 distinct drivers other than the
    query's driver; -1 if none. `keys` are the cell keys without lap (e.g. race_id, corner_id)."""
    fd = free_rows[keys + ["lap", "driver"]].drop_duplicates()
    out = np.full(len(queries), -1, dtype=int)
    q = queries[keys + ["lap", "driver"]].reset_index(drop=True).assign(_q=np.arange(len(queries)))
    for w in sorted(PHI_WINDOWS, reverse=True):
        ex = pd.concat([fd.assign(lap=fd["lap"] + d) for d in range(-w, w + 1)]).drop_duplicates()
        n_all = ex.groupby(keys + ["lap"]).size().rename("n_all").reset_index()
        m = q.merge(n_all, on=keys + ["lap"], how="left")
        own = q.merge(ex.assign(_own=1), on=keys + ["lap", "driver"], how="left")
        n = m.sort_values("_q")["n_all"].fillna(0).to_numpy() - own.sort_values("_q")["_own"].fillna(0).to_numpy()
        out = np.where(n >= PHI_MIN_DRIVERS, w, out)
    return out


def _nearest_free_laps(group_codes: np.ndarray, laps: np.ndarray, free_codes: np.ndarray, free_laps: np.ndarray,
                       window: int) -> tuple[np.ndarray, np.ndarray]:
    """Nearest free lap strictly before (>= lap - window) and strictly after (<= lap + window) in the same group."""
    enc = np.unique(free_codes.astype(np.int64) * 100_000 + free_laps.astype(np.int64))
    q = group_codes.astype(np.int64) * 100_000 + laps.astype(np.int64)
    i0 = np.searchsorted(enc, q, "left") - 1
    i1 = np.searchsorted(enc, q, "right")
    e0 = enc[np.clip(i0, 0, max(len(enc) - 1, 0))] if len(enc) else np.zeros_like(q)
    e1 = enc[np.clip(i1, 0, max(len(enc) - 1, 0))] if len(enc) else np.zeros_like(q)
    ok0 = (i0 >= 0) & (e0 // 100_000 == group_codes) & (laps - e0 % 100_000 <= window)
    ok1 = (i1 < len(enc)) & (e1 // 100_000 == group_codes) & (e1 % 100_000 - laps <= window)
    return np.where(ok0, e0 % 100_000, np.nan), np.where(ok1, e1 % 100_000, np.nan)


def theta_layout(p: pd.DataFrame, free: np.ndarray, race_key: str = "race_id", class_mask=None) -> ThetaLayout:
    """§6d: per race (within one corner class), the compound with the most free passes is the reference (ties to
    the compound name first bytewise), its linear term fixed at 0. A compound with free passes from < 3 drivers
    takes the reference curve; if the reference itself has < 3 drivers, every compound shares one curve."""
    m = free if class_mask is None else free & class_mask
    f = p.loc[m, [race_key, "compound", "driver"]]
    cells = f.groupby([race_key, "compound"]).agg(n=("driver", "size"), nd=("driver", "nunique")).reset_index()
    rows, default, nid = [], {}, 0
    for race, g in cells.groupby(race_key, sort=True):
        g = g.assign(_b=g["compound"].map(lambda s: str(s).encode()))
        g = g.sort_values(["n", "_b"], ascending=[False, True])
        ref = g.iloc[0]
        q_ref = nid
        nid += 1
        default[race] = q_ref
        ref_thin = ref["nd"] < THIN_MIN_DRIVERS
        for comp, nd in zip(g["compound"], g["nd"]):
            if ref_thin or comp == ref["compound"] or nd < THIN_MIN_DRIVERS:
                rows.append((race, comp, -1, q_ref))
            else:
                rows.append((race, comp, nid, nid + 1))  # lin id, quad id
                nid += 2
    table = pd.DataFrame(rows, columns=[race_key, "compound", "lin", "quad"])
    return ThetaLayout(table=table, default_quad=default, n_params=nid)


def theta_ids(layout: ThetaLayout, races: pd.Series, compounds: pd.Series, race_key: str = "race_id"
              ) -> tuple[np.ndarray, np.ndarray]:
    """(lin id or -1, quad id or -1) per row; a compound not in the table takes the race's reference curve."""
    q = pd.DataFrame({race_key: races.to_numpy(), "compound": compounds.to_numpy()})
    m = q.merge(layout.table, on=[race_key, "compound"], how="left")
    dq = q[race_key].map(layout.default_quad)
    lin = m["lin"].fillna(-1).to_numpy(dtype=int)
    quad = m["quad"].fillna(dq).fillna(-1).to_numpy(dtype=int)
    return lin, quad


def structure_sets(p: pd.DataFrame, y_time: pd.Series) -> Structure:
    """§6a, §6c, §6d, §8a from the seg_time_s free-pass trim."""
    ft = free_set(p, y_time, TIME)
    gcode = pd.factorize(p["group"])[0]
    nfg = np.bincount(gcode, weights=ft.astype(float), minlength=gcode.max() + 1)[gcode]
    fol = p["following"].to_numpy()
    supported = fol & (nfg >= MIN_FREE_SUPPORT)
    free_rows = p.loc[ft, ["race_id", "corner_id", "lap", "driver"]]
    W = np.full(len(p), -2, dtype=int)
    W[fol] = phi_window_counts(free_rows, p.loc[fol, ["race_id", "corner_id", "lap", "driver"]],
                               ["race_id", "corner_id"])
    lap = p["lap"].to_numpy()
    lb, la = _nearest_free_laps(gcode, lap, gcode[ft], lap[ft], BRACKET_LAPS)
    bracketed = supported & np.isfinite(lb) & np.isfinite(la)
    theta = {k: theta_layout(p, ft, class_mask=(p["corner_class"] == k).to_numpy()) for k in CLASSES}
    return Structure(free_time=ft, n_free_group=nfg, supported=supported, W=W, lap_b=lb, lap_a=la,
                     bracketed=bracketed, theta=theta, free_rows_time=free_rows)


# --------------------------------------------------------------------------- the fixed-effects solver (§6b)


@dataclass
class FESolution:
    alpha: np.ndarray  # n_alpha x ncol
    phi: np.ndarray  # n_phi x ncol
    theta: np.ndarray  # n_theta x ncol
    resid: np.ndarray  # n x ncol
    sweeps: int
    comp_alpha: np.ndarray  # component label per alpha level
    comp_phi: np.ndarray
    n_components: int


def ap_demean(V: np.ndarray, a: np.ndarray, f: np.ndarray, tol: float = CONV_TOL, max_sweeps: int = MAX_SWEEPS
              ) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Alternating projections of the columns of V on indicators of a and f (codes 0..n-1). Returns (residual,
    alpha coefficients, phi coefficients, sweeps). Converged when the largest absolute change of any coefficient
    in one sweep is below `tol` (§6b); failure in `max_sweeps` is a run error."""
    r = np.array(V, dtype=float, copy=True)
    na, nf = int(a.max()) + 1, int(f.max()) + 1
    ca, cf = np.bincount(a, minlength=na).astype(float), np.bincount(f, minlength=nf).astype(float)
    alpha, phi = np.zeros((na, r.shape[1])), np.zeros((nf, r.shape[1]))
    for sweep in range(1, max_sweeps + 1):
        da = np.stack([np.bincount(a, weights=r[:, j], minlength=na) for j in range(r.shape[1])], 1) / ca[:, None]
        alpha += da
        r -= da[a]
        df = np.stack([np.bincount(f, weights=r[:, j], minlength=nf) for j in range(r.shape[1])], 1) / cf[:, None]
        phi += df
        r -= df[f]
        if max(float(np.abs(da).max(initial=0.0)), float(np.abs(df).max(initial=0.0))) < tol:
            return r, alpha, phi, sweep
    raise EstimatorError(f"step 1 did not converge in {max_sweeps} sweeps (§6b: run error)")


def solve_fe(Y: np.ndarray, a: np.ndarray, f: np.ndarray, lin: np.ndarray, quad: np.ndarray, t: np.ndarray,
             n_theta: int, block: np.ndarray, tol: float = CONV_TOL, max_sweeps: int = MAX_SWEEPS) -> FESolution:
    """Least squares of each column of Y on alpha[a] + phi[f] + theta[lin]*t + theta[quad]*t^2, unweighted, with
    alpha and phi absorbed by alternating projections (§6b): every column (Y and each tyre-trend regressor) is
    demeaned on alpha and phi; theta is OLS on the demeaned columns; alpha and phi are then recovered by
    alternating projections on Y - Z theta. Exact for each column separately, so a later Frisch-Waugh-Lovell step
    on the residualised columns gives the joint fit. alpha, phi and theta cells never cross a `block` (race), so
    the work is done block by block. `quad` must be >= 0 for every row; `lin` is -1 where there is no linear term.
    A singular tyre-term block takes the minimum-norm (pseudo-inverse) solution."""
    Y = np.asarray(Y, dtype=float)
    if Y.ndim == 1:
        Y = Y[:, None]
    n, ncol = Y.shape
    if (quad < 0).any():
        raise EstimatorError("a step-1 row has no tyre-trend cell")
    na, nf = int(a.max()) + 1, int(f.max()) + 1
    alpha, phi, theta = np.zeros((na, ncol)), np.zeros((nf, ncol)), np.zeros((n_theta, ncol))
    resid = np.zeros((n, ncol))
    sweeps = 0
    for b in np.unique(block):
        idx = np.flatnonzero(block == b)
        la, a_uni = pd.factorize(a[idx])
        lf, f_uni = pd.factorize(f[idx])
        ids = np.unique(np.concatenate([quad[idx], lin[idx][lin[idx] >= 0]]))
        Z = np.zeros((len(idx), len(ids)))
        pos = {int(p): j for j, p in enumerate(ids)}
        tt = t[idx]
        Z[np.arange(len(idx)), [pos[int(q)] for q in quad[idx]]] = tt * tt
        has = lin[idx] >= 0
        Z[np.flatnonzero(has), [pos[int(q)] for q in lin[idx][has]]] = tt[has]
        D, _, _, s1 = ap_demean(np.column_stack([Y[idx], Z]), la, lf, tol, max_sweeps)
        Yd, Zd = D[:, :ncol], D[:, ncol:]
        th = np.linalg.pinv(Zd) @ Yd  # len(ids) x ncol
        theta[ids] = th
        E_, al, ph, s2 = ap_demean(Y[idx] - Z @ th, la, lf, tol, max_sweeps)
        alpha[a_uni] = al
        phi[f_uni] = ph
        resid[idx] = E_
        sweeps = max(sweeps, s1, s2)
    g = coo_matrix((np.ones(n), (a, f + na)), shape=(na + nf, na + nf))
    ncomp, labels = connected_components(g, directed=False)
    return FESolution(alpha=alpha, phi=phi, theta=theta, resid=resid, sweeps=sweeps,
                      comp_alpha=labels[:na], comp_phi=labels[na:], n_components=int(ncomp))


# --------------------------------------------------------------------------- step 1 per class and outcome


@dataclass
class Step1:
    """Step 1 of one corner class and one outcome. Coefficients are kept as y-part and x-part (x = behind_1s,
    Frisch-Waugh-Lovell), so coefficient(gamma) = y-part - gamma * x-part for any race weighting."""

    outcome: str
    k: str
    rows: np.ndarray  # prep rows of the free passes in the fit
    race_idx: np.ndarray
    alpha: pd.DataFrame  # index group -> y, x, n, comp
    phi: pd.DataFrame  # (race_id, corner_id, lap) -> y, x, n, comp
    theta: np.ndarray  # n_theta x 2 (y, x)
    layout: ThetaLayout
    ry: np.ndarray  # FE-residualised outcome per free row
    rx: np.ndarray  # FE-residualised behind_1s per free row
    n_r: np.ndarray  # per race (Appendix A order)
    syy: np.ndarray
    sxy: np.ndarray
    sxx: np.ndarray
    p_r: np.ndarray  # §6b parameters per race: alpha + phi + estimated theta - components
    sweeps: int

    def gamma(self, w: np.ndarray | None = None) -> float:
        w = np.ones(N_RACES) if w is None else w
        den = float(w @ self.sxx)
        if den <= 0:
            raise EstimatorError(f"{self.k} {self.outcome}: no behind_1s variation after the fixed effects")
        return float(w @ self.sxy) / den

    def sigma(self, w: np.ndarray | None = None, gamma: float | None = None) -> float:
        """§6b: sqrt(RSS / (n - p)); in a draw n, RSS and p all count every entry (every entry of a race is a
        separate copy: circuit copies by §10, a race drawn twice within one copy by ruling 5); gamma counts once."""
        w = np.ones(N_RACES) if w is None else w
        g = self.gamma(w) if gamma is None else gamma
        rss = float(w @ (self.syy - 2 * g * self.sxy + g * g * self.sxx))
        dof = float(w @ self.n_r) - (float(w @ self.p_r) + 1.0)
        if dof <= 0:
            raise EstimatorError(f"{self.k} {self.outcome}: no residual degrees of freedom")
        return float(np.sqrt(rss / dof))


def fit_step1(p: pd.DataFrame, y: pd.Series, outcome: str, k: str, st: Structure, free: np.ndarray) -> Step1:
    """§6b on the free passes of class k in `free` (free_set of this outcome)."""
    m = free & (p["corner_class"] == k).to_numpy()
    f = p.loc[m]
    lay = st.theta[k]
    lin, quad = theta_ids(lay, f["race_id"], f["compound"])
    a_codes, a_uni = pd.factorize(f["group"])
    cell = pd.MultiIndex.from_frame(f[["race_id", "corner_id", "lap"]])
    f_codes, f_uni = pd.factorize(cell)
    yv = y.to_numpy(dtype=float)[m]
    xv = f["behind"].to_numpy(dtype=float)
    sol = solve_fe(np.column_stack([yv, xv]), a_codes, f_codes, lin, quad, f["t"].to_numpy(dtype=float),
                   lay.n_params, f["race_idx"].to_numpy())
    ry, rx = sol.resid[:, 0], sol.resid[:, 1]
    ri = f["race_idx"].to_numpy()
    n_r = np.bincount(ri, minlength=N_RACES).astype(float)
    syy = np.bincount(ri, weights=ry * ry, minlength=N_RACES)
    sxy = np.bincount(ri, weights=rx * ry, minlength=N_RACES)
    sxx = np.bincount(ri, weights=rx * rx, minlength=N_RACES)
    # §6b parameters per race: alpha levels + phi cells + estimated theta terms - connected components
    a_race = pd.Series(ri).groupby(a_codes).first().to_numpy()
    f_race = pd.Series(ri).groupby(f_codes).first().to_numpy()
    th = pd.DataFrame({"r": np.concatenate([ri, ri[lin >= 0]]), "id": np.concatenate([quad, lin[lin >= 0]])})
    th_r = th.drop_duplicates()["r"].to_numpy()
    comp_r = pd.Series(np.concatenate([a_race, f_race]))
    comp_l = np.concatenate([sol.comp_alpha, sol.comp_phi])
    ncomp_r = pd.DataFrame({"r": comp_r, "c": comp_l}).drop_duplicates()["r"].to_numpy()
    p_r = (np.bincount(a_race, minlength=N_RACES) + np.bincount(f_race, minlength=N_RACES)
           + np.bincount(th_r, minlength=N_RACES) - np.bincount(ncomp_r, minlength=N_RACES)).astype(float)
    alpha = pd.DataFrame({"y": sol.alpha[:, 0], "x": sol.alpha[:, 1], "n": np.bincount(a_codes),
                          "comp": sol.comp_alpha}, index=pd.Index(a_uni, name="group"))
    phi = pd.DataFrame(list(f_uni), columns=["race_id", "corner_id", "lap"])
    phi = phi.assign(y=sol.phi[:, 0], x=sol.phi[:, 1], n=np.bincount(f_codes), comp=sol.comp_phi)
    return Step1(outcome=outcome, k=k, rows=f["row"].to_numpy(), race_idx=ri, alpha=alpha, phi=phi, theta=sol.theta,
                 layout=lay, ry=ry, rx=rx, n_r=n_r, syy=syy, sxy=sxy, sxx=sxx, p_r=p_r, sweeps=sol.sweeps)


def phi_tilde(s1: Step1, q: pd.DataFrame, W: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """§6c: phi-hat at (r, c, l) for W = 0, else the free-pass-count-weighted mean over laps l-W..l+W that have a
    free pass in this fit. Returns (y-part, x-part, ok, component or -1 if the cells span several components)."""
    return window_mean(s1.phi, q, W, ["race_id", "corner_id"])


def window_mean(phi: pd.DataFrame, q: pd.DataFrame, W: np.ndarray, keys: list[str]
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """phi: keys + lap -> y, x, n, comp. Weighted (by n) mean of y and x over laps l-W..l+W with a cell."""
    base = q[keys + ["lap"]].reset_index(drop=True).assign(_q=np.arange(len(q)), _W=W)
    parts = []
    for d in range(-max(PHI_WINDOWS), max(PHI_WINDOWS) + 1):
        sub = base[base["_W"] >= abs(d)]
        parts.append(sub.assign(lap=sub["lap"] + d))
    ex = pd.concat(parts).merge(phi, on=keys + ["lap"], how="inner")
    agg = ex.assign(wy=ex["n"] * ex["y"], wx=ex["n"] * ex["x"]).groupby("_q").agg(
        n=("n", "sum"), wy=("wy", "sum"), wx=("wx", "sum"), c0=("comp", "min"), c1=("comp", "max"))
    agg = agg.reindex(np.arange(len(q)))
    n = agg["n"].fillna(0).to_numpy()
    ok = (W >= 0) & (n > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        py, px = agg["wy"].to_numpy() / n, agg["wx"].to_numpy() / n
    comp = np.where(agg["c0"].to_numpy() == agg["c1"].to_numpy(), agg["c0"].fillna(-1).to_numpy(), -1)
    return np.where(ok, py, np.nan), np.where(ok, px, np.nan), ok, comp.astype(float)


def g_parts(s1: Step1, races: pd.Series, compounds: pd.Series, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """§6d: g_k(t; r, m) y-part and x-part; NaN where the race has no curve in this class."""
    lin, quad = theta_ids(s1.layout, races, compounds)
    out = []
    for j in range(2):
        th = s1.theta[:, j]
        gl = np.where(lin >= 0, th[np.clip(lin, 0, None)] * t, 0.0)
        gq = np.where(quad >= 0, th[np.clip(quad, 0, None)] * t * t, np.nan)
        out.append(gl + gq)
    return out[0], out[1]


def alpha_parts(s1: Step1, groups: pd.Series) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    a = s1.alpha.reindex(groups.to_numpy())
    return (a["y"].to_numpy(dtype=float), a["x"].to_numpy(dtype=float), a["y"].notna().to_numpy(),
            a["comp"].to_numpy(dtype=float))


# --------------------------------------------------------------------------- step 2: per-pass effects (§6e, §8a)


@dataclass
class Effects:
    """Per following pass of one class and outcome: tau(gamma) = A + gamma * B (sign applied, §6e);
    the bracketed tau-loc(gamma) = Aloc + gamma * Bloc (§8a)."""

    outcome: str
    rows: np.ndarray
    A: np.ndarray
    B: np.ndarray
    valid: np.ndarray  # supported, not racecraft, phi-supported, outcome present, alpha present
    Aloc: np.ndarray
    Bloc: np.ndarray
    loc_ok: np.ndarray  # bracketed and both bracket passes present in this outcome's fit
    drops: dict = field(default_factory=dict)


def following_table(p: pd.DataFrame, st: Structure, k: str) -> pd.DataFrame:
    """Every eligible following pass of class k, with its fixed labels."""
    m = p["following"].to_numpy() & (p["corner_class"] == k).to_numpy()
    ft = p.loc[m].copy()
    idx = ft["row"].to_numpy()
    ft["supported"], ft["W"] = st.supported[idx], st.W[idx]
    ft["bracketed"], ft["lap_b"], ft["lap_a"] = st.bracketed[idx], st.lap_b[idx], st.lap_a[idx]
    ft["near"] = np.isin(ft["bin"].to_numpy(), NEAR_BINS)
    ft["s2_cell"] = (pd.Categorical(ft["gap_change"], GAP_CHANGES).codes * len(S2_TIERS)
                     + pd.Categorical(ft["s2_tier"], S2_TIERS).codes)
    return ft.reset_index(drop=True)


def _component_check(ok: np.ndarray, c_alpha: np.ndarray, c_phi: np.ndarray) -> np.ndarray:
    """Ruling 3: keep rows whose alpha group and phi cells are in one component of the alpha-phi graph; a
    disconnected (not identified) prediction is dropped. Callers count the drop as ok & ~result."""
    return ok & (c_phi >= 0) & (c_alpha == c_phi)


def effects(p: pd.DataFrame, y: pd.Series, s1: Step1, ft: pd.DataFrame) -> Effects:
    """§6e tau for every following pass of the class, and the §8a interpolated local-baseline tau-loc."""
    s = SIGN[s1.outcome]
    yv = y.to_numpy(dtype=float)[ft["row"].to_numpy()]
    ay, ax, a_ok, ac = alpha_parts(s1, ft["group"])
    fy, fx, f_ok, fc = phi_tilde(s1, ft, ft["W"].to_numpy())
    gy, gx = g_parts(s1, ft["race_id"], ft["compound"], ft["t"].to_numpy())
    b = ft["behind"].to_numpy()
    base = ft["supported"].to_numpy() & ~ft["racecraft"].to_numpy() & (ft["W"].to_numpy() >= 0)
    drops = {"not_supported": int((~ft["supported"]).sum()),
             "racecraft": int((ft["supported"] & ft["racecraft"]).sum()),
             "phi_unsupported": int((ft["supported"] & ~ft["racecraft"] & (ft["W"] < 0)).sum())}
    present = base & np.isfinite(yv)
    drops["outcome_null"] = int((base & ~np.isfinite(yv)).sum())
    has = present & a_ok & f_ok & np.isfinite(gy)
    drops["no_free_pass_this_outcome"] = int((present & ~a_ok).sum())
    drops["phi_cell_missing_this_outcome"] = int((present & a_ok & ~f_ok).sum())
    valid = _component_check(has, ac, fc)
    drops["disconnected"] = int((has & ~valid).sum())
    A = s * (yv - (ay + fy + gy))
    B = s * ((ax + fx + gx) - b)
    # §8a: r = y - phi-hat(own cell) - g - gamma*b of the nearest earlier / later free pass, both in this fit
    fr = p.loc[s1.rows, ["group", "lap", "race_id", "corner_id", "compound", "t", "behind"]].assign(
        yb=yv_full_at(y, s1.rows))
    fr = fr.merge(s1.phi[["race_id", "corner_id", "lap", "y", "x"]], on=["race_id", "corner_id", "lap"], how="left")
    gby, gbx = g_parts(s1, fr["race_id"], fr["compound"], fr["t"].to_numpy())
    fr["R0"] = fr["yb"] - fr["y"] - gby
    fr["R1"] = fr["x"] + gbx - fr["behind"]
    key = fr.set_index(["group", "lap"])[["R0", "R1"]]
    sides = {}
    for side in ("lap_b", "lap_a"):
        lk = pd.MultiIndex.from_arrays([ft["group"].to_numpy(), ft[side].fillna(-1).astype(int).to_numpy()])
        sides[side] = key.reindex(lk)
    lb, la, lap = ft["lap_b"].to_numpy(), ft["lap_a"].to_numpy(), ft["lap"].to_numpy(dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        wb, wa = (la - lap) / (la - lb), (lap - lb) / (la - lb)
    r0 = wb * sides["lap_b"]["R0"].to_numpy() + wa * sides["lap_a"]["R0"].to_numpy()
    r1 = wb * sides["lap_b"]["R1"].to_numpy() + wa * sides["lap_a"]["R1"].to_numpy()
    Aloc = s * (yv - fy - gy - r0)
    Bloc = s * (fx + gx - b - r1)
    brk = ft["bracketed"].to_numpy()
    loc_ok = valid & brk & np.isfinite(Aloc) & np.isfinite(Bloc)
    drops["bracket_pass_missing_this_outcome"] = int((valid & brk & ~loc_ok).sum())
    return Effects(outcome=s1.outcome, rows=ft["row"].to_numpy(), A=A, B=B, valid=valid, Aloc=Aloc, Bloc=Bloc,
                   loc_ok=loc_ok, drops=drops)


def yv_full_at(y: pd.Series, rows: np.ndarray) -> np.ndarray:
    return y.to_numpy(dtype=float)[rows]


# --------------------------------------------------------------------------- pass class, cross-fitted (§6h)


@dataclass
class ClassParts:
    """Delta(gamma) = dy - gamma*dx + gamma*db; held up if Delta > 2 * sigma_k * s0 (§6h), for `known` rows."""

    dy: np.ndarray
    dx: np.ndarray
    db: np.ndarray
    s0: np.ndarray
    known: np.ndarray
    racecraft: np.ndarray
    unknown_reason: np.ndarray
    skipped_corners: int = 0  # ruling 2: (pass, side, other corner) entries skipped for an empty alpha-bar

    def labels(self, gamma: float, sigma: float) -> np.ndarray:
        with np.errstate(invalid="ignore"):
            held = (self.dy - gamma * self.dx + gamma * self.db) > HELD_UP_SE_MULT * sigma * self.s0
        return np.where(self.racecraft, RACECRAFT, np.where(~self.known, UNKNOWN, np.where(held, HELD_UP, DIRTY_AIR)))


def class_parts(p: pd.DataFrame, st: Structure, s1: Step1, ft: pd.DataFrame) -> ClassParts:
    """§6h from the time model s1 (seg_time_s) of this class."""
    if s1.outcome != TIME:
        raise EstimatorError("the pass class uses the time model's quantities (§6h)")
    n = len(ft)
    # the leader's pass row at (race, leader, leader_lap, corner)
    lead = p[["race_id", "driver", "lap", "corner_id", "stint_key", "compound", "eligible", "t", "behind", "row"]]
    lead = lead.rename(columns={"driver": "leader", "lap": "leader_lap", "stint_key": "L", "compound": "m_L",
                                "eligible": "L_elig", "t": "t_L", "behind": "b_L", "row": "L_row"})
    q = ft[["race_id", "leader", "leader_lap", "corner_id", "stint_key", "compound", "group", "lap", "t",
            "behind", "W", "racecraft"]].rename(columns={"stint_key": "F", "compound": "m_F"})
    q["leader_lap"] = q["leader_lap"].astype(float)
    lead = lead.assign(leader_lap=lead["leader_lap"].astype(float))
    q = q.merge(lead, on=["race_id", "leader", "leader_lap", "corner_id"], how="left").reset_index(drop=True)
    q["_i"] = np.arange(n)
    # groups of this class in the time fit: (race, stint, compound, corner) -> alpha parts and free count
    gt = s1.alpha.reset_index()
    gi = p.drop_duplicates("group").set_index("group").loc[gt["group"], ["race_id", "stint_key", "compound", "corner_id"]]
    gt = pd.concat([gt.reset_index(drop=True), gi.reset_index(drop=True)], axis=1)
    sums = gt.groupby(["race_id", "compound", "corner_id"]).agg(Sy=("y", "sum"), Sx=("x", "sum"), K=("y", "size"))
    sums = sums.reset_index()

    def alpha_of(stint: pd.Series, corner: pd.Series) -> pd.DataFrame:
        k = pd.DataFrame({"stint_key": stint.to_numpy(), "corner_id": corner.to_numpy()})
        return k.merge(gt[["stint_key", "corner_id", "y", "x"]], on=["stint_key", "corner_id"], how="left")

    def alpha_bar(race, comp, corner, own_stint, own_comp, other_stint, other_comp) -> tuple:
        """mean alpha over groups at (race, comp, corner) excluding both stints (only those at that compound)."""
        k = pd.DataFrame({"race_id": race, "compound": comp, "corner_id": corner})
        s = k.merge(sums, on=["race_id", "compound", "corner_id"], how="left")
        sy, sx, kk = s["Sy"].fillna(0).to_numpy(), s["Sx"].fillna(0).to_numpy(), s["K"].fillna(0).to_numpy()
        for stint, scomp in ((own_stint, own_comp), (other_stint, other_comp)):
            a = alpha_of(pd.Series(stint), pd.Series(corner))
            here = a["y"].notna().to_numpy() & (np.asarray(scomp, dtype=object) == np.asarray(comp, dtype=object))
            sy = sy - np.where(here, a["y"].fillna(0).to_numpy(), 0.0)
            sx = sx - np.where(here, a["x"].fillna(0).to_numpy(), 0.0)
            kk = kk - here
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(kk > 0, sy / kk, np.nan), np.where(kk > 0, sx / kk, np.nan), kk

    def offset(side: str, other: str, comp_side: str, comp_other: str) -> tuple:
        """o[S, c, k] and N_S over the stint's other corners of the class (§6h). Ruling 2: another corner whose
        alpha-bar has no group left is skipped (neither in o nor in N) and counted; too few left -> N < 2 rule."""
        e = q[["_i", "race_id", "corner_id", side, other, comp_side, comp_other]].dropna(subset=[side])
        e = e.merge(gt[["stint_key", "corner_id", "y", "x", "n"]].rename(
            columns={"stint_key": side, "corner_id": "c2"}), on=side, how="inner")
        e = e[e["c2"] != e["corner_id"]]
        aby, abx, kk = alpha_bar(e["race_id"].to_numpy(), e[comp_side].to_numpy(), e["c2"].to_numpy(),
                                 e[side].to_numpy(), e[comp_side].to_numpy(), e[other].to_numpy(),
                                 e[comp_other].to_numpy())
        empty = kk <= 0
        skipped = int(empty.sum())
        e, aby, abx = e[~empty], aby[~empty], abx[~empty]
        e = e.assign(wy=e["n"] * (e["y"] - aby), wx=e["n"] * (e["x"] - abx))
        agg = e.groupby("_i").agg(N=("n", "sum"), wy=("wy", "sum"), wx=("wx", "sum")).reindex(np.arange(n))
        N = agg["N"].fillna(0).to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            oy, ox = agg["wy"].to_numpy() / N, agg["wx"].to_numpy() / N
        return oy, ox, N, skipped

    oFy, oFx, NF, skF = offset("F", "L", "m_F", "m_L")
    oLy, oLx, NL, skL = offset("L", "F", "m_L", "m_F")
    abFy, abFx, _ = alpha_bar(q["race_id"].to_numpy(), q["m_F"].to_numpy(), q["corner_id"].to_numpy(),
                              q["F"].to_numpy(), q["m_F"].to_numpy(), q["L"].to_numpy(), q["m_L"].to_numpy())
    abLy, abLx, _ = alpha_bar(q["race_id"].to_numpy(), q["m_L"].to_numpy(), q["corner_id"].to_numpy(),
                              q["L"].to_numpy(), q["m_L"].to_numpy(), q["F"].to_numpy(), q["m_F"].to_numpy())
    fFy, fFx, fF_ok, _ = phi_tilde(s1, q, q["W"].to_numpy())
    lq = q[["race_id", "corner_id", "leader_lap", "leader"]].rename(columns={"leader_lap": "lap", "leader": "driver"})
    lq["lap"] = lq["lap"].fillna(-10_000).astype(int)
    WL = phi_window_counts(st.free_rows_time, lq, ["race_id", "corner_id"])
    fLy, fLx, fL_ok, _ = phi_tilde(s1, lq, WL)
    gFy, gFx = g_parts(s1, q["race_id"], q["m_F"], q["t"].to_numpy())
    gLy, gLx = g_parts(s1, q["race_id"], q["m_L"].fillna(""), q["t_L"].to_numpy(dtype=float))
    yF_y, yF_x = abFy + oFy + fFy + gFy, abFx + oFx + fFx + gFx
    yL_y, yL_x = abLy + oLy + fLy + gLy, abLx + oLx + fLx + gLx
    L_elig = q["L_elig"].fillna(False).astype(bool).to_numpy()
    reason = np.select(
        [q["racecraft"].to_numpy(), ~L_elig, NF < 2, NL < 2, ~fL_ok, ~fF_ok,
         ~(np.isfinite(yF_y) & np.isfinite(yL_y) & np.isfinite(yF_x) & np.isfinite(yL_x))],
        ["racecraft", "leader_not_eligible", "N_F<2", "N_L<2", "leader_phi_unsupported", "own_phi_unsupported",
         "alpha_bar_or_curve_undefined"], default="")
    known = reason == ""
    with np.errstate(invalid="ignore", divide="ignore"):
        s0 = np.sqrt(1.0 / NL + 1.0 / NF)
    return ClassParts(dy=yL_y - yF_y, dx=yL_x - yF_x, db=q["b_L"].fillna(0).to_numpy(dtype=float) - q["behind"].to_numpy(),
                      s0=s0, known=known, racecraft=q["racecraft"].to_numpy(dtype=bool), unknown_reason=reason,
                      skipped_corners=skF + skL)


# --------------------------------------------------------------------------- the model and one draw


@dataclass
class ClassModel:
    k: str
    ft: pd.DataFrame
    step1: dict  # outcome -> Step1
    eff: dict  # outcome -> Effects
    cls: ClassParts
    s3_group: np.ndarray  # per following row: its group is in the S3 population structure (>=3 free, span >= 8)
    s3_d: np.ndarray  # tyre-age distance to the group's free-pass mean
    s3_gid: np.ndarray  # group code for S3 slopes (-1 if not in the population structure)
    s3_slope_y: np.ndarray  # per S3 group: OLS slope of the residualised y on tyre_life
    s3_slope_x: np.ndarray


@dataclass
class Model:
    prep: pd.DataFrame
    st: Structure
    classes: dict  # k -> ClassModel
    racecraft_free_dropped: dict = field(default_factory=dict)  # ruling 1: outcome -> count


def fit_model(p: pd.DataFrame, y: dict[str, pd.Series], outcomes=OUTCOMES) -> Model:
    """The point fit: structure from seg_time_s, step 1 per class and outcome, effects, the pass class, the S3
    pieces. `y` maps outcome name -> Series aligned with p (synthetic in SG checks, decoded after RUN START in
    the run)."""
    if TIME not in y:
        raise EstimatorError("seg_time_s is required: it fixes the structure sets (§6a)")
    st = structure_sets(p, y[TIME])
    frees = {o: (st.free_time if o == TIME else free_set(p, y[o], o)) for o in outcomes}
    classes = {}
    for k in CLASSES:
        ft = following_table(p, st, k)
        s1 = {o: fit_step1(p, y[o], o, k, st, frees[o]) for o in outcomes}
        eff = {o: effects(p, y[o], s1[o], ft) for o in outcomes}
        cp = class_parts(p, st, s1[TIME], ft)
        s3 = _s3_pieces(p, st, s1[TIME], ft)
        classes[k] = ClassModel(k=k, ft=ft, step1=s1, eff=eff, cls=cp, **s3)
    return Model(prep=p, st=st, classes=classes,
                 racecraft_free_dropped={o: racecraft_free_dropped(p, y[o]) for o in outcomes})


def _s3_pieces(p: pd.DataFrame, st: Structure, s1: Step1, ft: pd.DataFrame) -> dict:
    """§11 S3 structure: groups with >= 3 free passes (time set, after trims) spanning >= 8 tyre-age laps; each
    group's slope of the step-1 residual on tyre_life, as y-part and x-part; d_i per following pass."""
    fr = pd.DataFrame({"group": p["group"].to_numpy()[s1.rows], "t": p["t"].to_numpy()[s1.rows],
                       "ry": s1.ry, "rx": s1.rx})
    g = fr.groupby("group")
    stats = g.agg(n=("t", "size"), tmin=("t", "min"), tmax=("t", "max"), tm=("t", "mean"))
    pop = stats[(stats["n"] >= S3_MIN_FREE) & (stats["tmax"] - stats["tmin"] >= S3_MIN_SPAN)]
    fr = fr[fr["group"].isin(pop.index)]
    fr = fr.assign(dt=fr["t"] - fr["group"].map(pop["tm"]))
    agg = fr.assign(ty=fr["dt"] * fr["ry"], tx=fr["dt"] * fr["rx"], tt=fr["dt"] ** 2).groupby("group")[
        ["ty", "tx", "tt"]].sum()
    gid = pd.Index(agg.index)
    code = gid.get_indexer(ft["group"].to_numpy())
    d = ft["t"].to_numpy() - ft["group"].map(pop["tm"]).to_numpy(dtype=float)
    return {"s3_group": code >= 0, "s3_d": d, "s3_gid": code,
            "s3_slope_y": (agg["ty"] / agg["tt"]).to_numpy(), "s3_slope_x": (agg["tx"] / agg["tt"]).to_numpy()}


def _bin_means(values: np.ndarray, bins: np.ndarray, weight: np.ndarray, n_bins: int = N_BINS) -> np.ndarray:
    num = np.bincount(bins, weights=weight * np.where(weight > 0, values, 0.0), minlength=n_bins)[:n_bins]
    den = np.bincount(bins, weights=weight, minlength=n_bins)[:n_bins]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def _near(beta: np.ndarray) -> float:
    return float(np.mean(beta[list(NEAR_BINS)]))


def _far(beta: np.ndarray) -> float:
    return float(np.mean(beta[list(FAR_BINS)]))


def _cell_near(tau, bins, cell, w, mask) -> np.ndarray:
    """Near band per S2 cell (mean of the two near-bin means; one bin missing -> the other's mean)."""
    out = np.full(len(GAP_CHANGES) * len(S2_TIERS), np.nan)
    m0 = mask & (bins == NEAR_BINS[0])
    m1 = mask & (bins == NEAR_BINS[1])
    n0 = np.bincount(cell[m0], weights=w[m0], minlength=len(out))
    n1 = np.bincount(cell[m1], weights=w[m1], minlength=len(out))
    s0 = np.bincount(cell[m0], weights=(w * tau)[m0], minlength=len(out))
    s1 = np.bincount(cell[m1], weights=(w * tau)[m1], minlength=len(out))
    with np.errstate(invalid="ignore", divide="ignore"):
        b0, b1 = np.where(n0 > 0, s0 / n0, np.nan), np.where(n1 > 0, s1 / n1, np.nan)
    out = np.where(np.isfinite(b0) & np.isfinite(b1), (b0 + b1) / 2, np.where(np.isfinite(b0), b0, b1))
    return out


def _s2_pieces(tau, tau_loc, keep, loc_keep, bins, cell, w, extra=None) -> dict:
    """§11 S2 for one class and set: one-sided near band standardized to the bracketed mix over the 15 cells."""
    extra = np.ones_like(keep) if extra is None else extra
    near = np.isin(bins, NEAR_BINS)
    one = keep & extra & near  # the caller passes keep = entering beta and one-sided
    brk = loc_keep & extra & near
    n_one_cell = np.bincount(cell[one], weights=w[one], minlength=len(GAP_CHANGES) * len(S2_TIERS))
    thin = n_one_cell < S2_CELL_MIN_ONE_SIDED
    brk_kept = brk & ~thin[cell]
    n_brk = float(w[brk_kept].sum())
    w_cell = np.bincount(cell[brk_kept], weights=w[brk_kept], minlength=len(thin))
    beta_brk = _near(_bin_means(tau_loc, bins, w * brk_kept))
    one_cell = _cell_near(tau, bins, cell, w, one)
    with np.errstate(invalid="ignore", divide="ignore"):
        ws = w_cell / w_cell.sum() if w_cell.sum() > 0 else np.full_like(w_cell, np.nan)
    used = ws > 0
    std_one = float(np.sum(ws[used] * one_cell[used])) if used.any() else np.nan
    if used.any() and not np.isfinite(one_cell[used]).all():
        std_one = np.nan
    return {"beta_brk": beta_brk, "std_one": std_one, "D": std_one - beta_brk, "n_brk": n_brk,
            "brk_dropped_thin_cell": float(w[brk & thin[cell]].sum()),
            "beta_one": _near(_bin_means(tau, bins, w * one)),
            "beta_brk_all": _near(_bin_means(tau_loc, bins, w * brk))}


def draw_stats(model: Model, w: np.ndarray | None = None) -> dict:
    """Every statistic the switch rule needs, for one race weighting (point: all ones). Keys are flat strings.
    w[r] = entries of race r in the draw; every entry is a separate copy (§10 circuit copies; ruling 5)."""
    w = np.ones(N_RACES) if w is None else np.asarray(w, dtype=float)
    out: dict = {}
    for k, cm in model.classes.items():
        ft = cm.ft
        bins = ft["bin"].to_numpy()
        cell = ft["s2_cell"].to_numpy()
        wr = w[ft["race_idx"].to_numpy()]
        bracketed = ft["bracketed"].to_numpy()
        gt = cm.step1[TIME].gamma(w)
        sg = cm.step1[TIME].sigma(w, gt)
        lab = cm.cls.labels(gt, sg)
        out[f"{k}|gamma|{TIME}"], out[f"{k}|sigma"] = gt, sg
        for o, ef in cm.eff.items():
            g = gt if o == TIME else cm.step1[o].gamma(w)
            tau = ef.A + g * ef.B
            tloc = ef.Aloc + g * ef.Bloc
            with np.errstate(invalid="ignore"):
                keep = ef.valid & (np.abs(tau) <= TRIM_EFFECT[o])
            lk = keep & ef.loc_ok
            one = keep & ~bracketed
            for name, m, v in (("all", keep, tau), ("one", one, tau), ("brk", lk, tloc),
                               ("held_up", keep & (lab == HELD_UP), tau), ("dirty_air", keep & (lab == DIRTY_AIR), tau),
                               ("brk_dirty", lk & (lab == DIRTY_AIR), tloc), ("one_dirty", one & (lab == DIRTY_AIR), tau)):
                beta = _bin_means(v, np.clip(bins, 0, None), wr * m)
                out[f"{k}|{o}|{name}|beta"] = beta
                out[f"{k}|{o}|{name}|near"] = _near(beta)
                out[f"{k}|{o}|{name}|far"] = _far(beta)
                out[f"{k}|{o}|{name}|n"] = np.bincount(np.clip(bins, 0, None), weights=wr * m, minlength=N_BINS)
            if o == TIME:
                out.update({f"{k}|S2pace|{a}": b for a, b in
                            _s2_pieces(tau, tloc, keep & ~bracketed, lk, bins, cell, wr).items()})
                # S3 (§11): near-band passes entering beta_near, in population groups
                nearm = keep & np.isin(bins, NEAR_BINS) & cm.s3_group
                slope = cm.s3_slope_y[cm.s3_gid[nearm]] - gt * cm.s3_slope_x[cm.s3_gid[nearm]]
                ww = wr[nearm]
                out[f"{k}|S3|B"] = float(np.sum(ww * slope * cm.s3_d[nearm]) / ww.sum()) if ww.sum() > 0 else np.nan
                allnear = keep & np.isin(bins, NEAR_BINS)
                out[f"{k}|S3|coverage"] = float(ww.sum() / wr[allnear].sum()) if wr[allnear].sum() > 0 else np.nan
            if o == MINSPEED:
                dirty = lab == DIRTY_AIR
                out.update({f"{k}|S2aero|{a}": b for a, b in
                            _s2_pieces(tau, tloc, keep & ~bracketed & dirty, lk & dirty, bins, cell, wr).items()})
        out[f"{k}|class_counts"] = {c: float(wr[lab == c].sum()) for c in (HELD_UP, DIRTY_AIR, UNKNOWN, RACECRAFT)}
    for a, b in (("fast", "slow"), ("medium", "slow")):
        if a in model.classes and b in model.classes:
            out[f"aero|{a}-{b}|all"] = (out[f"{a}|{MINSPEED}|dirty_air|near"] - out[f"{b}|{MINSPEED}|dirty_air|near"])
            out[f"aero|{a}-{b}|D"] = ((out[f"{a}|S2aero|std_one"] - out[f"{b}|S2aero|std_one"])
                                      - (out[f"{a}|S2aero|beta_brk"] - out[f"{b}|S2aero|beta_brk"]))
            out[f"aero|{a}-{b}|brk"] = out[f"{a}|S2aero|beta_brk"] - out[f"{b}|S2aero|beta_brk"]
            out[f"aero|{a}-{b}|n_brk"] = min(out[f"{a}|S2aero|n_brk"], out[f"{b}|S2aero|n_brk"])
    return out


# --------------------------------------------------------------------------- the bootstrap (§10)


@dataclass(frozen=True)
class Plan:
    """B draws: per draw, entries per race (multiplicity, Appendix A order). Every entry is a separate copy (a
    circuit drawn twice by §10; a race drawn twice within one copy by ruling 5), so copies == weights."""

    weights: np.ndarray  # B x N_RACES

    @property
    def copies(self) -> np.ndarray:
        return self.weights


def bootstrap_plan(n_draws: int = N_BOOT, seed: int = SEED) -> Plan:
    """§10: one default_rng(seed); per draw integers(0, 24, 24) over the Appendix A circuits, then for each drawn
    circuit in draw order integers(0, m, m) over its races. A circuit drawn twice is two copies; a race drawn
    twice within a copy is two copies too (ruling 5)."""
    rng = np.random.default_rng(seed)
    races_of = [[RACE_INDEX[r] for r in sorted(APPENDIX_A[c], key=lambda r: r.encode())] for c in CIRCUITS]
    W = np.zeros((n_draws, N_RACES))
    for i in range(n_draws):
        for c in rng.integers(0, len(CIRCUITS), len(CIRCUITS)):
            own = races_of[c]
            picked = np.array(own)[rng.integers(0, len(own), len(own))]
            np.add.at(W[i], picked, 1.0)
    return Plan(weights=W)


def check_appendix_a(p: pd.DataFrame, calendar: dict) -> None:
    """§10: refuse unless build_pass_table.race_calendar gives exactly the Appendix A mapping over the races
    with an eligible braking pass."""
    kept = p.loc[p["eligible"], ["season", "race_id", "race"]].drop_duplicates()
    found: dict[str, set] = {}
    for season, rid, slug in kept.itertuples(index=False, name=None):
        key = calendar.get((int(season), str(slug)))
        if key is None:
            raise EstimatorError(f"no calendar entry for {season} {slug}")
        found.setdefault(unicodedata.normalize("NFC", key[0]), set()).add(str(rid))
    want = {unicodedata.normalize("NFC", c): set(r) for c, r in APPENDIX_A.items()}
    if found != want:
        raise EstimatorError("race_calendar mapping differs from Appendix A (§10): the run refuses to start")


def run_draws(model: Model, plan: Plan, draws: range | None = None) -> list[dict]:
    idx = range(plan.weights.shape[0]) if draws is None else draws
    return [draw_stats(model, plan.weights[i]) for i in idx]


def interval(draws: list[dict], key: str, pct=CI95) -> tuple[float, float]:
    """Percentile interval of a scalar statistic over draws. Ruling 4: if any draw leaves it undefined, the
    interval is undefined (NaN, NaN); no draw is skipped or redrawn."""
    v = np.array([d[key] for d in draws], dtype=float)
    if len(v) == 0 or not np.isfinite(v).all():
        return np.nan, np.nan
    lo, hi = np.percentile(v, pct)
    return float(lo), float(hi)


def switch_undefined_counts(draws: list[dict], lap_draw_list: list[dict] | None = None) -> dict:
    """Ruling 4: per switch, the number of draws in which at least one statistic its verdict uses is undefined.
    S1: near and near - far per class; S2 pace: D' per class; S2 aero: D'_A (fast - slow); F1: Near_lap."""
    def n_bad(ds, fn):
        return int(sum(1 for d in ds if not np.isfinite(np.asarray(fn(d), dtype=float)).all()))
    out = {
        "S1": n_bad(draws, lambda d: [v for k in CLASSES for v in (d[f"{k}|{TIME}|all|near"],
                                                                  d[f"{k}|{TIME}|all|near"] - d[f"{k}|{TIME}|all|far"])]),
        "S2 pace": n_bad(draws, lambda d: [d[f"{k}|S2pace|D"] for k in CLASSES]),
        "S2 aero": n_bad(draws, lambda d: [d["aero|fast-slow|D"]]),
    }
    if lap_draw_list is not None:
        out["F1"] = n_bad(lap_draw_list, lambda d: [d["lap|near"]])
    return out


# --------------------------------------------------------------------------- the switch rule (§11)


def s1_verdicts(point: dict, draws: list[dict]) -> dict:
    """S1 per class: lower 95 % end of near > 0 and of (near - far) > 0 (seg time, all passes)."""
    out = {}
    for k in CLASSES:
        lo_n, _ = interval(draws, f"{k}|{TIME}|all|near")
        dd = [{"x": d[f"{k}|{TIME}|all|near"] - d[f"{k}|{TIME}|all|far"]} for d in draws]
        lo_d, _ = interval(dd, "x")
        out[k] = bool(lo_n > 0 and lo_d > 0)
    return out


def s2_verdict(D_draws: list[float], beta_brk_point: float, n_brk_point: float, floor: float) -> tuple[str, dict]:
    """§11 S2 equivalence test on the 90 % interval of D'. An undefined interval (ruling 4) is INCONCLUSIVE."""
    lo, hi = interval([{"D": x} for x in D_draws], "D", CI90)
    T = max(S2_TOL_FRAC * abs(beta_brk_point), floor) if np.isfinite(beta_brk_point) else np.nan
    info = {"lo90": lo, "hi90": hi, "T": T, "n_brk": n_brk_point}
    if not (np.isfinite(lo) and np.isfinite(hi) and np.isfinite(T)):
        return INCONCLUSIVE, info
    if -T <= lo and hi <= T and n_brk_point >= S2_AGREE_MIN:
        return AGREE, info
    if (hi < -T or lo > T) and n_brk_point >= S2_DISAGREE_MIN:
        return DISAGREE, info
    return INCONCLUSIVE, info


def s2_pace(point: dict, draws: list[dict]) -> dict:
    return {k: s2_verdict([d[f"{k}|S2pace|D"] for d in draws], point[f"{k}|S2pace|beta_brk"],
                          point[f"{k}|S2pace|n_brk"], S2_PACE_FLOOR) for k in CLASSES}


def s2_aero(point: dict, draws: list[dict]) -> tuple[str, dict]:
    key = "aero|fast-slow"
    return s2_verdict([d[f"{key}|D"] for d in draws], point[f"{key}|brk"], point[f"{key}|n_brk"], S2_AERO_FLOOR)


def s3_verdicts(point: dict) -> dict:
    """§11 S3 on point estimates: |B_k| <= max(0.25 |near_k|, 0.010 s)."""
    out = {}
    for k in CLASSES:
        B, near = point[f"{k}|S3|B"], point[f"{k}|{TIME}|all|near"]
        out[k] = bool(np.isfinite(B) and np.isfinite(near) and abs(B) <= max(S3_TOL_FRAC * abs(near), S3_FLOOR))
    return out


def go_no_go(s1: dict, s2p: dict, s2a: str, s3: dict, f1: bool, s2_unpowered: bool = False, *,
             undefined: dict) -> tuple[str, str, str]:
    """§11 table, first match wins. Returns (line verdict, aero proposal, the printed line). `undefined` is
    switch_undefined_counts(...): the number of undefined draws per switch, printed on the line (ruling 4)."""
    s2_ok = (all(s2p[k] != DISAGREE for k in CLASSES) and s2p["medium"] == AGREE and s2p["slow"] == AGREE)
    if s2_unpowered:
        s2_ok = True
    if all(s1[k] for k in CLASSES) and s2_ok and all(s3[k] for k in CLASSES):
        verdict = "DESIGN A"
        aero = "proposed" if s2a != DISAGREE else "—"
    elif f1:
        verdict, aero = "FALLBACK (lap level, pace only)", "—"
    else:
        verdict, aero = "NEITHER", "—"
    pf = lambda b: "pass" if b else "fail"  # noqa: E731
    line = (f"GO/NO-GO: {verdict} | S1 {','.join(pf(s1[k]) for k in CLASSES)} | S2 pace "
            f"{','.join(s2p[k] for k in CLASSES)} | S2 aero {s2a} | S3 {','.join(pf(s3[k]) for k in CLASSES)}"
            f" | F1 {pf(f1)}"
            f" | undefined draws {', '.join(f'{name} {int(n)}' for name, n in undefined.items())}")
    notes = []
    if verdict == "DESIGN A" and s2p["fast"] == INCONCLUSIVE:
        notes.append("fast-corner bracketed check inconclusive")
    if verdict == "DESIGN A" and s2a == INCONCLUSIVE:
        notes.append("aero bracketed check inconclusive")
    if verdict.startswith("FALLBACK"):
        notes.append("lap drift checked through corner-level S3 only")
    if s2_unpowered:
        notes.append("S2 unpowered")
    if notes:
        line += " | " + "; ".join(notes)
    return verdict, aero, line
