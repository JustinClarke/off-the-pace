"""
WC-10e diagnostics X1-X15 (registration §12) and the per-lap scores (§13 item 7).

Rules come from the signed discovery registration, wi/WC-10-discovery-preregistration-DRAFT.md (commit 6fd0330,
DD-WC20). THIS HAS NOT BEEN RUN ON REAL DATA. Library only: opens no file, writes nothing.

Every diagnostic is labelled DIAGNOSTIC, moves no level, cut point or go/no-go line, and uses draws 1-200 of the
registered plan (§10, CHOICE D3): `diag_plan` keeps the first 200 rows of design_a.bootstrap_plan. X1-X15 run on
the time-model structure sets (§6a) except X14, which refits step 1. Each statistic is a flat key
"X<n>|<class>|<subset>|<stat>"; keys holding a count contain "|n_" and get no interval.

Mandatory companion (§8a): "every table that shows a near-band, far-band or aero-contrast value shows its
bracketed value beside it". Diagnostics that show a near band therefore carry `brk_near` / `brk_far` (the §8a
interpolated local baseline, tau-loc, on the same subset), except X15 (it is the lap-arm bracketed comparison).

Per-lap scores use all draws of the plan (80 % percentile interval, §10). They need `seg_start_t` / `seg_end_t`
(the WC-03 §7 weights), which wc10_io treats as outcome-equivalent columns: in the real run they exist only after
RUN START.

Open choices: the three diagnostics choices are ruled by the owner (RULED_CHOICES below: x1_trim =
registered_tau, modal_leader_tie = drop, fallback_negative_median = bin_0.3-0.5). The code implements only the
ruled values: choice() raises OpenChoiceError for None (when the case occurs) and for any other value, and
preflight() refuses RUN START unless all eight choices (these three and design_a's five) are set to their rulings.
The five design_a choices are ruled (design_a.RULED_CHOICES) and applied here as there: racecraft free passes
dropped, disconnected predictions dropped, undefined draws propagate (an interval with an undefined draw is
undefined), every entry of a race in a draw is a separate copy.

Amendment B2 (DD-WC23) is applied here as in design_a and lap_arm: rows without tyre_life do not enter any step 1
(X5 free sets, X14 refit via the time free set, the lap step 1 for X6 / X15), and following rows without it are
counted under drops["tyre_life_missing"].
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tasks.wake_calibration import design_a as A
from tasks.wake_calibration import estimator as E
from tasks.wake_calibration import lap_arm as L

TIME, MINSPEED, EXIT = A.TIME, A.MINSPEED, "exit_speed_kph"
COAST, THROTTLE = "coast_time_s", "partial_throttle_share"
DIAG_DRAWS = 200  # §10: diagnostics use draws 1-200
COAST_CAP_S = 10.0  # §7 CHOICE D15: values > 10.0 s -> null (coast_implausible)
X5_TRIM = {COAST: 3.0, THROTTLE: 0.5}  # §6e: X5 free-pass and effect trims
X5_SIGN = {COAST: 1.0, THROTTLE: 1.0}  # §6e: only the speeds are sign-flipped
COVERAGE_FLOOR = 0.70  # §7
X1_WINDOWS = (4, 8)
X1_MIN_FREE = 2
X3_FLAG = "catching sensitivity large"
X6_FOLLOWING_MED_S = 1.5  # §8f lap state
X6_CLEAR_FILL_S = 30.0
X13_TRAIN_GAP_S = 1.0
X14_WASHOUT_LAPS = 3
X15_BRACKET_LAPS = 5
SCORE_CI = A.CI80
DIAGNOSTIC = "DIAGNOSTIC"

RULED_CHOICES: dict[str, str] = {
    # X1 (§12): "alpha replaced, per following pass, by the mean ... over the group's free passes within +-W laps".
    # §6f (ii) trims |tau| > 2.0 s; §8a says the bracketed set is trimmed once on the group-alpha tau. X1 does not
    # say which tau the trim uses. Owner ruling "registered_tau": the pass enters X1 only if it entered beta (trim
    # on the group-alpha tau). Any other value (e.g. "own_tau") is rejected, never silently applied.
    "x1_trim": "registered_tau",
    # X6 (§8f): "L's modal leader". When two leaders tie for the mode on lap L, the registration (and r03, which used
    # duckdb mode()) does not say which is taken. Owner ruling "drop": such a lap is not an X6 event; the tie count
    # is reported (X6 counts, summary). The 2022 / 2023 recount (39 / 48) must still be reproduced, or X6 refuses.
    "modal_leader_tie": "drop",
    # §13 item 7 under FALLBACK: S_pace = beta_lap(the lap's median-gap bin). A score lap may hold racecraft corners
    # with gap_s < 0, so its median gap can be negative, which has no bin. Owner ruling "bin_0.3-0.5": price it at
    # the 0.3-0.5 s value (as racecraft gap < 0 is priced in design A).
    "fallback_negative_median": "bin_0.3-0.5",
}
OPEN_CHOICES: dict[str, str | None] = dict(RULED_CHOICES)


class OpenChoiceError(A.EstimatorError):
    """An open choice is unset (the case occurs) or not the owner's ruling (the only value implemented)."""


def choice(name: str, occurs: bool = True, detail: str = "") -> str | None:
    v = OPEN_CHOICES[name]
    if occurs and v is None:
        raise OpenChoiceError(f"open choice {name!r} (diagnostics) is not set and the case occurs"
                                f"{': ' + detail if detail else ''}")
    if v is not None and v != RULED_CHOICES[name]:
        raise OpenChoiceError(f"open choice {name!r} = {v!r} rejected: only the owner's ruling "
                                f"{RULED_CHOICES[name]!r} is implemented")
    return v


def preflight() -> None:
    """Refuse RUN START unless all eight open choices are set to the owner's rulings: design_a's five
    (design_a.preflight) and the three diagnostics choices here. The real run calls this before RUN START."""
    A.preflight()
    unset = sorted(k for k in RULED_CHOICES if OPEN_CHOICES.get(k) is None)
    if unset:
        raise OpenChoiceError(f"RUN START refused: diagnostics open choice(s) not set: {unset}")
    other = sorted(k for k in RULED_CHOICES if OPEN_CHOICES[k] != RULED_CHOICES[k])
    if other:
        raise OpenChoiceError(f"RUN START refused: diagnostics open choice(s) differ from the owner's ruling: {other}")


def diag_plan(plan: A.Plan, n: int = DIAG_DRAWS) -> A.Plan:
    """§10: draws 1-200 of the same plan."""
    return A.Plan(weights=plan.weights[:n])


def cap_coast(coast: pd.Series) -> tuple[pd.Series, int]:
    """§7: coast_time_s > 10.0 s set to null (coast_implausible); returns (capped, count). Outcome-derived count."""
    v = coast.astype(float)
    bad = v > COAST_CAP_S
    return v.where(~bad), int(bad.sum())


# --------------------------------------------------------------------------- per-draw pass quantities


@dataclass
class ClassDraw:
    wr: np.ndarray
    lab: np.ndarray
    gamma: float
    sigma: float
    delta: np.ndarray  # Delta-hat (time, §6h); NaN where the class is not known
    tau: dict
    keep: dict
    tloc: dict
    lk: dict


def class_draws(model: A.Model, w: np.ndarray | None = None) -> dict:
    """The per-pass quantities design_a.draw_stats uses, for one race weighting (same formulas)."""
    w = np.ones(A.N_RACES) if w is None else np.asarray(w, dtype=float)
    out = {}
    for k, cm in model.classes.items():
        wr = w[cm.ft["race_idx"].to_numpy()]
        gt = cm.step1[TIME].gamma(w)
        sg = cm.step1[TIME].sigma(w, gt)
        lab = cm.cls.labels(gt, sg)
        delta = np.where(cm.cls.known, cm.cls.dy - gt * cm.cls.dx + gt * cm.cls.db, np.nan)
        tau, keep, tloc, lk = {}, {}, {}, {}
        for o, ef in cm.eff.items():
            g = gt if o == TIME else cm.step1[o].gamma(w)
            tau[o] = ef.A + g * ef.B
            tloc[o] = ef.Aloc + g * ef.Bloc
            with np.errstate(invalid="ignore"):
                keep[o] = ef.valid & (np.abs(tau[o]) <= A.TRIM_EFFECT[o])
            lk[o] = keep[o] & ef.loc_ok
        out[k] = ClassDraw(wr=wr, lab=lab, gamma=gt, sigma=sg, delta=delta, tau=tau, keep=keep, tloc=tloc, lk=lk)
    return out


def _nf(out: dict, prefix: str, tau, bins, m, wr, tloc=None, lk=None, beta_key: bool = False) -> None:
    """Near, far, near - far and the near-band count of `tau` on mask m; with the §8a bracketed companion."""
    b = np.clip(bins, 0, None)
    beta = A._bin_means(np.where(m, tau, 0.0), b, wr * m)
    near, far = A._near(beta), A._far(beta)
    out[f"{prefix}|near"], out[f"{prefix}|far"], out[f"{prefix}|near-far"] = near, far, near - far
    nb = np.isin(bins, A.NEAR_BINS)
    out[f"{prefix}|n_near"] = float((wr * (m & nb)).sum())
    if beta_key:
        for i in range(A.N_BINS):
            out[f"{prefix}|bin{i}"] = float(beta[i])
            out[f"{prefix}|n_bin{i}"] = float((wr * (m & (bins == i))).sum())
    if tloc is not None:
        mb = m & lk
        bb = A._bin_means(np.where(mb, tloc, 0.0), b, wr * mb)
        out[f"{prefix}|brk_near"], out[f"{prefix}|brk_far"] = A._near(bb), A._far(bb)
        out[f"{prefix}|n_brk_near"] = float((wr * (mb & nb)).sum())


def _contrast(out: dict, prefix: str, near_key) -> None:
    """Aero contrasts fast - slow and medium - slow from per-class keys near_key(k) (and their brk companions)."""
    for a, b in (("fast", "slow"), ("medium", "slow")):
        for s in ("near", "brk_near"):
            ka, kb = near_key(a, s), near_key(b, s)
            if ka in out and kb in out:
                out[f"{prefix}|{a}-{b}|{s}"] = out[ka] - out[kb]


# --------------------------------------------------------------------------- context (fixed per run)


@dataclass
class Context:
    model: A.Model
    y: dict
    x1: dict = field(default_factory=dict)  # (k, W) -> (A, B, ok, counts)
    x5: dict = field(default_factory=dict)  # (o, k) -> dict
    x5_meta: dict = field(default_factory=dict)
    x13: dict = field(default_factory=dict)  # k -> bool tag per ft row
    x11: dict = field(default_factory=dict)  # k -> team per ft row
    x14: dict = field(default_factory=dict)  # k -> (Step1, Effects)
    x14_meta: dict = field(default_factory=dict)
    lap: object = None  # LapStep1
    release: object = None  # ReleaseEvents
    exit_coverage: dict = field(default_factory=dict)


def _free_x(p: pd.DataFrame, y: pd.Series, limit: float) -> np.ndarray:
    """Free passes for an X5 outcome: as design_a.free_set (racecraft free passes dropped, ruling 1; free passes
    without tyre_life dropped, B2), with the X5 trim (§6e)."""
    yv = y.to_numpy(dtype=float)
    base = p["free"].to_numpy() & np.isfinite(yv) & ~p["racecraft"].to_numpy(dtype=bool) & A.tyre_ok(p)
    med = pd.Series(yv[base]).groupby(p["group"].to_numpy()[base]).median()
    m = p["group"].map(med).to_numpy(dtype=float)
    with np.errstate(invalid="ignore"):
        return base & (np.abs(yv - m) <= limit)


def effects_signed(p: pd.DataFrame, y: pd.Series, s1: A.Step1, ft: pd.DataFrame, sign: float) -> A.Effects:
    """design_a.effects with the sign given (design_a.SIGN has no entry for the X5 outcomes). Same formulas."""
    s = float(sign)
    yv = y.to_numpy(dtype=float)[ft["row"].to_numpy()]
    ay, ax, a_ok, ac = A.alpha_parts(s1, ft["group"])
    fy, fx, f_ok, fc = A.phi_tilde(s1, ft, ft["W"].to_numpy())
    gy, gx = A.g_parts(s1, ft["race_id"], ft["compound"], ft["t"].to_numpy())
    b = ft["behind"].to_numpy()
    base, d0 = A._following_base(ft)  # B2: rows without tyre_life counted first, under tyre_life_missing
    present = base & np.isfinite(yv)
    has = present & a_ok & f_ok & np.isfinite(gy)
    valid = A._component_check(has, ac, fc)
    drops = {A.TYRE_LIFE_MISSING: d0[A.TYRE_LIFE_MISSING], "outcome_null": int((base & ~np.isfinite(yv)).sum()),
             "no_free_pass_this_outcome": int((present & ~a_ok).sum()), "disconnected": int((has & ~valid).sum())}
    Aa = s * (yv - (ay + fy + gy))
    Bb = s * ((ax + fx + gx) - b)
    fr = p.loc[s1.rows, ["group", "lap", "race_id", "corner_id", "compound", "t", "behind"]].assign(
        yb=y.to_numpy(dtype=float)[s1.rows])
    fr = fr.merge(s1.phi[["race_id", "corner_id", "lap", "y", "x"]], on=["race_id", "corner_id", "lap"], how="left")
    gby, gbx = A.g_parts(s1, fr["race_id"], fr["compound"], fr["t"].to_numpy())
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
    Aloc, Bloc = s * (yv - fy - gy - r0), s * (fx + gx - b - r1)
    loc_ok = valid & ft["bracketed"].to_numpy() & np.isfinite(Aloc) & np.isfinite(Bloc)
    return A.Effects(outcome=s1.outcome, rows=ft["row"].to_numpy(), A=Aa, B=Bb, valid=valid, Aloc=Aloc, Bloc=Bloc,
                     loc_ok=loc_ok, drops=drops)


def _x1_parts(model: A.Model, y_time: pd.Series, k: str, W: int):
    """X1: alpha replaced by the mean of r = y - phi-hat - g - gamma*b over the group's free passes within +-W
    laps (>= 2 required). Returns (A, B) with tau = A + gamma*B, and ok."""
    cm = model.classes[k]
    s1, ft, p = cm.step1[TIME], cm.ft, model.prep
    fr = p.loc[s1.rows, ["group", "lap", "race_id", "corner_id", "compound", "t", "behind"]].assign(
        yb=y_time.to_numpy(dtype=float)[s1.rows])
    fr = fr.merge(s1.phi[["race_id", "corner_id", "lap", "y", "x"]], on=["race_id", "corner_id", "lap"], how="left")
    gby, gbx = A.g_parts(s1, fr["race_id"], fr["compound"], fr["t"].to_numpy())
    fr = fr.assign(R0=fr["yb"] - fr["y"] - gby, R1=fr["x"] + gbx - fr["behind"])
    q = pd.DataFrame({"group": ft["group"].to_numpy(), "lap": ft["lap"].to_numpy(), "_i": np.arange(len(ft))})
    m = q.merge(fr[["group", "lap", "R0", "R1"]].rename(columns={"lap": "lap_f"}), on="group", how="inner")
    m = m[np.abs(m["lap_f"] - m["lap"]) <= W]
    agg = m.groupby("_i").agg(n=("R0", "size"), R0=("R0", "mean"), R1=("R1", "mean")).reindex(np.arange(len(ft)))
    n = agg["n"].fillna(0).to_numpy()
    ok = n >= X1_MIN_FREE
    yv = y_time.to_numpy(dtype=float)[ft["row"].to_numpy()]
    fy, fx, _, _ = A.phi_tilde(s1, ft, ft["W"].to_numpy())
    gy, gx = A.g_parts(s1, ft["race_id"], ft["compound"], ft["t"].to_numpy())
    b = ft["behind"].to_numpy()
    Aw = yv - fy - gy - agg["R0"].to_numpy()
    Bw = fx + gx - b - agg["R1"].to_numpy()
    return Aw, Bw, ok


def _x14_free(p: pd.DataFrame, free_time: np.ndarray) -> np.ndarray:
    """X14: drop free passes within 3 laps after a following spell of their group (a maximal run of consecutive
    laps on which the group's pass has 0 <= gap < 3 or is racecraft). A free pass at lap l is within 3 laps after
    a spell iff one of laps l-1..l-3 of its group is a spell lap (l itself is free, so a spell there has ended)."""
    gap = p["gap_s"].to_numpy(dtype=float)
    with np.errstate(invalid="ignore"):
        spell = ((gap >= 0) & (gap < A.FREE_GAP_S)) | p["racecraft"].to_numpy()
    sp = set(zip(p.loc[spell, "group"], p.loc[spell, "lap"].astype(int)))
    grp, lap = p["group"].to_numpy(), p["lap"].to_numpy(dtype=int)
    after = np.array([any((g, l - d) in sp for d in range(1, X14_WASHOUT_LAPS + 1)) if f else False
                      for g, l, f in zip(grp, lap, free_time)], dtype=bool)
    return free_time & ~after


def build_context(model: A.Model, y: dict, coast: pd.Series | None = None, throttle: pd.Series | None = None,
                  lap: pd.DataFrame | None = None, team: pd.DataFrame | None = None,
                  release_expected: dict | None = None) -> Context:
    """Everything the diagnostics need that does not change across draws. `y` holds seg_time_s, min_speed_kph and
    exit_speed_kph aligned with model.prep; coast (already capped) and throttle likewise; `lap` is
    lap_arm.lap_frame(p, lap_times); `team` has race_id, driver, lap, team."""
    p, st = model.prep, model.st
    ctx = Context(model=model, y=y)
    for k, cm in model.classes.items():
        for W in X1_WINDOWS:
            ctx.x1[(k, W)] = _x1_parts(model, y[TIME], k, W)
        sup = cm.ft["supported"].to_numpy()
        if EXIT in y:
            ex = y[EXIT].to_numpy(dtype=float)[cm.ft["row"].to_numpy()]
            ctx.exit_coverage[k] = float(np.isfinite(ex[sup]).mean()) if sup.any() else np.nan
    # X5
    for o, ys in ((COAST, coast), (THROTTLE, throttle)):
        if ys is None:
            continue
        free = _free_x(p, ys, X5_TRIM[o])
        for k, cm in model.classes.items():
            s1 = A.fit_step1(p, ys, o, k, st, free)
            ef = effects_signed(p, ys, s1, cm.ft, X5_SIGN[o])
            sup = cm.ft["supported"].to_numpy()
            yv = ys.to_numpy(dtype=float)[cm.ft["row"].to_numpy()]
            cov = float(np.isfinite(yv[sup]).mean()) if sup.any() else np.nan
            ctx.x5[(o, k)] = {"s1": s1, "ef": ef, "coverage": cov}
    # X13 train tag: the car ahead's own gap_s at the same corner and lap < 1.0
    lead = p[["race_id", "driver", "lap", "corner_id", "gap_s"]].rename(
        columns={"driver": "leader", "lap": "leader_lap", "gap_s": "L_gap"})
    lead = lead.assign(leader_lap=lead["leader_lap"].astype(float))
    for k, cm in model.classes.items():
        q = cm.ft[["race_id", "leader", "leader_lap", "corner_id"]].assign(
            leader_lap=cm.ft["leader_lap"].astype(float))
        m = q.merge(lead, on=["race_id", "leader", "leader_lap", "corner_id"], how="left")
        with np.errstate(invalid="ignore"):
            ctx.x13[k] = (m["L_gap"].to_numpy(dtype=float) < X13_TRAIN_GAP_S)
    # X11 team
    if team is not None:
        tm = team[["race_id", "driver", "lap", "team"]].drop_duplicates(["race_id", "driver", "lap"])
        for k, cm in model.classes.items():
            m = cm.ft[["race_id", "driver", "lap"]].merge(tm, on=["race_id", "driver", "lap"], how="left")
            ctx.x11[k] = m["team"].fillna("(no team)").astype(str).to_numpy()
    # X14 washout refit
    fx = _x14_free(p, st.free_time)
    ctx.x14_meta = {"free_time": int(st.free_time.sum()), "dropped_washout": int((st.free_time & ~fx).sum())}
    for k, cm in model.classes.items():
        s1 = A.fit_step1(p, y[TIME], TIME, k, st, fx)
        ctx.x14[k] = (s1, A.effects(p, y[TIME], s1, cm.ft))
    if lap is not None and "scored" in lap.columns:
        ctx.lap = lap_step1(lap)
        ctx.release = release_events(p, release_expected)
    return ctx


# --------------------------------------------------------------------------- the lap arm, for X6 and X15


@dataclass
class LapStep1:
    sc: pd.DataFrame  # scored laps
    pred: np.ndarray  # alpha + phi-tilde + g per scored lap (NaN where not predictable)
    pred_ok: np.ndarray  # supported (stint >= 3 free laps), phi-supported, connected
    phi_own: np.ndarray  # phi-hat at the lap's own cell (free laps), y-part
    g: np.ndarray
    phit: np.ndarray  # phi-tilde (§6c rule) per scored lap
    r: np.ndarray  # free laps: LapTime - phi-hat(own) - g
    fol_idx: np.ndarray  # positions (in sc) of the following laps
    tau: np.ndarray  # per following lap
    valid: np.ndarray
    brk: np.ndarray
    tloc: np.ndarray
    race_idx: np.ndarray
    bins: np.ndarray


def lap_step1(lap: pd.DataFrame) -> LapStep1:
    """§9a step 1, as lap_arm.fit_lap_arm, keeping the pieces X6 and X15 need: a prediction for every scored lap,
    the free laps' residuals and the lap-arm bracket (free lap 1-5 laps earlier and 1-5 later in the stint)."""
    sc = lap[lap["scored"]].reset_index(drop=True)
    free = L.lap_free(sc)  # B2: tyre_life required; layout after the drop
    f = sc[free]
    lay = A.theta_layout(sc, free, race_key="race_id")
    lin, quad = A.theta_ids(lay, f["race_id"], f["compound"])
    a_codes, a_uni = pd.factorize(f[L.STINT_KEY])
    f_codes, f_uni = pd.factorize(pd.MultiIndex.from_frame(f[["race_id", "lap"]]))
    sol = A.solve_fe(f["lap_time_s"].to_numpy(dtype=float), a_codes, f_codes, lin, quad, f["t"].to_numpy(dtype=float),
                     lay.n_params, f["race_idx"].to_numpy())
    alpha = pd.DataFrame({"y": sol.alpha[:, 0], "n": np.bincount(a_codes), "comp": sol.comp_alpha},
                         index=pd.Index(a_uni))
    phi = pd.DataFrame(list(f_uni), columns=["race_id", "lap"]).assign(
        y=sol.phi[:, 0], x=0.0, n=np.bincount(f_codes), comp=sol.comp_phi)
    W = A.phi_window_counts(f[["race_id", "lap", "driver"]], sc[["race_id", "lap", "driver"]], ["race_id"])
    py, _, p_ok, pc = A.window_mean(phi, sc, W, ["race_id"])
    a = alpha.reindex(sc[L.STINT_KEY].to_numpy())
    nfree = a["n"].fillna(0).to_numpy()
    lq, qq = A.theta_ids(lay, sc["race_id"], sc["compound"])
    th = sol.theta[:, 0]
    t = sc["t"].to_numpy(dtype=float)
    g = np.where(lq >= 0, th[np.clip(lq, 0, None)] * t, 0.0) + np.where(qq >= 0, th[np.clip(qq, 0, None)] * t * t,
                                                                          np.nan)
    pred = a["y"].to_numpy(dtype=float) + py + g
    has = (nfree >= L.LAP_MIN_FREE) & p_ok & np.isfinite(pred)
    ok = A._component_check(has, a["comp"].to_numpy(dtype=float), pc)
    own = sc[["race_id", "lap"]].merge(phi[["race_id", "lap", "y"]], on=["race_id", "lap"], how="left")["y"]
    phi_own = own.to_numpy(dtype=float)
    lt = sc["lap_time_s"].to_numpy(dtype=float)
    r = np.where(free, lt - phi_own - g, np.nan)
    fol = np.flatnonzero(sc["following_lap"].to_numpy())
    tau = lt[fol] - pred[fol]
    with np.errstate(invalid="ignore"):
        valid = ok[fol] & (np.abs(tau) <= L.LAP_TRIM_S)
    # X15 bracket over the stint's free laps
    scode = pd.factorize(sc[L.STINT_KEY])[0]
    lapn = sc["lap"].to_numpy(dtype=int)
    lb, la = A._nearest_free_laps(scode[fol], lapn[fol], scode[free], lapn[free], X15_BRACKET_LAPS)
    rk = pd.Series(r[free], index=pd.MultiIndex.from_arrays([scode[free], lapn[free]]))
    rb = rk.reindex(pd.MultiIndex.from_arrays([scode[fol], np.nan_to_num(lb, nan=-1).astype(int)])).to_numpy()
    ra = rk.reindex(pd.MultiIndex.from_arrays([scode[fol], np.nan_to_num(la, nan=-1).astype(int)])).to_numpy()
    lf = lapn[fol].astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        wb, wa = (la - lf) / (la - lb), (lf - lb) / (la - lb)
    tloc = lt[fol] - py[fol] - g[fol] - (wb * rb + wa * ra)
    brk = np.isfinite(lb) & np.isfinite(la)
    return LapStep1(sc=sc, pred=np.where(ok, pred, np.nan), pred_ok=ok, phi_own=phi_own, g=g, phit=py, r=r,
                    fol_idx=fol, tau=tau, valid=valid, brk=brk, tloc=tloc,
                    race_idx=sc["race_idx"].to_numpy()[fol], bins=sc["bin"].to_numpy()[fol])


# --------------------------------------------------------------------------- X6 release events (§8f)


@dataclass
class ReleaseEvents:
    events: pd.DataFrame  # identity-matched and free on L+2 (>= 3 rule)
    by_season: pd.DataFrame  # season, candidates, matched_free_ge3, matched_free_gt3, expected
    reproduced: bool
    ties: int


def _lap_states(p: pd.DataFrame, free_gt: bool) -> pd.DataFrame:
    """§8f lap state over the lap's eligible braking passes (no compound filter, racecraft kept)."""
    gap = p["gap_s"].to_numpy(dtype=float)
    clear = p["clear_ahead"].astype("boolean").fillna(False).to_numpy(dtype=bool)
    k = ((p["segment_basis"] == A.BRAKING_BASIS).to_numpy() & p["reason"].isna().to_numpy()
         & ~E.is_yielding(p["tag"]).to_numpy() & p["stint"].notna().to_numpy())
    with np.errstate(invalid="ignore"):
        free = clear | ((gap > A.FREE_GAP_S) if free_gt else (gap >= A.FREE_GAP_S))
    d = p.loc[k, ["season", "race_id", "driver", "lap", "stint", "leader"]].assign(
        g=np.where(clear[k], X6_CLEAR_FILL_S, gap[k]), free=free[k])
    keys = ["season", "race_id", "driver", "lap"]
    lap = d.groupby(keys).agg(stint=("stint", "first"), med=("g", "median"), n=("g", "size"),
                              n_free=("free", "sum")).reset_index()
    modes = d.dropna(subset=["leader"]).groupby(keys)["leader"].agg(lambda s: tuple(sorted(s.mode().tolist())))
    lap = lap.merge(modes.rename("lead_modes").reset_index(), on=keys, how="left")
    med = lap["med"].to_numpy(dtype=float)
    with np.errstate(invalid="ignore"):
        lap["state"] = np.select([med < X6_FOLLOWING_MED_S, lap["n_free"].to_numpy() == lap["n"].to_numpy(),
                                  med >= A.FREE_GAP_S], ["following", "free", "mostly_free"], default="mid")
    return lap


def release_events(p: pd.DataFrame, expected: dict | None = None) -> ReleaseEvents:
    """§8f identity-matched release events, recounted under >= 3 (registered) and > 3 (r03). The recount must
    reproduce `expected` (season -> count, from c2_release_by_season.csv) under one of the two."""
    pr = p.assign(lap=p["lap"].astype(int))
    pl = pr.groupby(["race_id", "driver", "lap"]).agg(
        leader_pit=("reason", lambda s: bool((s == "pit_lap_leader").any())),
        own_pit=("reason", lambda s: bool((s == "pit_lap").any()))).reset_index()
    pit_leaders = (pr[pr["reason"] == "pit_lap_leader"].dropna(subset=["leader"])
                   .groupby(["race_id", "driver", "lap"])["leader"].agg(lambda s: set(s)).rename("pit_leaders"))
    pl = pl.merge(pit_leaders.reset_index(), on=["race_id", "driver", "lap"], how="left")
    out, ties = {}, 0
    for variant, gt in (("ge3", False), ("gt3", True)):
        lap = _lap_states(pr, gt)
        l1 = pl.assign(lap=pl["lap"] - 1)
        ev = lap[lap["state"] == "following"].merge(l1, on=["race_id", "driver", "lap"], how="inner")
        ev = ev[ev["leader_pit"] & ~ev["own_pit"]]
        l2 = lap[["race_id", "driver", "lap", "stint", "state"]].rename(columns={"state": "state_L2"})
        l2 = l2.assign(lap=l2["lap"] - 2)
        ev = ev.merge(l2, on=["race_id", "driver", "lap", "stint"], how="left")
        modes = ev["lead_modes"].apply(lambda x: x if isinstance(x, tuple) else ())
        tie = modes.apply(len).to_numpy() > 1
        if tie.any():
            choice("modal_leader_tie", detail=f"{int(tie.sum())} laps")  # ruled "drop" (anything else raises)
        if variant == "ge3":
            ties = int(tie.sum())
        pls = ev["pit_leaders"].apply(lambda x: x if isinstance(x, set) else set())
        match = np.array([bool(set(m) & s) for m, s in zip(modes, pls)], dtype=bool)
        match &= ~tie  # ruling "drop": a lap whose modal leader is tied is not an X6 event (counted in `ties`)
        ok = match & ev["state_L2"].isin(["free", "mostly_free"]).to_numpy()
        ev = ev.assign(candidate=True, matched_free=ok)
        out[variant] = ev
    seasons = sorted(set(out["ge3"]["season"]) | set(out["gt3"]["season"]) | set((expected or {}).keys()))
    rows = []
    for s in seasons:
        rows.append({"season": int(s), "candidates_ge3": int((out["ge3"]["season"] == s).sum()),
                     "matched_free_ge3": int(out["ge3"].loc[out["ge3"]["season"] == s, "matched_free"].sum()),
                     "matched_free_gt3": int(out["gt3"].loc[out["gt3"]["season"] == s, "matched_free"].sum()),
                     "expected": (expected or {}).get(int(s), np.nan)})
    bs = pd.DataFrame(rows)
    if expected is None:
        reproduced = True
    else:
        e = {int(k): int(v) for k, v in expected.items()}
        got3 = {int(r.season): r.matched_free_ge3 for r in bs.itertuples()}
        gotr = {int(r.season): r.matched_free_gt3 for r in bs.itertuples()}
        reproduced = all(got3.get(s) == v for s, v in e.items()) or all(gotr.get(s) == v for s, v in e.items())
    ev = out["ge3"]
    return ReleaseEvents(events=ev[ev["matched_free"]].reset_index(drop=True), by_season=bs,
                         reproduced=bool(reproduced), ties=ties)


def x6_table(ctx: Context, pace_point: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Per event: lap-arm effect on L and on L+2 and the sign of the change, the pace score on L; drop counts."""
    rel, ls = ctx.release, ctx.lap
    counts = {"events": int(len(rel.events)), "recount_reproduced": rel.reproduced,
              "modal_ties_dropped": rel.ties}
    if not rel.reproduced:
        counts["status"] = "—, recount does not reproduce c2_release_by_season.csv"
        return pd.DataFrame(), counts
    sc = ls.sc
    idx = pd.Series(np.arange(len(sc)), index=pd.MultiIndex.from_frame(sc[["race_id", "driver", "lap"]]))
    lt = sc["lap_time_s"].to_numpy(dtype=float)
    rows, reasons = [], {}
    for e in rel.events.itertuples(index=False):
        r = {"race_id": e.race_id, "driver": e.driver, "lap_L": int(e.lap), "season": int(e.season)}
        effs = []
        for name, l_ in (("L", int(e.lap)), ("L+2", int(e.lap) + 2)):
            i = idx.get((e.race_id, e.driver, l_))
            if i is None:
                reason = f"{name} not a scored lap (§9a)"
            elif not ls.pred_ok[i]:
                reason = f"{name} not predictable (support or phi)"
            else:
                reason = ""
            eff = lt[i] - ls.pred[i] if reason == "" else np.nan
            r[f"effect_{name}_s"] = eff
            r[f"reason_{name}"] = reason
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
            effs.append(eff)
        d = effs[1] - effs[0]
        r["change_sign"] = ("—" if not np.isfinite(d) else ("+" if d > 0 else ("-" if d < 0 else "0")))
        if pace_point is not None:
            m = pace_point[(pace_point["race_id"] == e.race_id) & (pace_point["driver"] == e.driver)
                           & (pace_point["lap"] == int(e.lap))]
            r["S_pace_L"] = float(m["S_pace"].iloc[0]) if len(m) else np.nan
        rows.append(r)
    t = pd.DataFrame(rows)
    counts.update({f"drop: {k}": v for k, v in sorted(reasons.items())})
    if len(t):
        for s in ("+", "-", "0", "—"):
            counts[f"change_sign {s}"] = int((t["change_sign"] == s).sum())
    return t, counts


# --------------------------------------------------------------------------- the per-draw diagnostic statistics


def diag_stats(ctx: Context, w: np.ndarray | None = None) -> dict:
    """Every X statistic with an interval, for one race weighting (point: all ones)."""
    w = np.ones(A.N_RACES) if w is None else np.asarray(w, dtype=float)
    model = ctx.model
    cds = class_draws(model, w)
    out: dict = {}
    for k, cm in model.classes.items():
        cd, ft = cds[k], cm.ft
        bins = ft["bin"].to_numpy()
        tau, keep, tloc, lk, wr = cd.tau[TIME], cd.keep[TIME], cd.tloc[TIME], cd.lk[TIME], cd.wr
        _nf(out, f"X0|{k}|registered", tau, bins, keep, wr, tloc, lk)
        # X1 local-baseline windows
        choice("x1_trim")  # ruled "registered_tau"; None or any other value raises OpenChoiceError
        for W in X1_WINDOWS:
            Aw, Bw, ok = ctx.x1[(k, W)]
            tw = Aw + cd.gamma * Bw
            m = keep & ok  # registered_tau: the pass enters X1 only if it entered beta (group-alpha tau trim)
            _nf(out, f"X1|{k}|W{W}", np.where(m, tw, 0.0), bins, m, wr, tloc, lk)
            out[f"X1|{k}|W{W}|n_supported"] = float((wr * (cm.eff[TIME].valid & ok)).sum())
            out[f"X1|{k}|W{W}|n_close_supported"] = float((wr * (cm.eff[TIME].valid & ok & (bins <= 3))).sum())
            out[f"X1|{k}|W{W}|n_dropped_lt2"] = float((wr * (cm.eff[TIME].valid & ~ok)).sum())
        # X2 lagged gap
        prev = ft["prev_lap_gap_s"].to_numpy(dtype=float)
        pb = E.gap_bin(prev)
        has_prev = keep & np.isfinite(prev)
        _nf(out, f"X2|{k}|prev_gap_bins", tau, pb, has_prev & (pb >= 0), wr, tloc, lk, beta_key=True)
        out[f"X2|{k}|prev_gap_bins|n_prev_ge3"] = float((wr * (has_prev & (pb < 0))).sum())
        # X3 catching split (arrived_from_free counts as shrinking; also reported alone)
        gc = ft["gap_change"].to_numpy()
        for name, m in (("shrinking", np.isin(gc, ["shrinking", "arrived_from_free"])),
                        ("arrived_from_free", gc == "arrived_from_free"), ("steady", gc == "steady"),
                        ("growing", gc == "growing"), ("unknown", gc == "unknown")):
            _nf(out, f"X3|{k}|{name}", tau, bins, keep & m, wr, tloc, lk)
        # X4 DRS
        drs = ft["drs_open_approach"].astype("boolean")
        for name, m in (("drs_open", drs.fillna(False).to_numpy(dtype=bool)),
                        ("drs_closed", (~drs).fillna(False).to_numpy(dtype=bool))):
            _nf(out, f"X4|{k}|{name}", tau, bins, keep & m, wr, tloc, lk)
        out[f"X4|{k}|drs_null|n_near"] = float((wr * (keep & drs.isna().to_numpy() & np.isin(bins, A.NEAR_BINS))).sum())
        # X5 coast and partial throttle
        for o in (COAST, THROTTLE):
            if (o, k) not in ctx.x5:
                continue
            x5 = ctx.x5[(o, k)]
            ef = x5["ef"]
            g = x5["s1"].gamma(w)
            t5 = ef.A + g * ef.B
            with np.errstate(invalid="ignore"):
                m5 = ef.valid & (np.abs(t5) <= X5_TRIM[o])
            _nf(out, f"X5|{k}|{o}", t5, bins, m5, wr, ef.Aloc + g * ef.Bloc, m5 & ef.loc_ok, beta_key=True)
        # X7 close-share tiers (seg time; the aero contrast below)
        tier = ft["tier"].to_numpy()
        for tn in ("<0.20", "0.20-0.50", "0.50-0.80", ">=0.80"):
            _nf(out, f"X7|{k}|tier {tn}", tau, bins, keep & (tier == tn), wr, tloc, lk)
            dm = cd.lab == A.DIRTY_AIR
            _nf(out, f"X7m|{k}|tier {tn}", cd.tau[MINSPEED], bins, cd.keep[MINSPEED] & dm & (tier == tn), wr,
                cd.tloc[MINSPEED], cd.lk[MINSPEED])
        # X8 field-effect window
        Wv = ft["W"].to_numpy()
        _nf(out, f"X8|{k}|W=0", tau, bins, keep & (Wv == 0), wr, tloc, lk)
        _nf(out, f"X8|{k}|W>=1", tau, bins, keep & (Wv >= 1), wr, tloc, lk)
        # X9 dirty air with Delta-hat <= 0 only (min speed)
        with np.errstate(invalid="ignore"):
            d0 = (cd.lab == A.DIRTY_AIR) & (cd.delta <= 0)
        _nf(out, f"X9|{k}|dirty_delta<=0", cd.tau[MINSPEED], bins, cd.keep[MINSPEED] & d0, wr, cd.tloc[MINSPEED],
            cd.lk[MINSPEED])
        # X10 monotone (PAVA, WC-03 C7 style) beside the raw bins, seg time, all passes
        b = np.clip(bins, 0, None)
        raw = A._bin_means(np.where(keep, tau, 0.0), b, wr * keep)
        nbin = np.bincount(b, weights=wr * keep, minlength=A.N_BINS)[:A.N_BINS]
        if np.isfinite(raw).all() and (nbin > 0).all():
            mono = E.pava_nonincreasing(raw, nbin)
        else:
            mono = np.full(A.N_BINS, np.nan)
        for i in range(A.N_BINS):
            out[f"X10|{k}|raw|bin{i}"], out[f"X10|{k}|pava|bin{i}"] = float(raw[i]), float(mono[i])
        # X11 per team
        if k in ctx.x11:
            teams = ctx.x11[k]
            for tm in sorted(set(teams)):
                _nf(out, f"X11|{k}|{tm}", tau, bins, keep & (teams == tm), wr, tloc, lk)
        # X12 exit speed, dirty air (contrast below)
        if EXIT in cd.tau:
            dm = cd.lab == A.DIRTY_AIR
            _nf(out, f"X12|{k}|dirty", cd.tau[EXIT], bins, cd.keep[EXIT] & dm, wr, cd.tloc[EXIT], cd.lk[EXIT])
        # X13 train tag
        tag = ctx.x13[k]
        for name, m in (("train", tag), ("no_train", ~tag)):
            _nf(out, f"X13|{k}|{name}", tau, bins, keep & m, wr, tloc, lk)
            dm = cd.lab == A.DIRTY_AIR
            _nf(out, f"X13m|{k}|{name}", cd.tau[MINSPEED], bins, cd.keep[MINSPEED] & dm & m, wr, cd.tloc[MINSPEED],
                cd.lk[MINSPEED])
        # X14 washout refit
        s1x, efx = ctx.x14[k]
        gx = s1x.gamma(w)
        tx = efx.A + gx * efx.B
        with np.errstate(invalid="ignore"):
            mx = efx.valid & (np.abs(tx) <= A.TRIM_EFFECT[TIME])
        _nf(out, f"X14|{k}|washout_refit", tx, bins, mx, wr, efx.Aloc + gx * efx.Bloc, mx & efx.loc_ok)
    # aero contrasts
    for tn in ("<0.20", "0.20-0.50", "0.50-0.80", ">=0.80"):
        _contrast(out, f"X7|aero tier {tn}", lambda c, s, tn=tn: f"X7m|{c}|tier {tn}|{s}")
    _contrast(out, "X9|aero", lambda c, s: f"X9|{c}|dirty_delta<=0|{s}")
    _contrast(out, "X12|aero exit", lambda c, s: f"X12|{c}|dirty|{s}")
    for name in ("train", "no_train"):
        _contrast(out, f"X13|aero {name}", lambda c, s, name=name: f"X13m|{c}|{name}|{s}")
    # X15 lap-arm bracketed companion
    if ctx.lap is not None:
        ls = ctx.lap
        wr = w[ls.race_idx]
        b = np.clip(ls.bins, 0, None)
        one = ls.valid & ~ls.brk
        brk = ls.valid & ls.brk & np.isfinite(ls.tloc)
        n1 = A._near(A._bin_means(np.where(one, ls.tau, 0.0), b, wr * one))
        n2 = A._near(A._bin_means(np.where(brk, ls.tloc, 0.0), b, wr * brk))
        nb = np.isin(ls.bins, A.NEAR_BINS)
        out["X15|lap|one_sided|near_lap"], out["X15|lap|bracketed|near_lap"] = n1, n2
        out["X15|lap|one-bracketed|near_lap"] = n1 - n2
        out["X15|lap|one_sided|n_near"] = float((wr * (one & nb)).sum())
        out["X15|lap|bracketed|n_near"] = float((wr * (brk & nb)).sum())
        out["X15|lap|bracketed|n_following"] = float((wr * brk).sum())
    return out


def is_count(key: str) -> bool:
    return "|n_" in key


def stats_table(point: dict, draws: list[dict], pct=A.CI95) -> pd.DataFrame:
    """One row per statistic: point (full-sample), 95 % percentile interval over the diagnostic draws (counts have
    none). A statistic undefined at the point is "—" and gets no interval."""
    rows = []
    for key, v in point.items():
        diag = key.split("|")[0].rstrip("m")  # X7m / X13m (min-speed parts) belong to X7 / X13
        row = {"diagnostic": diag, "key": key, "estimate": v, "lo95": np.nan, "hi95": np.nan, "status": "ok"}
        if is_count(key):
            row["status"] = "count"
        elif not np.isfinite(v):
            row["status"] = "—, undefined (empty subset)"
        else:
            row["lo95"], row["hi95"] = A.interval(draws, key, pct)
        rows.append(row)
    t = pd.DataFrame(rows)
    t.insert(0, "title", t["diagnostic"].map(lambda d: f"{DIAGNOSTIC} {d}" if d != "X0" else "registered near band (reference for X3)"))
    return t


def coverage_flags(ctx: Context) -> pd.DataFrame:
    """§7 coverage rule for the sidecar diagnostics (X5) and exit speed (X12): >= 0.70 non-null among supported
    following passes per class, else "—, coverage < 0.70"."""
    rows = []
    for (o, k), x5 in ctx.x5.items():
        c = x5["coverage"]
        rows.append({"outcome": o, "class": k, "coverage": c,
                     "status": "ok" if np.isfinite(c) and c >= COVERAGE_FLOOR else "—, coverage < 0.70"})
    for k, c in ctx.exit_coverage.items():
        rows.append({"outcome": EXIT, "class": k, "coverage": c,
                     "status": "ok" if np.isfinite(c) and c >= COVERAGE_FLOOR else "—, coverage < 0.70"})
    return pd.DataFrame(rows)


def apply_coverage(table: pd.DataFrame, cov: pd.DataFrame) -> pd.DataFrame:
    """Blank (never 0) the X5 / X12 rows of a class whose coverage is below the floor."""
    t = table.copy()
    for r in cov.itertuples(index=False):
        if r.status == "ok":
            continue
        if r.outcome == EXIT:
            m = t["key"].str.startswith(f"X12|{r[1]}|") | (
                t["key"].str.startswith("X12|aero exit|") & t["key"].str.contains(f"{r[1]}"))
        else:
            m = t["key"].str.startswith(f"X5|{r[1]}|{r.outcome}|")
        m &= t["status"] != "count"
        t.loc[m, ["estimate", "lo95", "hi95"]] = np.nan
        t.loc[m, "status"] = "—, coverage < 0.70"
    return t


def x3_flags(point: dict) -> dict:
    """§8d: 'catching sensitivity large' for a class if |near_grow - near_shrink| > |near| (point estimates)."""
    out = {}
    for k in A.CLASSES:
        g, s, n = (point.get(f"X3|{k}|growing|near"), point.get(f"X3|{k}|shrinking|near"),
                   point.get(f"X0|{k}|registered|near"))
        if g is None or not all(np.isfinite(x) for x in (g, s, n)):
            out[k] = "—, undefined"
        else:
            out[k] = X3_FLAG if abs(g - s) > abs(n) else "no flag"
    return out


def structural_shares(ctx: Context) -> pd.DataFrame:
    """X7 and X11 supported shares (structural): supported following / following, per class and tier / team."""
    rows = []
    for k, cm in ctx.model.classes.items():
        ft = cm.ft
        sup = ft["supported"].to_numpy()
        for tn in ("<0.20", "0.20-0.50", "0.50-0.80", ">=0.80"):
            m = ft["tier"].to_numpy() == tn
            rows.append({"diagnostic": "X7", "class": k, "subset": tn, "following": int(m.sum()),
                         "supported": int((m & sup).sum())})
        if k in ctx.x11:
            for tm in sorted(set(ctx.x11[k])):
                m = ctx.x11[k] == tm
                rows.append({"diagnostic": "X11", "class": k, "subset": tm, "following": int(m.sum()),
                             "supported": int((m & sup).sum())})
    t = pd.DataFrame(rows)
    if len(t):
        t["supported_share"] = t["supported"] / t["following"].where(t["following"] > 0)
        t.insert(0, "title", "DIAGNOSTIC " + t["diagnostic"])
    return t


def run_diagnostics(ctx: Context, plan: A.Plan, pace_point: pd.DataFrame | None = None) -> dict:
    """X1-X15 on draws 1-200 of the plan. Returns {"stats", "x3_flags", "coverage", "shares", "x6", "x6_counts",
    "release_by_season", "x14_meta", "n_draws"}."""
    dp = diag_plan(plan)
    point = diag_stats(ctx)
    draws = [diag_stats(ctx, dp.weights[i]) for i in range(dp.weights.shape[0])]
    cov = coverage_flags(ctx)
    table = apply_coverage(stats_table(point, draws), cov)
    out = {"stats": table, "x3_flags": x3_flags(point), "coverage": cov, "shares": structural_shares(ctx),
           "x14_meta": ctx.x14_meta, "n_draws": dp.weights.shape[0]}
    if ctx.release is not None:
        out["x6"], out["x6_counts"] = x6_table(ctx, pace_point)
        out["release_by_season"] = ctx.release.by_season
    return out


# --------------------------------------------------------------------------- per-lap scores (§13 item 7)


@dataclass
class ScoreFrame:
    laps: pd.DataFrame  # one row per score lap
    corners: pd.DataFrame  # braking corners of score laps, with lap position, weight, class, price bin


def score_frame(p: pd.DataFrame, seg_start: np.ndarray, seg_end: np.ndarray) -> ScoreFrame:
    """Score laps: every braking corner of the race on that lap is an eligible pass or a racecraft pass; a lap with
    a yielding tag is not scored; LapTime not required. `seg_start` / `seg_end` are aligned with p (outcome-
    equivalent columns: after RUN START in the real run). Weights: WC-03 §7 (estimator.lap_weights)."""
    keys = ["race_id", "driver", "lap"]
    br = p[(p["segment_basis"] == A.BRAKING_BASIS).to_numpy()].copy()
    br["seg_start_t"], br["seg_end_t"] = np.asarray(seg_start)[br["row"]], np.asarray(seg_end)[br["row"]]
    nb = br.groupby("race_id")["corner_id"].nunique()
    br["ok_corner"] = br["eligible"] | br["racecraft"]
    lap = br.groupby(keys).agg(stint=("stint", "first"), extrapolated=("extrapolated", "max")).reset_index()
    okc = br[br["ok_corner"]].groupby(keys)["corner_id"].nunique().rename("n_ok_c")
    lap = lap.merge(okc.reset_index(), on=keys, how="left")
    yl = p[E.is_yielding(p["tag"]).to_numpy()][keys].drop_duplicates().assign(yielding=True)
    lap = lap.merge(yl, on=keys, how="left")
    lap["nb"] = lap["race_id"].map(nb).to_numpy()
    lap["score_lap"] = (lap["n_ok_c"].fillna(0).to_numpy() == lap["nb"].to_numpy()) & lap["yielding"].isna().to_numpy()
    laps = lap[lap["score_lap"]].drop(columns=["n_ok_c", "yielding", "score_lap"]).reset_index(drop=True)
    laps["_li"] = np.arange(len(laps))
    c = br.merge(laps[keys + ["_li"]], on=keys, how="inner")
    gap = c["gap_s"].to_numpy(dtype=float)
    rc = c["racecraft"].to_numpy(dtype=bool)
    with np.errstate(invalid="ignore"):
        inr = (gap >= 0) & (gap < A.FREE_GAP_S)
        pb = np.where(inr, E.gap_bin(gap), np.where(rc & (gap < 0), 1, -1))
    c["price_bin"] = np.where(pb == 0, 1, pb)  # the 0-0.3 s bin is priced at the 0.3-0.5 s value
    c["following_corner"] = inr | rc
    c["aero_corner"] = inr & c["corner_class"].isin(["fast", "medium"]).to_numpy()
    c["aero_bin"] = np.where(c["aero_corner"], c["price_bin"], -1)
    # WC-03 §7 weights over the lap's braking corners
    w = np.full(len(c), np.nan)
    bad = np.zeros(len(laps), dtype=bool)
    for li, g in c.groupby("_li"):
        ww = E.lap_weights(g["seg_start_t"].to_numpy(), g["seg_end_t"].to_numpy(), g["corner_number"].to_numpy())
        if ww is None:
            bad[li] = True
        else:
            w[g.index.to_numpy()] = ww
    c["w"] = w
    laps["weights_ok"] = ~bad
    laps["following_lap"] = np.bincount(c["_li"], weights=c["following_corner"].astype(float),
                                        minlength=len(laps)) > 0
    fm = c["aero_corner"].to_numpy()  # fast and medium corners at 0 <= gap < 3 (the S_aero set)
    laps["n_fm_following"] = np.bincount(c["_li"], weights=fm.astype(float), minlength=len(laps)).astype(int)
    laps["n_racecraft_corners_aero"] = np.bincount(
        c["_li"], weights=(fm & rc).astype(float), minlength=len(laps)).astype(int)
    # lap median gap (FALLBACK): free corners -> 3.0
    free = c["clear_ahead"].astype("boolean").fillna(False).to_numpy(dtype=bool) | (np.nan_to_num(gap, nan=-1) >= 3.0)
    c["gfill"] = np.where(free, A.FREE_GAP_S, gap)
    laps["med_gap"] = c.groupby("_li")["gfill"].median().reindex(np.arange(len(laps))).to_numpy()
    return ScoreFrame(laps=laps, corners=c)


def _labels_by_row(model: A.Model, d: dict) -> dict:
    out = {}
    for k in ("fast", "medium"):
        if k in model.classes:
            cm = model.classes[k]
            lab = cm.cls.labels(d[f"{k}|gamma|{TIME}"], d[f"{k}|sigma"])
            out.update(dict(zip(cm.ft["row"].to_numpy(), lab)))
    return out


def _pace_values(sf: ScoreFrame, d: dict, verdict: str, lap_d: dict | None) -> np.ndarray:
    c, n = sf.corners, len(sf.laps)
    if verdict.startswith("FALLBACK"):
        beta = lap_d["lap|beta"]
        med = sf.laps["med_gap"].to_numpy(dtype=float)
        b = E.gap_bin(med)
        with np.errstate(invalid="ignore"):
            neg = med < 0  # a NaN median stays unpriced ("curve bin undefined")
        if neg.any():
            choice("fallback_negative_median", detail=f"{int(neg.sum())} laps")  # ruled "bin_0.3-0.5"
        # §13 item 7: the 0-0.3 s bin is priced at the 0.3-0.5 s value (bin 1), under FALLBACK as in design A.
        b = np.where(b == 0, 1, b)
        # Ruling fallback_negative_median = "bin_0.3-0.5": a negative median gap is priced at the 0.3-0.5 s bin.
        b = np.where(neg, 1, b)
        v = np.where(b >= 0, beta[np.clip(b, 0, None)], np.where(med >= A.FREE_GAP_S, 0.0, np.nan))
        return v
    priced = c["price_bin"].to_numpy() >= 0
    vals = np.zeros(len(c))
    for k in A.CLASSES:
        m = priced & (c["corner_class"].to_numpy() == k)
        beta = d[f"{k}|{TIME}|all|beta"]
        vals[m] = beta[c["price_bin"].to_numpy()[m]]
    contrib = c["w"].to_numpy() * vals
    out = np.bincount(c["_li"], weights=np.nan_to_num(contrib, nan=0.0), minlength=n)
    undefined = np.bincount(c["_li"], weights=(~np.isfinite(contrib)).astype(float), minlength=n) > 0
    return np.where(undefined, np.nan, out)


def _aero_values(sf: ScoreFrame, model: A.Model, d: dict) -> np.ndarray:
    # S_aero is the literal registered formula (registration §13 item 7, owner ruling): an unweighted sum over the
    # lap's fast and medium dirty-air corners at 0 <= gap < 3 of [beta_dirty(class_k, bin_k) - beta_dirty(slow,
    # bin_k)]. No w_k weights: §13 item 7 applies the WC-03 §7 w_k to S_pace only.
    c, n = sf.corners, len(sf.laps)
    lab = _labels_by_row(model, d)
    labs = np.array([lab.get(r, "") for r in c["row"].to_numpy()], dtype=object)
    fm_following = c["aero_corner"].to_numpy()
    unk = np.bincount(c["_li"], weights=(fm_following & (labs == A.UNKNOWN)).astype(float), minlength=n)
    tot = np.bincount(c["_li"], weights=fm_following.astype(float), minlength=n)
    m = c["aero_corner"].to_numpy() & (labs == A.DIRTY_AIR)
    vals = np.zeros(len(c))
    slow = d[f"slow|{MINSPEED}|dirty_air|beta"]
    for k in ("fast", "medium"):
        mk = m & (c["corner_class"].to_numpy() == k)
        bk = c["aero_bin"].to_numpy()[mk]
        vals[mk] = d[f"{k}|{MINSPEED}|dirty_air|beta"][bk] - slow[bk]
    s = np.bincount(c["_li"], weights=np.nan_to_num(vals, nan=0.0), minlength=n)
    undefined = np.bincount(c["_li"], weights=(~np.isfinite(vals)).astype(float), minlength=n) > 0
    return np.where((unk > tot / 2.0) | undefined, np.nan, s)


def _pct(mat: np.ndarray, pct) -> tuple[np.ndarray, np.ndarray]:
    """Percentiles per lap over draws; ruling 4: a lap with an undefined draw has an undefined interval."""
    bad = ~np.isfinite(mat)
    if bad.any():
        lo, hi = np.percentile(np.where(bad, 0.0, mat), pct, axis=1)
        anyb = bad.any(axis=1)
        return np.where(anyb, np.nan, lo), np.where(anyb, np.nan, hi)
    lo, hi = np.percentile(mat, pct, axis=1)
    return lo, hi


def per_lap_scores(sf: ScoreFrame, model: A.Model, point: dict, draws: list[dict], verdict: str, aero: str,
                   lap_point: dict | None = None, lap_draw_list: list[dict] | None = None) -> pd.DataFrame:
    """§13 item 7: S_pace and S_aero point (full-sample curves), 10th and 90th percentiles over every draw, the
    extrapolated flag and the reason when unavailable ("—", never 0). Tyre is not scored."""
    t = sf.laps[["race_id", "driver", "lap", "stint", "following_lap", "extrapolated", "n_fm_following",
                 "n_racecraft_corners_aero", "weights_ok"]].copy()
    fallback = verdict.startswith("FALLBACK")
    sp = _pace_values(sf, point, verdict, lap_point)
    mat = np.column_stack([_pace_values(sf, d, verdict, ld) for d, ld in
                           zip(draws, lap_draw_list if fallback else [None] * len(draws))])
    lo, hi = _pct(mat, SCORE_CI)
    reason = np.full(len(t), "", dtype=object)
    if not fallback:
        reason[~t["weights_ok"].to_numpy()] = "segment interval missing (WC-03 §7 step 5)"
    reason[(reason == "") & ~np.isfinite(sp)] = "curve bin undefined"
    if verdict == "NEITHER":
        reason[:] = "switch: NEITHER (no pace level)"
    una = reason != ""
    t["S_pace"] = np.where(una, np.nan, sp)
    t["S_pace_p10"], t["S_pace_p90"] = np.where(una, np.nan, lo), np.where(una, np.nan, hi)
    t["S_pace_reason"] = reason
    t["pace_basis"] = "lap arm, net of DRS/tow" if fallback else "design A, braking corners only"
    sa = _aero_values(sf, model, point)
    mat = np.column_stack([_aero_values(sf, model, d) for d in draws])
    lo, hi = _pct(mat, SCORE_CI)
    reason = np.full(len(t), "", dtype=object)
    with np.errstate(invalid="ignore"):
        reason[~np.isfinite(sa)] = "car-ahead level unknown"
    if aero == "—":
        reason[:] = f"switch: aero — ({verdict})"
    una = reason != ""
    t["S_aero"] = np.where(una, np.nan, sa)
    t["S_aero_p10"], t["S_aero_p90"] = np.where(una, np.nan, lo), np.where(una, np.nan, hi)
    t["S_aero_reason"] = reason
    for f in ("pace", "aero"):
        lo_, hi_ = t[f"S_{f}_p10"].to_numpy(dtype=float), t[f"S_{f}_p90"].to_numpy(dtype=float)
        with np.errstate(invalid="ignore"):
            t[f"{f}_interval_includes_0"] = np.where(np.isfinite(lo_), (lo_ <= 0) & (hi_ >= 0), False)
    t["tyre"] = "—, not scored in discovery (waits on C5)"
    return t
