"""
WC-03 / WC-04 §12b sensitivity runs. REPORT ONLY (Table 2): reported as figures, never pass or fail, never a
verdict input, and none rescues or sinks the verdict.

  - reference window ±2 and ±6 laps instead of ±4: references rebuilt from the pass table with the builder's
    own rule, then the whole chain refitted and rescored (1,000 draws each, same seed);
  - 2025 scored without 2024 Las Vegas in the fit (its passes leave the fit and its laps leave θ_now; A4 4b
    keeps the two race lists equal, so both lose it).
If W1 holds in the main run but not in a sensitivity run, the scorecard says so in its first lines (§12b).

Rules: pre-registration §12b (SHA-256 518c3348...), A1 (same plan construction, same seed), decision record
L4 (wi/WC-03-lead-decisions-2026-10-28-DRAFT.md, DRAFT, Opus-delegated).

SYNTHETIC ONLY; NOT RUN ON REAL DATA (tests/test_sensitivity.py). Pure functions: reads no file, writes nothing.
The builder (build_pass_table.py) is not changed: rereference() repeats its reference rule with the window as
an argument, and a test checks that at ±4 it reproduces the builder's columns exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tasks.wake_calibration import contest as C
from tasks.wake_calibration import estimator as E
from tasks.wake_calibration.build_pass_table import CLEAN_AHEAD_GAP_S, CLEAN_BEHIND_GAP_S, REF_HALF_WINDOW_LAPS, REF_MIN_N

REF_PM2, REF_PM6, NO_LV2024 = "reference_pm2", "reference_pm6", "without_2024_las_vegas"
VARIANTS = (REF_PM2, REF_PM6, NO_LV2024)
WINDOWS = {REF_PM2: 2, REF_PM6: 6}
LV2024 = (2024, "las_vegas_grand_prix")
REF_COLUMNS = ["clean", "ref_n", "ref_time_s", "ref_status", "delta_time_s"]
LABEL = {REF_PM2: "reference window ±2 laps", REF_PM6: "reference window ±6 laps",
         NO_LV2024: "without 2024 Las Vegas in the fit"}


def rereference(passes: pd.DataFrame, half_window: int) -> pd.DataFrame:
    """The builder's reference rule (build_pass_table.references) at another half-window, per race.

    Clean = reason NULL, no yielding tag, clear ahead or gap over 3 s, no car within 1 s behind, and a segment
    time. Donors: same race, driver, corner_id, stint and compound, clean, lap within ±half_window, the pass
    itself excluded; measured when at least REF_MIN_N donors; reference = donor median. Excluded passes get
    ref_n 0 and status 'excluded'. Only the five reference columns change."""
    out = passes.copy()
    tag = out["tag"].fillna("").astype(str)
    clean = (out["reason"].isna() & ~tag.str.contains("yielding")
             & (out["clear_ahead"].astype(bool) | (out["gap_s"] > CLEAN_AHEAD_GAP_S))
             & ~out["behind_1s"].astype(bool) & out["seg_time_s"].notna())
    out["clean"] = clean.to_numpy(dtype=bool)
    ref_n = np.zeros(len(out), dtype=int)
    ref_time = np.full(len(out), np.nan)
    pos = pd.Series(np.arange(len(out)), index=out.index)
    for _, g in out.groupby(["race_id", "driver", "corner_id", "stint", "compound"], dropna=True, sort=False):
        laps = g["lap"].to_numpy()
        donor = g["clean"].to_numpy()
        seg = g["seg_time_s"].to_numpy()
        for i, lap in enumerate(laps):
            m = donor & (np.abs(laps - lap) <= half_window) & (laps != lap)
            if m.any():
                j = pos[g.index[i]]
                ref_n[j] = int(m.sum())
                ref_time[j] = float(np.median(seg[m]))
    excluded = out["reason"].notna().to_numpy()
    ref_n[excluded] = 0
    ref_time[excluded] = np.nan
    out["ref_n"] = ref_n
    out["ref_time_s"] = np.where(ref_n >= REF_MIN_N, ref_time, np.nan)
    out["ref_status"] = np.where(excluded, "excluded",
                                 np.where(ref_n >= REF_MIN_N, "measured", "no_clean_reference"))
    out["delta_time_s"] = out["seg_time_s"] - out["ref_time_s"]
    return out


def lv2024_race_ids(passes: pd.DataFrame) -> list[str]:
    s, slug = LV2024
    return sorted(passes.loc[(passes["season"].astype(int) == s) & (passes["race"] == slug), "race_id"]
                  .astype(str).unique())


def variant_inputs(raw: pd.DataFrame, prepared: pd.DataFrame, panel: pd.DataFrame, calendar: dict,
                   variant: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(prepared passes, panel) for one sensitivity run. `raw` is the pass table as built; `prepared` the main
    run's prepare_passes output (reused for the Las Vegas run, which changes no reference)."""
    if variant in WINDOWS:
        w = WINDOWS[variant]
        return E.prepare_passes(rereference(raw, w), calendar, half_window=w), panel
    if variant == NO_LV2024:
        lv = lv2024_race_ids(raw)
        return (prepared[~prepared["race_key"].astype(str).isin(lv)],
                panel[~panel["race_id"].astype(str).isin(lv)])
    raise E.EstimatorError(f"unknown sensitivity run {variant!r}")


@dataclass
class VariantOutcome:
    variant: str
    result: C.EraResult | None
    error: str = ""


def run_variants(raw: pd.DataFrame, prepared: pd.DataFrame, panel: pd.DataFrame, calendar: dict,
                 held_out_races: list[str], n_draws: int = E.N_BOOT, seed: int = E.SEED,
                 fit_races: list[str] | None = None, race_circuit: dict[str, str] | None = None,
                 variants: tuple[str, ...] = VARIANTS) -> list[VariantOutcome]:
    """Each sensitivity run on the main era, same B and seed. A run that cannot be computed is reported with its
    reason (an error is recorded, not raised: these runs are report-only). Under DRAFT A5, Las Vegas also
    leaves the fit-race list."""
    out = []
    for v in variants:
        try:
            p, pan = variant_inputs(raw, prepared, panel, calendar, v)
            fr, rc = fit_races, race_circuit
            if fr is not None and v == NO_LV2024:
                lv = set(lv2024_race_ids(raw))
                fr = [r for r in fr if r not in lv]
                rc = {r: c for r, c in rc.items() if r not in lv}
            res = C.run_era(p, pan, held_out_races, "main", n_draws=n_draws, seed=seed, fit_races=fr,
                            race_circuit=rc)
            out.append(VariantOutcome(v, res))
        except (E.EstimatorError, ValueError, KeyError) as exc:
            out.append(VariantOutcome(v, None, f"{type(exc).__name__}: {exc}"[:200]))
    return out


def _check(res: C.EraResult, name: str) -> C.Check | None:
    return next((c for c in res.checks if c.name == name), None)


def w1_holds(res: C.EraResult | None) -> bool | None:
    c = None if res is None else _check(res, "W1")
    return None if c is None else c.passed


def table2_rows(outcomes: list[VariantOutcome]) -> list[dict]:
    """Figures only: W1 lower ends, W2 point and lower end, P1 and P2 figures, the setup state. Never pass/fail."""
    rows = []
    for o in outcomes:
        lab = LABEL[o.variant]
        if o.result is None:
            rows.append({"item": f"sensitivity, {lab}", "value": f"{C.UNAVAILABLE} (not computed: {o.error})"})
            continue
        res = o.result
        short = [c.name for c in res.checks if c.name in ("G5", "G7") and c.passed is not True]
        if short:
            rows.append({"item": f"sensitivity, {lab}: setup",
                         "value": f"{C.UNAVAILABLE} (" + "; ".join(f"{c.name}: {c.value}" for c in res.checks
                                                         if c.name in short) + ")"})
        for name in ("W1", "W2"):
            c = _check(res, name)
            rows.append({"item": f"sensitivity, {lab}: {name}",
                         "value": c.value if c is not None else f"{C.UNAVAILABLE} (not reached)"})
        for c, name in ((res.p1, "P1"), (res.p2, "P2")):
            rows.append({"item": f"sensitivity, {lab}: {name}",
                         "value": c.value if c is not None else f"{C.UNAVAILABLE} (not reached)"})
    return rows


def first_lines(main: C.EraResult, outcomes: list[VariantOutcome]) -> list[str]:
    """§12b: if W1 holds at ±4 but not at ±2 or ±6, say so in the scorecard's first lines. Also said, for the
    same reason, when W1 holds but not without 2024 Las Vegas. A run that could not be computed is named too,
    because then it cannot be said that W1 holds there."""
    if w1_holds(main) is not True:
        return []
    out = []
    for o in outcomes:
        h = w1_holds(o.result)
        if h is True:
            continue
        why = "does not hold" if h is False else "could not be assessed"
        out.append(f"Sensitivity: W1 holds in the registered run (±{REF_HALF_WINDOW_LAPS} laps) but {why} "
                   f"with the {LABEL[o.variant]} (Table 2).")
    return out
