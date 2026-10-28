"""
WC-03 / WC-04 §11 pit-stop figure: the comparison group, the adjusted jump, the predicted drop and the race
bootstrap. REPORT ONLY (Table 2 of the scorecard): never pass or fail, never a verdict input.

Rules: pre-registration §11 (wi/WC-03-preregistration-DRAFT.md, SHA-256 518c3348...), amendment A1 (the
curve draws for the predicted drop come from the main plan; the adjusted jump's interval stays race-level),
and the readings in decision record L3 (wi/WC-03-lead-decisions-2026-10-28-DRAFT.md, DRAFT, Opus-delegated).
The events and the raw jump are estimator.pit_stop_events / estimator._pit_jump (G1 iv), unchanged.

SYNTHETIC ONLY; NOT RUN ON REAL DATA (tests/test_pitstop.py). Apart from pit_laps_from_bronze, which reads
bronze lap files when the run calls it, this is a library of pure functions: it reads no file, opens no
warehouse and writes nothing.

Readings beyond L3, fixed here before any real run:
  - "No car ahead" for the predicted drop means `clear_ahead` true, or `reason_wc03 = no_car_ahead` where the
    column exists. §11 uses every braking corner whatever its exclusion reason, and the builder's reason_wc03
    is set only on rows with reason NULL. A post-stop row in clear air on an excluded lap is still priced 0.
  - The comparison pairs of a race are built once, for every lap P within PIT_CELL_LAPS of some event L in
    that race. Each event's cell then takes the pairs with the same band and |P - L| <= 5.
  - The ratio's point value is mean predicted drop / mean adjusted jump over the kept stops. If the mean
    adjusted jump is 0 (point or in any draw), the ratio is "—" (not computable).
"""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from tasks.wake_calibration import estimator as E
from tasks.wake_calibration.estimator import (
    BRAKING_BASIS, CI_PERCENTILES, CORNER_CLASSES, FOLLOW_MAX_GAP_S, N_BINS, N_BOOT, NO_CAR_AHEAD,
    PIT_POST_LAPS, PIT_PRE_LAPS, SEED, gap_bin, pit_outside_reference, pit_stop_events,
)

PIT_BANDS = ((0.0, 0.5), (0.5, 1.0), (1.0, 1.5))  # §11 comparison bands, each [lower, upper)
PIT_CELL_LAPS = 5  # §11: P within 5 laps of L
PIT_MIN_STOPS = 200  # §11 / C14: at least 200 distinct stops after every drop, else "not testable"
PIT_BOOT_STREAM = 11  # L3.5: numpy default_rng([SEED, 11]), separate from the curve plan's stream
PIT_COMPARISON_NO_PIT = range(-2, 3)  # neither car pits in or out on P-2 .. P+2
STOP_DROP_REASONS = ["no_band", "no_comparison", "no_prediction"]
NOT_TESTABLE, OK = "not testable", "ok"
UNAVAILABLE = "—"


def band_of(mean_gap: float) -> int | None:
    """Index into PIT_BANDS, or None (mean gap below 0 or at/after 1.5 s)."""
    for i, (lo, hi) in enumerate(PIT_BANDS):
        if lo <= mean_gap < hi:
            return i
    return None


# --------------------------------------------------------------------------- pit laps from bronze (L3.7)


def pit_laps_from_bronze(bronze: Path, seasons: Iterable[int]) -> pd.DataFrame:
    """One row per (season, race_id, driver, lap) with pit_in = PitInTime not null, pit_out = PitOutTime not
    null, from the bronze race lap files (session= subfolders, e.g. qualifying, skipped)."""
    seasons = {int(s) for s in seasons}
    frames = []
    for f in sorted(glob.glob(str(Path(bronze) / "laps" / "season=*" / "race=*" / "*.parquet"))):
        if "session=" in f:
            continue
        season = int(Path(f).parent.parent.name.split("=", 1)[1])
        if season not in seasons:
            continue
        d = pd.read_parquet(f, columns=["Driver", "LapNumber", "PitInTime", "PitOutTime", "race_id", "season"])
        frames.append(d)
    cols = ["season", "race_id", "driver", "lap", "pit_in", "pit_out"]
    if not frames:
        return pd.DataFrame(columns=cols)
    d = pd.concat(frames, ignore_index=True).dropna(subset=["Driver", "LapNumber"])
    out = pd.DataFrame({
        "season": d["season"].astype(int).to_numpy(), "race_id": d["race_id"].astype(str).to_numpy(),
        "driver": d["Driver"].astype(str).to_numpy(), "lap": d["LapNumber"].astype(int).to_numpy(),
        "pit_in": d["PitInTime"].notna().to_numpy(), "pit_out": d["PitOutTime"].notna().to_numpy(),
    })
    return out.groupby(["season", "race_id", "driver", "lap"], as_index=False)[["pit_in", "pit_out"]].any()[cols]


# --------------------------------------------------------------------------- the jump's rows and the predicted drop


def _jump_rows(g: pd.DataFrame, big_l: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The pre and post rows estimator._pit_jump averages: braking corners with an outside reference and a timed
    pass on both sides of the window (same selection, same order of filters)."""
    ref = pit_outside_reference(g, big_l)
    timed = g[g["seg_time_s"].notna()]
    pre = timed[timed["lap"].isin([big_l + d for d in PIT_PRE_LAPS]) & timed["corner_id"].isin(ref)]
    post = timed[timed["lap"].isin([big_l + d for d in PIT_POST_LAPS]) & timed["corner_id"].isin(ref)]
    both = set(pre["corner_id"]) & set(post["corner_id"])
    return pre[pre["corner_id"].isin(both)], post[post["corner_id"].isin(both)]


def _no_car_ahead(rows: pd.DataFrame) -> np.ndarray:
    nca = np.zeros(len(rows), dtype=bool)
    if "clear_ahead" in rows:
        nca |= rows["clear_ahead"].fillna(False).astype(bool).to_numpy()
    if "reason_wc03" in rows:
        nca |= (rows["reason_wc03"] == NO_CAR_AHEAD).to_numpy()
    return nca


def _price_index(rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool]:
    """(class index, bin index, priced-nonzero mask, ok). §6: no car ahead -> 0; gap >= 3 -> 0; gap < 0 -> the
    first bin; else its bin. ok False when a row with a car ahead has no gap (cannot be priced)."""
    nca = _no_car_ahead(rows)
    gap = rows["gap_s"].to_numpy(dtype=float)
    if (~nca & ~np.isfinite(gap)).any():
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0, bool), False
    cls = pd.Categorical(rows["corner_class"], categories=list(CORNER_CLASSES)).codes
    on = ~nca & (gap < FOLLOW_MAX_GAP_S)
    if (on & (cls < 0)).any():
        raise E.EstimatorError("a priced pit-stop row has an unknown corner class")
    b = np.where(gap < 0, 0, gap_bin(np.where(np.isfinite(gap), gap, 0.0)))
    return cls, b, on, True


def predicted_drop(g_follower: pd.DataFrame, big_l: int, curve: np.ndarray) -> float | np.ndarray:
    """L3.4: the curve at the follower's gaps on L-2, L-1 minus at its gaps on L+1, L+2, over the same rows as
    the event's jump (mean over the pre rows minus mean over the post rows). `curve` is classes x bins, or a
    stack (B x classes x bins) for which an array of B is returned. NaN (or NaN array) when a row with a car
    ahead has no gap, or when the jump has no corner."""
    curve = np.asarray(curve, dtype=float)
    stack = curve.ndim == 3
    nan = np.full(curve.shape[0], np.nan) if stack else np.nan
    pre, post = _jump_rows(g_follower[g_follower["segment_basis"] == BRAKING_BASIS], big_l)
    if pre.empty or post.empty:
        return nan
    total = np.zeros(curve.shape[0]) if stack else 0.0
    for rows, sign in ((pre, 1.0), (post, -1.0)):
        cls, b, on, ok = _price_index(rows)
        if not ok:
            return nan
        vals = curve[..., cls[on], b[on]]  # (B, k) or (k,)
        total = total + sign * vals.sum(axis=-1) / len(rows)
    return total


# --------------------------------------------------------------------------- the comparison group (L3.1-L3.3)


COMPARISON_COLUMNS = ["follower", "leader", "P", "mean_gap_s", "band", "jump_s", "corners"]


def comparison_jumps(passes: pd.DataFrame, pits: pd.DataFrame, race_id: str, season: int,
                     laps_p: set[int]) -> pd.DataFrame:
    """Comparison pairs (F, A, P) in one race, for P in laps_p (L3.1): on P-2 and P-1 F has the same car ahead A
    at every braking corner, lap == leader_lap at each, mean gap in a band; neither F nor A pits in or out on
    P-2..P+2; the jump (estimator._pit_jump at P, outside reference on P-6..P-3, P+3..P+6) has a corner."""
    brk = passes[(passes["segment_basis"] == BRAKING_BASIS) & (passes["season"] == season)
                 & (passes["race_id"] == race_id)]
    p = pits[(pits["season"] == season) & (pits["race_id"] == race_id)]
    pitted = set(map(tuple, p.loc[p["pit_in"].astype(bool) | p["pit_out"].astype(bool), ["driver", "lap"]]
                     .itertuples(index=False, name=None)))
    rows = []
    for f, g in brk.groupby("driver"):
        g_laps = set(g["lap"].astype(int))
        for big_p in sorted(laps_p):
            pre_laps = [big_p + d for d in PIT_PRE_LAPS]
            if not set(pre_laps) <= g_laps:
                continue
            pre = g[g["lap"].isin(pre_laps)]
            leaders = pre["leader"]
            if leaders.isna().any() or leaders.nunique() != 1:
                continue
            a = leaders.iloc[0]
            gaps = pre["gap_s"].to_numpy(dtype=float)
            if not np.isfinite(gaps).all():
                continue
            if (pre["lap"].astype(float) != pre["leader_lap"].astype(float)).any():
                continue
            band = band_of(float(gaps.mean()))
            if band is None:
                continue
            if any((f, big_p + d) in pitted or (a, big_p + d) in pitted for d in PIT_COMPARISON_NO_PIT):
                continue
            jump, n = E._pit_jump(g, big_p)
            if n == 0:
                continue
            rows.append({"follower": f, "leader": a, "P": big_p, "mean_gap_s": float(gaps.mean()), "band": band,
                         "jump_s": jump, "corners": n})
    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS)


# --------------------------------------------------------------------------- the figure and its bootstrap (L3.5, L3.6)


@dataclass
class PitFigure:
    events: pd.DataFrame
    drops: pd.DataFrame  # reason, count
    summary: dict = field(default_factory=dict)

    def table2_rows(self) -> list[dict]:
        """Plain-English rows for Table 2. Reported as figures; unavailable is "—" with a reason."""
        s = self.summary
        rows = [{"item": "pit-stop figure: distinct stops after every drop", "value": str(s["n_stops"])}]
        rows += [{"item": f"pit-stop figure: dropped ({r})", "value": str(int(c))}
                 for r, c in self.drops[["reason", "count"]].itertuples(index=False, name=None)]
        if s["status"] != OK:
            reason = f"{NOT_TESTABLE}: fewer than {PIT_MIN_STOPS} stops"
            for k in ("mean predicted drop (s)", "mean adjusted jump (s)", "predicted drop as share of jump"):
                rows.append({"item": f"pit-stop figure: {k}", "value": f"{UNAVAILABLE} ({reason})"})
            return rows

        def num(v, nd=3):
            return f"{v:.{nd}f}" if v is not None and np.isfinite(v) else None

        def interval(lo, hi, why, nd=3):
            a, b = num(lo, nd), num(hi, nd)
            return f"[{a}, {b}]" if a is not None and b is not None else f"{UNAVAILABLE} ({why})"

        rows.append({"item": "pit-stop figure: mean predicted drop (s)",
                     "value": f"{num(s['mean_predicted_s'])} {interval(s['predicted_ci_lower'], s['predicted_ci_upper'], s.get('predicted_ci_reason', ''))}"})
        rows.append({"item": "pit-stop figure: mean adjusted jump (s)",
                     "value": f"{num(s['mean_adjusted_jump_s'])} {interval(s['adjusted_ci_lower'], s['adjusted_ci_upper'], s.get('adjusted_ci_reason', ''))}"})
        if s["ratio"] is None or not np.isfinite(s["ratio"]):
            rows.append({"item": "pit-stop figure: predicted drop as share of jump",
                         "value": f"{UNAVAILABLE} (mean adjusted jump is 0)"})
        else:
            ci = interval(None if s["ratio_ci_lower"] is None else 100 * s["ratio_ci_lower"],
                          None if s["ratio_ci_upper"] is None else 100 * s["ratio_ci_upper"],
                          s.get("ratio_ci_reason", ""), nd=0)
            rows.append({"item": "pit-stop figure: predicted drop as share of jump",
                         "value": f"predicted drop is {100 * s['ratio']:.0f} % of the observed jump (95 % interval {ci})"})
        return rows


EVENT_COLUMNS = ["season", "race_id", "leader", "pit_lap", "follower", "mean_gap_s", "band", "jump_s",
                 "comparison_jump_s", "n_comparison", "adjusted_jump_s", "predicted_drop_s"]


def _pct(d: np.ndarray) -> tuple[float | None, float | None]:
    if not np.isfinite(d).all():
        return None, None
    lo, hi = np.percentile(d, CI_PERCENTILES)
    return float(lo), float(hi)


def pit_figure(passes: pd.DataFrame, pits: pd.DataFrame, seasons: Iterable[int], curve_point: np.ndarray,
               curve_draws: np.ndarray, n_draws: int = N_BOOT) -> PitFigure:
    """§11 figure on the given seasons against one curve (point: classes x bins; draws: B x classes x bins from
    the main plan, A1). Events and raw jumps from estimator.pit_stop_events; stop-level drops no_band,
    no_comparison, no_prediction (L3.2, L3.4); race bootstrap of the kept stops (L3.5); fewer than 200 stops
    -> "not testable", counts only (L3.6)."""
    seasons = {int(s) for s in seasons}
    curve_draws = np.asarray(curve_draws, dtype=float)
    if curve_draws.shape[0] != n_draws:
        raise E.EstimatorError(f"curve_draws has {curve_draws.shape[0]} draws, expected {n_draws}")
    ps = passes[passes["season"].astype(int).isin(seasons)]
    pt = pits[pits["season"].astype(int).isin(seasons)]
    events, cand_drops = pit_stop_events(ps, pt)
    drops = {r: int(c) for r, c in cand_drops.itertuples(index=False, name=None)}
    drops.update({r: 0 for r in STOP_DROP_REASONS})
    comp_cache: dict[tuple, pd.DataFrame] = {}
    for (season, race_id), ev in events.groupby(["season", "race_id"]):
        laps_p = {int(L) + d for L in ev["pit_lap"] for d in range(-PIT_CELL_LAPS, PIT_CELL_LAPS + 1)}
        comp_cache[(season, race_id)] = comparison_jumps(ps, pt, race_id, season, laps_p)
    by_driver = {k: g for k, g in ps.groupby(["season", "race_id", "driver"])}
    kept, pred_draws = [], []
    for e in events.itertuples(index=False):
        band = band_of(e.mean_gap_s)
        if band is None:
            drops["no_band"] += 1
            continue
        comp = comp_cache[(e.season, e.race_id)]
        cell = comp[(comp["band"] == band) & ((comp["P"] - e.pit_lap).abs() <= PIT_CELL_LAPS)]
        if cell.empty:
            drops["no_comparison"] += 1
            continue
        g = by_driver[(e.season, e.race_id, e.follower)]
        pred = predicted_drop(g, int(e.pit_lap), curve_point)
        if not np.isfinite(pred):
            drops["no_prediction"] += 1
            continue
        cj = float(cell["jump_s"].mean())
        kept.append({"season": e.season, "race_id": e.race_id, "leader": e.leader, "pit_lap": e.pit_lap,
                     "follower": e.follower, "mean_gap_s": e.mean_gap_s, "band": band, "jump_s": e.jump_s,
                     "comparison_jump_s": cj, "n_comparison": len(cell), "adjusted_jump_s": e.jump_s - cj,
                     "predicted_drop_s": float(pred)})
        pred_draws.append(predicted_drop(g, int(e.pit_lap), curve_draws))
    ev_df = pd.DataFrame(kept, columns=EVENT_COLUMNS)
    drops_df = pd.DataFrame([{"reason": r, "count": c} for r, c in drops.items()])
    n = len(ev_df)
    summary = {"n_stops": n, "status": OK if n >= PIT_MIN_STOPS else NOT_TESTABLE, "n_draws": n_draws,
               "mean_predicted_s": None, "predicted_ci_lower": None, "predicted_ci_upper": None,
               "mean_adjusted_jump_s": None, "adjusted_ci_lower": None, "adjusted_ci_upper": None,
               "ratio": None, "ratio_ci_lower": None, "ratio_ci_upper": None}
    if summary["status"] != OK:
        return PitFigure(ev_df, drops_df, summary)
    adj = ev_df["adjusted_jump_s"].to_numpy(dtype=float)
    pred = ev_df["predicted_drop_s"].to_numpy(dtype=float)
    pd_draws = np.stack(pred_draws)  # events x B
    # A draw whose curve is not estimable anywhere (NaN in any cell) gives no predicted drop in that draw, even
    # if no kept stop uses the NaN cell; the interval is then "—", never taken over fewer than B draws.
    pd_draws[:, np.isnan(curve_draws).reshape(n_draws, -1).any(axis=1)] = np.nan
    races = sorted(ev_df["race_id"].astype(str).unique())
    r_idx = pd.Categorical(ev_df["race_id"].astype(str), categories=races).codes
    rng = np.random.default_rng([SEED, PIT_BOOT_STREAM])
    w = np.stack([np.bincount(rng.integers(0, len(races), len(races)), minlength=len(races))[r_idx]
                  for _ in range(n_draws)]).astype(float)  # B x events
    ws = w.sum(1)
    adj_d = (w @ adj) / ws
    pred_d = np.einsum("be,eb->b", w, pd_draws) / ws
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio_d = np.where(adj_d != 0, pred_d / adj_d, np.nan)
    m_adj, m_pred = float(adj.mean()), float(pred.mean())
    summary.update({"mean_predicted_s": m_pred, "mean_adjusted_jump_s": m_adj,
                    "ratio": m_pred / m_adj if m_adj != 0 else None})
    summary["adjusted_ci_lower"], summary["adjusted_ci_upper"] = _pct(adj_d)
    summary["predicted_ci_lower"], summary["predicted_ci_upper"] = _pct(pred_d)
    summary["ratio_ci_lower"], summary["ratio_ci_upper"] = _pct(ratio_d)
    if summary["predicted_ci_lower"] is None:
        summary["predicted_ci_reason"] = "not computable: a curve draw is not estimable"
    if summary["ratio_ci_lower"] is None:
        summary["ratio_ci_reason"] = ("not computable: a curve draw is not estimable"
                                      if summary["predicted_ci_lower"] is None
                                      else "not computable: mean adjusted jump is 0 in some draw")
    return PitFigure(ev_df, drops_df, summary)
