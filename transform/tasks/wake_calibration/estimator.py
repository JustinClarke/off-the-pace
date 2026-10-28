"""
WC-03 estimator: per-pass corner loss, the pass classes, the non-increasing loss-versus-gap curve per corner
class and era, and cluster bootstrap intervals (circuit then race, amendment A1).

Rules come from the signed pre-registration, wi/WC-03-preregistration-DRAFT.md (SIGNED 2026-10-28, SHA-256
518c3348...). Section numbers in comments (§) point into that document. Every threshold below is copied
from it; none may change after a result has been seen (§0).

AMENDMENT A1 (draft, wi/WC-03-amendment-A1-circuit-bootstrap.md; owner decision 2026-10-28; not yet
committed or hashed): the curve bootstrap resamples circuits, then races within each drawn circuit, instead
of races (§6 Intervals, §8c). Adopted after G1 (i) failed under the registered race-level resample on
synthetic data. B, the seed, the percentile interval and every threshold are unchanged. The race-level
resample is kept as a labelled comparison only (BOOTSTRAP_COMPARISON).

This module is a library of pure functions on DataFrames. It reads no file, opens no warehouse and writes
nothing. It has been run on synthetic data only (tests/test_estimator.py, gate G1). The one real run (§0),
with G2 and G3 before it, is not wired up here.

Also here: the held-up and dirty-air class curves (§6), the under-attack difference at the same gap (§12b,
reported only), and the explicit no-verdict / not-estimable result for a gap bin with no fit pass.

Also here, because gate G1 (§12a) tests them with the estimator:
  - the lap-total weights and the measured cost of a lap (§7);
  - the pieces of the contest that G1 names: flat-now with unknown kept unknown, the §8a step-2 filter,
    the θ_now point fit and the §8b score (§2d, §8a, §8b);
  - the pit-stop event builder (§11 "Events" and "Jump"; the comparison group, adjusted jump and
    predicted drop are in pitstop.py).

Also here (AMENDMENT A3, draft, not yet committed or hashed): §8a step 1 lap-level counting (lap_1,
last_lap, no_pass_rows, by position in the panel), the step-4 short-stint drop (stint_under_2_laps)
applied once to whatever step 3 kept, and step-5
counting of each dropped lap once, at its first step. And (amendment A2) the §12b no_reference counts.

Not here: §8a step 3 (the ±5 s trim, label residual_beyond_5s, amendment A4), the θ_now refit per draw, the
2025 rescoring, the contest bootstrap, W1-W3, P1/P2, G5 and G7 are in contest.py; G2, G3, G6, PROVENANCE and
the evidence files are in run_wc03.py (the CLI, not run on real data). The §11 comparison group, adjusted
jump and predicted drop are in pitstop.py; the §12b sensitivity runs in sensitivity.py (which calls
prepare_passes / reference_spread with half_window 2 or 6; the default stays the registered 4); coverage per
team and Table 2 in report.py. All report-only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from tasks.wake_calibration.build_pass_table import (
    CLEAN_AHEAD_GAP_S,
    REF_HALF_WINDOW_LAPS,
    REF_MIN_N,
)

# --------------------------------------------------------------------------- fixed numbers (§0)

# Seasons (§3). The main curve and θ_now are fitted on 2022-2024 only; 2025 is the held-out season.
# The older-car curve is fitted on 2018-2020 and scored on 2021.
ERAS = {
    "main": {"fit": (2022, 2023, 2024), "held_out": 2025},
    "older": {"fit": (2018, 2019, 2020), "held_out": 2021},
}
# No season that is held out in any era may enter a fit of the era that holds it out (G4).

BRAKING_BASIS = "brake_onset"  # §4b C1: flat-out corners (fixed_before_apex) are out of the curve and lap totals
CORNER_CLASSES = ("slow", "medium", "fast")
# Gap bins, each [lower, upper) (§0).
GAP_EDGES = np.array([0.0, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0])
N_BINS = len(GAP_EDGES) - 1
FOLLOW_MAX_GAP_S = 3.0  # §5 C4: following = 0 <= gap_s < 3.0; gap_s < 0 is racecraft
LOSS_TRIM_S = 2.0  # §4b C3: fit passes with |delta_time_s| > 2.0 are left out
HELD_UP_SPREAD_MULT = 2.0  # §5 C6/N3: held up if the car ahead's time > ref + 2 x spread
SPREAD_FLOOR_S = 0.01  # §5: reference spread floor
RACECRAFT_CORNERS = 3  # §5 C5: a leader change at any braking corner within 3 corners either side
YIELDING_TAGS = {"yielding", "lapped+yielding"}  # §4b C2

N_BOOT = 1000  # §8c: fixed, no fallback count (unchanged by amendment A1)
SEED = 20261027  # §8c: numpy default_rng
CI_PERCENTILES = (2.5, 97.5)  # §8c: 95 % percentile interval
MIN_FIT_RACES = 60  # §8c / G5: of the 68 fit races
MIN_HELD_OUT_RACES = 20  # §8c / G5: of the 24 held-out races

FLAT_CLAMP_S = (0.0, 5.0)  # §2d: flat penalty and flat-now are clamped 0-5 s

# Pit-stop events (§11).
PIT_CLOSE_GAP_S = 1.5
PIT_PRE_LAPS = (-2, -1)  # L-2, L-1 (never L itself)
PIT_POST_LAPS = (1, 2)  # L+1, L+2
PIT_FOLLOWER_NO_PIT = range(-2, 3)  # follower has no pit in or out on L-2 .. L+2
PIT_LEADER_NO_PIT = (-2, -1)  # car ahead has none on L-2 or L-1
PIT_REF_LAPS = (-6, -5, -4, -3, 3, 4, 5, 6)  # the follower's reference: L-6..L-3 and L+3..L+6
PIT_REF_MIN_N = 2

# Class labels (§5 C6/N3). Every following pass gets exactly one (§5: "every following pass gets exactly
# one"). NO_REFERENCE is the label for a following pass that is neither racecraft nor no_leader_time and has
# no measured own reference, so held up versus dirty air cannot be judged. It is report-only: the §6 fit set
# requires ref_status = measured, so a no_reference pass never enters the main curve or a class curve.
RACECRAFT, NO_LEADER_TIME, HELD_UP, DIRTY_AIR = "racecraft", "no_leader_time", "held_up", "dirty_air"
NO_REFERENCE = "no_reference"
PASS_CLASSES = (RACECRAFT, NO_LEADER_TIME, NO_REFERENCE, HELD_UP, DIRTY_AIR)
NO_CAR_AHEAD = "no_car_ahead"  # §4b N2


class EstimatorError(ValueError):
    """A rule the pre-registration fixes cannot be applied to the data given (never silently patched)."""


class LeakageError(EstimatorError):
    """A held-out season row reached a fit (G4)."""


class EmptyBinError(EstimatorError):
    """A gap bin has no fit pass in a corner class, so its fixed effect is not identified. Raised by
    reml_fit only; the curve functions catch it and report no verdict / not estimable (see CURVE_ROLES)."""


# --------------------------------------------------------------------------- per-pass measures (§4b, §5)


def wc03_reason(passes: pd.DataFrame) -> pd.Series:
    """§4b N2: 'no_car_ahead' where the builder's reason is NULL and no car went through in the 30 s before."""
    no_car = passes["reason"].isna() & passes["clear_ahead"].astype(bool)
    return pd.Series(np.where(no_car, NO_CAR_AHEAD, None), index=passes.index, dtype=object)


def is_yielding(tag: pd.Series) -> pd.Series:
    return tag.fillna("").astype(str).isin(YIELDING_TAGS)


def circuit_of(passes: pd.DataFrame, calendar: dict) -> pd.Series:
    """§6: the builder's circuit name after CIRCUIT_ALIASES, with SEPARATE_LAYOUT_SLUGS kept separate.

    `calendar` is build_pass_table.race_calendar(): (season, race slug) -> (circuit key, date). A race with
    no calendar entry is an error, not a guess.
    """
    keys = list(zip(passes["season"].astype(int), passes["race"].astype(str)))
    missing = sorted({k for k in keys if k not in calendar})
    if missing:
        raise EstimatorError(f"no circuit for {len(missing)} race(s), e.g. {missing[:3]}")
    return pd.Series([calendar[k][0] for k in keys], index=passes.index, dtype=object)


def reference_spread(passes: pd.DataFrame, half_window: int = REF_HALF_WINDOW_LAPS) -> pd.Series:
    """§5: median absolute deviation of seg_time_s over the same donors the builder used, floor 0.01 s.

    Donors: same race, driver, corner_id, stint and compound; clean; lap within ±half_window (the registered
    ±REF_HALF_WINDOW_LAPS = 4; 2 or 6 only in the §12b sensitivity runs, after sensitivity.rereference);
    the pass itself excluded. Defined only where ref_status is 'measured'; NaN elsewhere. As a check that
    the donors are the builder's, their median must equal the stored ref_time_s.
    """
    spread = np.full(len(passes), np.nan)
    pos = pd.Series(np.arange(len(passes)), index=passes.index)
    keys = ["season", "race_id", "driver", "corner_id", "stint", "compound"]
    for _, g in passes.groupby(keys, dropna=True, sort=False):
        measured = (g["ref_status"] == "measured").to_numpy()
        if not measured.any():
            continue
        laps = g["lap"].to_numpy()
        donor = g["clean"].astype(bool).to_numpy()
        seg = g["seg_time_s"].to_numpy(dtype=float)
        ref = g["ref_time_s"].to_numpy(dtype=float)
        for i in np.flatnonzero(measured):
            m = donor & (np.abs(laps - laps[i]) <= half_window) & (laps != laps[i])
            if m.sum() < REF_MIN_N:
                raise EstimatorError(f"measured reference with fewer than {REF_MIN_N} donors at row {g.index[i]}")
            med = float(np.median(seg[m]))
            if not np.isclose(med, ref[i], rtol=0.0, atol=1e-9):
                raise EstimatorError(f"donor median {med} differs from ref_time_s {ref[i]} at row {g.index[i]}")
            spread[pos[g.index[i]]] = max(float(np.median(np.abs(seg[m] - med))), SPREAD_FLOOR_S)
    return pd.Series(spread, index=passes.index)


def leader_time(passes: pd.DataFrame) -> pd.Series:
    """§5: seg_time_s of the car ahead's row at (race, leader, leader_lap, corner_id); NaN if none."""
    own = passes[["season", "race_id", "driver", "lap", "corner_id", "seg_time_s"]].rename(
        columns={"driver": "leader", "lap": "leader_lap", "seg_time_s": "leader_time_s"}
    )
    own = own.assign(leader_lap=own["leader_lap"].astype(float))
    if own.duplicated(["season", "race_id", "leader", "leader_lap", "corner_id"]).any():
        raise EstimatorError("pass table has more than one row per (race, driver, lap, corner)")
    left = passes[["season", "race_id", "leader", "leader_lap", "corner_id"]].copy()
    left["leader_lap"] = left["leader_lap"].astype(float)
    out = left.merge(own, on=["season", "race_id", "leader", "leader_lap", "corner_id"], how="left")
    return pd.Series(out["leader_time_s"].to_numpy(dtype=float), index=passes.index)


def braking_corner_order(passes: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Rank of each braking corner within its race (0..n-1, by corner_number then corner_id); NaN elsewhere."""
    braking = passes["segment_basis"] == BRAKING_BASIS
    corners = (
        passes.loc[braking, ["season", "race_id", "corner_number", "corner_id"]]
        .drop_duplicates()
        .sort_values(["season", "race_id", "corner_number", "corner_id"])
    )
    corners["rank"] = corners.groupby(["season", "race_id"]).cumcount()
    corners["n"] = corners.groupby(["season", "race_id"])["rank"].transform("size")
    out = passes[["season", "race_id", "corner_id"]].merge(
        corners[["season", "race_id", "corner_id", "rank", "n"]], on=["season", "race_id", "corner_id"], how="left"
    )
    rank = np.where(braking.to_numpy(), out["rank"].to_numpy(dtype=float), np.nan)
    n = np.where(braking.to_numpy(), out["n"].to_numpy(dtype=float), np.nan)
    return pd.Series(rank, index=passes.index), pd.Series(n, index=passes.index)


def racecraft(passes: pd.DataFrame) -> pd.Series:
    """§5 C5: gap_s < 0, or the leader differs between this braking corner and any braking corner within
    RACECRAFT_CORNERS before or after it (same or adjoining lap). A missing leader at a neighbouring corner
    does not count as a change. No lateral rule. False for flat-out corners.

    "Within 3 corners" is counted along the race's braking-corner sequence: position = lap x n + rank, so a
    corner with no pass row on a lap still occupies its place in the sequence.
    """
    rank, n = braking_corner_order(passes)
    seq = pd.DataFrame(
        {
            "season": passes["season"].to_numpy(),
            "race_id": passes["race_id"].to_numpy(),
            "driver": passes["driver"].to_numpy(),
            "lap": passes["lap"].to_numpy(dtype=float),
            "pos": passes["lap"].to_numpy(dtype=float) * n.to_numpy() + rank.to_numpy(),
            "leader": passes["leader"].to_numpy(dtype=object),
        }
    )
    braking = np.isfinite(seq["pos"].to_numpy())
    nb = seq[braking & seq["leader"].apply(lambda x: isinstance(x, str)).to_numpy()]
    change = np.zeros(len(passes), dtype=bool)
    keys = ["season", "race_id", "driver", "pos"]
    for d in range(-RACECRAFT_CORNERS, RACECRAFT_CORNERS + 1):
        if d == 0:
            continue
        other = nb[keys + ["lap", "leader"]].rename(columns={"lap": "o_lap", "leader": "o_leader"})
        other = other.assign(pos=other["pos"] - d)  # the row at pos+d, keyed at pos
        m = seq.reset_index(drop=True).merge(other, on=keys, how="left")
        has = m["o_leader"].apply(lambda x: isinstance(x, str)).to_numpy()
        own = m["leader"].apply(lambda x: isinstance(x, str)).to_numpy()
        adj = np.abs(m["o_lap"].to_numpy(dtype=float) - m["lap"].to_numpy(dtype=float)) <= 1
        change |= has & own & adj & (m["o_leader"].astype(str).to_numpy() != m["leader"].astype(str).to_numpy())
    gap = passes["gap_s"].to_numpy(dtype=float)
    out = braking & ((np.isfinite(gap) & (gap < 0)) | change)
    return pd.Series(out, index=passes.index)


def pass_class(passes: pd.DataFrame) -> pd.Series:
    """§5 C6/N3, priority order: racecraft; no_leader_time; no_reference; held_up; dirty_air.

    Applies to following passes (gap_s < 3.0, negative included) at braking corners; every one gets exactly
    one class (§5). held_up and dirty_air need the follower's measured reference and its spread; a following
    pass that is neither racecraft nor no_leader_time and has no measured reference gets `no_reference`
    (review item Q5). That label is report-only and feeds no fit: §6 fit passes need ref_status = measured.
    Its place in the order (after no_leader_time, before held_up) changes the class of no pass that the
    registered rule could classify. Not-following passes get None.
    Needs columns from prepare_passes: racecraft, leader_time_s, ref_spread_s.
    """
    gap = passes["gap_s"].to_numpy(dtype=float)
    following = (passes["segment_basis"] == BRAKING_BASIS).to_numpy() & np.isfinite(gap) & (gap < FOLLOW_MAX_GAP_S)
    lt = passes["leader_time_s"].to_numpy(dtype=float)
    ref = passes["ref_time_s"].to_numpy(dtype=float)
    spread = passes["ref_spread_s"].to_numpy(dtype=float)
    has_ref = np.isfinite(ref) & np.isfinite(spread)
    bound = ref + HELD_UP_SPREAD_MULT * spread
    rc = passes["racecraft"].to_numpy(dtype=bool)
    no_lt = ~np.isfinite(lt)
    with np.errstate(invalid="ignore"):
        slower = lt > bound
    cls = np.select(
        [following & rc, following & no_lt, following & ~has_ref, following & slower, following],
        [RACECRAFT, NO_LEADER_TIME, NO_REFERENCE, HELD_UP, DIRTY_AIR],
        default="",
    )
    return pd.Series(cls, index=passes.index).replace("", None)


def no_reference_counts(prepared: pd.DataFrame) -> pd.DataFrame:
    """§12b "Counts" as amended by A2 (report-only): per season and corner class, the no_reference passes and
    their share of following braking passes. "Following braking passes" here = the passes pass_class gives a
    class (braking corner, gap_s < 3.0, negative included), the same set §5 says gets exactly one class."""
    following = prepared["pass_class"].notna()
    g = prepared[following].groupby(["season", "corner_class"])
    out = g.size().rename("following_braking_passes").to_frame()
    out["no_reference_passes"] = g["pass_class"].apply(lambda s: int((s == NO_REFERENCE).sum()))
    out["no_reference_share"] = out["no_reference_passes"] / out["following_braking_passes"]
    return out.reset_index()


def gap_bin(gap: np.ndarray) -> np.ndarray:
    """Bin index 0..7 for 0 <= gap < 3.0 ([lower, upper)); -1 otherwise (NaN, negative or >= 3.0)."""
    gap = np.asarray(gap, dtype=float)
    idx = np.searchsorted(GAP_EDGES, gap, side="right") - 1
    ok = np.isfinite(gap) & (gap >= GAP_EDGES[0]) & (gap < GAP_EDGES[-1])
    return np.where(ok, idx, -1)


def prepare_passes(passes: pd.DataFrame, calendar: dict, half_window: int = REF_HALF_WINDOW_LAPS) -> pd.DataFrame:
    """The pass table with the WC-03 analysis columns added. The builder's columns are not changed (G2).
    half_window is the reference window the table's references were built with (4, registered; 2 or 6 only
    in the §12b sensitivity runs)."""
    out = passes.copy()
    out["reason_wc03"] = wc03_reason(out)
    out["yielding"] = is_yielding(out["tag"])
    out["circuit"] = circuit_of(out, calendar)
    # CLARIFICATION (§6 C7), pending owner confirmation: the "random effect per corner_id" is nested in the
    # circuit, keyed circuit|corner_id, so corner 4 at Monaco and corner 4 at Monza are different groups and
    # one physical corner keeps one group across the seasons the circuit hosts. §6 names a random effect per
    # circuit and one per corner_id but does not say crossed or nested; nested is what the REML code assumes.
    out["corner_key"] = out["circuit"].astype(str) + "|" + out["corner_id"].astype(str)
    out["ref_spread_s"] = reference_spread(out, half_window)
    out["leader_time_s"] = leader_time(out)
    out["racecraft"] = racecraft(out)
    out["pass_class"] = pass_class(out)
    out["under_attack"] = out["behind_1s"].astype(bool)  # §5: a flag, not a class
    out["gap_bin"] = gap_bin(out["gap_s"].to_numpy(dtype=float))
    out["race_key"] = out["race_id"].astype(str)  # the bootstrap cluster; race_id already carries the season
    if out.groupby("race_key")["season"].nunique().gt(1).any():
        raise EstimatorError("a race_id appears in more than one season")
    return out


# --------------------------------------------------------------------------- fit set (§6) and leakage (G4)


def assert_no_leak(frame: pd.DataFrame, era: str) -> None:
    """G4: no held-out row (2025 for the main era, 2021 for the older one) is in a fit, and no fit season
    lies outside the era's fit seasons."""
    seasons = set(frame["season"].astype(int).unique())
    held = ERAS[era]["held_out"]
    if held in seasons:
        raise LeakageError(f"{era} fit contains held-out season {held}")
    extra = seasons - set(ERAS[era]["fit"])
    if extra:
        raise LeakageError(f"{era} fit contains seasons outside {ERAS[era]['fit']}: {sorted(extra)}")


def fit_passes(prepared: pd.DataFrame, era: str = "main") -> pd.DataFrame:
    """§6 fit passes: the era's fit seasons; braking corners; reason and reason_wc03 NULL; measured
    reference; not yielding; 0 <= gap_s < 3.0; |delta_time_s| <= 2.0."""
    p = prepared
    gap = p["gap_s"].to_numpy(dtype=float)
    keep = (
        p["season"].astype(int).isin(ERAS[era]["fit"]).to_numpy()
        & (p["segment_basis"] == BRAKING_BASIS).to_numpy()
        & p["reason"].isna().to_numpy()
        & p["reason_wc03"].isna().to_numpy()
        & (p["ref_status"] == "measured").to_numpy()
        & ~p["yielding"].to_numpy(dtype=bool)
        & np.isfinite(gap) & (gap >= 0.0) & (gap < FOLLOW_MAX_GAP_S)
        & (np.abs(p["delta_time_s"].to_numpy(dtype=float)) <= LOSS_TRIM_S)
    )
    out = p[keep].copy()
    assert_no_leak(out, era)
    return out


def contributing_fit_races(fit: pd.DataFrame) -> int:
    """§8c / G5: races that contribute fit passes (must be at least MIN_FIT_RACES)."""
    return int(fit["race_key"].nunique())


# --------------------------------------------------------------------------- the REML curve fit (§6 C7)


@dataclass
class CornerStats:
    """Sufficient statistics of one fit set, per (race, corner) cell.

    The model is linear Gaussian with one fixed effect per gap bin, so a REML fit needs, per corner, only
    the pass count per bin, the sum of the loss per bin and the sum of the squared loss. Keeping them per
    (race, corner) lets a bootstrap draw (races with multiplicity) be summed without touching the passes.
    """

    race: np.ndarray  # race index per cell
    corner: np.ndarray  # corner index per cell
    circuit_of_corner: np.ndarray  # circuit index per corner
    count: np.ndarray  # cells x bins
    total: np.ndarray  # cells x bins, sum of loss
    sq: np.ndarray  # cells, sum of squared loss
    races: list[str]
    corners: list[str]
    circuits: list[str]  # circuit name per circuit index


def corner_stats(fit: pd.DataFrame, races: list[str] | None = None) -> CornerStats:
    """Cells for one corner class (or class subset). `races` fixes the race index order (the bootstrap
    resamples over it); default: the races present."""
    races = sorted(fit["race_key"].unique()) if races is None else list(races)
    missing = set(fit["race_key"].unique()) - set(races)
    if missing:
        raise EstimatorError(f"fit passes from races not in the race list: {sorted(missing)[:3]}")
    if (fit["gap_bin"] < 0).any():
        raise EstimatorError("fit pass outside the gap bins")
    corners = sorted(fit["corner_key"].unique())
    circ = fit.drop_duplicates("corner_key").set_index("corner_key")["circuit"]
    circuits = sorted(circ.unique())
    c_index = {c: i for i, c in enumerate(circuits)}
    r_idx = pd.Categorical(fit["race_key"], categories=races).codes
    k_idx = pd.Categorical(fit["corner_key"], categories=corners).codes
    cell = r_idx.astype(np.int64) * len(corners) + k_idx
    uniq, inv = np.unique(cell, return_inverse=True)
    b = fit["gap_bin"].to_numpy(dtype=int)
    y = fit["delta_time_s"].to_numpy(dtype=float)
    count = np.zeros((len(uniq), N_BINS))
    total = np.zeros((len(uniq), N_BINS))
    np.add.at(count, (inv, b), 1.0)
    np.add.at(total, (inv, b), y)
    sq = np.bincount(inv, weights=y * y, minlength=len(uniq))
    return CornerStats(
        race=(uniq // len(corners)).astype(int),
        corner=(uniq % len(corners)).astype(int),
        circuit_of_corner=np.array([c_index[circ[c]] for c in corners], dtype=int),
        count=count, total=total, sq=sq, races=races, corners=corners, circuits=list(circuits),
    )


def draw_stats(stats: CornerStats, race_weight: np.ndarray | None = None):
    """Per-corner (count, total, sq, circuit) for the point fit (race_weight None) or for a race-weighted
    set: each race's cells times its multiplicity, in their own circuit and corner groups.

    Bootstrap draws do not use this: they go through plan_draw_stats (adopted method, amendment A1: a
    circuit drawn twice is two circuit groups; within a copy a race drawn twice counts twice). Under the
    race-level COMPARISON method, plan_draw_stats gives the same sums as this function with the draw's race
    multiplicities (a race drawn k times is frequency weight k in its own circuit and corner groups).
    """
    w = np.ones(len(stats.races)) if race_weight is None else np.asarray(race_weight, dtype=float)
    cw = w[stats.race]
    n_k = len(stats.corners)
    count = np.zeros((n_k, N_BINS))
    total = np.zeros((n_k, N_BINS))
    np.add.at(count, stats.corner, stats.count * cw[:, None])
    np.add.at(total, stats.corner, stats.total * cw[:, None])
    sq = np.bincount(stats.corner, weights=stats.sq * cw, minlength=n_k)
    keep = count.sum(1) > 0
    return count[keep], total[keep], sq[keep], stats.circuit_of_corner[keep]


@dataclass
class RemlFit:
    beta: np.ndarray  # bin fixed effects
    var_beta: np.ndarray  # their variances
    sigma2: float  # noise variance
    var_circuit: float
    var_corner: float
    n: float


def _reml_parts(log_g, count, total, sq, circuit, n_circuits):
    """-2 x restricted log-likelihood (profiled over the noise variance, constants dropped), and the GLS
    pieces, for y = X beta + circuit effect + corner effect + noise, corners nested in circuits.

    With H = V / sigma2 = D + g_a 11' per circuit and D = blockdiag(I + g_b J) per corner, H^-1 has a closed
    form (Woodbury twice), so every term is a sum over corners and circuits.

    The closed form needs each corner inside exactly one circuit: the nested reading of §6 C7 (see
    prepare_passes, corner_key = circuit|corner_id). A crossed design would need a different likelihood.
    """
    g_a, g_b = np.exp(log_g)
    n_j = count.sum(1)
    sy_j = total.sum(1)
    d = 1.0 + n_j * g_b
    g_j = g_b / d
    s_i = np.bincount(circuit, weights=n_j / d, minlength=n_circuits)
    h_i = g_a / (1.0 + g_a * s_i)
    q = np.zeros((n_circuits, N_BINS))
    np.add.at(q, circuit, count / d[:, None])
    r = np.bincount(circuit, weights=sy_j / d, minlength=n_circuits)
    a = np.diag(count.sum(0)) - (count * g_j[:, None]).T @ count - (q * h_i[:, None]).T @ q
    b = total.sum(0) - (count * (g_j * sy_j)[:, None]).sum(0) - (q * (h_i * r)[:, None]).sum(0)
    yhy = sq.sum() - (g_j * sy_j * sy_j).sum() - (h_i * r * r).sum()
    logdet_h = np.log(d).sum() + np.log1p(g_a * s_i).sum()
    sign, logdet_a = np.linalg.slogdet(a)
    if sign <= 0:
        return np.inf, None
    beta = np.linalg.solve(a, b)
    rss = yhy - b @ beta
    n = n_j.sum()
    sigma2 = rss / (n - N_BINS)
    if not np.isfinite(sigma2) or sigma2 <= 0:
        return np.inf, None
    m2ll = (n - N_BINS) * np.log(sigma2) + logdet_h + logdet_a
    return m2ll, (a, beta, sigma2, g_a, g_b, n)


# Search range for log(variance ratio); exp(-20) is a variance component of zero for every practical purpose.
LOG_RATIO_BOUNDS = (-20.0, 8.0)


def reml_fit(count, total, sq, circuit, start=None) -> RemlFit:
    """REML fit of the bin fixed effects with a random effect per circuit and per corner (§6)."""
    if (count.sum(0) <= 0).any():
        raise EmptyBinError(f"gap bins with no fit pass: {np.flatnonzero(count.sum(0) <= 0).tolist()}")
    _, circuit = np.unique(circuit, return_inverse=True)
    n_c = int(circuit.max()) + 1
    # Every fit, bootstrap draws included, searches from the fixed starts and keeps the best. A warm start
    # (the full-data optimum) is tried first but never alone: when the full-data fit puts a variance ratio
    # at the lower bound, a search started there can stop on the flat boundary short of the draw's REML
    # optimum (seen on synthetic data, 2026-10-28: -2 log L -3540.50 warm-only against -3540.74).
    starts = [np.array([-2.0, -2.0]), np.array([-6.0, -6.0]), np.array([0.0, 0.0])]
    if start is not None:
        starts.insert(0, np.asarray(start, dtype=float))
    best = None
    for x in starts:
        res = minimize(lambda v: _reml_parts(v, count, total, sq, circuit, n_c)[0], x, method="L-BFGS-B",
                       bounds=[LOG_RATIO_BOUNDS] * 2)
        if best is None or res.fun < best.fun - 1e-9:
            best = res
    _, parts = _reml_parts(best.x, count, total, sq, circuit, n_c)
    if parts is None:
        raise EstimatorError("REML fit failed")
    a, beta, sigma2, g_a, g_b, n = parts
    var_beta = sigma2 * np.diag(np.linalg.inv(a))
    return RemlFit(beta=beta, var_beta=var_beta, sigma2=float(sigma2), var_circuit=float(sigma2 * g_a),
                   var_corner=float(sigma2 * g_b), n=float(n))


def pava_nonincreasing(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Weighted least-squares projection onto non-increasing sequences (pool adjacent violators)."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if not (np.isfinite(values).all() and np.isfinite(weights).all() and (weights > 0).all()):
        raise EstimatorError("PAVA needs finite values and positive weights")
    blocks: list[list[float]] = []  # [mean, weight, length]
    for v, w in zip(values, weights):
        blocks.append([v, w, 1])
        while len(blocks) > 1 and blocks[-2][0] < blocks[-1][0]:
            v2, w2, n2 = blocks.pop()
            v1, w1, n1 = blocks.pop()
            blocks.append([(v1 * w1 + v2 * w2) / (w1 + w2), w1 + w2, n1 + n2])
    return np.concatenate([np.full(n, v) for v, _, n in blocks])


def fit_curve_from_stats(count, total, sq, circuit, start=None) -> tuple[np.ndarray, RemlFit]:
    """§6: REML bin estimates, then non-increasing with gap by PAVA weighted by 1 / variance."""
    fit = reml_fit(count, total, sq, circuit, start=start)
    return pava_nonincreasing(fit.beta, 1.0 / fit.var_beta), fit


# --------------------------------------------------------------------------- empty gap bins (review item Q6)

# A gap bin with no fit pass in a corner class leaves that bin's fixed effect unidentified. The run does not
# patch it (no merged bins, no prior) and does not skip or redraw a bootstrap draw (§8c: fixed B, no fallback
# count). What happens instead depends on what the curve is for:
#   - the main (contest) curve is a verdict input (§6, §9, §10 P1): an empty bin in the point fit or in any
#     of the B draws, in any corner class, means the run has NO VERDICT, and main_curve_verdict_line() says so
#     in words for the scorecard's first line;
#   - a class curve (held_up, dirty_air) is reported only (§6, §12b): the affected corner class of that class
#     curve is marked NOT ESTIMABLE, with no estimate and no interval, and the other corner classes stand.
CURVE_OK = "ok"
CURVE_NO_VERDICT = "no_verdict"  # main curve
CURVE_NOT_ESTIMABLE = "not_estimable"  # class curves and other reported-only figures
CURVE_ROLES = {"main": CURVE_NO_VERDICT, "class": CURVE_NOT_ESTIMABLE}


def _empty_bins(sub: pd.DataFrame) -> list[int]:
    present = set(sub["gap_bin"].astype(int).unique()) if not sub.empty else set()
    return [b for b in range(N_BINS) if b not in present]


def fit_curves(fit: pd.DataFrame, races: list[str] | None = None) -> pd.DataFrame:
    """One curve per corner class on the given fit passes (all following passes: the main curve; or a
    pass-class subset: the class curves). Long table: corner_class, bin, edges, estimate, raw estimate and
    its standard error, variance components, passes, races, and `point_empty_bins` (the bins with no fit
    pass in that corner class, "" if none).

    A corner class with an empty bin is not fitted and not raised on: its estimate columns are NaN and
    `point_empty_bins` names the bins. What that means for the run is decided by curve_with_intervals
    (main curve: no verdict; class curve: not estimable)."""
    rows = []
    for cls in CORNER_CLASSES:
        sub = fit[fit["corner_class"] == cls]
        empty = _empty_bins(sub)
        if empty:
            curve = beta = se = np.full(N_BINS, np.nan)
            var_circuit = var_corner = sigma2 = np.nan
        else:
            stats = corner_stats(sub, races)
            curve, reml = fit_curve_from_stats(*draw_stats(stats))
            beta, se = reml.beta, np.sqrt(reml.var_beta)
            var_circuit, var_corner, sigma2 = reml.var_circuit, reml.var_corner, reml.sigma2
        per_bin = sub.groupby("gap_bin").agg(passes=("gap_bin", "size"), races=("race_key", "nunique"))
        for b in range(N_BINS):
            rows.append({
                "corner_class": cls, "bin": b, "gap_lower_s": GAP_EDGES[b], "gap_upper_s": GAP_EDGES[b + 1],
                "estimate_s": curve[b], "raw_estimate_s": beta[b], "raw_se_s": float(se[b]),
                "var_circuit": var_circuit, "var_corner": var_corner, "sigma2": sigma2,
                "passes": int(per_bin["passes"].get(b, 0)), "races": int(per_bin["races"].get(b, 0)),
                "point_empty_bins": ",".join(map(str, empty)),
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- curve bootstrap (§6 Intervals, §8c)
#
# ADOPTED (pre-result amendment A1, wi/WC-03-amendment-A1-circuit-bootstrap.md; owner decision 2026-10-28,
# NOT YET COMMITTED OR HASHED): the fit side of the bootstrap is a two-stage circuit-then-race resample.
#   1. Resample the fit circuits with replacement, to their count.
#   2. For each drawn circuit, in draw order, resample that circuit's fit races with replacement, to that
#      circuit's own race count.
#   3. A circuit drawn twice enters the REML fit as two distinct circuit groups, and each of its corners as two
#      distinct corner groups (one per copy). Within one copy, a race drawn twice counts twice (frequency
#      weight) and stays in that copy's circuit and corner groups.
# The held-out races are still resampled at race level, independently, after the fit side of each draw.
# One numpy default_rng(SEED) drives the whole plan, B = N_BOOT draws, fixed before anything is fitted.
#
# Why: G1 (i) failed under the registered race-level resample on the registered model's own design (circuit
# and corner random effects, about 3 races per circuit): per-bin coverage 0.595-0.645 against the 90 % bar.
# A race-level resample keeps every circuit's effect in every draw, so the between-circuit spread that the
# bin estimates carry is not reproduced. The change was made AFTER that synthetic failure was seen.
#
# COMPARISON ONLY (not the adopted method): the registered race-level resample, method "race". It is kept so
# the two can be set side by side on synthetic data; it must not be used for any reported interval.

BOOTSTRAP_ADOPTED = "circuit"  # amendment A1
BOOTSTRAP_COMPARISON = "race"  # the registered §8c race-level resample; comparison only
BOOTSTRAP_METHODS = (BOOTSTRAP_ADOPTED, BOOTSTRAP_COMPARISON)


@dataclass(frozen=True)
class BootstrapPlan:
    """The B draws, fixed before anything is fitted.

    fit_draws[i] = (races, groups): the drawn fit races of draw i (indices into fit_races, with repeats) and,
    for each, the circuit group it enters the REML fit in. Adopted method: the group is the circuit copy (the
    position of the circuit draw, 0..n_circuits-1), so a circuit drawn twice is two groups. Comparison method:
    the group is the race's own circuit, so a race drawn twice stays in its circuit and corner groups.
    """

    method: str
    fit_races: list[str]
    held_out_races: list[str]
    circuits: list[str]
    race_circuit: np.ndarray  # circuit index (into circuits) per fit race
    fit_draws: tuple  # B x (races, groups)
    held_idx: np.ndarray  # B x n_held, race-level

    @property
    def n_draws(self) -> int:
        return len(self.fit_draws)

    def race_weights(self) -> np.ndarray:
        """B x n_fit: how many times each fit race enters each draw (over all circuit copies)."""
        return np.stack([np.bincount(r, minlength=len(self.fit_races)) for r, _ in self.fit_draws]).astype(float)


def race_circuits(fit: pd.DataFrame) -> dict[str, str]:
    """race_key -> circuit, from the fit passes. A race at more than one circuit is an error."""
    per = fit.groupby("race_key")["circuit"].unique()
    bad = per[per.apply(len) != 1]
    if len(bad):
        raise EstimatorError(f"race(s) at more than one circuit: {bad.index[:3].tolist()}")
    return {r: str(c[0]) for r, c in per.items()}


def resample_plan(fit_races: list[str], race_circuit: dict[str, str], held_out_races: list[str],
                  n_draws: int = N_BOOT, seed: int = SEED, method: str = BOOTSTRAP_ADOPTED) -> BootstrapPlan:
    """The bootstrap plan from one numpy default_rng(seed). Race and circuit lists are sorted first so the
    plan does not depend on input order; a circuit's races are taken in sorted order.

    Per draw, in this order:
      method "circuit" (ADOPTED, amendment A1): rng.integers(0, n_circuits, n_circuits) picks the circuits;
        then, for each picked circuit in that order, rng.integers(0, m, m) picks among its m fit races;
      method "race" (COMPARISON ONLY, the registered §8c resample): rng.integers(0, n_fit, n_fit);
    then rng.integers(0, n_held, n_held) for the held-out races (race level under both methods)."""
    if method not in BOOTSTRAP_METHODS:
        raise EstimatorError(f"unknown bootstrap method {method!r}")
    fit_races, held_out_races = sorted(fit_races), sorted(held_out_races)
    if set(fit_races) & set(held_out_races):
        raise LeakageError("a race is in both the fit and the held-out list")
    missing = [r for r in fit_races if r not in race_circuit]
    if missing:
        raise EstimatorError(f"no circuit for fit race(s) {missing[:3]}")
    circuits = sorted({str(race_circuit[r]) for r in fit_races})
    c_index = {c: i for i, c in enumerate(circuits)}
    rc = np.array([c_index[str(race_circuit[r])] for r in fit_races], dtype=int)
    races_of = [np.flatnonzero(rc == c) for c in range(len(circuits))]
    rng = np.random.default_rng(seed)
    draws = []
    held_idx = np.empty((n_draws, len(held_out_races)), dtype=int)
    for i in range(n_draws):
        if method == BOOTSTRAP_ADOPTED:
            races, groups = [], []
            for j, c in enumerate(rng.integers(0, len(circuits), len(circuits))):
                own = races_of[c]
                races.append(own[rng.integers(0, len(own), len(own))])
                groups.append(np.full(len(own), j))
            r, g = np.concatenate(races), np.concatenate(groups)
        else:
            r = rng.integers(0, len(fit_races), len(fit_races))
            g = rc[r]
        draws.append((r.astype(int), g.astype(int)))
        held_idx[i] = rng.integers(0, len(held_out_races), len(held_out_races))
    return BootstrapPlan(method=method, fit_races=fit_races, held_out_races=held_out_races, circuits=circuits,
                         race_circuit=rc, fit_draws=tuple(draws), held_idx=held_idx)


def plan_draw_stats(stats: CornerStats, plan: BootstrapPlan, i: int):
    """Per corner group (count, total, sq, circuit group) for draw i of the plan. The corner group is
    (circuit group, corner), so under the adopted method a circuit drawn twice gives two circuit groups and
    two copies of each of its corners; a race drawn twice inside one copy counts twice in that copy.
    `stats` must be built on plan.fit_races, and every cell's circuit must be its race's circuit in the plan."""
    if list(stats.races) != list(plan.fit_races):
        raise EstimatorError("corner stats and bootstrap plan use different fit race lists")
    races, groups = plan.fit_draws[i]
    order = np.argsort(stats.race, kind="stable")
    starts = np.searchsorted(stats.race[order], np.arange(len(stats.races) + 1))
    lengths = starts[1:] - starts[:-1]
    cells = np.concatenate([order[starts[r]:starts[r + 1]] for r in races]) if len(races) else np.empty(0, int)
    group = np.repeat(groups, lengths[races])
    n_k = len(stats.corners)
    key = group.astype(np.int64) * n_k + stats.corner[cells]
    uniq, inv = np.unique(key, return_inverse=True)
    count = np.zeros((len(uniq), N_BINS))
    total = np.zeros((len(uniq), N_BINS))
    np.add.at(count, inv, stats.count[cells])
    np.add.at(total, inv, stats.total[cells])
    sq = np.bincount(inv, weights=stats.sq[cells], minlength=len(uniq))
    keep = count.sum(1) > 0
    return count[keep], total[keep], sq[keep], (uniq // n_k)[keep]


def _check_plan_circuits(stats: CornerStats, plan: BootstrapPlan) -> None:
    """Every cell's corner must sit at the circuit the plan gives its race (the corner is nested in it)."""
    cell_circuit = np.array([str(c) for c in stats.circuits])[stats.circuit_of_corner[stats.corner]]
    plan_circuit = np.array(plan.circuits)[plan.race_circuit[stats.race]]
    if len(cell_circuit) and (cell_circuit != plan_circuit).any():
        raise EstimatorError("a fit pass sits at a circuit other than its race's circuit in the plan")


def bootstrap_curves(fit: pd.DataFrame, plan: BootstrapPlan,
                     classes: tuple[str, ...] = CORNER_CLASSES) -> np.ndarray:
    """Refit the whole chain (REML and the non-increasing step) on each draw of the plan (adopted: circuit
    then race, amendment A1; see plan_draw_stats for how a repeated circuit or race enters the fit).
    Returns an array draws x classes x bins.

    Every draw in the plan is fitted, in order; none is skipped and none is redrawn (§8c). A draw in which a
    corner class has a gap bin with no fit pass is recorded as NaN across that class's bins, and the caller
    (curve_with_intervals) turns any NaN into no verdict (main curve) or not estimable (class curve).
    """
    out = np.empty((plan.n_draws, len(classes), N_BINS))
    for c, cls in enumerate(classes):
        sub = fit[fit["corner_class"] == cls]
        if _empty_bins(sub):  # every draw is a subset of the point fit's races, so every draw is empty too
            out[:, c] = np.nan
            continue
        stats = corner_stats(sub, plan.fit_races)
        _check_plan_circuits(stats, plan)
        full = reml_fit(*draw_stats(stats))
        start = np.log(np.clip([full.var_circuit / full.sigma2, full.var_corner / full.sigma2], 1e-9, None))
        for i in range(plan.n_draws):
            try:
                out[i, c], _ = fit_curve_from_stats(*plan_draw_stats(stats, plan, i), start=start)
            except EmptyBinError:
                out[i, c] = np.nan
    return out


def percentile_interval(draws: np.ndarray, axis: int = 0) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = np.percentile(draws, CI_PERCENTILES, axis=axis)
    return lo, hi


def curve_with_intervals(fit: pd.DataFrame, plan: BootstrapPlan,
                         role: str = "main") -> tuple[pd.DataFrame, np.ndarray]:
    """The curve table (fit_curves) with the 95 % percentile interval of each bin over the plan's draws
    (adopted: circuit then race, amendment A1), and a status per corner class.

    role "main": the contest curve. role "class": a held-up or dirty-air class curve (reported only).
    Columns added: ci_lower_s, ci_upper_s, n_draws, empty_bin_draws (draws in which that corner class had a
    gap bin with no fit pass) and status: CURVE_OK when the point fit and all B draws are fitted; otherwise
    CURVE_NO_VERDICT (main) or CURVE_NOT_ESTIMABLE (class), with estimate and interval set to NaN. The B
    draws are always all fitted; the interval is never taken over fewer than B."""
    if role not in CURVE_ROLES:
        raise EstimatorError(f"unknown curve role {role!r}")
    table = fit_curves(fit, plan.fit_races)
    draws = bootstrap_curves(fit, plan)
    c_of = {c: i for i, c in enumerate(CORNER_CLASSES)}
    ci = table["corner_class"].map(c_of).to_numpy()
    b = table["bin"].to_numpy()
    empty_draws = np.isnan(draws).any(axis=2).sum(axis=0)  # per corner class
    ok_class = (empty_draws == 0) & np.array(
        [table.loc[table["corner_class"] == c, "point_empty_bins"].iloc[0] == "" for c in CORNER_CLASSES])
    lo = np.full((len(CORNER_CLASSES), N_BINS), np.nan)
    hi = np.full((len(CORNER_CLASSES), N_BINS), np.nan)
    if ok_class.any():
        lo[ok_class], hi[ok_class] = percentile_interval(draws[:, ok_class])
    table["ci_lower_s"] = lo[ci, b]
    table["ci_upper_s"] = hi[ci, b]
    table["n_draws"] = plan.n_draws
    table["bootstrap_method"] = plan.method
    table["empty_bin_draws"] = empty_draws[ci].astype(int)
    table["status"] = np.where(ok_class[ci], CURVE_OK, CURVE_ROLES[role])
    bad = table["status"] != CURVE_OK
    table.loc[bad, ["estimate_s", "raw_estimate_s", "raw_se_s"]] = np.nan
    return table, draws


def main_curve_verdict_line(table: pd.DataFrame) -> str | None:
    """None when the main curve stands; otherwise the plain-words line the run prints and the scorecard
    leads with: no verdict, the flat penalty stays, which corner class, which bins, how many draws."""
    bad = table[table["status"] != CURVE_OK]
    if bad.empty:
        return None
    parts = []
    for cls, g in bad.groupby("corner_class", sort=False):
        point = g["point_empty_bins"].iloc[0]
        where = f"bins {point} have no fit pass" if point else "no bin is empty in the point fit"
        parts.append(f"{cls}: {where}; {int(g['empty_bin_draws'].iloc[0])} of {int(g['n_draws'].iloc[0])} "
                     f"draws had an empty bin")
    return ("No verdict: the main curve cannot be estimated because a gap bin has no fit pass ("
            + "; ".join(parts) + "). The flat penalty stays. No draw was skipped or redrawn (§8c).")


def class_curves_with_intervals(fit: pd.DataFrame, plan: BootstrapPlan
                                ) -> dict[str, tuple[pd.DataFrame, np.ndarray]]:
    """§6 class curves: the same estimator on the held_up and on the dirty_air fit passes, with the same
    plan (same draws) as the main curve. Reported only; a corner class with an empty bin is
    CURVE_NOT_ESTIMABLE."""
    out = {}
    for pc in (HELD_UP, DIRTY_AIR):
        table, draws = curve_with_intervals(fit[fit["pass_class"] == pc], plan, role="class")
        out[pc] = (table.assign(pass_class=pc), draws)
    return out


# --------------------------------------------------------------------------- under attack (§5, §12b; review item Q7)

UNDER_ATTACK_FLAGS = (True, False)


def under_attack_difference(fit: pd.DataFrame, plan: BootstrapPlan) -> pd.DataFrame:
    """The under-attack difference at the same gap (§12b, reported only; expected near zero). Fixed here,
    before any run:

    - Passes: the main-curve fit passes of the era (§6: braking corners, reason and reason_wc03 NULL,
      measured reference, not yielding, 0 <= gap_s < 3.0, |delta_time_s| <= 2.0), whatever their pass class.
    - Flag: under_attack = behind_1s (§5: a flag, not a class).
    - Per corner class and gap bin: difference = mean delta_time_s of flagged passes minus mean delta_time_s
      of not-flagged passes. Plain pass means, every pass weight 1; no random effects, no non-increasing step.
    - Interval: the same draws as the main curve (the same BootstrapPlan, B fixed, same seed; adopted method
      circuit then race, amendment A1); in a draw a race that enters k times, over all circuit copies,
      counts k times (a plain mean has no circuit or corner groups, so only the multiplicity matters); the
      95 % percentile interval over the B draws.
    - A cell with no flagged or no not-flagged pass in the point data has no difference (NaN) and status
      CURVE_NOT_ESTIMABLE. If any draw leaves a cell with no flagged or no not-flagged pass, that cell's
      interval is not taken over fewer than B draws: interval NaN and status CURVE_NOT_ESTIMABLE, the point
      difference still shown. No draw is skipped or redrawn.
    - Reported only. It never enters a verdict, a curve or a contest score.
    """
    races = list(plan.fit_races)
    r_idx = pd.Categorical(fit["race_key"], categories=races).codes
    if (r_idx < 0).any():
        raise EstimatorError("fit passes from races not in the race list")
    c_idx = pd.Categorical(fit["corner_class"], categories=list(CORNER_CLASSES)).codes
    if (c_idx < 0).any():
        raise EstimatorError("fit pass with an unknown corner class")
    b_idx = fit["gap_bin"].to_numpy(dtype=int)
    if (b_idx < 0).any():
        raise EstimatorError("fit pass outside the gap bins")
    f_idx = np.where(fit["under_attack"].to_numpy(dtype=bool), 0, 1)  # 0 flagged, 1 not flagged
    y = fit["delta_time_s"].to_numpy(dtype=float)
    shape = (len(races), len(CORNER_CLASSES), N_BINS, 2)
    count = np.zeros(shape)
    total = np.zeros(shape)
    np.add.at(count, (r_idx, c_idx, b_idx, f_idx), 1.0)
    np.add.at(total, (r_idx, c_idx, b_idx, f_idx), y)

    def diff(n, s):
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = s / n
        d = mean[..., 0] - mean[..., 1]
        return np.where((n[..., 0] > 0) & (n[..., 1] > 0), d, np.nan), mean

    n_pt, s_pt = count.sum(0), total.sum(0)
    point, mean_pt = diff(n_pt, s_pt)
    w = plan.race_weights()  # B x races
    n_dr = np.einsum("br,rcgf->bcgf", w, count)
    s_dr = np.einsum("br,rcgf->bcgf", w, total)
    draws, _ = diff(n_dr, s_dr)
    undefined = np.isnan(draws).sum(axis=0)
    ok = np.isfinite(point) & (undefined == 0)
    lo = np.full(point.shape, np.nan)
    hi = np.full(point.shape, np.nan)
    if ok.any():
        l_, h_ = percentile_interval(draws[:, ok])
        lo[ok], hi[ok] = l_, h_
    rows = []
    for c, cls in enumerate(CORNER_CLASSES):
        for b in range(N_BINS):
            rows.append({
                "corner_class": cls, "bin": b, "gap_lower_s": GAP_EDGES[b], "gap_upper_s": GAP_EDGES[b + 1],
                "passes_under_attack": int(n_pt[c, b, 0]), "passes_not_under_attack": int(n_pt[c, b, 1]),
                "mean_loss_under_attack_s": mean_pt[c, b, 0] if n_pt[c, b, 0] > 0 else np.nan,
                "mean_loss_not_under_attack_s": mean_pt[c, b, 1] if n_pt[c, b, 1] > 0 else np.nan,
                "difference_s": point[c, b], "ci_lower_s": lo[c, b], "ci_upper_s": hi[c, b],
                "n_draws": plan.n_draws, "undefined_draws": int(undefined[c, b]),
                "status": CURVE_OK if ok[c, b] else CURVE_NOT_ESTIMABLE,
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- applying the curve (§6) and lap totals (§7)


def curve_lookup(table: pd.DataFrame) -> dict[str, np.ndarray]:
    return {cls: g.sort_values("bin")["estimate_s"].to_numpy(dtype=float)
            for cls, g in table.groupby("corner_class")}


def curve_value(curve: dict[str, np.ndarray], corner_class: str, gap: float, no_car_ahead: bool) -> float:
    """§6: gap >= 3.0 -> 0; no_car_ahead -> 0; gap < 0 -> the first bin; otherwise its bin. Fixed part only."""
    if no_car_ahead:
        return 0.0
    if not np.isfinite(gap):
        raise EstimatorError("a following corner with no gap cannot be priced")
    if gap >= FOLLOW_MAX_GAP_S:
        return 0.0
    if gap < 0:
        return float(curve[corner_class][0])
    return float(curve[corner_class][gap_bin(np.array([gap]))[0]])


def lap_weights(start: np.ndarray, end: np.ndarray, corner_number: np.ndarray | None = None) -> np.ndarray | None:
    """§7 steps 2-3: corners sorted by segment start (ties by corner number); each instant belongs to the
    first corner whose interval covers it; weight = owned share of the corner's own interval, in [0, 1].
    Returned in the input order. None when any interval is missing or empty (step 5: the lap is not scored).
    """
    start = np.asarray(start, dtype=float)
    end = np.asarray(end, dtype=float)
    if not (np.isfinite(start).all() and np.isfinite(end).all()) or (end <= start).any():
        return None
    tie = np.zeros(len(start)) if corner_number is None else np.asarray(corner_number, dtype=float)
    order = np.lexsort((tie, start))
    w = np.empty(len(start))
    reach = -np.inf  # the union of earlier intervals, from this start on, is [start, reach]
    for k in order:
        covered = max(0.0, min(end[k], reach) - start[k])
        w[k] = (end[k] - start[k] - covered) / (end[k] - start[k])
        reach = max(reach, end[k])
    return w


def lap_measured_cost(lap: pd.DataFrame, curve: dict[str, np.ndarray]) -> float:
    """§7 step 4: sum over the lap's braking corners of weight x curve value; NaN when step 5 fails.
    `lap` is one (race, driver, lap); flat-out corners are dropped here and contribute 0."""
    rows = lap[lap["segment_basis"] == BRAKING_BASIS]
    if rows.empty:
        return 0.0
    w = lap_weights(rows["seg_start_t"], rows["seg_end_t"], rows["corner_number"])
    if w is None:
        return np.nan
    no_car = (rows["reason_wc03"] == NO_CAR_AHEAD).to_numpy()
    values = [curve_value(curve, c, g, nc) for c, g, nc in
              zip(rows["corner_class"], rows["gap_s"].to_numpy(dtype=float), no_car)]
    return float(np.dot(w, values))


# --------------------------------------------------------------------------- contest pieces G1 tests (§2d, §8a, §8b)


def flat_now(share: np.ndarray, theta_now: float) -> np.ndarray:
    """§2d: clamp(theta_now x same-lap share, 0, 5). NaN share stays NaN (never 0)."""
    share = np.asarray(share, dtype=float)
    return np.where(np.isfinite(share), np.clip(theta_now * share, *FLAT_CLAMP_S), np.nan)


def demean_two_way(values: np.ndarray, a: np.ndarray, b: np.ndarray, tol: float = 1e-12, max_iter: int = 10_000):
    """Residual of `values` on indicators of a and b (alternating projections to convergence). Columns of a
    2-D `values` are residualised together."""
    v = np.array(values, dtype=float, copy=True)
    two_d = v.ndim == 2
    if not two_d:
        v = v[:, None]
    ia = pd.factorize(pd.Series(a))[0]
    ib = pd.factorize(pd.Series(b))[0]
    na, nb = np.bincount(ia), np.bincount(ib)
    for _ in range(max_iter):
        before = v.copy()
        for idx, n in ((ia, na), (ib, nb)):
            means = np.zeros((len(n), v.shape[1]))
            np.add.at(means, idx, v)
            v -= (means / n[:, None])[idx]
        if np.max(np.abs(v - before)) < tol:
            break
    else:
        raise EstimatorError("two-way demeaning did not converge")
    return v if two_d else v[:, 0]


def fit_theta_now(panel: pd.DataFrame, era: str = "main") -> float:
    """§2d N1 point estimate: coefficient on dirty_air_share_lap in partial_residual_s ~ share | stint_id +
    age_bin, on the era's fit seasons only (race_year). Rows with a NULL share are dropped, as feols does."""
    p = panel[panel["race_year"].astype(int).isin(ERAS[era]["fit"])]
    assert_no_leak(p.rename(columns={"race_year": "season"}), era)
    p = p[np.isfinite(p["dirty_air_share_lap"].to_numpy(dtype=float))
          & np.isfinite(p["partial_residual_s"].to_numpy(dtype=float))]
    r = demean_two_way(p[["partial_residual_s", "dirty_air_share_lap"]].to_numpy(dtype=float),
                       p["stint_id"].to_numpy(), p["age_bin"].to_numpy())
    denom = float(r[:, 1] @ r[:, 1])
    if denom <= 0:
        raise EstimatorError("no within-stint variation in the same-lap share")
    return float(r[:, 1] @ r[:, 0]) / denom


# §8a step 1 (AMENDMENT A3, draft, wi/WC-03-amendment-A3-last-lap-exclusion.md; not yet committed or hashed).
# A panel lap with no pass row cannot join the pass table and is dropped at step 1, counted under exactly one
# of these, checked in this order. They are lap-level counting labels assigned here, in the analysis layer;
# the builder and its pass-level `reason` codes are untouched (G2). No pass row, reference or fit set changes:
# these laps have no pass rows to begin with.
LAP_1, LAST_LAP, NO_PASS_ROWS = "lap_1", "last_lap", "no_pass_rows"
STEP1_DROP_REASONS = [LAP_1, LAST_LAP, NO_PASS_ROWS]
PANEL_KEY = ["race_year", "race_id", "driver_id", "lap_number"]  # §2f, panel side
PASS_KEY = ["season", "race_id", "driver", "lap"]  # §2f, pass-table side


def lap_step1_reason(panel: pd.DataFrame, passes: pd.DataFrame) -> pd.Series:
    """§8a step 1 as amended by A3, one value per panel row (None = the lap has pass rows and goes on to
    step 2).

    panel: yardstick-panel rows (race_year, race_id, driver_id, lap_number); the caller restricts it to 2025.
    passes: the pass table (season, race_id, driver, lap); only its keys are read. Join as §2f.

    A panel lap with no pass row gets, in this order: `lap_1` if lap_number < 2; `last_lap` if lap_number is
    the highest lap_number that driver has among the race's panel rows (all rows of `panel`, joined or not);
    otherwise `no_pass_rows`. Neither input is modified.

    The labels go by the lap's position in the panel, not by why it has no pass row (A3, decision record
    2026-10-28): a driver's last panel lap with no telemetry of its own is still `last_lap`, and lap 1 is
    still `lap_1`. Telemetry is not an input; only the panel and the pass table's keys are read.
    """
    if panel[PANEL_KEY].isna().any().any():
        raise EstimatorError("panel row with a missing join key")
    if panel.duplicated(PANEL_KEY).any():
        raise EstimatorError("panel has more than one row per (race, driver, lap)")
    left = pd.DataFrame({
        "season": panel["race_year"].astype(int).to_numpy(), "race_id": panel["race_id"].astype(str).to_numpy(),
        "driver": panel["driver_id"].astype(str).to_numpy(), "lap": panel["lap_number"].astype(int).to_numpy(),
    })
    keys = passes[PASS_KEY].dropna().drop_duplicates()
    keys = pd.DataFrame({
        "season": keys["season"].astype(int).to_numpy(), "race_id": keys["race_id"].astype(str).to_numpy(),
        "driver": keys["driver"].astype(str).to_numpy(), "lap": keys["lap"].astype(int).to_numpy(),
        "_has_pass": True,
    })
    joined = left.merge(keys, on=PASS_KEY, how="left")
    has_pass = joined["_has_pass"].eq(True).to_numpy()
    last = left.groupby(["season", "race_id", "driver"])["lap"].transform("max").to_numpy()
    lap = left["lap"].to_numpy()
    reason = np.select([~has_pass & (lap < 2), ~has_pass & (lap == last), ~has_pass],
                       STEP1_DROP_REASONS, default="")
    return pd.Series(reason, index=panel.index).replace("", None)


# §8a step 4: the counting label for the laps of a panel stint (stint_id) left with fewer than 2 laps.
# The label `stint_under_2_laps` is registered by amendment A3 (§4a and §8a step 5 as amended).
SHORT_STINT = "stint_under_2_laps"
MIN_STINT_LAPS = 2


def short_stint_reason(panel: pd.DataFrame, kept: pd.Series) -> pd.Series:
    """§8a step 4, once: among the laps still kept after step 3 (`kept`, aligned to panel), the laps of a
    panel stint_id with fewer than MIN_STINT_LAPS kept laps get SHORT_STINT; every other row None."""
    kept = kept.reindex(panel.index).fillna(False).astype(bool)
    n = panel.loc[kept, "stint_id"].map(panel.loc[kept, "stint_id"].value_counts())
    short = pd.Series(False, index=panel.index)
    short.loc[n.index] = (n < MIN_STINT_LAPS).to_numpy()
    return pd.Series(np.where(short, SHORT_STINT, None), index=panel.index, dtype=object)


def lap_drop_counts(steps: dict[str, pd.Series]) -> pd.DataFrame:
    """§8a step 5 as amended by A3: each dropped lap counted once, under the first step (in the dict's order)
    whose reason is not None, and that step's reason. Every Series must share one index (the panel rows).
    Returns step, reason, laps; step 1's three reasons are always listed, with 0 where none fired."""
    names = list(steps)
    frame = pd.DataFrame({k: steps[k] for k in names})
    if len(frame) != len(steps[names[0]]):
        raise EstimatorError("the steps' reasons are not on one index")
    taken = pd.Series(False, index=frame.index)
    rows = []
    for step in names:
        r = frame[step].where(~taken)
        hit = r.notna()
        counts = r[hit].value_counts()
        if step == names[0] and set(counts.index) <= set(STEP1_DROP_REASONS):
            counts = counts.reindex(STEP1_DROP_REASONS, fill_value=0)
        rows += [{"step": step, "reason": k, "laps": int(v)} for k, v in counts.items()]
        taken |= hit
    return pd.DataFrame(rows, columns=["step", "reason", "laps"])


# §8a step 2, in the order the registration lists them; a lap carries the first that applies.
LAP_DROP_REASONS = ["flat_unknown", "flat_now_unknown", "corner_missing", "no_gap", "yielding", "no_segment_time"]


def lap_drop_reason(laps: pd.DataFrame, passes: pd.DataFrame) -> pd.Series:
    """§8a step 2 for each lap (one row per lap: season, race_id, driver, lap, x_flat, x_now). None = kept.

    flat_unknown: x_flat (dirty_air_tax_s) NULL. flat_now_unknown: x_now NULL. corner_missing: a braking
    corner of the race has no pass row on the lap with reason NULL and reason_wc03 NULL or no_car_ahead.
    no_gap: such a corner with a car ahead has no gap. yielding: any pass on the lap is yielding.
    no_segment_time: §7 step 5.
    """
    key = ["season", "race_id", "driver", "lap"]
    brk = passes[passes["segment_basis"] == BRAKING_BASIS]
    n_corners = brk.groupby(["season", "race_id"])["corner_id"].nunique().rename("n_race_corners")
    ok_row = brk["reason"].isna() & (brk["reason_wc03"].isna() | (brk["reason_wc03"] == NO_CAR_AHEAD))
    n_ok = brk[ok_row].groupby(key)["corner_id"].nunique().rename("n_ok")
    car_ahead = ok_row & brk["reason_wc03"].isna()
    no_gap = car_ahead & ~np.isfinite(brk["gap_s"].to_numpy(dtype=float))
    gap_missing = no_gap.groupby([brk[k] for k in key]).any().rename("gap_missing")
    yield_any = passes["yielding"].astype(bool).groupby([passes[k] for k in key]).any().rename("yield_any")
    seg_bad = brk.groupby(key)[["seg_start_t", "seg_end_t", "corner_number"]].apply(
        lambda g: lap_weights(g["seg_start_t"], g["seg_end_t"], g["corner_number"]) is None
    ).rename("seg_bad")
    t = laps.set_index(key)
    for part in (n_ok, gap_missing, yield_any, seg_bad):
        t = t.join(part, how="left")
    t = t.join(n_corners, on=["season", "race_id"], how="left")
    conditions = [
        ~np.isfinite(t["x_flat"].to_numpy(dtype=float)),
        ~np.isfinite(t["x_now"].to_numpy(dtype=float)),
        t["n_ok"].fillna(0).to_numpy() < t["n_race_corners"].fillna(np.inf).to_numpy(),
        t["gap_missing"].astype("boolean").fillna(False).to_numpy(dtype=bool),
        t["yield_any"].astype("boolean").fillna(False).to_numpy(dtype=bool),
        t["seg_bad"].astype("boolean").fillna(True).to_numpy(dtype=bool),
    ]
    reason = np.select(conditions, LAP_DROP_REASONS, default="")
    return pd.Series(reason, index=laps.index).replace("", None)


def contest_scores(y: np.ndarray, candidates: dict[str, np.ndarray], stint_id: np.ndarray, age_bin: np.ndarray,
                   subsets: dict[str, np.ndarray] | None = None) -> pd.DataFrame:
    """§8b: e_c = y - x_c; residual r_c on stint and tyre-age indicators over all scored laps (coefficient
    on x_c fixed at 1); MSE_c(S) = mean r_c^2 over S; R_flat = 1 - MSE_measured / MSE_flat and
    R_now = 1 - MSE_measured / MSE_now. Every x_c must be known on every scored lap."""
    names = list(candidates)
    x = np.column_stack([np.asarray(candidates[c], dtype=float) for c in names])
    if not np.isfinite(x).all():
        raise EstimatorError("a scored lap has an unknown candidate cost; it should not have been scored")
    r = demean_two_way(np.asarray(y, dtype=float)[:, None] - x, stint_id, age_bin)
    subsets = {"all": np.ones(len(y), dtype=bool)} if subsets is None else subsets
    rows = []
    for name, mask in subsets.items():
        mse = {c: float(np.mean(r[np.asarray(mask, dtype=bool), i] ** 2)) for i, c in enumerate(names)}
        row = {"set": name, "laps": int(np.sum(mask)), **{f"mse_{c}": v for c, v in mse.items()}}
        if {"measured", "flat"} <= set(mse):
            row["r_flat"] = 1.0 - mse["measured"] / mse["flat"]
        if {"measured", "now"} <= set(mse):
            row["r_now"] = 1.0 - mse["measured"] / mse["now"]
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- pit-stop events (§11, G1 iv)

PIT_DROP_REASONS = ["not_close", "different_lap", "follower_pits", "leader_pits", "no_outside_reference"]


def pit_stop_events(passes: pd.DataFrame, pits: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """§11 events and the raw jump, one per car-ahead pit stop.

    passes: prepared pass rows (season, race_id, driver, lap, stint, compound, corner_id, segment_basis,
    leader, leader_lap, gap_s, reason, clean, seg_time_s). pits: one row per (season, race_id, driver, lap)
    with booleans pit_in (the pit-entry lap) and pit_out.

    §11 says "every braking corner". Every braking-corner pass is therefore used here, whatever its WC-01
    exclusion `reason`: §11 lists its own drops and no reason filter. (Until 2026-10-28 the code kept only
    passes with reason NULL. That filter is not in §11 and was removed on the owner's instruction of
    2026-10-28.) The follower's reference donors are still `clean` passes, and clean implies reason NULL:
    that is the registered reference rule (§4a, §11 "own clean passes").

    For each stop (car ahead A, pit-entry lap L), every driver with A as its car ahead at a braking corner on
    L-2 or L-1 is a candidate. Checks, in the order the registration lists them; the first failure is the
    candidate's drop reason: not_close (on both L-2 and L-1, every braking-corner pass has A ahead, and
    their mean gap is under 1.5 s); different_lap (lap != leader_lap at any of them);
    follower_pits (pit in or out on L-2..L+2); leader_pits (A pits on L-2 or L-1); no_outside_reference (no
    braking corner has >= 2 own clean passes, same stint and compound, on L-6..L-3 or L+3..L+6, and passes
    on both sides of the window). Of the candidates left, the one with the smallest mean gap is kept, so
    each stop is counted once. Returns (events, candidate drops counted by reason).
    """
    brk = passes[(passes["segment_basis"] == BRAKING_BASIS)]
    usable = brk  # §11 "every braking corner": no reason filter (see docstring)
    pit_any = pits.assign(any_pit=pits["pit_in"].astype(bool) | pits["pit_out"].astype(bool))
    pitted = set(map(tuple, pit_any.loc[pit_any["any_pit"], ["season", "race_id", "driver", "lap"]]
                     .itertuples(index=False, name=None)))
    stops = pits.loc[pits["pit_in"].astype(bool), ["season", "race_id", "driver", "lap"]]
    by_driver = {k: g for k, g in usable.groupby(["season", "race_id", "driver"])}
    events, drops = [], []
    for season, race_id, a, big_l in stops.itertuples(index=False, name=None):
        pre_laps = [big_l + d for d in PIT_PRE_LAPS]
        cand = usable[(usable["season"] == season) & (usable["race_id"] == race_id)
                      & usable["lap"].isin(pre_laps) & (usable["leader"] == a)]["driver"].unique()
        kept = []
        for f in sorted(cand):
            g = by_driver[(season, race_id, f)]
            pre = g[g["lap"].isin(pre_laps)]
            reason = None
            gaps = pre["gap_s"].to_numpy(dtype=float)
            if (set(pre["lap"]) != set(pre_laps) or not (pre["leader"] == a).all()
                    or not np.isfinite(gaps).all() or not gaps.mean() < PIT_CLOSE_GAP_S):
                reason = "not_close"
            elif (pre["lap"].astype(float) != pre["leader_lap"].astype(float)).any():
                reason = "different_lap"
            elif any((season, race_id, f, big_l + d) in pitted for d in PIT_FOLLOWER_NO_PIT):
                reason = "follower_pits"
            elif any((season, race_id, a, big_l + d) in pitted for d in PIT_LEADER_NO_PIT):
                reason = "leader_pits"
            else:
                jump, n_corners = _pit_jump(g, big_l)
                if n_corners == 0:
                    reason = "no_outside_reference"
            if reason is not None:
                drops.append({"season": season, "race_id": race_id, "leader": a, "pit_lap": big_l,
                              "follower": f, "reason": reason})
                continue
            kept.append({"season": season, "race_id": race_id, "leader": a, "pit_lap": big_l, "follower": f,
                         "mean_gap_s": float(gaps.mean()), "jump_s": jump, "corners": n_corners})
        if kept:
            events.append(min(kept, key=lambda e: (e["mean_gap_s"], e["follower"])))
    drops_df = pd.DataFrame(drops, columns=["season", "race_id", "leader", "pit_lap", "follower", "reason"])
    counts = drops_df["reason"].value_counts().reindex(PIT_DROP_REASONS, fill_value=0).rename_axis("reason")
    cols = ["season", "race_id", "leader", "pit_lap", "follower", "mean_gap_s", "jump_s", "corners"]
    return pd.DataFrame(events, columns=cols), counts.reset_index(name="candidates")


def pit_outside_reference(g: pd.DataFrame, big_l: int) -> dict[str, float]:
    """Per braking corner: median of the follower's own clean passes on L-6..L-3 and L+3..L+6, same stint
    and compound as on L-2, at least PIT_REF_MIN_N of them. Never uses laps L-2..L+2."""
    window = g[g["lap"] == big_l - 2]
    if window.empty:
        return {}
    stint, compound = window["stint"].iloc[0], window["compound"].iloc[0]
    donors = g[g["lap"].isin([big_l + d for d in PIT_REF_LAPS]) & g["clean"].astype(bool)
               & (g["stint"] == stint) & (g["compound"] == compound) & g["seg_time_s"].notna()]
    ref = donors.groupby("corner_id")["seg_time_s"].agg(["median", "size"])
    return ref.loc[ref["size"] >= PIT_REF_MIN_N, "median"].to_dict()


def _pit_jump(g: pd.DataFrame, big_l: int) -> tuple[float, int]:
    """Mean loss against the outside reference on L-2, L-1 minus on L+1, L+2, over braking corners with a
    reference and a measured segment time on both sides (§11 "braking corners measured on both sides only").
    (nan, 0) when there are none."""
    ref = pit_outside_reference(g, big_l)
    timed = g[g["seg_time_s"].notna()]
    pre = timed[timed["lap"].isin([big_l + d for d in PIT_PRE_LAPS]) & timed["corner_id"].isin(ref)]
    post = timed[timed["lap"].isin([big_l + d for d in PIT_POST_LAPS]) & timed["corner_id"].isin(ref)]
    both = set(pre["corner_id"]) & set(post["corner_id"])
    if not both:
        return np.nan, 0
    pre, post = pre[pre["corner_id"].isin(both)], post[post["corner_id"].isin(both)]
    loss_pre = (pre["seg_time_s"] - pre["corner_id"].map(ref)).mean()
    loss_post = (post["seg_time_s"] - post["corner_id"].map(ref)).mean()
    return float(loss_pre - loss_post), len(both)
