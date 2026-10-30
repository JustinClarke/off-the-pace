"""
WC-10e discovery run: command-line tool and output writing (registration §13), with a synthetic mode.

Rules come from the signed discovery registration, wi/WC-10-discovery-preregistration-DRAFT.md (commit 6fd0330,
DD-WC20) and status/BUILD-ORDER.md. THE REAL MODE HAS NOT BEEN RUN.

    cd transform
    ../.venv/bin/python -m tasks.wake_calibration.run_wc10 --mode synthetic --out <scratch folder> \
        [--draws 30] [--assume-choices name=value,...]
    ../.venv/bin/python -m tasks.wake_calibration.run_wc10 --mode real --run-start      # the one discovery run

Real mode, in this order (§0a, §16):
  0. Refused outright (exit 2, nothing read, no ledger line) unless --run-start is given; refused if the artifact
     folder already holds files; --draws and --assume-choices are refused (B = 1,000, diagnostics 200, seed and
     open choices are the registered / owner-set values only).
  1. START in the ledger `_evidence/WC-10-discovery-<date>/PROVENANCE.txt` (wc10_io.Ledger; restart rule).
  2. The data gate (data_gate.run_checks: file bytes and names only). Its lines and PASS / FAIL go to the ledger.
     A failure stops here: FAILED_RESTARTABLE.
  3. Structure only (no outcome column): pass table + sidecar structure, the 2022-23 schedule (circuit keys) and
     the Appendix A check (§10: the run refuses to start on a mismatch), bronze laps structure (Team).
  4. RUN START. Only now `wc10_io.load_outcomes` may run; it writes OUTCOME DECODED before the first decode.
  5. The whole analysis in memory. Nothing outcome-derived is printed.
  6. OUTCOME-DERIVED WRITTEN (the run COMPLETES), then the outputs and SHA256SUMS, then output hashes.
  Every exception after START is caught; only its type, file and line reach the ledger and stderr (§0a).

Outputs (the per-lap parquet, the CSVs, SUMMARY.md) go to `_roadmap/_wake-calibration/_artifacts/WC-10/discovery/`
with a SHA256SUMS (registration §13, BUILD-ORDER rule 8; owner ruling on the output location); the ledger stays in the evidence folder. SG1-SG7 (§17) are not built here and are not checked by
this tool: they must pass on the committed code before RUN START.

Synthetic mode makes a small world (structure and outcomes invented, three Appendix A races), fits it with a plan
restricted to those races, and writes the same outputs to --out, marked SYNTHETIC. It never opens a real file
and refuses an --out inside the real artifact or evidence folders.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from tasks.wake_calibration import build_pass_table as BPT
from tasks.wake_calibration import carryover as C
from tasks.wake_calibration import data_gate as G
from tasks.wake_calibration import design_a as A
from tasks.wake_calibration import diagnostics as D
from tasks.wake_calibration import estimator as E
from tasks.wake_calibration import lap_arm as L
from tasks.wake_calibration import wc10_io as IO

WC = IO.WC
DEFAULT_ARTIFACTS = WC / "_artifacts" / "WC-10" / "discovery"  # registration §13: `_artifacts/WC-10/discovery/`
EVIDENCE_ROOT = WC / "_evidence"
RELEASE_CSV = WC / "_evidence" / "WC-10-2026-10-29" / "counts" / "csv" / "r03" / "c2_release_by_season.csv"
CODE_FILES = ("design_a.py", "wc10_io.py", "lap_arm.py", "carryover.py", "diagnostics.py", "run_wc10.py",
              "estimator.py", "data_gate.py", "build_pass_table.py", "run_wc03.py")

# §13 item 1 and §15, verbatim. LINE2 is kept word for word (owner ruling); a banned-word check exempts exactly
# this line and nothing else.
LINE2 ="Exploratory, discovery data (2022-23), in-sample, not confirmed."
LINE3 = "Levels are relative to the typical following lap."
DD_WC2 = ("Normalised from other compounds, based on stints from other drivers or the general performance of the "
          "tyres after removing other factors.")
DD_WC18 = "Level = typical effect for a car in this situation, not a measurement of this lap"
MULTIPLE_TESTING = "Discovery intervals are unadjusted and describe 2022-23 only; no discovery interval is a test."
CLUSTERS = "Intervals rest on about 24 clusters (24 circuits, 43 races; circuit-then-race bootstrap)."
BRAKING_ONLY = "braking corners only; straights and flat-out corners not priced"
SYNTHETIC_LINE = "SYNTHETIC DATA: invented structure and outcomes; not a discovery result."

SUBSETS = ("all", "held_up", "dirty_air")
CURVE_SETS = ("all", "brk", "held_up", "dirty_air")


class Refused(SystemExit):
    """A refusal before anything is read (exit status 2)."""


class _GateFailed(Exception):
    pass


# --------------------------------------------------------------------------- inputs


@dataclass
class Inputs:
    structure: pd.DataFrame  # wc10_io.load_structure columns
    y: dict  # seg_time_s, min_speed_kph, exit_speed_kph aligned with structure rows
    coast: pd.Series  # capped (§7)
    throttle: pd.Series
    lap_times: pd.DataFrame  # race_id, driver, lap, lap_time_s
    seg_start: np.ndarray
    seg_end: np.ndarray
    team: pd.DataFrame | None
    release_expected: dict | None
    coast_capped: int = 0
    synthetic: bool = False
    meta: dict = field(default_factory=dict)


def assemble_inputs(structure: pd.DataFrame, outcomes: dict, lap_structure: pd.DataFrame | None,
                    release_expected: dict | None) -> Inputs:
    """Join the decoded outcome columns to the structure rows (1:1 on the sidecar key). Real mode, after RUN
    START only."""
    key = IO.SIDECAR_KEY
    s = structure.reset_index(drop=True)
    pm = s[key].merge(outcomes["pass"], on=key, how="left", validate="one_to_one")
    sm = s[key].merge(outcomes["sidecar"], on=key, how="left", validate="one_to_one")
    coast, n_cap = D.cap_coast(sm["coast_time_s"])
    lt = outcomes["laps"][["race_id", "driver", "lap", "lap_time_s"]].copy()
    return Inputs(structure=s, y={o: (pm if o != "exit_speed_kph" else sm)[o].astype(float) for o in A.OUTCOMES},
                  coast=coast, throttle=sm["partial_throttle_share"].astype(float), lap_times=lt,
                  seg_start=pm["seg_start_t"].to_numpy(dtype=float), seg_end=pm["seg_end_t"].to_numpy(dtype=float),
                  team=lap_structure, release_expected=release_expected, coast_capped=n_cap)


def read_release_expected(path: Path = RELEASE_CSV) -> dict:
    """§8f: the 2022 / 2023 identity-matched-and-free counts the recount must reproduce (counts only)."""
    t = pd.read_csv(path)
    t = t[t["season"].isin(IO.DISCOVERY_SEASONS)]
    return {int(r.season): int(r.matched_free_L2) for r in t.itertuples()}


def calendar_2022_23(bronze: Path, ledger: IO.Ledger | None = None) -> dict:
    """build_pass_table.race_calendar restricted to the 2022-23 schedule files, so that only 2022-23 paths are
    opened (§4: the run log lists every parquet file opened, 2022-23 only). Same key rule."""
    out = {}
    for s in IO.DISCOVERY_SEASONS:
        path = IO.guard_path(Path(bronze) / "schedule" / f"season={s}" / "schedule.parquet")
        cols = ["EventName", "Location", "EventDate", "season"]
        if ledger is not None:
            ledger.opened(path, cols)
        sched = pq.read_table(path, columns=cols).to_pandas()
        IO.check_season_column(sched, path)
        for name, loc, date, season in sched.itertuples(index=False, name=None):
            slug = BPT._slug(name)
            k = BPT.SEPARATE_LAYOUT_SLUGS.get(slug, BPT.CIRCUIT_ALIASES.get(str(loc), str(loc)))
            out[(int(season), slug)] = (k, pd.Timestamp(date))
    return out


# --------------------------------------------------------------------------- analysis (in memory, writes nothing)


RACE_CIRCUIT = {r: c for c in A.CIRCUITS for r in A.APPENDIX_A[c]}
IDX_CIRCUIT = np.array([RACE_CIRCUIT[r] for r in A.RACES], dtype=object)


@dataclass
class Results:
    tables: dict  # name -> DataFrame (CSV) ; "per_lap_scores" -> parquet
    summary: str
    n_intervals: int
    verdict: str
    line: str


def _iv(draws: list, f, pct=A.CI95) -> tuple[float, float]:
    return A.interval([{"x": f(d)} for d in draws], "x", pct)


def _companion(model: A.Model, w=None) -> dict:
    """Bracketed companions for the near/far table (subsets all, held_up, dirty_air), one race weighting."""
    out = {}
    for k, cd in D.class_draws(model, w).items():
        bins = model.classes[k].ft["bin"].to_numpy()
        for o in cd.tau:
            for sub in SUBSETS:
                m = np.ones(len(bins), bool) if sub == "all" else (cd.lab == sub)
                tmp = {}
                D._nf(tmp, "c", cd.tau[o], bins, cd.keep[o] & m, cd.wr, cd.tloc[o], cd.lk[o] & m)
                out[f"{k}|{o}|{sub}|brk_near"] = tmp["c|brk_near"]
                out[f"{k}|{o}|{sub}|brk_far"] = tmp["c|brk_far"]
                out[f"{k}|{o}|{sub}|n_brk_near"] = tmp["c|n_brk_near"]
    return out


def curves_table(model, point, draws) -> pd.DataFrame:
    cds = D.class_draws(model)
    rows = []
    for k in A.CLASSES:
        cm, cd = model.classes[k], cds[k]
        bins = cm.ft["bin"].to_numpy()
        ri = cm.ft["race_idx"].to_numpy()
        for o in A.OUTCOMES:
            masks = {"all": cd.keep[o], "brk": cd.lk[o], "held_up": cd.keep[o] & (cd.lab == A.HELD_UP),
                     "dirty_air": cd.keep[o] & (cd.lab == A.DIRTY_AIR)}
            for s in CURVE_SETS:
                beta, n = point[f"{k}|{o}|{s}|beta"], point[f"{k}|{o}|{s}|n"]
                for b in range(A.N_BINS):
                    mb = masks[s] & (bins == b)
                    lo, hi = (_iv(draws, lambda d, k=k, o=o, s=s, b=b: d[f"{k}|{o}|{s}|beta"][b])
                              if np.isfinite(beta[b]) else (np.nan, np.nan))
                    rows.append({"class": k, "outcome": o, "set": s, "bin": b,
                                 "gap_lo": E.GAP_EDGES[b], "gap_hi": E.GAP_EDGES[b + 1], "estimate": beta[b],
                                 "lo95": lo, "hi95": hi, "passes": int(n[b]), "races": int(len(set(ri[mb]))),
                                 "circuits": int(len(set(IDX_CIRCUIT[ri[mb]]))),
                                 "decision_use": "none (0-0.3 s bin)" if b == 0 else ""})
    return pd.DataFrame(rows)


def near_far_table(point, draws, comp_point, comp_draws) -> pd.DataFrame:
    rows = []
    for k in A.CLASSES:
        for o in A.OUTCOMES:
            for s in SUBSETS:
                r = {"class": k, "outcome": o, "subset": s}
                for stat in ("near", "far"):
                    key = f"{k}|{o}|{s}|{stat}"
                    r[stat] = point[key]
                    r[f"{stat}_lo95"], r[f"{stat}_hi95"] = _iv(draws, lambda d, key=key: d[key]) \
                        if np.isfinite(point[key]) else (np.nan, np.nan)
                nf = point[f"{k}|{o}|{s}|near"] - point[f"{k}|{o}|{s}|far"]
                r["near-far"] = nf
                r["near-far_lo95"], r["near-far_hi95"] = _iv(
                    draws, lambda d: d[f"{k}|{o}|{s}|near"] - d[f"{k}|{o}|{s}|far"]) if np.isfinite(nf) else (np.nan,) * 2
                for stat in ("brk_near", "brk_far"):
                    key = f"{k}|{o}|{s}|{stat}"
                    r[stat] = comp_point[key]
                    r[f"{stat}_lo95"], r[f"{stat}_hi95"] = _iv(comp_draws, lambda d, key=key: d[key]) \
                        if np.isfinite(comp_point[key]) else (np.nan, np.nan)
                r["n_near"] = float(sum(point[f"{k}|{o}|{s}|n"][list(A.NEAR_BINS)]))
                r["n_brk_near"] = comp_point[f"{k}|{o}|{s}|n_brk_near"]
                rows.append(r)
    return pd.DataFrame(rows)


def aero_table(point, draws) -> pd.DataFrame:
    rows = []
    for o in (A.MINSPEED, "exit_speed_kph"):
        for a, b in (("fast", "slow"), ("medium", "slow")):
            def f(d, kind):
                return d[f"{a}|{o}|{kind}|near"] - d[f"{b}|{o}|{kind}|near"]
            r = {"outcome": o, "contrast": f"{a}-{b}", "set": "dirty_air"}
            for kind, col in (("dirty_air", "estimate"), ("brk_dirty", "brk_estimate")):
                v = f(point, kind)
                r[col] = v
                r[f"{col}_lo95"], r[f"{col}_hi95"] = _iv(draws, lambda d, kind=kind: f(d, kind)) \
                    if np.isfinite(v) else (np.nan, np.nan)
            r["role"] = "aero primary" if o == A.MINSPEED else "aero secondary (enters no level, CHOICE D14)"
            rows.append(r)
    return pd.DataFrame(rows)


def switch_tables(point, draws, s1, s2p_full, s2a, s3, lap_pt, lap_dr, f1) -> dict:
    rows = []
    for k in A.CLASSES:
        nlo, _ = _iv(draws, lambda d: d[f"{k}|{A.TIME}|all|near"])
        dlo, _ = _iv(draws, lambda d: d[f"{k}|{A.TIME}|all|near"] - d[f"{k}|{A.TIME}|all|far"])
        rows.append({"rule": "S1", "class": k, "near": point[f"{k}|{A.TIME}|all|near"], "near_lo95": nlo,
                     "near-far": point[f"{k}|{A.TIME}|all|near"] - point[f"{k}|{A.TIME}|all|far"],
                     "near-far_lo95": dlo, "threshold": "lower 95 % end of near > 0 and of near-far > 0",
                     "verdict": "pass" if s1[k] else "fail"})
    s1t = pd.DataFrame(rows)
    rows = []
    for k in A.CLASSES:
        v, info = s2p_full[k]
        rows.append({"rule": "S2 pace", "class": k, "beta_brk_near": point[f"{k}|S2pace|beta_brk"],
                     "std_one_near": point[f"{k}|S2pace|std_one"], "D_std": point[f"{k}|S2pace|D"],
                     "D_unstd": point[f"{k}|S2pace|beta_one"] - point[f"{k}|S2pace|beta_brk_all"],
                     "lo90": info["lo90"], "hi90": info["hi90"], "T": info["T"], "n_brk": info["n_brk"],
                     "brk_dropped_thin_cell": point[f"{k}|S2pace|brk_dropped_thin_cell"],
                     "threshold": "AGREE: 90 % of D' in [-T, T] and n >= 500; DISAGREE: wholly outside, n >= 100",
                     "verdict": v})
    v, info = s2a
    rows.append({"rule": "S2 aero", "class": "fast-slow", "beta_brk_near": point["aero|fast-slow|brk"],
                 "D_std": point["aero|fast-slow|D"], "lo90": info["lo90"], "hi90": info["hi90"], "T": info["T"],
                 "n_brk": info["n_brk"], "threshold": "as S2 pace; T floor 0.75 km/h", "verdict": v})
    s2t = pd.DataFrame(rows)
    rows = []
    for k in A.CLASSES:
        B = point[f"{k}|S3|B"]
        lo, hi = _iv(draws, lambda d: d[f"{k}|S3|B"]) if np.isfinite(B) else (np.nan, np.nan)
        near = point[f"{k}|{A.TIME}|all|near"]
        rows.append({"rule": "S3", "class": k, "B": B, "B_lo95": lo, "B_hi95": hi,
                     "tolerance": max(A.S3_TOL_FRAC * abs(near), A.S3_FLOOR) if np.isfinite(near) else np.nan,
                     "coverage_of_near_band": point[f"{k}|S3|coverage"], "verdict": "pass" if s3[k] else "fail"})
    s3t = pd.DataFrame(rows)
    lo, hi = A.interval(lap_dr, "lap|near")
    f1t = pd.DataFrame([{"rule": "F1", "near_lap": lap_pt["lap|near"], "near_lap_lo95": lo, "near_lap_hi95": hi,
                         "S3_medium": "pass" if s3["medium"] else "fail", "S3_slow": "pass" if s3["slow"] else "fail",
                         "note": "lap drift checked through corner-level S3 only", "verdict": "pass" if f1 else "fail"}])
    return {"switch_S1": s1t, "switch_S2": s2t, "switch_S3": s3t, "switch_F1": f1t}


def support_tables(model: A.Model) -> dict:
    """§13 item 2 (structural and fit-stage counts; the fit-stage ones use the seg_time_s point fit)."""
    p = model.prep
    cds = D.class_draws(model)
    rows, cls_rows, s2_rows, exp_rows = [], [], [], []
    for k, cm in model.classes.items():
        ft, cd = cm.ft, cds[k]
        ef = cm.eff[A.TIME]
        wcat = np.where(ft["W"] == 0, "W=0", np.where(ft["W"] >= 1, "W>=1", "phi-unsupported"))
        t = pd.DataFrame({"bin": ft["bin"], "W": wcat, "bracketed": ft["bracketed"], "tier": ft["tier"],
                          "following": 1, "supported": ft["supported"].astype(int),
                          "not_racecraft": (ft["supported"] & ~ft["racecraft"]).astype(int),
                          "phi_supported": (ft["supported"] & ~ft["racecraft"] & (ft["W"] >= 0)).astype(int),
                          "valid": ef.valid.astype(int), "entering_beta": cd.keep[A.TIME].astype(int)})
        g = t.groupby(["bin", "W", "bracketed", "tier"]).sum().reset_index()
        rows.append(g.assign(**{"class": k}))
        cls_rows += [{"class": k, "pass_class": c, "passes": int((cd.lab == c).sum()),
                      "supported_close": int(((cd.lab == c) & ft["supported"].to_numpy() & ft["close"].to_numpy()).sum())}
                     for c in (A.HELD_UP, A.DIRTY_AIR, A.UNKNOWN, A.RACECRAFT)]
        for reason, n in pd.Series(cm.cls.unknown_reason[cm.cls.unknown_reason != ""]).value_counts().items():
            cls_rows.append({"class": k, "pass_class": f"unknown/racecraft reason: {reason}", "passes": int(n)})
        # S2 composition cells (15 per class)
        nearm = np.isin(ft["bin"].to_numpy(), A.NEAR_BINS)
        one = cd.keep[A.TIME] & ~ft["bracketed"].to_numpy() & nearm
        brk = cd.lk[A.TIME] & nearm
        cell = ft["s2_cell"].to_numpy()
        n1 = np.bincount(cell[one], minlength=15)
        nb = np.bincount(cell[brk], minlength=15)
        thin = n1 < A.S2_CELL_MIN_ONE_SIDED
        kept = np.where(thin, 0, nb)
        for i in range(15):
            s2_rows.append({"class": k, "gap_change": A.GAP_CHANGES[i // 3], "tier": A.S2_TIERS[i % 3],
                            "one_sided_near": int(n1[i]), "bracketed_near": int(nb[i]),
                            "w_s": kept[i] / kept.sum() if kept.sum() else np.nan,
                            "bracketed_dropped_thin_cell": int(nb[i] if thin[i] else 0)})
        # §8e (5) per bin: mean signed tyre-age distance to the group's free passes; side shares
        fr = pd.DataFrame({"group": p["group"].to_numpy()[model.st.free_time], "t": p["t"].to_numpy()[model.st.free_time]})
        gm = fr.groupby("group")["t"].mean()
        sup = ft["supported"].to_numpy()
        d = ft["t"].to_numpy() - ft["group"].map(gm).to_numpy(dtype=float)
        side = np.where(ft["bracketed"], "bracketed",
                        np.where(np.isfinite(ft["lap_a"]), "after_only_within5",
                                 np.where(np.isfinite(ft["lap_b"]), "before_only_within5", "none_within5")))
        for b in range(A.N_BINS):
            m = sup & (ft["bin"].to_numpy() == b)
            r = {"class": k, "bin": b, "supported": int(m.sum()), "mean_signed_tyre_age_distance": float(np.mean(d[m]))
                 if m.any() else np.nan}
            for sname in ("bracketed", "after_only_within5", "before_only_within5", "none_within5"):
                r[f"share_{sname}"] = float(np.mean(side[m] == sname)) if m.any() else np.nan
            exp_rows.append(r)
    # phi-unsupported share per race and per circuit (supported following passes)
    allft = pd.concat([cm.ft[["race_id", "supported", "racecraft", "W"]] for cm in model.classes.values()])
    s = allft[allft["supported"]]
    pr = s.assign(phi_uns=(s["W"] < 0)).groupby("race_id")["phi_uns"].agg(["sum", "size"]).reset_index()
    pr["circuit"] = pr["race_id"].map(RACE_CIRCUIT)
    pc = pr.groupby("circuit")[["sum", "size"]].sum().reset_index()
    for t in (pr, pc):
        t["phi_unsupported_share"] = t["sum"] / t["size"]
        t.rename(columns={"sum": "phi_unsupported", "size": "supported_following"}, inplace=True)
    return {"support_class_bin_W": pd.concat(rows, ignore_index=True), "support_pass_class": pd.DataFrame(cls_rows),
            "support_S2_cells": pd.DataFrame(s2_rows), "support_exposure_by_bin": pd.DataFrame(exp_rows),
            "support_phi_by_race": pr, "support_phi_by_circuit": pc}


def _count_intervals(tables: dict) -> int:
    n = 0
    for t in tables.values():
        if not isinstance(t, pd.DataFrame):
            continue
        for c in t.columns:
            if c.endswith("lo95") or c.endswith("lo90") or c.endswith("_p10"):
                n += int(t[c].notna().sum())
    return n


def _md(t: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    cols = list(t.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in t.itertuples(index=False):
        cells = []
        for v in r:
            if isinstance(v, (float, np.floating)):
                cells.append("—" if not np.isfinite(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def analyse(inp: Inputs, plan: A.Plan, n_diag: int = D.DIAG_DRAWS) -> Results:
    """The whole discovery chain in memory. Writes nothing and prints nothing."""
    p = A.prepare(inp.structure)
    y = {o: inp.y[o].reset_index(drop=True) for o in A.OUTCOMES}
    model = A.fit_model(p, y)
    point = A.draw_stats(model)
    draws = A.run_draws(model, plan)
    s1 = A.s1_verdicts(point, draws)
    s2p_full = A.s2_pace(point, draws)
    s2p = {k: v[0] for k, v in s2p_full.items()}
    s2a = A.s2_aero(point, draws)
    s3 = A.s3_verdicts(point)
    lap = L.lap_frame(p, inp.lap_times)
    arm = L.fit_lap_arm(lap)
    lap_pt = L.lap_stats(arm)
    lap_dr = L.lap_draws(arm, plan)
    f1 = L.f1_verdict(lap_dr, s3)
    undefined = A.switch_undefined_counts(draws, lap_dr)
    verdict, aero, line = A.go_no_go(s1, s2p, s2a[0], s3, f1, undefined=undefined)
    comp_point = _companion(model)
    comp_draws = [_companion(model, plan.weights[i]) for i in range(plan.weights.shape[0])]
    tables = {"curves": curves_table(model, point, draws),
              "near_far": near_far_table(point, draws, comp_point, comp_draws),
              "aero_contrasts": aero_table(point, draws)}
    tables.update(switch_tables(point, draws, s1, s2p_full, s2a, s3, lap_pt, lap_dr, f1))
    lb = []
    for b in range(A.N_BINS):
        v = lap_pt["lap|beta"][b]
        lo, hi = _iv(lap_dr, lambda d, b=b: d["lap|beta"][b]) if np.isfinite(v) else (np.nan, np.nan)
        lb.append({"bin": b, "gap_lo": E.GAP_EDGES[b], "gap_hi": E.GAP_EDGES[b + 1], "estimate_s": v, "lo95": lo,
                   "hi95": hi, "laps": int(lap_pt["lap|n"][b]), "label": "net of DRS/tow"})
    tables["lap_arm"] = pd.DataFrame(lb)
    tables["lap_arm_drops"] = pd.DataFrame([arm.drops])
    sc = C.carry_frame(lap)
    cf = C.fit_carry(sc)
    tables["tyre_carry"] = C.carry_table(cf, plan)
    tables["tyre_carry_counts"] = pd.DataFrame([cf.counts])
    sf = D.score_frame(p, inp.seg_start, inp.seg_end)
    scores = D.per_lap_scores(sf, model, point, draws, verdict, aero, lap_pt, lap_dr)
    tables["per_lap_scores"] = scores
    ctx = D.build_context(model, y, inp.coast, inp.throttle, lap, inp.team, inp.release_expected)
    dres = D.run_diagnostics(ctx, plan if n_diag == D.DIAG_DRAWS else D.diag_plan(plan, n_diag), scores)
    tables["DIAGNOSTIC_X1-X15"] = dres["stats"]
    tables["DIAGNOSTIC_coverage"] = dres["coverage"]
    tables["DIAGNOSTIC_X7_X11_supported_shares"] = dres["shares"]
    if "x6" in dres:
        tables["DIAGNOSTIC_X6_release_events"] = dres["x6"]
        tables["DIAGNOSTIC_X6_counts"] = pd.DataFrame([dres["x6_counts"]])
        tables["DIAGNOSTIC_X6_recount_by_season"] = dres["release_by_season"]
    tables.update(support_tables(model))
    tables["support_rulings"] = pd.DataFrame(
        [{"ruling": "1 racecraft free passes dropped", "class": "all", "outcome": o, "count": int(n)}
         for o, n in model.racecraft_free_dropped.items()]
        + [{"ruling": "2 skipped other corners (empty alpha-bar)", "class": k, "outcome": A.TIME,
            "count": int(cm.cls.skipped_corners)} for k, cm in model.classes.items()])
    tables["support_other"] = pd.DataFrame([{"coast_implausible_set_null": inp.coast_capped,
                                             "x14_free_time": dres["x14_meta"]["free_time"],
                                             "x14_dropped_washout": dres["x14_meta"]["dropped_washout"]}])
    n_iv = _count_intervals(tables)
    summary = build_summary(line, tables, dres, verdict, aero, n_iv, plan, inp)
    return Results(tables=tables, summary=summary, n_intervals=n_iv, verdict=verdict, line=line)


def build_summary(line, tables, dres, verdict, aero, n_iv, plan, inp) -> str:
    out = [line, LINE2, LINE3]
    if inp.synthetic:
        out.append(SYNTHETIC_LINE)
    out += ["", f"Draws: B = {plan.weights.shape[0]} (main), diagnostics use draws 1-{dres['n_draws']}. {CLUSTERS}",
            f"Aero proposal: {aero}. Tyre: — (not scored in discovery; waits on confirmatory C5).", ""]
    for name, title in (("switch_S1", "S1 dose-response (seg time)"), ("switch_S2", "S2 one-sided vs bracketed"),
                        ("switch_S3", "S3 drift (exposure-weighted)"), ("switch_F1", "F1 fallback")):
        out += [f"## {title}", "", _md(tables[name].drop(columns=["threshold"], errors="ignore")), ""]
    out += ["## DIAGNOSTIC X3 catching flag", ""]
    out += [f"- {k}: {v}" for k, v in dres["x3_flags"].items()]
    if "x6_counts" in dres:
        xc = dres["x6_counts"]
        out += ["", "## DIAGNOSTIC X6 release events", "",
                f"- modal-leader ties dropped (not events, ruling modal_leader_tie = drop): {xc['modal_ties_dropped']}",
                f"- recount reproduces c2_release_by_season.csv: {'yes' if xc['recount_reproduced'] else 'no'}",
                f"- events: {xc['events']}" if xc["recount_reproduced"] else f"- {xc['status']}"]
    out += ["", "## Labels", "", f"Every modelled level carries these two lines:", "", f"1. {DD_WC2}", f"2. {DD_WC18}",
            "", f"Corner-level pace: {BRAKING_ONLY}. The lap-arm pace carries \"net of DRS/tow\". Replay v1 is "
            "retrospective. Laps in stints with close share >= 0.80 carry the `extrapolated` flag.",
            "Unavailable values are shown as \"—\" with a reason, never 0.", "",
            f"Intervals reported: {n_iv}. {MULTIPLE_TESTING}", "",
            "Files: " + ", ".join(sorted(f"{k}.csv" if k != "per_lap_scores" else f"{k}.parquet" for k in tables))]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- writing


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_outputs(res: Results, out_dir: Path) -> dict:
    """SUMMARY.md, one CSV per table (per-lap scores as parquet), then SHA256SUMS over every file written."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    (out_dir / "SUMMARY.md").write_text(res.summary)
    written.append("SUMMARY.md")
    for name, t in res.tables.items():
        if name == "per_lap_scores":
            t.to_parquet(out_dir / f"{name}.parquet", index=False)
            written.append(f"{name}.parquet")
        else:
            t.to_csv(out_dir / f"{name}.csv", index=False)
            written.append(f"{name}.csv")
    hashes = {n: sha256_file(out_dir / n) for n in sorted(written, key=lambda s: s.encode())}
    (out_dir / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for n, h in hashes.items()))
    return hashes


# --------------------------------------------------------------------------- fingerprints


def code_fingerprint() -> str:
    here = Path(__file__).resolve().parent
    text = "".join(f"{sha256_file(here / f)}  {f}\n" for f in CODE_FILES)
    return hashlib.sha256(text.encode()).hexdigest()


def inputs_fingerprint() -> str:
    return hashlib.sha256(json.dumps({"expected": G.EXPECTED, "registration": IO.REGISTRATION_SHA256},
                                     sort_keys=True).encode()).hexdigest()


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=IO.REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance only
        return "unknown"


# --------------------------------------------------------------------------- synthetic world


SYN_RACES = ("2022_1", "2022_2", "2022_3")
SYN_CLASS_OF = {"C1": "fast", "C2": "fast", "C3": "medium", "C4": "medium", "C5": "slow", "C6": "slow"}
SYN_BETA_T = np.array([0.12, 0.10, 0.08, 0.06, 0.04, 0.02, 0.01, 0.005])
SYN_BETA_V = np.array([3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 0.2, 0.1])


def synthetic_world(seed: int = 3, races=SYN_RACES, n_drivers: int = 12, n_laps: int = 40) -> Inputs:
    """An invented world with the structure columns of wc10_io.load_structure, a planted dose-response, sidecar
    outcomes, segment start/end times, lap times and teams. No real file is opened."""
    rng = np.random.default_rng(seed)
    rows = []
    for r in races:
        season = int(r[:4])
        pit = {d: int(rng.integers(15, 26)) for d in range(n_drivers)}
        phi = {(c, l): -0.003 * l + rng.normal(0, 0.02) for c in SYN_CLASS_OF for l in range(1, n_laps + 1)}
        alpha = {}
        for d in range(n_drivers):
            g = rng.uniform(0.0, 6.0)
            for l in range(1, n_laps + 1):
                g = float(np.clip(g + rng.normal(0, 0.6), 0.05, 6.0))
                stint = 1 if l <= pit[d] else 2
                comp = "MEDIUM" if stint == 1 else "HARD"
                t = l - (0 if stint == 1 else pit[d]) + 2
                for c in SYN_CLASS_OF:
                    gap = max(0.01, g + rng.normal(0, 0.1))
                    clear = bool(gap >= 3.0 and rng.random() < 0.5)
                    key = (d, stint, c)
                    alpha.setdefault(key, rng.normal(0, 0.3))
                    rows.append(dict(season=season, race_id=r, race=f"race_{r}", driver=f"D{d:02d}", lap=l,
                                     stint=float(stint), compound=comp, tyre_life=float(t), corner_id=c,
                                     corner_number=int(c[1]), corner_class=SYN_CLASS_OF[c],
                                     segment_basis="brake_onset", leader=f"D{(d - 1) % n_drivers:02d}",
                                     leader_lap=float(l), gap_s=np.nan if clear else gap, clear_ahead=clear,
                                     behind_1s=bool(rng.random() < 0.3), tag=None, reason=None,
                                     exit_bracket_m=20.0, throttle_n=10, drs_open_approach=bool(gap < 1.0),
                                     _alpha=alpha[key], _phi=phi[(c, l)]))
    f = pd.DataFrame(rows)
    prev = f[["season", "race_id", "driver", "lap", "corner_id", "gap_s", "clear_ahead", "reason"]].copy()
    prev["lap"] += 1
    prev = prev.rename(columns={"gap_s": "prev_lap_gap_s", "clear_ahead": "prev_lap_clear_ahead",
                                "reason": "prev_lap_reason"})
    f = f.merge(prev, on=["season", "race_id", "driver", "lap", "corner_id"], how="left")
    gap = f["gap_s"].to_numpy(float)
    b = E.gap_bin(np.where(np.isnan(gap), 9.0, gap))
    t = f["tyre_life"].to_numpy(float)
    gt = np.where(f["compound"] == "MEDIUM", 0.002 * t + 1e-4 * t * t, 0.001 * t + 5e-5 * t * t)
    eff_t = np.where(b >= 0, SYN_BETA_T[np.clip(b, 0, None)], 0.0)
    eff_v = np.where(b >= 0, SYN_BETA_V[np.clip(b, 0, None)], 0.0)
    base = 2.0 + f["_alpha"] + f["_phi"] + gt
    n = len(f)
    seg = base + 0.03 * f["behind_1s"] + eff_t + rng.normal(0, 0.02, n)
    mins = 150 + 10 * (f["_alpha"] + f["_phi"] + gt) - 0.5 * f["behind_1s"] - eff_v + rng.normal(0, 0.5, n)
    exits = mins + 60 + rng.normal(0, 0.5, n)
    coast = np.clip(0.8 + 2.0 * eff_t + rng.normal(0, 0.1, n), 0, None)
    coast[rng.random(n) < 0.002] = 15.0  # a few implausible values, for the §7 cap
    thr = np.clip(0.1 + 0.5 * eff_t + rng.normal(0, 0.02, n), 0, 1)
    start = f["lap"].to_numpy() * 100.0 + f["corner_number"].to_numpy() * 10.0
    structure = f[IO.PASS_STRUCTURE_COLUMNS + [c for c in IO.SIDECAR_STRUCTURE_COLUMNS
                                               if c not in IO.SIDECAR_KEY]].copy()
    lt = f.assign(seg=seg).groupby(["race_id", "driver", "lap"])["seg"].sum().rename("lap_time_s").reset_index()
    lt["lap_time_s"] += 60.0 + rng.normal(0, 0.05, len(lt))
    team = f[["race_id", "driver", "lap"]].drop_duplicates().assign(
        team=lambda x: "T" + (x["driver"].str[1:].astype(int) // 2).astype(str))
    capped, ncap = D.cap_coast(pd.Series(coast))
    return Inputs(structure=structure, y={"seg_time_s": seg.astype(float), "min_speed_kph": mins.astype(float),
                                          "exit_speed_kph": pd.Series(exits).astype(float)},
                  coast=capped, throttle=pd.Series(thr), lap_times=lt, seg_start=start,
                  seg_end=start + seg.to_numpy(), team=team, release_expected=None, coast_capped=ncap, synthetic=True)


def synthetic_plan(n_draws: int, races=SYN_RACES, seed: int = A.SEED) -> A.Plan:
    """A plan over the synthetic races only (the Appendix A plan would leave most draws without them)."""
    rng = np.random.default_rng(seed)
    keep = np.array([A.RACE_INDEX[r] for r in races])
    W = np.zeros((n_draws, A.N_RACES))
    for i in range(n_draws):
        np.add.at(W[i], keep[rng.integers(0, len(keep), len(keep))], 1.0)
    return A.Plan(weights=W)


# --------------------------------------------------------------------------- command line


def _parse_choices(text: str | None) -> dict:
    if not text:
        return {}
    out = {}
    for part in text.split(","):
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _apply_choices(ch: dict) -> None:
    """Synthetic mode only: values for the diagnostics' open choices. All eight are ruled, so only the ruled value
    is accepted (design_a's five may not be named at all)."""
    for k, v in ch.items():
        if k not in D.OPEN_CHOICES:
            raise Refused(f"unknown or ruled choice {k!r} (only diagnostics.OPEN_CHOICES may be assumed)")
        if v != D.RULED_CHOICES[k]:
            raise Refused(f"choice {k}={v!r} rejected: only the owner's ruling {D.RULED_CHOICES[k]!r} is implemented")
        D.OPEN_CHOICES[k] = v


def _inside(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def run_synthetic(a) -> int:
    if a.out is None:
        raise Refused("synthetic mode needs --out")
    if _inside(a.out, DEFAULT_ARTIFACTS) or _inside(a.out, EVIDENCE_ROOT):
        raise Refused("synthetic output may not go into the real artifact or evidence folders")
    _apply_choices(_parse_choices(a.assume_choices))
    inp = synthetic_world(seed=a.seed)
    plan = synthetic_plan(a.draws)
    res = analyse(inp, plan, n_diag=min(D.DIAG_DRAWS, a.draws))
    hashes = write_outputs(res, a.out)
    (Path(a.out) / "SYNTHETIC").write_text(SYNTHETIC_LINE + "\n")
    print(res.line)
    print(f"synthetic outputs: {len(hashes)} files in {a.out}")
    return 0


def run_real(a, gate_fn=None) -> int:
    """§0a order. `gate_fn` (tests only) replaces data_gate.run_checks."""
    if not a.run_start:
        raise Refused("REFUSED: real mode needs --run-start (the owner's explicit RUN START); nothing was read")
    if a.draws is not None or a.assume_choices:
        raise Refused("REFUSED: --draws and --assume-choices are synthetic-only (B = 1,000 and owner-set choices)")
    art = Path(a.artifacts_dir)
    if art.exists() and any(art.iterdir()):
        raise Refused(f"REFUSED: {art} already holds files (one discovery run, §0a)")
    ev = Path(a.evidence_dir) if a.evidence_dir else EVIDENCE_ROOT / f"WC-10-discovery-{dt.date.today().isoformat()}"
    ledger = IO.Ledger(ev)
    try:
        ledger.begin(a.reason, code=code_fingerprint(), inputs=inputs_fingerprint(),
                     prior_exit_status=a.prior_exit_status)
    except IO.RestartRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    gate_fn = gate_fn or (lambda: G.run_checks(a.bronze, a.pass_table_dir, a.sidecar_dir))

    def body():
        ok, lines = gate_fn()
        ledger.gate(ok, lines)  # a failure writes EXIT FAILED_RESTARTABLE
        for line in lines:
            print(line)
        if not ok:
            raise _GateFailed()
        structure = IO.load_structure(a.pass_table_dir, a.sidecar_dir, ledger=ledger)
        A.check_appendix_a(A.prepare(structure), calendar_2022_23(a.bronze, ledger))
        lap_structure = IO.load_lap_structure(a.bronze, ledger=ledger)
        expected = read_release_expected()
        D.preflight()  # the diagnostics' open choices must be set by the owner before RUN START
        ledger.run_start()  # wc10_io also runs design_a.preflight here
        print("RUN START written")
        outcomes = IO.load_outcomes(ledger, a.pass_table_dir, a.sidecar_dir, a.bronze)
        inp = assemble_inputs(structure, outcomes, lap_structure, expected)
        res = analyse(inp, A.bootstrap_plan())
        ledger.outcome_written(unicodedata.normalize("NFC", str(art)))
        hashes = write_outputs(res, art)
        rl = res.tables.get("support_rulings")
        if rl is not None:
            ledger._write("INFO", "rulings " + " ".join(f"[{r[0]}|{r[1]}|{r[2]}]={r[3]}"
                                                        for r in rl.itertuples(index=False)))
        ledger._write("INFO", f"registration_sha256={IO.REGISTRATION_SHA256} commit={git_head()} "
                              f"python={sys.version.split()[0]} seed={A.SEED} B={A.N_BOOT} diag_draws={D.DIAG_DRAWS}")
        for n, h in hashes.items():
            ledger._write("OUTPUT", f"{h}  {n}")
        print(f"outputs: {len(hashes)} files in {art}")

    try:
        body()
    except _GateFailed:
        print("GATE: FAIL (restartable; nothing read)", file=sys.stderr)
        return 1
    except BaseException as exc:  # noqa: BLE001 - §0a: every exception is caught
        line = IO.safe_exception_line(exc)
        try:
            ledger.error(exc)
            ledger.exit(exc=exc)
        finally:
            print(f"ERROR {line}", file=sys.stderr)
        return 1
    ledger.exit()
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("synthetic", "real"), required=True)
    ap.add_argument("--run-start", action="store_true", help="real mode: the owner's explicit RUN START")
    ap.add_argument("--out", type=Path, help="synthetic mode: output folder")
    ap.add_argument("--draws", type=int, default=None, help="synthetic mode only (default 30)")
    ap.add_argument("--seed", type=int, default=3, help="synthetic world seed")
    ap.add_argument("--assume-choices", default=None, help="synthetic mode only: name=value,... for open choices")
    ap.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    ap.add_argument("--evidence-dir", type=Path, default=None)
    ap.add_argument("--bronze", type=Path, default=IO.DEFAULT_BRONZE)
    ap.add_argument("--pass-table-dir", type=Path, default=IO.DEFAULT_PASS_DIR)
    ap.add_argument("--sidecar-dir", type=Path, default=IO.DEFAULT_SIDECAR_DIR)
    ap.add_argument("--prior-exit-status", type=int, default=None)
    ap.add_argument("--reason", default="discovery run")
    return ap


def main(argv=None, gate_fn=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        if a.mode == "synthetic":
            a.draws = 30 if a.draws is None else a.draws
            return run_synthetic(a)
        return run_real(a, gate_fn=gate_fn)
    except Refused as r:
        print(str(r), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
