"""
WC-10e synthetic checks SG1-SG7 (registration §17), run on SYNTHETIC outcomes laid over the REAL 2022-23 structure.

Rules come from the signed discovery registration, wi/WC-10-discovery-preregistration-DRAFT.md (commit 6fd0330,
DD-WC20), and amendment B1 (wi/WC-10-amendment-B1-open-choices-DRAFT.md, commit b89e54c). This module edits
nothing committed: it calls the committed estimator (design_a.fit_model, draw_stats, bootstrap_plan, the switch
functions) exactly as the real run would, on synthetic y.

What is read. Only structure columns, through wc10_io.load_structure (pass table + sidecar structure, 2022-23; the
loader refuses every guarded column, seg_start_t / seg_end_t included, and refuses 2024-25 before opening a
file). No outcome column is read, no ledger is written, nothing real is fitted, RUN START is never written.
`data/dev.duckdb` is not opened. Every number this module produces is synthetic and not outcome-derived (§17).

The plants (§17; where §17 leaves a detail open, the reading is stated here and in the evidence README):
  - SG1: y = alpha + phi + g + beta_true(bin) + u_circuit + v_race + noise on every pass, with alpha per driver
    stint (race, driver, stint, compound) SD 0.3 s; phi[race, corner, lap] = -0.003 s * lap + N(0, 0.02);
    g = compound-specific quadratics in tyre_life (COMPOUND_G); beta_true 0.12 ... 0.005 s by registered bin on
    following passes (0 <= gap < 3); u_circuit SD 0.02 and v_race SD 0.02 added to every following pass of that
    circuit / race (the WC-03 A1 design: loss = bin effect + circuit effect + race shock); noise SD 0.06 s.
    No car-behind term is planted (none is listed in §17).
  - SG2: SG1 plus a compound-specific tyre drift that varies by race: slope per (race, compound) =
    SG2_DRIFT_MEAN[compound] + N(0, 0.002) s per tyre-age lap and curvature N(0, 2e-5) s per lap^2.
  - SG3: SG1 plus +0.01 s per tyre-age lap in every group with >= 1 supported near-band pass (structural support:
    >= 2 non-racecraft free passes, ruling 1), made relative to the field: from every pass the mean of the
    planted term over the free (non-racecraft) passes of its (race, corner, lap) cell is subtracted.
  - SG6: pace as SG1 plus a driver-lap shock shared by every corner of the lap (SD 0.02 s) and a driver x corner
    interaction (SD 0.02 s); minimum speed = -KAPPA x (the same alpha, phi, g, beta, u, v) with its own noise,
    lap shock correlated -0.6 with the time lap shock, noise correlated -0.6 with the time noise; the planted
    minimum-speed loss by bin is the SAME in every corner class, so the true fast - slow contrast is 0.
  - Every SG also plants a minimum-speed outcome (draw_stats needs it); outside SG6 it is not evaluated.
The minimum speed is planted as -KAPPA times the time components with noise SD KAPPA x 0.06 = 2.4 km/h.

Determinism: one numpy SeedSequence per (SG, simulation) from SEED_BASE; the bootstrap is draws 1-200 of the
registered plan (design_a.bootstrap_plan, seed 20261029). BLAS threads are pinned to 1.

    cd transform
    ../.venv/bin/python -m tasks.wake_calibration.sg_checks --out <dir> [--sims 200] [--draws 200] [--workers 6]
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from tasks.wake_calibration import design_a as A  # noqa: E402
from tasks.wake_calibration import estimator as E  # noqa: E402
from tasks.wake_calibration import wc10_io as IO  # noqa: E402

# --------------------------------------------------------------------------- registered SG numbers (§17)

N_SIMS = 200
N_DRAWS = 200
SEED_BASE = 20261030  # SG simulation seed (synthetic only; the bootstrap keeps the registered 20261029)

NOISE_SD = 0.06
ALPHA_SD = 0.3
PHI_SLOPE = -0.003
PHI_SD = 0.02
BETA_TRUE = np.array([0.12, 0.10, 0.08, 0.06, 0.04, 0.02, 0.01, 0.005])
CIRCUIT_SD = 0.02
RACE_SD = 0.02
NEAR_TRUE = float(BETA_TRUE[list(A.NEAR_BINS)].mean())  # 0.07 s

# compound-specific quadratics g(t) = th1 t + th2 t^2 (synthetic design; UNKNOWN takes MEDIUM's)
COMPOUND_G = {"SOFT": (0.003, 6e-5), "MEDIUM": (0.002, 4e-5), "HARD": (0.001, 2e-5),
              "INTERMEDIATE": (0.002, 4e-5), "WET": (0.002, 4e-5)}
SG2_DRIFT_MEAN = {"SOFT": 0.008, "MEDIUM": 0.005, "HARD": 0.003}
SG2_DRIFT_SD, SG2_CURV_SD = 0.002, 2e-5
SG3_DRIFT = 0.01
SG6_LAP_SD, SG6_DXC_SD, SG6_RHO = 0.02, 0.02, -0.6
KAPPA = 40.0  # km/h per s for the planted minimum speed

COVERAGE_MIN = 0.90  # SG1, SG2
BIAS_TOL = 0.10  # SG1, SG2: mean near band within +-10 % of planted
SG3_FAIL_MIN, SG3_PASS_MIN = 0.80, 0.90
SG6_CONTAINS_MIN, SG6_SHARE_PP = 0.90, 0.05
SG7_AGREE_MIN, SG7_DISAGREE_MAX = 0.80, 0.05
DECISION_BINS = list(range(1, A.N_BINS))  # 0.3-3.0 s (the 0-0.3 s bin is in no decision)

RACE_CIRCUIT = {r: c for c in A.CIRCUITS for r in A.APPENDIX_A[c]}


# --------------------------------------------------------------------------- structure (no outcome column)


def load_real_structure() -> pd.DataFrame:
    """The real 2022-23 structure, prepared (design_a.prepare). wc10_io.load_structure refuses every guarded column
    and every season outside 2022-23 before a file is opened."""
    return A.prepare(IO.load_structure())


def _codes(*cols) -> np.ndarray:
    return pd.MultiIndex.from_arrays([np.asarray(c) for c in cols]).factorize()[0] if len(cols) > 1 \
        else pd.factorize(np.asarray(cols[0]))[0]


def structural_keys(p: pd.DataFrame) -> dict:
    """Integer codes and masks the plants need, from structure columns only."""
    gap = p["gap_s"].to_numpy(dtype=float)
    fol_any = np.isfinite(gap) & (gap >= 0) & (gap < A.FREE_GAP_S)
    b = np.where(fol_any, E.gap_bin(np.where(fol_any, gap, 0.0)), -1)
    circ = p["race_id"].map(RACE_CIRCUIT).fillna("").to_numpy()
    free_nr = p["free"].to_numpy() & ~p["racecraft"].to_numpy(dtype=bool)
    gcode = _codes(p["group"].to_numpy())
    n_free_g = np.bincount(gcode, weights=free_nr.astype(float))[gcode]
    near_sup = p["following"].to_numpy() & np.isin(p["bin"].to_numpy(), A.NEAR_BINS) & (n_free_g >= A.MIN_FREE_SUPPORT)
    drift_group = np.zeros(gcode.max() + 1, bool)
    drift_group[gcode[near_sup]] = True
    return {
        "bin": b, "fol": fol_any,
        "stint": _codes(p["stint_key"].to_numpy()),
        "cell": _codes(p["race_id"].to_numpy(), p["corner_id"].to_numpy(), p["lap"].to_numpy()),
        "lap": p["lap"].to_numpy(dtype=float), "t": p["t"].to_numpy(dtype=float),
        "race": _codes(p["race_id"].to_numpy()), "circ": _codes(circ),
        "race_comp": _codes(p["race_id"].to_numpy(), p["compound"].astype(str).to_numpy()),
        "drv_lap": _codes(p["race_id"].to_numpy(), p["driver"].to_numpy(), p["lap"].to_numpy()),
        "drv_corner": _codes(p["race_id"].to_numpy(), p["driver"].to_numpy(), p["corner_id"].to_numpy()),
        "compound": p["compound"].astype(str).to_numpy(),
        "free_nr": free_nr, "group": gcode, "drift_group": drift_group[gcode],
        "class": p["corner_class"].to_numpy(),
    }


# --------------------------------------------------------------------------- plants (§17)


def _g(compound: np.ndarray, t: np.ndarray) -> np.ndarray:
    th1 = np.array([COMPOUND_G.get(c, COMPOUND_G["MEDIUM"])[0] for c in compound])
    th2 = np.array([COMPOUND_G.get(c, COMPOUND_G["MEDIUM"])[1] for c in compound])
    return th1 * t + th2 * t * t


def plant(keys: dict, sg: str, rng: np.random.Generator) -> dict[str, pd.Series]:
    """Synthetic outcomes for one simulation of `sg` (SG1, SG2, SG3, SG6). Returns {seg_time_s, min_speed_kph}."""
    n = len(keys["bin"])

    def draw(codes, sd):
        return rng.normal(0.0, sd, codes.max() + 1)[codes]

    alpha = draw(keys["stint"], ALPHA_SD)
    phi = PHI_SLOPE * keys["lap"] + draw(keys["cell"], PHI_SD)
    g = _g(keys["compound"], keys["t"])
    fol = keys["fol"]
    beta = np.where(fol, BETA_TRUE[np.clip(keys["bin"], 0, None)], 0.0)
    u = np.where(fol, draw(keys["circ"], CIRCUIT_SD) + draw(keys["race"], RACE_SD), 0.0)
    eps_t = rng.normal(0.0, NOISE_SD, n)
    eps_v = KAPPA * NOISE_SD * rng.standard_normal(n)  # independent unless SG6
    extra_t = np.zeros(n)
    extra_v = np.zeros(n)
    if sg == "SG2":
        nrc = keys["race_comp"].max() + 1
        mean = np.array([SG2_DRIFT_MEAN.get(c, SG2_DRIFT_MEAN["MEDIUM"]) for c in keys["compound"]])
        slope = mean + rng.normal(0.0, SG2_DRIFT_SD, nrc)[keys["race_comp"]]
        curv = rng.normal(0.0, SG2_CURV_SD, nrc)[keys["race_comp"]]
        extra_t = slope * keys["t"] + curv * keys["t"] ** 2
    elif sg == "SG3":
        term = np.where(keys["drift_group"], SG3_DRIFT * keys["t"], 0.0)
        fr = keys["free_nr"]
        nc = keys["cell"].max() + 1
        s = np.bincount(keys["cell"][fr], weights=term[fr], minlength=nc)
        c = np.bincount(keys["cell"][fr], minlength=nc)
        cell_mean = np.where(c > 0, s / np.maximum(c, 1), 0.0)
        extra_t = term - cell_mean[keys["cell"]]
    elif sg == "SG6":
        z1 = rng.standard_normal(keys["drv_lap"].max() + 1)
        z2 = rng.standard_normal(keys["drv_lap"].max() + 1)
        lap_t = SG6_LAP_SD * z1
        lap_v = KAPPA * SG6_LAP_SD * (SG6_RHO * z1 + np.sqrt(1 - SG6_RHO ** 2) * z2)
        extra_t = lap_t[keys["drv_lap"]] + draw(keys["drv_corner"], SG6_DXC_SD)
        extra_v = lap_v[keys["drv_lap"]]
        zt = eps_t / NOISE_SD
        eps_v = KAPPA * NOISE_SD * (SG6_RHO * zt + np.sqrt(1 - SG6_RHO ** 2) * rng.standard_normal(n))
    elif sg != "SG1":
        raise ValueError(sg)
    y_t = 2.0 + alpha + phi + g + beta + u + extra_t + eps_t
    # minimum speed: the time components scaled by -KAPPA (speed lost where time is lost); the planted loss is the
    # same in every corner class, so the true fast - slow aero contrast is 0 (SG6).
    y_v = 150.0 - KAPPA * (alpha + phi + g + beta + u) + extra_v + eps_v
    return {A.TIME: pd.Series(y_t), A.MINSPEED: pd.Series(y_v)}


# --------------------------------------------------------------------------- one simulation


def sim_seed(sg: str, i: int) -> np.random.SeedSequence:
    return np.random.SeedSequence([SEED_BASE, int(sg[2:]), i])


def evaluate(model: A.Model, draws: list[dict]) -> dict:
    """Everything the SG criteria need from one simulation (point fit + draws of the registered plan)."""
    point = A.draw_stats(model)
    rec: dict = {}
    for k in A.CLASSES:
        beta = point[f"{k}|{A.TIME}|all|beta"]
        for b in range(A.N_BINS):
            lo, hi = _iv(draws, lambda d, k=k, b=b: d[f"{k}|{A.TIME}|all|beta"][b])
            rec[f"{k}|beta{b}"], rec[f"{k}|beta{b}|lo"], rec[f"{k}|beta{b}|hi"] = float(beta[b]), lo, hi
        rec[f"{k}|near"] = float(point[f"{k}|{A.TIME}|all|near"])
        rec[f"{k}|S3B"] = float(point[f"{k}|S3|B"])
        rec[f"{k}|n_brk"] = float(point[f"{k}|S2pace|n_brk"])
        cc = point[f"{k}|class_counts"]
        known = cc[A.HELD_UP] + cc[A.DIRTY_AIR]
        rec[f"{k}|held_up_share"] = cc[A.HELD_UP] / known if known > 0 else np.nan
        rec[f"{k}|n_held_up"], rec[f"{k}|n_dirty_air"] = cc[A.HELD_UP], cc[A.DIRTY_AIR]
    s3 = A.s3_verdicts(point)
    s2 = A.s2_pace(point, draws)
    for k in A.CLASSES:
        rec[f"{k}|S3"] = "pass" if s3[k] else "fail"
        v, info = s2[k]
        rec[f"{k}|S2"] = v
        rec[f"{k}|S2|lo90"], rec[f"{k}|S2|hi90"], rec[f"{k}|S2|T"] = info["lo90"], info["hi90"], info["T"]
    rec["aero_fs"] = float(point["aero|fast-slow|all"])
    rec["aero_fs|lo"], rec["aero_fs|hi"] = _iv(draws, lambda d: d["aero|fast-slow|all"])
    rec["aero_ms"] = float(point["aero|medium-slow|all"])
    und = A.switch_undefined_counts(draws)
    rec["undef_S1"], rec["undef_S2pace"], rec["undef_S2aero"] = und["S1"], und["S2 pace"], und["S2 aero"]
    return rec


def _iv(draws, f, pct=A.CI95):
    return A.interval([{"x": f(d)} for d in draws], "x", pct)


_P: pd.DataFrame | None = None
_K: dict | None = None
_PLAN: A.Plan | None = None


def _init(n_draws: int, structure_fn=None) -> None:
    global _P, _K, _PLAN
    _P = (structure_fn or load_real_structure)()
    _K = structural_keys(_P)
    _PLAN = A.bootstrap_plan(n_draws)


def run_one(args: tuple) -> dict:
    sg, i = args
    t0 = time.perf_counter()
    rng = np.random.default_rng(sim_seed(sg, i))
    y = plant(_K, sg, rng)
    model = A.fit_model(_P, y, outcomes=(A.TIME, A.MINSPEED))
    t1 = time.perf_counter()
    draws = A.run_draws(model, _PLAN)
    rec = evaluate(model, draws)
    rec.update({"sg": sg, "sim": i, "_fit_s": t1 - t0, "_draws_s": time.perf_counter() - t1})
    return rec


# --------------------------------------------------------------------------- criteria


def sg_coverage(df: pd.DataFrame) -> tuple[bool, pd.DataFrame, pd.DataFrame]:
    """SG1 / SG2: per-bin 95 % coverage >= 0.90 in bins 0.3-3.0 s, per class; mean near within +-10 %."""
    rows = []
    for k in A.CLASSES:
        for b in range(A.N_BINS):
            lo, hi = df[f"{k}|beta{b}|lo"].to_numpy(), df[f"{k}|beta{b}|hi"].to_numpy()
            cov = np.mean((lo <= BETA_TRUE[b]) & (BETA_TRUE[b] <= hi))
            und = int((~np.isfinite(lo)).sum())
            rows.append({"class": k, "bin": b, "gap": f"{E.GAP_EDGES[b]}-{E.GAP_EDGES[b + 1]}",
                         "planted": BETA_TRUE[b], "mean_estimate": df[f"{k}|beta{b}"].mean(), "coverage95": cov,
                         "undefined_intervals": und, "in_decision": b in DECISION_BINS,
                         "pass": bool(cov >= COVERAGE_MIN) if b in DECISION_BINS else None})
    cov = pd.DataFrame(rows)
    brows = []
    for k in A.CLASSES:
        m = df[f"{k}|near"].mean()
        rel = (m - NEAR_TRUE) / NEAR_TRUE
        brows.append({"class": k, "planted_near": NEAR_TRUE, "mean_near": m, "relative_bias": rel,
                      "pass": bool(abs(rel) <= BIAS_TOL)})
    bias = pd.DataFrame(brows)
    ok = bool(cov.loc[cov["in_decision"], "pass"].all() and bias["pass"].all())
    return ok, cov, bias


def s2_rates(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for k in A.CLASSES:
        v = df[f"{k}|S2"]
        rows.append({"class": k, "AGREE": float((v == A.AGREE).mean()), "DISAGREE": float((v == A.DISAGREE).mean()),
                     "INCONCLUSIVE": float((v == A.INCONCLUSIVE).mean()),
                     "median_n_brk": float(df[f"{k}|n_brk"].median()), "min_n_brk": float(df[f"{k}|n_brk"].min()),
                     "median_lo90": float(df[f"{k}|S2|lo90"].median()), "median_hi90": float(df[f"{k}|S2|hi90"].median()),
                     "median_T": float(df[f"{k}|S2|T"].median())})
    return pd.DataFrame(rows)


def sg7(df: pd.DataFrame) -> tuple[bool, pd.DataFrame, dict]:
    """SG7 under SG1: AGREE in medium and slow in >= 80 % (both in the same simulation, as the go/no-go table
    needs both; each class also reported), DISAGREE <= 5 % in every class."""
    r = s2_rates(df)
    both = float(((df["medium|S2"] == A.AGREE) & (df["slow|S2"] == A.AGREE)).mean())
    either_inc = float(((df["medium|S2"] == A.INCONCLUSIVE) | (df["slow|S2"] == A.INCONCLUSIVE)).mean())
    ok = bool(both >= SG7_AGREE_MIN and (r["DISAGREE"] <= SG7_DISAGREE_MAX).all())
    return ok, r, {"agree_medium_and_slow": both, "inconclusive_medium_or_slow": either_inc}


def sg3(drift: pd.DataFrame, null: pd.DataFrame) -> tuple[bool, pd.DataFrame]:
    """S3 (every class must pass) fails in >= 80 % of drift simulations and passes in >= 90 % without drift."""
    rows = []
    for name, df in (("drift", drift), ("no_drift", null)):
        allpass = np.all([df[f"{k}|S3"] == "pass" for k in A.CLASSES], axis=0)
        r = {"arm": name, "sims": len(df), "S3_fail_rate": float(1 - allpass.mean()),
             "S3_pass_rate": float(allpass.mean())}
        for k in A.CLASSES:
            r[f"{k}_fail_rate"] = float((df[f"{k}|S3"] == "fail").mean())
            r[f"{k}_mean_B"] = float(df[f"{k}|S3B"].mean())
            r[f"{k}_realized_near_bias"] = float(df[f"{k}|near"].mean() - NEAR_TRUE)
        rows.append(r)
    t = pd.DataFrame(rows)
    ok = bool(t.loc[0, "S3_fail_rate"] >= SG3_FAIL_MIN and t.loc[1, "S3_pass_rate"] >= SG3_PASS_MIN)
    return ok, t


def sg6(df: pd.DataFrame) -> tuple[bool, pd.DataFrame]:
    lo, hi = df["aero_fs|lo"].to_numpy(), df["aero_fs|hi"].to_numpy()
    contains = float(np.mean((lo <= 0) & (0 <= hi)))
    shares = {k: float(df[f"{k}|held_up_share"].mean()) for k in A.CLASSES}
    spread = max(shares.values()) - min(shares.values())
    per_sim = np.nanmax(df[[f"{k}|held_up_share" for k in A.CLASSES]].to_numpy(), 1) - \
        np.nanmin(df[[f"{k}|held_up_share" for k in A.CLASSES]].to_numpy(), 1)
    t = pd.DataFrame([{"contrast_fast_minus_slow_mean": float(df["aero_fs"].mean()),
                       "interval95_contains_0": contains, "undefined_intervals": int((~np.isfinite(lo)).sum()),
                       **{f"held_up_share_{k}": v for k, v in shares.items()},
                       "held_up_share_spread_pp": 100 * spread,
                       "per_sim_spread_pp_median": float(100 * np.median(per_sim)),
                       "per_sim_spread_le_5pp_rate": float(np.mean(per_sim <= SG6_SHARE_PP))}])
    ok = bool(contains >= SG6_CONTAINS_MIN and spread <= SG6_SHARE_PP)
    return ok, t


# --------------------------------------------------------------------------- SG4 (mechanics) and SG5 (timing)

SG4_RACES = ("2022_1", "2023_1", "2022_2")  # Sakhir (both seasons) and Jeddah 2022: real structure
# B-ii literal refit: every entry beyond the first is a separate copy, relabelled as an Appendix A race not in the
# subset. Draw: Sakhir drawn twice (copy 1 picks 2022_1 twice: a race drawn twice within one copy; copy 2 picks
# 2022_1 and 2023_1), Jeddah once picking 2022_2 twice. Weights 2022_1: 3, 2023_1: 1, 2022_2: 2.
SG4_COPIES = {"2022_1": ("2022_3", "2022_4"), "2022_2": ("2022_5",)}
SG4_WEIGHTS = {"2022_1": 3, "2023_1": 1, "2022_2": 2}
SG4_DUP_ONLY = ({"2022_2": ("2022_5",)}, {"2022_1": 1, "2023_1": 1, "2022_2": 2})


def _plant_frame(p: pd.DataFrame, seed: int) -> dict[str, pd.Series]:
    y = plant(structural_keys(p), "SG1", np.random.default_rng(seed))
    rng = np.random.default_rng(seed + 1)
    y["exit_speed_kph"] = y[A.MINSPEED] + 60.0 + rng.normal(0.0, 2.0, len(p))
    return y


def _replicate(s: pd.DataFrame, y: dict, copies: dict) -> tuple[pd.DataFrame, dict]:
    parts, yparts = [s], [pd.DataFrame(y)]
    for r, news in copies.items():
        m = (s["race_id"] == r).to_numpy()
        for new in news:
            parts.append(s.loc[m].assign(race_id=new, season=int(new[:4]), race=f"copy_{new}"))
            yparts.append(pd.DataFrame(y).loc[m])
    lit = pd.concat(parts, ignore_index=True)
    yl = pd.concat(yparts, ignore_index=True)
    return lit, {o: yl[o].reset_index(drop=True) for o in yl.columns}


def _compare_draws(a: dict, b: dict, tag: str) -> list[dict]:
    """Every statistic the go/no-go line uses (and the pass-class counts), reweighted (a) vs literal refit (b)."""
    rows = []

    def add(key, va, vb):
        va, vb = np.asarray(va, dtype=float), np.asarray(vb, dtype=float)
        both_nan = np.isnan(va) & np.isnan(vb)
        diff = np.where(both_nan, 0.0, np.abs(va - vb))
        rows.append({"case": tag, "statistic": key, "max_abs_diff": float(np.nanmax(np.where(np.isnan(diff), np.inf, diff))),
                     "reweighted": json.dumps(np.round(va, 12).tolist()), "literal": json.dumps(np.round(vb, 12).tolist())})

    for k in A.CLASSES:
        add(f"{k}|gamma|seg_time_s", a[f"{k}|gamma|seg_time_s"], b[f"{k}|gamma|seg_time_s"])
        add(f"{k}|sigma", a[f"{k}|sigma"], b[f"{k}|sigma"])
        for o in A.OUTCOMES:
            for s in ("all", "one", "brk", "dirty_air", "held_up", "brk_dirty", "one_dirty"):
                add(f"{k}|{o}|{s}|beta", a[f"{k}|{o}|{s}|beta"], b[f"{k}|{o}|{s}|beta"])
                add(f"{k}|{o}|{s}|n", a[f"{k}|{o}|{s}|n"], b[f"{k}|{o}|{s}|n"])
        add(f"{k}|S3|B", a[f"{k}|S3|B"], b[f"{k}|S3|B"])
        for sw in ("S2pace", "S2aero"):
            for part in ("D", "beta_brk", "std_one", "n_brk"):
                add(f"{k}|{sw}|{part}", a[f"{k}|{sw}|{part}"], b[f"{k}|{sw}|{part}"])
        cc = (A.HELD_UP, A.DIRTY_AIR, A.UNKNOWN, A.RACECRAFT)
        add(f"{k}|class_counts", [a[f"{k}|class_counts"][c] for c in cc], [b[f"{k}|class_counts"][c] for c in cc])
    for key in ("aero|fast-slow|D", "aero|fast-slow|brk", "aero|fast-slow|n_brk", "aero|fast-slow|all"):
        add(key, a[key], b[key])
    return rows


def _labels_match(m_rw: A.Model, d_rw: dict, m_lit: A.Model, d_lit: dict, races: tuple) -> list[dict]:
    """Per-pass class labels: the original rows in the reweighted model vs the same rows in the literal refit."""
    out = []
    for k in A.CLASSES:
        la = m_rw.classes[k].cls.labels(d_rw[f"{k}|gamma|seg_time_s"], d_rw[f"{k}|sigma"])
        lb = m_lit.classes[k].cls.labels(d_lit[f"{k}|gamma|seg_time_s"], d_lit[f"{k}|sigma"])
        fa, fb = m_rw.classes[k].ft, m_lit.classes[k].ft
        key = ["race_id", "driver", "lap", "corner_id"]
        ja = fa[key].assign(lab_a=la)
        jb = fb[key].assign(lab_b=lb)
        j = ja.merge(jb, on=key, how="inner")
        out.append({"class": k, "passes_compared": len(j), "label_mismatches": int((j["lab_a"] != j["lab_b"]).sum())})
    return out


def sg4_reweight_vs_refit(base: pd.DataFrame, seed: int = SEED_BASE + 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    """B-ii evidence on the REAL structure of three races with synthetic y: the reweighted draw (circuit drawn
    twice, a race drawn twice within one copy; ruling 5) equals a literal refit of the replicated data. `base` is
    the prepared real structure; only its structure columns are used."""
    cols = IO.PASS_STRUCTURE_COLUMNS + [c for c in IO.SIDECAR_STRUCTURE_COLUMNS if c not in IO.PASS_STRUCTURE_COLUMNS]
    sub = base.loc[base["race_id"].isin(SG4_RACES), cols].reset_index(drop=True)
    p = A.prepare(sub)
    y = _plant_frame(p, seed)
    m = A.fit_model(p, y)
    rows, lab = [], []
    for tag, copies, weights in (("circuit copy + duplicate race", SG4_COPIES, SG4_WEIGHTS),
                                 ("duplicate race only",) + SG4_DUP_ONLY):
        lit, yl = _replicate(sub, y, copies)
        pl = A.prepare(lit)
        ml = A.fit_model(pl, yl)
        w = np.zeros(A.N_RACES)
        for r, n in weights.items():
            w[A.RACE_INDEX[r]] = n
        da, db = A.draw_stats(m, w), A.draw_stats(ml)
        rows += _compare_draws(da, db, tag)
        lab += [dict(case=tag, **r) for r in _labels_match(m, da, ml, db, SG4_RACES)]
    return pd.DataFrame(rows), pd.DataFrame(lab)


SG4_TOL = 1e-7  # the §6b convergence tolerance is 1e-10 per coefficient; statistics compared to 1e-7


def sg4_mechanics(p: pd.DataFrame, keys: dict, tmp: Path) -> pd.DataFrame:
    """SG4 items on the real structure with synthetic y: one label per following pass; null outcomes never filled;
    the loader refuses 2024-25 before opening; the gate decodes no column; the restart guard."""
    import pyarrow.parquet as pq

    from tasks.wake_calibration import data_gate as G

    rows = []
    y = plant(keys, "SG1", np.random.default_rng(SEED_BASE + 40))
    rng = np.random.default_rng(SEED_BASE + 41)
    y_null = {o: v.copy() for o, v in y.items()}
    fol_rows = np.flatnonzero(p["following"].to_numpy())
    hole_v = rng.choice(fol_rows, size=len(fol_rows) // 7, replace=False)
    y_null[A.MINSPEED].iloc[hole_v] = np.nan
    hole_t = rng.choice(fol_rows, size=len(fol_rows) // 11, replace=False)
    y_null[A.TIME].iloc[hole_t] = np.nan
    m = A.fit_model(p, y_null, outcomes=(A.TIME, A.MINSPEED))
    pt = A.draw_stats(m)
    allowed = {A.HELD_UP, A.DIRTY_AIR, A.UNKNOWN, A.RACECRAFT}
    for k, cm in m.classes.items():
        lab = cm.cls.labels(pt[f"{k}|gamma|seg_time_s"], pt[f"{k}|sigma"])
        want = np.flatnonzero(p["following"].to_numpy() & (p["corner_class"] == k).to_numpy())
        got = cm.ft["row"].to_numpy()
        one_each = bool(len(lab) == len(got) and len(np.unique(got)) == len(got) and set(got) == set(want))
        rc = cm.ft["racecraft"].to_numpy(dtype=bool)
        ok = one_each and set(lab) <= allowed and bool(((lab == A.RACECRAFT) == rc).all())
        rows.append({"item": "class rule: exactly one of held up / dirty air / unknown / racecraft per following pass",
                     "scope": k, "detail": f"following {len(want)}; " + ", ".join(
                         f"{c} {int((lab == c).sum())}" for c in sorted(allowed)), "pass": ok})
        for o in (A.TIME, A.MINSPEED):
            ef = cm.eff[o]
            isnull = ~np.isfinite(y_null[o].to_numpy()[ef.rows])
            vals = ef.A[ef.valid]
            ok = bool(not (ef.valid & isnull).any() and ef.drops["outcome_null"] > 0 and np.isfinite(vals).all())
            rows.append({"item": "a null outcome is never filled (left out, counted)", "scope": f"{k} {o}",
                         "detail": f"nulls among following {int(isnull.sum())}; counted outcome_null "
                                   f"{ef.drops['outcome_null']}; null and valid {int((ef.valid & isnull).sum())}",
                         "pass": ok})
    # step 1 never uses a null free pass: free_set requires a finite outcome
    fs = A.free_set(p, y_null[A.MINSPEED], A.MINSPEED)
    rows.append({"item": "a null outcome is never filled (step 1)", "scope": "free set",
                 "detail": "free passes with null outcome in step 1: "
                           f"{int((fs & ~np.isfinite(y_null[A.MINSPEED].to_numpy())).sum())}",
                 "pass": bool(not (fs & ~np.isfinite(y_null[A.MINSPEED].to_numpy())).any())})
    # the loader refuses 2024-25 before opening any file
    opened = []
    real_read = pq.read_table

    def spy(path, *a, **kw):
        opened.append(str(path))
        return real_read(path, *a, **kw)

    refusals = []
    pq.read_table = spy
    try:
        for seasons in ((2024,), (2025,), (2022, 2024), (2023, 2025)):
            try:
                IO.load_structure(seasons=seasons)
                refusals.append((seasons, "not refused"))
            except IO.SealError:
                refusals.append((seasons, "SealError"))
        for path in (IO.DEFAULT_PASS_DIR / "pass_table_2024.parquet", IO.DEFAULT_SIDECAR_DIR / "sidecar_2025.parquet",
                     IO.DEFAULT_BRONZE / "laps" / "season=2024" / "race=x" / "a.parquet"):
            try:
                IO.guard_path(path)
                refusals.append((str(path.name), "not refused"))
            except IO.SealError:
                refusals.append((str(path.name), "SealError"))
        led = IO.Ledger(tmp / "seal_ledger")
        try:
            IO.load_outcomes(led, seasons=(2024,))
            refusals.append(("load_outcomes 2024", "not refused"))
        except IO.SealError:
            refusals.append(("load_outcomes 2024", "SealError"))
    finally:
        pq.read_table = real_read
    ok = all(r == "SealError" for _, r in refusals) and not opened and not led.path.exists()
    rows.append({"item": "the loader refuses 2024-25 (before any file is opened)", "scope": "wc10_io",
                 "detail": f"{len(refusals)} requests refused with SealError: "
                           f"{sum(r == 'SealError' for _, r in refusals)}; parquet files opened: {len(opened)}",
                 "pass": ok})
    # the gate decodes no column: every parquet / duckdb reader raises while the gate runs on fake inputs
    import pandas as _pd
    fake = tmp / "gate"
    for sub_ in ("pass", "side", "bronze/laps/season=2022/race=a", "bronze/telemetry/season=2022/race=a",
                 "bronze/weather/season=2022/race=a", "bronze/schedule/season=2022"):
        (fake / sub_).mkdir(parents=True, exist_ok=True)
    for f in ("pass/pass_table_2022.parquet", "side/sidecar_2022.parquet", "bronze/laps/season=2022/race=a/x.parquet",
              "bronze/telemetry/season=2022/race=a/x.parquet", "bronze/weather/season=2022/race=a/x.parquet",
              "bronze/schedule/season=2022/schedule.parquet"):
        (fake / f).write_bytes(b"PAR1 not a real parquet PAR1")
    calls = []

    def boom(*a, **kw):
        calls.append(a[:1])
        raise AssertionError("decode attempted")

    saved = {(pq, n): getattr(pq, n) for n in ("read_table", "ParquetFile", "read_schema", "read_metadata")}
    saved[(_pd, "read_parquet")] = _pd.read_parquet
    try:
        for (mod, n) in saved:
            setattr(mod, n, boom)
        gate_ok, gate_lines = G.run_checks(fake / "bronze", fake / "pass", fake / "side")
        err = ""
    except Exception as exc:  # noqa: BLE001
        gate_ok, gate_lines, err = False, [], type(exc).__name__
    finally:
        for (mod, n), f in saved.items():
            setattr(mod, n, f)
    rows.append({"item": "the gate decodes no column", "scope": "data_gate.run_checks on fake inputs",
                 "detail": f"reader calls {len(calls)}; gate result {'PASS' if gate_ok else 'FAIL (fake digests, expected)'}"
                           f"; lines {len(gate_lines)}; exception {err or 'none'}",
                 "pass": bool(not calls and not err and len(gate_lines) == 4)})
    # the restart guard
    led = IO.Ledger(tmp / "restart_a")
    led.begin("s1", "c", "i")
    led.gate(False, ["check 2: FAIL"])
    st1 = led.current().state
    try:
        led.begin("s2 after a gate failure", "c", "i")
        after_fail = "allowed"
    except IO.RestartRefused:
        after_fail = "refused"
    led2 = IO.Ledger(tmp / "restart_b")
    led2.begin("s1", "c", "i")
    led2.gate(True, [])
    led2.run_start()
    led2.outcome_decoded("seg_time_s", "pass_table_2022.parquet")
    led2.outcome_written("SUMMARY.md")
    try:
        led2.begin("s2 after an outcome-derived number", "c", "i")
        after_written = "allowed"
    except IO.RestartRefused:
        after_written = "refused"
    rows.append({"item": "restart guard: allowed after a gate failure with nothing written; refused after",
                 "scope": "wc10_io.Ledger", "detail": f"state after gate failure {st1}; restart {after_fail}; "
                                                      f"restart after OUTCOME-DERIVED WRITTEN {after_written}",
                 "pass": bool(st1 == "FAILED_RESTARTABLE" and after_fail == "allowed" and after_written == "refused")})
    return pd.DataFrame(rows)


def sg5_timing(p: pd.DataFrame, keys: dict, n_draws: int = 20) -> pd.DataFrame:
    """SG5: timing of one full point fit (three outcomes, structure sets, step 1, effects, class, S3) on the real
    structure, of one bootstrap draw (draw_stats), and of the lap arm on synthetic lap times; projected to the
    registered B = 1,000 (diagnostics, per-lap scores and tyre carry-over not timed)."""
    from tasks.wake_calibration import lap_arm as L

    y = plant(keys, "SG1", np.random.default_rng(SEED_BASE + 50))
    y["exit_speed_kph"] = y[A.MINSPEED] + 60.0 + np.random.default_rng(SEED_BASE + 51).normal(0, 2.0, len(p))
    t0 = time.perf_counter()
    m = A.fit_model(p, y)
    t_fit = time.perf_counter() - t0
    plan = A.bootstrap_plan(n_draws)
    t0 = time.perf_counter()
    A.run_draws(m, plan)
    t_draw = (time.perf_counter() - t0) / n_draws
    lt = pd.DataFrame({"race_id": p["race_id"], "driver": p["driver"], "lap": p["lap"], "y": y[A.TIME]})
    lt = lt.groupby(["race_id", "driver", "lap"])["y"].sum().rename("lap_time_s").reset_index()
    lt["lap_time_s"] += 60.0
    t0 = time.perf_counter()
    try:
        arm = L.fit_lap_arm(L.lap_frame(p, lt))
        lap_note = ""
    except A.EstimatorError as exc:  # §6b: non-convergence is a run error; recorded, not patched
        arm, lap_note = None, f"FAILED: {type(exc).__name__}: {exc}"
    t_lap = time.perf_counter() - t0
    t_lapdraw = np.nan
    if arm is not None:
        t0 = time.perf_counter()
        L.lap_draws(arm, plan)
        t_lapdraw = (time.perf_counter() - t0) / n_draws
    total = t_fit + A.N_BOOT * t_draw + t_lap + A.N_BOOT * (0.0 if arm is None else t_lapdraw)
    return pd.DataFrame([
        {"step": "design A point fit, 3 outcomes (real structure, synthetic y)", "seconds": t_fit, "note": ""},
        {"step": f"one bootstrap draw, draw_stats (mean of {n_draws})", "seconds": t_draw, "note": ""},
        {"step": "lap arm fit (synthetic lap times)", "seconds": t_lap, "note": lap_note},
        {"step": f"one lap-arm draw (mean of {n_draws})", "seconds": t_lapdraw,
         "note": "not timed: the lap arm fit failed" if arm is None else ""},
        {"step": "projected design A + lap arm, B = 1,000 (single process)", "seconds": total,
         "note": "diagnostics (200 draws), per-lap scores and tyre carry-over not timed"},
    ])


def lap_arm_convergence(p: pd.DataFrame) -> pd.DataFrame:
    """Structure-only check of the lap arm's step 1 (§9a with the §6b solver): per race, the alternating
    projections of the tyre-trend regressors (t, t^2 in the registered theta layout) on the lap arm's alpha
    (race, driver, stint) and phi (race, lap) over free scored laps. These columns hold no lap time, so whether
    they converge in 10,000 sweeps is a property of the structure: a race that fails here fails in the real run
    whatever LapTime holds. Assumes every structurally scored lap has a LapTime (LapTime is not read)."""
    from tasks.wake_calibration import lap_arm as L

    lt = p[["race_id", "driver", "lap"]].drop_duplicates().assign(lap_time_s=0.0)  # placeholder, never used below
    lap = L.lap_frame(p, lt)
    sc = lap[lap["scored"]].reset_index(drop=True)
    free = sc["free_lap"].to_numpy()
    f = sc[free]
    lay = A.theta_layout(sc, free, race_key="race_id")
    lin, quad = A.theta_ids(lay, f["race_id"], f["compound"])
    a_codes, _ = pd.factorize(f[L.STINT_KEY])
    f_codes, _ = pd.factorize(pd.MultiIndex.from_frame(f[["race_id", "lap"]]))
    t, blk = f["t"].to_numpy(float), f["race_idx"].to_numpy()
    rows = []
    for b in np.unique(blk):
        idx = np.flatnonzero(blk == b)
        la, _ = pd.factorize(a_codes[idx])
        lf, _ = pd.factorize(f_codes[idx])
        ids = np.unique(np.concatenate([quad[idx], lin[idx][lin[idx] >= 0]]))
        Z = np.zeros((len(idx), len(ids)))
        pos = {int(q): j for j, q in enumerate(ids)}
        tt = t[idx]
        Z[np.arange(len(idx)), [pos[int(q)] for q in quad[idx]]] = tt * tt
        has = lin[idx] >= 0
        Z[np.flatnonzero(has), [pos[int(q)] for q in lin[idx][has]]] = tt[has]
        try:
            _, _, _, sw = A.ap_demean(Z, la, lf)
            ok = True
        except A.EstimatorError:
            sw, ok = A.MAX_SWEEPS, False
        rows.append({"race_id": A.RACES[b], "free_scored_laps": len(idx), "alpha_levels": int(la.max() + 1),
                     "phi_cells": int(lf.max() + 1), "sweeps": int(sw), "converged": ok})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- driver


def run_set(sg: str, n_sims: int, n_draws: int, workers: int, structure_fn=None) -> pd.DataFrame:
    jobs = [(sg, i) for i in range(n_sims)]
    if workers <= 1:
        _init(n_draws, structure_fn)
        recs = [run_one(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(n_draws, structure_fn)) as ex:
            recs = list(ex.map(run_one, jobs, chunksize=1))
    return pd.DataFrame(recs).sort_values("sim").reset_index(drop=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(t: pd.DataFrame, path: Path) -> None:
    t.to_csv(path, index=False, float_format="%.17g")


def run_all(out: Path, n_sims: int = N_SIMS, n_draws: int = N_DRAWS, workers: int = 6, sets=("SG1", "SG2", "SG3", "SG6"),
            structure_fn=None, sg4: bool = True, sg5: bool = True) -> dict:
    """Runs the simulation sets, writes per-simulation records (timings in a separate file, so the determinism
    hash covers results only) and the verdict tables. Returns the verdicts."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    res, verdicts, timing = {}, {}, []
    if sg5:  # §17: SG5 runs first
        p = (structure_fn or load_real_structure)()
        sg5_timing(p, structural_keys(p)).to_csv(out / "timing_SG5.csv", index=False)
        write_csv(lap_arm_convergence(p), out / "SG5_lap_arm_convergence_structural.csv")
        del p
    for sg in sets:
        t0 = time.perf_counter()
        df = run_set(sg, n_sims, n_draws, workers, structure_fn)
        timing.append({"set": sg, "sims": n_sims, "draws": n_draws, "wall_s": time.perf_counter() - t0,
                       "mean_fit_s": df["_fit_s"].mean(), "mean_draws_s": df["_draws_s"].mean()})
        res[sg] = df
        write_csv(df.drop(columns=["_fit_s", "_draws_s"]), out / f"{sg}_sims.csv")
    if "SG1" in res:
        ok, cov, bias = sg_coverage(res["SG1"])
        write_csv(cov, out / "SG1_coverage.csv")
        write_csv(bias, out / "SG1_bias.csv")
        verdicts["SG1"] = ok
        ok7, r7, x7 = sg7(res["SG1"])
        write_csv(r7.assign(**{k: v for k, v in x7.items()}), out / "SG7_s2_rates.csv")
        verdicts["SG7"] = ok7
    if "SG2" in res:
        ok, cov, bias = sg_coverage(res["SG2"])
        write_csv(cov, out / "SG2_coverage.csv")
        write_csv(bias, out / "SG2_bias.csv")
        verdicts["SG2"] = ok
    if "SG3" in res and "SG1" in res:
        ok, t = sg3(res["SG3"], res["SG1"])
        write_csv(t, out / "SG3_s3.csv")
        write_csv(pd.concat([s2_rates(res["SG3"]).assign(arm="drift"), s2_rates(res["SG1"]).assign(arm="no_drift")]),
                  out / "SG3_s2_rates.csv")
        verdicts["SG3"] = ok
    if "SG6" in res:
        ok, t = sg6(res["SG6"])
        write_csv(t, out / "SG6_class.csv")
        verdicts["SG6"] = ok
    if sg4:
        p = (structure_fn or load_real_structure)()
        with tempfile.TemporaryDirectory() as tmp:
            mech = sg4_mechanics(p, structural_keys(p), Path(tmp))
        rw, lab = sg4_reweight_vs_refit(p)
        write_csv(mech, out / "SG4_mechanics.csv")
        write_csv(rw, out / "SG4_reweight_vs_literal_refit.csv")
        write_csv(lab, out / "SG4_labels_reweight_vs_literal_refit.csv")
        verdicts["SG4"] = bool(mech["pass"].all() and (rw["max_abs_diff"] <= SG4_TOL).all()
                               and (lab["label_mismatches"] == 0).all() and (lab["passes_compared"] > 0).all())
    pd.DataFrame(timing).to_csv(out / "timing_sets.csv", index=False)
    shown = {k: "PASS" if v else "FAIL" for k, v in verdicts.items()}
    if sg5:
        conv = pd.read_csv(out / "SG5_lap_arm_convergence_structural.csv")
        bad = conv.loc[~conv["converged"], "race_id"].tolist()
        shown["SG5"] = "RECORDED" + (f"; lap arm step 1 does not converge (structure) in {bad}" if bad else "")
    (out / "verdicts.json").write_text(json.dumps(shown, indent=1, sort_keys=True) + "\n")
    write_sums(out)
    return verdicts


def result_files(out: Path) -> list[str]:
    """Files covered by the determinism hash: every output except the wall-clock timing files and SHA256SUMS."""
    return sorted((f.name for f in Path(out).iterdir()
                   if f.is_file() and not f.name.startswith("timing_") and f.name != "SHA256SUMS"),
                  key=lambda s: s.encode())


def write_sums(out: Path) -> None:
    (Path(out) / "SHA256SUMS").write_text("".join(f"{sha256_file(Path(out) / n)}  {n}\n" for n in result_files(out)))


def compare_runs(a: Path, b: Path) -> tuple[bool, list[str]]:
    """Run 1 vs run 2: identical result-file sets and identical sha256 per file."""
    fa, fb = result_files(a), result_files(b)
    lines, ok = [], fa == fb
    if not ok:
        lines.append(f"file sets differ: only in run 1 {sorted(set(fa) - set(fb))}; only in run 2 {sorted(set(fb) - set(fa))}")
    for n in sorted(set(fa) & set(fb), key=lambda s: s.encode()):
        ha, hb = sha256_file(Path(a) / n), sha256_file(Path(b) / n)
        ok &= ha == hb
        lines.append(f"{'IDENTICAL' if ha == hb else 'DIFFERENT'}  {ha}  {hb}  {n}")
    return ok, lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sims", type=int, default=N_SIMS)
    ap.add_argument("--draws", type=int, default=N_DRAWS)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--sets", default="SG1,SG2,SG3,SG6")
    ap.add_argument("--skip-sg4", action="store_true")
    ap.add_argument("--skip-sg5", action="store_true")
    ap.add_argument("--compare", nargs=2, type=Path, metavar=("RUN1", "RUN2"),
                    help="compare two output folders by sha256 (no simulation); --out gets DETERMINISM.txt")
    a = ap.parse_args(argv)
    if a.compare:
        ok, lines = compare_runs(*a.compare)
        text = "\n".join([f"run 1: {a.compare[0]}", f"run 2: {a.compare[1]}",
                          f"DETERMINISM: {'IDENTICAL' if ok else 'DIFFERENT'}"] + lines) + "\n"
        Path(a.out).mkdir(parents=True, exist_ok=True)
        (Path(a.out) / "DETERMINISM.txt").write_text(text)
        print(text, end="")
        return 0 if ok else 1
    sets = tuple(x for x in a.sets.split(",") if x)
    v = run_all(a.out, a.sims, a.draws, a.workers, sets, sg4=not a.skip_sg4, sg5=not a.skip_sg5)
    for k, ok in sorted(v.items()):
        print(f"{k}: {'PASS' if ok else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
