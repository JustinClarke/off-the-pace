"""
WC-03 / WC-04 contest: §8a step 3 (the ±5 s trim), the full §8a scored set, the measured cost per lap as a
linear map of the curve, the clean-reference / no-reference halves and train laps (§5), the θ_now refit and
the 2025 rescoring inside every bootstrap draw (§2d, §8b, §8c), W1-W3 (§9, §10), G5 and G7, and the verdict
table (§9).

Rules come from the signed pre-registration (wi/WC-03-preregistration-DRAFT.md, SHA-256 518c3348...) read
with amendments A1-A3 (committed, not yet hashed on the log) and A4 (wi/WC-03-amendment-A4-rulings.md, DRAFT,
not committed or hashed). Every threshold is copied from the registration; none may change after a result
has been seen (§0).

Like estimator.py this is a library of pure functions on DataFrames: it reads no file, opens no warehouse
and writes nothing. It has been run on synthetic data only (tests/test_contest.py). The real run is
run_wc03.py, which refuses to start until every amendment is committed and its SHA-256 recorded.

Not here (report-only, Table 2, never a verdict input): the §11 pit-stop figure (pitstop.py), the §12b
sensitivity runs (sensitivity.py) and coverage per team and Table 2 itself (report.py).

DRAFT amendment A5 (wi/WC-03-amendment-A5-fit-race-list-DRAFT.md, not adopted): run_era can draw the plan
over an explicit fit-race list (fit_race_list, run_era(fit_races=...)). Off unless the caller passes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tasks.wake_calibration import estimator as E

# --------------------------------------------------------------------------- fixed numbers (§0, §8a, §9, §10)

STEP3_TRIM_S = 5.0  # §8a step 3 (C10): |residual| > 5 s on the no-traffic baseline
STEP3_REASON = "residual_beyond_5s"  # amendment A4 ruling 3: the registered label of the step-3 drop
W1_MARGIN = 0.005  # §9 W1: lower end of the 95 % interval of R_flat and of R_now >= 0.005
W2_LOWER = -0.005  # §9 W2 (C12): point R_flat >= 0 and lower end >= -0.005, on train laps
P1_FAR_SHARE = 0.25  # §10 P1 (C13): |far| <= 0.25 x near
NEAR_BINS = (2, 3)  # 0.5-0.75, 0.75-1.0
FAR_BINS = (6, 7)  # 2.0-2.5, 2.5-3.0
TRAIN_MEDIAN_GAP_S = 1.5  # §5 N4
NO_CAR_AHEAD_GAP_S = 3.0  # §5 N4: no_car_ahead corners counted as 3 s in the train-lap median
CONTEST_MIN_LAPS = 1000  # §0 / G5
CONTEST_MIN_RACES = 18  # §0 / G5
MIN_STEP2_LAPS_FOR_TRIM = 2

CANDIDATES = ("none", "flat", "now", "measured")
SET_ALL, SET_CLEAN, SET_NOREF, SET_TRAIN, SET_MIXED = "all", "clean_reference", "no_reference", "train", "mixed_stints"
SETS = (SET_ALL, SET_CLEAN, SET_NOREF, SET_TRAIN, SET_MIXED)
MINIMUM_SETS = (SET_ALL, SET_CLEAN, SET_TRAIN)  # §0 "Contest minimums"

# Verdicts (§9), read top to bottom.
NO_VERDICT, REPLACE, KEEP_AND_SHOW, KEEP_AND_STOP = "no_verdict", "replace", "keep_and_show", "keep_and_stop"
VERDICT_TEXT = {
    NO_VERDICT: "No verdict. The flat penalty stays.",
    REPLACE: "Replace the flat penalty with the measured cost (2022-2025 laps that pass §8a steps 1-2).",
    KEEP_AND_SHOW: "Keep the flat penalty and show the measured figure beside it.",
    KEEP_AND_STOP: "Keep the flat penalty and stop. WC-05, WC-06 and WC-08 do not start.",
}
WITHIN_STINT_LINE = "This contest checks changes in traffic within a stint, not the level of a whole stint spent in a train."
UNAVAILABLE = "—"  # rule 7: unavailable is "—" with a reason, never 0

# DD-WC2, word for word. The WC-03/WC-04 scorecard holds no modelled value (amendment A4 ruling 4f); this is
# kept here so any modelled value added later carries it unchanged.
DD_WC2_DISCLAIMER = ("Normalised from other compounds, based on stints from other drivers or the general "
                     "performance of the tyres after removing other factors.")


# --------------------------------------------------------------------------- stint + tyre-age residual (§2d, §8b)


def resid_stint_age(values: np.ndarray, stint: np.ndarray, age: np.ndarray,
                    weight: np.ndarray | None = None) -> np.ndarray:
    """Residual of `values` (n or n x k) on stint and age-bin indicators, by weighted least squares, exactly
    (Frisch-Waugh: demean within stint, then regress on the stint-demeaned age-bin indicators). Rows with
    weight 0 get NaN. When the weight is constant within each stint (a bootstrap race weight is: stints are
    nested in races), weight k is the same as k copies of the stint with the stint relabelled per copy
    (amendment A4 ruling 4a; test_a4_weighted_equals_separate_copies). A weight that varies inside a stint is
    refused."""
    v = np.asarray(values, dtype=float)
    one_d = v.ndim == 1
    v = v[:, None] if one_d else v
    w = np.ones(len(v)) if weight is None else np.asarray(weight, dtype=float)
    if (w < 0).any():
        raise E.EstimatorError("negative weight")
    on = w > 0
    out = np.full(v.shape, np.nan)
    if not on.any():
        return out[:, 0] if one_d else out
    vv, ww = v[on], w[on]
    s = pd.factorize(pd.Series(np.asarray(stint)[on]))[0]
    if np.any(np.bincount(s, weights=ww) != np.bincount(s) * ww[np.unique(s, return_index=True)[1]]):
        raise E.EstimatorError("weight varies inside a stint; A4 4a needs one weight per stint")
    a = pd.factorize(pd.Series(np.asarray(age)[on]))[0]
    sw = np.bincount(s, weights=ww)

    def within(x):
        m = np.stack([np.bincount(s, weights=ww * x[:, j]) for j in range(x.shape[1])], axis=1) / sw[:, None]
        return x - m[s]

    vd = within(vv)
    d = within(np.eye(a.max() + 1)[a])
    sq = np.sqrt(ww)[:, None]
    coef, *_ = np.linalg.lstsq(d * sq, vd * sq, rcond=None)
    out[on] = vd - d @ coef
    return out[:, 0] if one_d else out


def theta_now_weighted(panel_fit: pd.DataFrame, weight: np.ndarray | None = None) -> float:
    """§2d N1: the coefficient on dirty_air_share_lap in partial_residual_s ~ share | stint_id + age_bin, with
    frequency weights per row (a bootstrap draw's race multiplicities; None = the point fit). `panel_fit` must
    already be the era's fit seasons with finite share and residual (see theta_fit_rows)."""
    r = resid_stint_age(panel_fit[["partial_residual_s", "dirty_air_share_lap"]].to_numpy(dtype=float),
                        panel_fit["stint_id"].to_numpy(), panel_fit["age_bin"].to_numpy(), weight)
    w = np.ones(len(panel_fit)) if weight is None else np.asarray(weight, dtype=float)
    on = w > 0
    denom = float(np.sum(w[on] * r[on, 1] ** 2))
    if denom <= 0:
        raise E.EstimatorError("no within-stint variation in the same-lap share")
    return float(np.sum(w[on] * r[on, 1] * r[on, 0])) / denom


def theta_fit_rows(panel: pd.DataFrame, era: str = "main") -> pd.DataFrame:
    """The θ_now fit rows: the era's fit seasons only (G4), share and residual known (as feols drops NaN)."""
    p = panel[panel["race_year"].astype(int).isin(E.ERAS[era]["fit"])]
    E.assert_no_leak(p.rename(columns={"race_year": "season"}), era)
    keep = (np.isfinite(p["dirty_air_share_lap"].to_numpy(dtype=float))
            & np.isfinite(p["partial_residual_s"].to_numpy(dtype=float)))
    return p[keep].reset_index(drop=True)


def theta_now_draws(panel_fit: pd.DataFrame, plan: E.BootstrapPlan, subset: bool = False) -> np.ndarray:
    """θ_now refitted in every draw on the draw's fit-race multiplicities (A1: over all circuit copies).

    subset False (A4 ruling 4b as written): the panel's fit races must be exactly the plan's fit races.
    subset True (DRAFT amendment A5, only when the owner adopts it): the plan is drawn over an explicit
    fit-race list, and the panel's fit races must lie inside it. A listed race with no panel lap adds no row."""
    races = list(plan.fit_races)
    panel_races = sorted(panel_fit["race_id"].astype(str).unique())
    if subset:
        outside = sorted(set(panel_races) - set(races))
        if outside:
            raise E.EstimatorError(f"θ_now panel races not on the fit-race list (A5): {outside[:3]}")
    elif panel_races != races:
        only_panel = sorted(set(panel_races) - set(races))
        only_plan = sorted(set(races) - set(panel_races))
        raise E.EstimatorError(f"θ_now fit races differ from the curve's fit races (A4 4b): panel only "
                               f"{only_panel[:3]}, plan only {only_plan[:3]}")
    r_idx = pd.Categorical(panel_fit["race_id"].astype(str), categories=races).codes
    w = plan.race_weights()
    return np.array([theta_now_weighted(panel_fit, w[i, r_idx]) for i in range(plan.n_draws)])


# --------------------------------------------------------------------------- §8a: the scored set


def panel_lap_keys(panel: pd.DataFrame) -> pd.DataFrame:
    """Panel rows in the pass table's key names (§2f)."""
    return pd.DataFrame({
        "season": panel["race_year"].astype(int).to_numpy(), "race_id": panel["race_id"].astype(str).to_numpy(),
        "driver": panel["driver_id"].astype(str).to_numpy(), "lap": panel["lap_number"].astype(int).to_numpy(),
    }, index=panel.index)


def step3_trim_reason(panel: pd.DataFrame, kept: pd.Series) -> pd.Series:
    """§8a step 3 (amendment A4 ruling 3): among the laps kept after step 2, regress partial_residual_s on
    stint_id and age_bin indicators once (OLS, weight 1) and give STEP3_REASON to laps with |residual| >
    5 s (strictly). Every other row None. Run once; never inside a bootstrap draw."""
    kept = kept.reindex(panel.index).fillna(False).astype(bool)
    out = pd.Series(None, index=panel.index, dtype=object)
    if kept.sum() < MIN_STEP2_LAPS_FOR_TRIM:
        return out
    sub = panel[kept]
    y = sub["partial_residual_s"].to_numpy(dtype=float)
    if not np.isfinite(y).all():
        raise E.EstimatorError("a step-2 lap has no partial_residual_s")
    r = resid_stint_age(y, sub["stint_id"].to_numpy(), sub["age_bin"].to_numpy())
    out.loc[sub.index[np.abs(r) > STEP3_TRIM_S]] = STEP3_REASON
    return out


def lap_halves(laps: pd.DataFrame, passes: pd.DataFrame) -> pd.DataFrame:
    """§5 per scored lap (laps: season, race_id, driver, lap, stint_id): clean_reference (at least half of the
    braking-corner passes, excluding no_car_ahead, have ref_status measured; a lap with none but no_car_ahead
    passes is clean, A4 ruling 4c), train (no-reference half and median braking-corner gap < 1.5 s with
    no_car_ahead counted as 3 s), mixed (panel stint with >= 2 clean-half and >= 2 train scored laps)."""
    key = ["season", "race_id", "driver", "lap"]
    brk = passes[(passes["segment_basis"] == E.BRAKING_BASIS) & passes["reason"].isna()
                 & (passes["reason_wc03"].isna() | (passes["reason_wc03"] == E.NO_CAR_AHEAD))]
    nca = (brk["reason_wc03"] == E.NO_CAR_AHEAD).to_numpy()
    tmp = pd.DataFrame({
        **{k: brk[k].to_numpy() for k in key},
        "eligible": ~nca,
        "measured": (~nca) & (brk["ref_status"] == "measured").to_numpy(),
        "gap": np.where(nca, NO_CAR_AHEAD_GAP_S, brk["gap_s"].to_numpy(dtype=float)),
    })
    agg = tmp.groupby(key).agg(eligible=("eligible", "sum"), measured=("measured", "sum"),
                               median_gap=("gap", "median"))
    t = laps[key + ["stint_id"]].join(agg, on=key)
    if t["eligible"].isna().any():
        raise E.EstimatorError("a scored lap has no braking-corner pass")
    clean = t["measured"].to_numpy() >= 0.5 * t["eligible"].to_numpy()
    train = ~clean & (t["median_gap"].to_numpy(dtype=float) < TRAIN_MEDIAN_GAP_S)
    st = pd.DataFrame({"stint_id": t["stint_id"].to_numpy(), "c": clean, "t": train})
    per = st.groupby("stint_id").agg(c=("c", "sum"), t=("t", "sum"))
    mixed_stint = (per["c"] >= 2) & (per["t"] >= 2)
    mixed = st["stint_id"].map(mixed_stint).to_numpy(dtype=bool)
    return pd.DataFrame({"clean_reference": clean, "train": train, "mixed": mixed,
                         "median_gap_s": t["median_gap"].to_numpy(dtype=float)}, index=laps.index)


@dataclass
class ScoredSet:
    laps: pd.DataFrame  # scored laps: panel columns + season/race_id/driver/lap + x_flat, x_now + halves
    drops: pd.DataFrame  # §8a step 5 counts: step, reason, laps
    reasons: pd.DataFrame  # per panel row: the reason at each step (None = passed it)


def scored_set(panel: pd.DataFrame, passes: pd.DataFrame, theta_now_point: float, era: str = "main") -> ScoredSet:
    """§8a steps 1-5 on the era's held-out laps, once, in order (A3 for steps 1, 4, 5; A4 for step 3).

    panel: yardstick-panel rows with race_year, race_id, driver_id, lap_number, stint_id, age_bin,
    partial_residual_s, dirty_air_tax_s (x_flat, the shipped value; NULL stays NULL), dirty_air_share_lap
    (unfilled). passes: prepared pass rows (estimator.prepare_passes). The scored set is frozen here and not
    recomputed inside bootstrap draws (§8a)."""
    held = E.ERAS[era]["held_out"]
    p = panel[panel["race_year"].astype(int) == held].copy()
    if p.empty:
        raise E.EstimatorError(f"no {held} panel laps")
    pass_rows = passes[passes["season"].astype(int) == held]
    keys = panel_lap_keys(p)
    p[["season", "race_id_k", "driver", "lap"]] = keys[["season", "race_id", "driver", "lap"]].to_numpy()
    step1 = E.lap_step1_reason(p, pass_rows)
    laps2 = keys.copy()
    laps2["x_flat"] = p["dirty_air_tax_s"].to_numpy(dtype=float)
    laps2["x_now"] = E.flat_now(p["dirty_air_share_lap"].to_numpy(dtype=float), theta_now_point)
    at2 = step1.isna()
    step2 = pd.Series(None, index=p.index, dtype=object)
    if at2.any():
        step2.loc[at2] = E.lap_drop_reason(laps2[at2], pass_rows).to_numpy()
    kept2 = at2 & step2.isna()
    step3 = step3_trim_reason(p, kept2)
    kept3 = kept2 & step3.isna()
    step4 = E.short_stint_reason(p, kept3)
    kept = kept3 & step4.isna()
    reasons = pd.DataFrame({"step_1": step1, "step_2": step2, "step_3": step3, "step_4": step4})
    drops = E.lap_drop_counts({"step_1": step1, "step_2": step2, "step_3": step3, "step_4": step4})
    laps = p[kept].copy()
    laps["season"], laps["driver"], laps["lap"] = laps["season"].astype(int), laps["driver"].astype(str), \
        laps["lap"].astype(int)
    laps["race_id"] = laps["race_id"].astype(str)
    laps["x_flat"] = laps2.loc[kept, "x_flat"].to_numpy()
    laps["x_now_point"] = laps2.loc[kept, "x_now"].to_numpy()
    halves = lap_halves(laps, pass_rows)
    laps = laps.join(halves)
    return ScoredSet(laps=laps.drop(columns=["race_id_k"]).reset_index(drop=True), drops=drops, reasons=reasons)


# --------------------------------------------------------------------------- measured cost as a linear map (§6, §7)


def lap_design(laps: pd.DataFrame, passes: pd.DataFrame) -> np.ndarray:
    """laps x (classes x bins): for each scored lap, the §7 weight summed per (corner class, gap bin), so the
    lap's measured cost under curve c (classes x bins) is design @ c.ravel(). Applies §6: gap >= 3.0 and
    no_car_ahead give 0 (no entry), gap < 0 takes the first bin. Equal to estimator.lap_measured_cost for
    any curve (test_lap_design_matches_lap_measured_cost)."""
    key = ["season", "race_id", "driver", "lap"]
    n_c = len(E.CORNER_CLASSES)
    out = np.zeros((len(laps), n_c * E.N_BINS))
    brk = passes[passes["segment_basis"] == E.BRAKING_BASIS]
    groups = {k: g for k, g in brk.groupby(key)}
    c_of = {c: i for i, c in enumerate(E.CORNER_CLASSES)}
    for i, k in enumerate(laps[key].itertuples(index=False, name=None)):
        g = groups.get(tuple(k))
        if g is None:
            raise E.EstimatorError(f"scored lap {k} has no braking-corner pass")
        w = E.lap_weights(g["seg_start_t"], g["seg_end_t"], g["corner_number"])
        if w is None:
            raise E.EstimatorError(f"scored lap {k} fails §7 step 5; it should not have been scored")
        nca = (g["reason_wc03"] == E.NO_CAR_AHEAD).to_numpy()
        gap = g["gap_s"].to_numpy(dtype=float)
        for wk, cls, gp, nc in zip(w, g["corner_class"], gap, nca):
            if nc:
                continue
            if not np.isfinite(gp):
                raise E.EstimatorError(f"scored lap {k}: a following corner with no gap")
            if gp >= E.FOLLOW_MAX_GAP_S:
                continue
            b = 0 if gp < 0 else int(E.gap_bin(np.array([gp]))[0])
            out[i, c_of[cls] * E.N_BINS + b] += wk
    return out


def curve_array(table: pd.DataFrame) -> np.ndarray:
    """classes x bins point estimates from a curve table (CORNER_CLASSES order)."""
    t = table.set_index(["corner_class", "bin"])["estimate_s"]
    return np.array([[t[(c, b)] for b in range(E.N_BINS)] for c in E.CORNER_CLASSES], dtype=float)


# --------------------------------------------------------------------------- §8b score, point and per draw


def set_masks(laps: pd.DataFrame) -> dict[str, np.ndarray]:
    clean = laps["clean_reference"].to_numpy(dtype=bool)
    return {SET_ALL: np.ones(len(laps), dtype=bool), SET_CLEAN: clean, SET_NOREF: ~clean,
            SET_TRAIN: laps["train"].to_numpy(dtype=bool), SET_MIXED: laps["mixed"].to_numpy(dtype=bool)}


def score(y: np.ndarray, x: dict[str, np.ndarray], stint: np.ndarray, age: np.ndarray,
          masks: dict[str, np.ndarray], weight: np.ndarray | None = None) -> dict[str, dict[str, float]]:
    """§8b with frequency weights: r_c = residual of (y - x_c) on stint and age-bin indicators over all laps
    with weight > 0; MSE_c(S) = weighted mean of r_c^2 over S; R_flat, R_now. NaN where S has no weight."""
    names = list(x)
    xx = np.column_stack([np.asarray(x[c], dtype=float) for c in names])
    w = np.ones(len(y)) if weight is None else np.asarray(weight, dtype=float)
    if not np.isfinite(xx[w > 0]).all():
        raise E.EstimatorError("a scored lap has an unknown candidate cost; it should not have been scored")
    r = resid_stint_age(np.asarray(y, dtype=float)[:, None] - xx, stint, age, w)
    out = {}
    for s, m in masks.items():
        mw = w * np.asarray(m, dtype=bool)
        tot = mw.sum()
        mse = {c: (float(np.nansum(mw * r[:, i] ** 2) / tot) if tot > 0 else np.nan) for i, c in enumerate(names)}
        row = {f"mse_{c}": v for c, v in mse.items()}
        row["laps"] = float(tot)
        row["r_flat"] = 1.0 - mse["measured"] / mse["flat"] if tot > 0 else np.nan
        row["r_now"] = 1.0 - mse["measured"] / mse["now"] if tot > 0 else np.nan
        if "none" in mse:
            for c in names:
                row[f"gain_{c}"] = 1.0 - mse[c] / mse["none"] if tot > 0 else np.nan
        out[s] = row
    return out


@dataclass
class ContestResult:
    point: dict  # set -> row (MSEs, R_flat, R_now, gains, laps)
    r_flat_draws: dict  # set -> B values
    r_now_draws: dict
    theta_point: float
    theta_draws: np.ndarray
    races: dict = field(default_factory=dict)  # set -> distinct races in the point set


def run_contest(laps: pd.DataFrame, design: np.ndarray, curve_point: np.ndarray, curve_draws: np.ndarray,
                theta_point: float, theta_draws: np.ndarray, plan: E.BootstrapPlan) -> ContestResult:
    """The point contest and its B draws (§8b, §8c). In draw i: the curve is curve_draws[i], θ_now is
    theta_draws[i], and the held-out laps carry their race's multiplicity plan.held_idx[i] (A4 4a). The
    shipped flat penalty is never re-estimated. The scored set is the frozen one."""
    y = laps["partial_residual_s"].to_numpy(dtype=float)
    share = laps["dirty_air_share_lap"].to_numpy(dtype=float)
    stint, age = laps["stint_id"].to_numpy(), laps["age_bin"].to_numpy()
    masks = set_masks(laps)
    x_flat = laps["x_flat"].to_numpy(dtype=float)

    def candidates(curve, theta):
        return {"none": np.zeros(len(y)), "flat": x_flat, "now": E.flat_now(share, theta),
                "measured": design @ np.asarray(curve, dtype=float).ravel()}

    point = score(y, candidates(curve_point, theta_point), stint, age, masks)
    held = list(plan.held_out_races)
    r_idx = pd.Categorical(laps["race_id"].astype(str), categories=held).codes
    if (r_idx < 0).any():
        raise E.EstimatorError("a scored lap's race is not in the plan's held-out list")
    rf = {s: np.empty(plan.n_draws) for s in masks}
    rn = {s: np.empty(plan.n_draws) for s in masks}
    for i in range(plan.n_draws):
        hw = np.bincount(plan.held_idx[i], minlength=len(held)).astype(float)[r_idx]
        sc = score(y, candidates(curve_draws[i], theta_draws[i]), stint, age, masks, hw)
        for s in masks:
            rf[s][i], rn[s][i] = sc[s]["r_flat"], sc[s]["r_now"]
    races = {s: int(laps.loc[m, "race_id"].nunique()) for s, m in masks.items()}
    return ContestResult(point=point, r_flat_draws=rf, r_now_draws=rn, theta_point=theta_point,
                         theta_draws=np.asarray(theta_draws), races=races)


# --------------------------------------------------------------------------- W1-W3, G5, G7, the verdict


@dataclass
class Check:
    name: str
    passed: bool | None  # None = cannot be assessed (no verdict)
    rule: str
    value: str
    reason: str = ""


def _lower(draws: np.ndarray) -> float:
    d = np.asarray(draws, dtype=float)
    return float(np.percentile(d, E.CI_PERCENTILES[0])) if np.isfinite(d).all() else np.nan


def _upper(draws: np.ndarray) -> float:
    d = np.asarray(draws, dtype=float)
    return float(np.percentile(d, E.CI_PERCENTILES[1])) if np.isfinite(d).all() else np.nan


def fmt(v: float, nd: int = 4, reason: str = "not computable") -> str:
    return f"{v:.{nd}f}" if np.isfinite(v) else f"{UNAVAILABLE} ({reason})"


def w1(res: ContestResult) -> Check:
    lf, ln = _lower(res.r_flat_draws[SET_ALL]), _lower(res.r_now_draws[SET_ALL])
    value = f"R_flat lower {fmt(lf)}; R_now lower {fmt(ln)}"
    if not (np.isfinite(lf) and np.isfinite(ln)):
        return Check("W1", None, "lower 95 % ends of R_flat and R_now >= 0.005", value,
                     "undefined in some draw (A4 4d)")
    return Check("W1", bool(lf >= W1_MARGIN and ln >= W1_MARGIN), "lower 95 % ends of R_flat and R_now >= 0.005",
                 value)


def w2(res: ContestResult) -> Check:
    pt = res.point[SET_TRAIN]["r_flat"]
    lo = _lower(res.r_flat_draws[SET_TRAIN])
    value = f"train R_flat point {fmt(pt)}, lower {fmt(lo)}"
    if not (np.isfinite(pt) and np.isfinite(lo)):
        return Check("W2", None, "train laps: R_flat point >= 0 and lower >= -0.005", value,
                     "undefined in the point or some draw (A4 4d)")
    return Check("W2", bool(pt >= 0.0 and lo >= W2_LOWER), "train laps: R_flat point >= 0 and lower >= -0.005", value)


def p1(main_point: np.ndarray, main_draws: np.ndarray) -> Check:
    """§10 P1, every corner class: near > 0; |far| <= 0.25 near (point); lower 95 % end of near - far > 0."""
    parts, ok = [], True
    for c, cls in enumerate(E.CORNER_CLASSES):
        near, far = main_point[c, list(NEAR_BINS)].mean(), main_point[c, list(FAR_BINS)].mean()
        diff = main_draws[:, c, list(NEAR_BINS)].mean(1) - main_draws[:, c, list(FAR_BINS)].mean(1)
        lo = _lower(diff)
        if not (np.isfinite(near) and np.isfinite(far) and np.isfinite(lo)):
            return Check("P1", None, "near > 0, |far| <= 0.25 near, lower(near - far) > 0, every class",
                         f"{cls}: not computable", "main curve not estimable (G7)")
        good = near > 0 and abs(far) <= P1_FAR_SHARE * near and lo > 0
        ok &= bool(good)
        parts.append(f"{cls}: near {near:.4f}, far {far:.4f}, lower(near-far) {lo:.4f}")
    return Check("P1", ok, "near > 0, |far| <= 0.25 near, lower(near - far) > 0, every class", "; ".join(parts))


def p2(dirty_point: np.ndarray, dirty_draws: np.ndarray) -> Check:
    """§10 P2 on the dirty-air class curve: the 95 % interval of fast - slow at 0.5-1.0 s must not lie wholly
    below zero (pass iff its upper end >= 0)."""
    f, s = E.CORNER_CLASSES.index("fast"), E.CORNER_CLASSES.index("slow")
    nb = list(NEAR_BINS)
    pt = dirty_point[f, nb].mean() - dirty_point[s, nb].mean()
    d = dirty_draws[:, f, nb].mean(1) - dirty_draws[:, s, nb].mean(1)
    lo, hi = _lower(d), _upper(d)
    value = f"fast - slow {fmt(pt)} [{fmt(lo)}, {fmt(hi)}]"
    if not (np.isfinite(pt) and np.isfinite(hi)):
        return Check("P2", None, "95 % interval of fast - slow not wholly below 0", value,
                     "dirty-air curve not estimable in fast or slow (G7)")
    return Check("P2", bool(hi >= 0.0), "95 % interval of fast - slow not wholly below 0", value)


def w3(c1: Check, c2: Check) -> Check:
    if c1.passed is None or c2.passed is None:
        return Check("W3", None, "P1 and P2 pass", f"P1 {c1.passed}, P2 {c2.passed}", "P1 or P2 not assessable")
    return Check("W3", c1.passed and c2.passed, "P1 and P2 pass", f"P1 {c1.passed}, P2 {c2.passed}")


def g7_curve_identified(main_table: pd.DataFrame, dirty_table: pd.DataFrame) -> Check:
    """Amendment A4 ruling 1: every bin of the main curve (all classes) and of the dirty-air class curve (fast
    and slow) has a fit pass in the point fit and in all B draws."""
    bad = []
    for name, t, classes in (("main", main_table, E.CORNER_CLASSES), ("dirty_air", dirty_table, ("fast", "slow"))):
        for cls in classes:
            g = t[t["corner_class"] == cls]
            if (g["status"] != E.CURVE_OK).any():
                bad.append(f"{name}/{cls}: point empty bins [{g['point_empty_bins'].iloc[0]}], "
                           f"{int(g['empty_bin_draws'].iloc[0])} of {int(g['n_draws'].iloc[0])} draws with an empty bin")
    return Check("G7", not bad, "every bin of the main curve and of the fast/slow dirty-air curve has a fit pass, "
                 "point fit and every draw", "; ".join(bad) or "all identified")


def g5_minimums(res: ContestResult | None, laps: pd.DataFrame, fit_races: int, held_races_scored: int,
                era: str = "main") -> Check:
    """G5: >= 1,000 laps and >= 18 races in the whole field, the clean-reference half and the train laps;
    main era also >= 60 fit races and >= 20 held-out races contributing (§8c)."""
    masks = set_masks(laps)
    short = []
    for s in MINIMUM_SETS:
        n, r = int(masks[s].sum()), int(laps.loc[masks[s], "race_id"].nunique())
        if n < CONTEST_MIN_LAPS or r < CONTEST_MIN_RACES:
            short.append(f"{s}: {n} laps, {r} races")
    if era == "main":
        if fit_races < E.MIN_FIT_RACES:
            short.append(f"fit races {fit_races} < {E.MIN_FIT_RACES}")
        if held_races_scored < E.MIN_HELD_OUT_RACES:
            short.append(f"held-out races with scored laps {held_races_scored} < {E.MIN_HELD_OUT_RACES}")
    return Check("G5", not short, ">= 1,000 laps and >= 18 races per set; >= 60 fit and >= 20 held-out races",
                 "; ".join(short) or "all met")


def verdict(setup: list[Check], c_w1: Check | None, c_w2: Check | None, c_w3: Check | None) -> tuple[str, str]:
    """§9, read top to bottom (A4 4e). Returns (code, the scorecard's first line)."""
    failed = [c for c in setup if c.passed is not True]
    undefined = [c for c in (c_w1, c_w2, c_w3) if c is None or c.passed is None]
    if failed or undefined:
        why = "; ".join([f"{c.name} failed: {c.value}" for c in failed]
                        + [f"{c.name if c else 'a W check'} not assessable: {c.reason if c else 'not run'}"
                           for c in undefined])
        return NO_VERDICT, f"{VERDICT_TEXT[NO_VERDICT]} {why}"
    if c_w1.passed and c_w2.passed and c_w3.passed:
        return REPLACE, VERDICT_TEXT[REPLACE]
    if c_w1.passed and c_w3.passed and not c_w2.passed:
        return KEEP_AND_SHOW, VERDICT_TEXT[KEEP_AND_SHOW]
    if not c_w1.passed:
        return KEEP_AND_STOP, VERDICT_TEXT[KEEP_AND_STOP] + " (W1 failed.)"
    return KEEP_AND_STOP, VERDICT_TEXT[KEEP_AND_STOP] + " (W3 failed.)"


# --------------------------------------------------------------------------- the whole chain on one era


@dataclass
class EraResult:
    era: str
    main_table: pd.DataFrame
    dirty_table: pd.DataFrame
    held_up_table: pd.DataFrame
    contest: ContestResult | None
    scored: ScoredSet | None
    checks: list[Check]
    verdict_code: str
    verdict_line: str
    # Kept for the report-only Table 2 (pit-stop figure, per-team contest, under attack); never verdict inputs.
    main_draws: np.ndarray | None = None
    plan: E.BootstrapPlan | None = None
    p1: Check | None = None
    p2: Check | None = None
    under_attack: pd.DataFrame | None = None
    design: np.ndarray | None = None


def fit_race_list(prepared: pd.DataFrame, panel: pd.DataFrame, race_circuit: dict[str, str], era: str = "main",
                  option: str = "union") -> tuple[list[str], dict[str, str]]:
    """DRAFT amendment A5 (not in force until the owner adopts it): the era's fit-race list and each race's
    circuit. "union" (option a): every fit-season race with a pass-table row or a panel row. "built" (option
    b): every fit-season race with a pass-table row. `race_circuit` maps race_id -> §6 circuit key (from the
    race calendar) and must cover every listed race."""
    seasons = E.ERAS[era]["fit"]
    built = set(prepared.loc[prepared["season"].astype(int).isin(seasons), "race_key"].astype(str))
    in_panel = set(panel.loc[panel["race_year"].astype(int).isin(seasons), "race_id"].astype(str))
    if option == "union":
        races = sorted(built | in_panel)
    elif option == "built":
        races = sorted(built)
    else:
        raise E.EstimatorError(f"unknown A5 option {option!r}")
    missing = [r for r in races if r not in race_circuit]
    if missing:
        raise E.EstimatorError(f"no circuit for listed fit race(s) {missing[:3]} (A5)")
    return races, {r: str(race_circuit[r]) for r in races}


def run_era(prepared: pd.DataFrame, panel: pd.DataFrame, held_out_races: list[str], era: str = "main",
            n_draws: int = E.N_BOOT, seed: int = E.SEED, setup_checks: list[Check] | None = None,
            fit_races: list[str] | None = None, race_circuit: dict[str, str] | None = None) -> EraResult:
    """Curve, class curves, θ_now, scored set, contest and verdict for one era, in that order, with one plan
    (A1) for every draw. `setup_checks` are the checks run before this (G1-G4, G6) by the caller; a failed one
    is carried to the verdict. Nothing here reads or writes a file.

    fit_races None: the plan is drawn over the races that contribute fit passes and θ_now's panel races must
    equal them (A4 ruling 4b as written). fit_races given (DRAFT amendment A5, only once adopted): the plan
    is drawn over that list with `race_circuit` for every listed race; fit passes and θ_now's panel races
    must lie inside it."""
    setup = list(setup_checks or [])
    fit = E.fit_passes(prepared, era)
    if fit_races is None:
        plan = E.resample_plan(sorted(fit["race_key"].unique()), E.race_circuits(fit), list(held_out_races),
                               n_draws=n_draws, seed=seed)
    else:
        outside = sorted(set(fit["race_key"].astype(str)) - set(fit_races))
        if outside:
            raise E.EstimatorError(f"fit passes from races not on the fit-race list (A5): {outside[:3]}")
        own = E.race_circuits(fit) if len(fit) else {}
        bad = sorted(r for r, c in own.items() if race_circuit.get(r) != c)
        if bad:
            raise E.EstimatorError(f"fit-race list circuit differs from the passes' circuit (A5): {bad[:3]}")
        plan = E.resample_plan(list(fit_races), race_circuit, list(held_out_races), n_draws=n_draws, seed=seed)
    main_table, main_draws = E.curve_with_intervals(fit, plan, role="main")
    classes = E.class_curves_with_intervals(fit, plan)
    dirty_table, dirty_draws = classes[E.DIRTY_AIR]
    held_table, _ = classes[E.HELD_UP]
    under = E.under_attack_difference(fit, plan) if len(fit) else None
    g7 = g7_curve_identified(main_table, dirty_table)
    setup.append(g7)
    if not g7.passed:
        code, line = verdict(setup, None, None, None)
        return EraResult(era, main_table, dirty_table, held_table, None, None, setup, code, line,
                         main_draws=main_draws, plan=plan, under_attack=under)
    panel_fit = theta_fit_rows(panel, era)
    theta_pt = theta_now_weighted(panel_fit)
    theta_dr = theta_now_draws(panel_fit, plan, subset=fit_races is not None)
    scored = scored_set(panel, prepared, theta_pt, era)
    design = lap_design(scored.laps, prepared[prepared["season"].astype(int) == E.ERAS[era]["held_out"]])
    res = run_contest(scored.laps, design, curve_array(main_table), main_draws, theta_pt, theta_dr, plan)
    g5 = g5_minimums(res, scored.laps, E.contributing_fit_races(fit), res.races[SET_ALL], era)
    setup.append(g5)
    c1 = w1(res)
    c2 = w2(res)
    cp1, cp2 = p1(curve_array(main_table), main_draws), p2(curve_array(dirty_table), dirty_draws)
    c3 = w3(cp1, cp2)
    code, line = verdict(setup, c1, c2, c3)
    return EraResult(era, main_table, dirty_table, held_table, res, scored, setup + [c1, c2, c3], code, line,
                     main_draws=main_draws, plan=plan, p1=cp1, p2=cp2, under_attack=under, design=design)


def scorecard(result: EraResult) -> str:
    """SCORECARD.md text (§15): first line the verdict, second the within-stint line, then Table 1."""
    lines = [result.verdict_line, "", WITHIN_STINT_LINE, "",
             "Table 1 (verdict inputs)", "", "| Check | Rule | Result | Pass |", "|---|---|---|---|"]
    for c in result.checks:
        mark = {True: "pass", False: "fail", None: f"{UNAVAILABLE} ({c.reason})"}[c.passed]
        lines.append(f"| {c.name} | {c.rule} | {c.value} | {mark} |")
    if result.contest is not None:
        lines += ["", "Contest (point estimates; context columns never decide the verdict)", "",
                  "| Set | Laps | Races | MSE none | MSE flat | MSE flat-now | MSE measured | R_flat | R_now |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for s in SETS:
            r = result.contest.point[s]
            lines.append(f"| {s} | {int(r['laps'])} | {result.contest.races[s]} | {fmt(r['mse_none'])} | "
                         f"{fmt(r['mse_flat'])} | {fmt(r['mse_now'])} | {fmt(r['mse_measured'])} | "
                         f"{fmt(r['r_flat'], reason='no laps')} | {fmt(r['r_now'], reason='no laps')} |")
    lines += ["", "The flat penalty under test is the shipped 0.331 s per lap. On the 2026-10-28 data its own "
              "procedure returns 0.305 (diagnostic only, not the benchmark; §2e, §12b)."]
    return "\n".join(lines) + "\n"
