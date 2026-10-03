"""
Fit the tyre-age curve that age-adjusts driver isolation's tier-3 relative pace.

Why (WI-16b, 2026-09-30)
------------------------
Tier 3 compares two cars on the same lap and compound whose tyre ages differ by at most
var('isolation_peer_age_tolerance') laps, and age-adjusts the raw gap:

    relative_pace_gain_s = (t(peer) - t(driver)) - (g(age_peer) - g(age_driver))

Until this fit, g was the compound seed's hockey stick (int_compound_cliff_predicted:
linear wear plus a saturating post-onset cliff ramp, per season x track x compound). The
pre-registered check (WI doc, V3 tier-3 (ii)) is that the adjustment must REDUCE the
pooled within-pair lap-to-lap variance. The seed's ΔC raised it by 3.40% on 2018-2024
[race-clustered 95% CI +2.53, +4.38], +10.5% on 2018 alone, so the seed's per-cell cliff
pricing adds noise to a same-lap comparison.

What
----
One smooth curve per group, fitted on the whole field rather than on the pairs:

    lap_time_s ~ sum_G 1[G] * B_G(age)[:, 1:] | race_driver_compound + race_lap

- B_G is a cubic B-spline basis in age_in_stint with 3 interior knots at the group's age
  quartiles and boundary knots at its 1st/99th percentiles (ages outside are clipped, so
  the curve is flat beyond them). The first basis column is dropped, so g_G is anchored
  at 0 at the lower boundary; only differences inside a (race, compound) mean anything.
- race_lap FE (race x lap number) absorbs fuel burn, track evolution and weather, which
  every car on that lap shares. race_driver_compound FE absorbs the car, the driver and
  that car's pace on that compound in that race.
- What identifies the slope: a driver who fits a NEW set of the SAME compound in the same
  race (M-H-H, S-M-M, ...; 25% of the fit laps sit in such cells on the 2026-09-30 dev):
  his age resets while the lap FE carries on, so the pace he gains against the field is
  the age effect. The other laps contribute curvature only.
- Why not a stint FE (the first version of this fit): inside a stint age = lap - (stint
  start), so a stint FE plus a race_lap FE absorb any LINEAR age effect exactly (the
  age-period-cohort collinearity). Only curvature and the clipped tails pinned the slope,
  and the curves swung by up to 2 s between folds (pre-2022 MEDIUM at age 20: -0.59 to
  +0.34 s). With the (race, driver, compound) FE they move by about 0.1 s.
- Groups G = era|compound: era is the panel's pre/post era_boundary label, except that
  2018 is its own tag because its compound labels are absolute Pirelli names
  (SUPERSOFT, ...), not the race-relative SOFT/MEDIUM/HARD used from 2019. A group with
  fewer than N_MIN_LAPS fit laps is pooled into era|OTHER.
- Fit sample: Ω panel laps in clean air and not in recovery (traffic is priced
  separately, by D, and is part of the relative gap on purpose).
- CROSS-FITTED BY RACE: races are sorted by (year, round) and dealt round-robin into
  K_FOLDS folds; a race's curve is fitted on the other folds only. So the variance check
  never grades a race with a curve fitted on that race. Appending later races does not
  move earlier races between folds.

Design choice, declared (evidence: _roadmap/_fixes/_evidence/wi-16-2026-09-30/age-curve/):
a spline fitted INSIDE the pair design (pair fixed effects) passes the variance check
(-0.32% [-0.66, +0.01]) but learns curves where a 3-lap-older pre-2022 SOFT or MEDIUM
tyre is up to 0.75 s FASTER. Within a pair the age gap is 0 in the first stint and
non-zero only after the stops, so the pair FE hands pair x compound pace differences to
"age". This field-level fit gives rising curves in every group (0.03-0.11 s/lap over
ages 5-20, steeper over the first laps of a set) and moves the within-pair variance by
about +0.7% on the 2026-09-30 dev: far less added noise than the seed, but NOT the
reduction the pre-registered rule asks for. It was chosen for identification and
physical plausibility, not for the score.

Output
------
data/fits/isolation_age_curve.parquet, one row per (race_year, race_id, compound,
age_in_stint) present in the panel (every Ω lap, not only the fit sample), with
age_effect_s (s, POSITIVE = slower than the group's reference age), the group, the fold
and provenance. Read by int_driver_isolation_age_curve. A per-build fit, not a seed.

Usage
-----
    python -m tasks.coefficients.fit_isolation_age_curve
    python -m tasks.coefficients.fit_isolation_age_curve --db <dev.duckdb> --out <parquet>
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyfixest as pf  # type: ignore
from scipy.interpolate import BSpline

from .provenance import build_provenance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
OUT_PATH = REPO_ROOT / "data" / "fits" / "isolation_age_curve.parquet"
FIT_METHOD = "isolation_age_curve_bspline_rdc_cf5_v1"

K_FOLDS = 5
N_MIN_LAPS = 3000
DEGREE = 3
INNER_KNOT_PCTS = (25.0, 50.0, 75.0)
BOUNDARY_PCTS = (1.0, 99.0)
# Seasons whose compound labels are absolute Pirelli names, not race-relative.
LEGACY_LABEL_YEARS = frozenset({2018})

PANEL_QUERY = """
SELECT
    lap_id,
    race_year,
    race_id,
    era,
    driver_id,
    stint_id,
    lap_number,
    compound,
    CAST(age_in_stint AS DOUBLE) AS age,
    lap_time_s,
    (NOT is_dirty_air_lap AND stint_phase <> 'recovery') AS in_fit
FROM int_driver_isolation_lap_panel
WHERE age_in_stint IS NOT NULL
  AND lap_time_s IS NOT NULL
-- A fixed row order: the FE solve is iterative, so the physical order of the table would
-- otherwise leak into the last digits of the curve.
ORDER BY lap_id
"""

OUTPUT_COLUMNS = [
    "race_year", "race_id", "compound", "age_in_stint", "age_effect_s",
    "fit_group", "fold", "n_fit_laps_group", "boundary_lo_age", "boundary_hi_age",
]


def race_order_key(race_id: str) -> tuple[int, int]:
    year, rnd = race_id.split("_")
    return int(year), int(rnd)


def race_folds(race_ids, k: int = K_FOLDS) -> dict[str, int]:
    """Races sorted by (year, round), dealt round-robin into k folds."""
    races = sorted(set(race_ids), key=race_order_key)
    return {r: i % k for i, r in enumerate(races)}


def era_tag(race_year: pd.Series, era: pd.Series) -> pd.Series:
    return pd.Series(
        np.where(race_year.isin(LEGACY_LABEL_YEARS), race_year.astype(str), era.astype(str)),
        index=race_year.index,
    )


def knots_for(ages: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(ages, BOUNDARY_PCTS)
    if not hi > lo:
        raise ValueError(f"degenerate age range [{lo}, {hi}] for a spline group")
    inner = np.unique(np.percentile(ages, INNER_KNOT_PCTS))
    inner = inner[(inner > lo) & (inner < hi)]
    return np.r_[[lo] * (DEGREE + 1), inner, [hi] * (DEGREE + 1)]


def basis(age: np.ndarray, t: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(age, dtype=float), t[DEGREE], t[-DEGREE - 1])
    return BSpline.design_matrix(x, t, DEGREE).toarray()


def group_key(tag: str, compound: str, big: set[tuple[str, str]]) -> str:
    return f"{tag}|{compound}" if (tag, compound) in big else f"{tag}|OTHER"


def fit_curves(train: pd.DataFrame) -> tuple[dict[str, dict], set[tuple[str, str]]]:
    """Fit g_G on `train` (fit-sample laps). Returns ({group: {t, beta, n}}, big groups)."""
    counts = train.groupby(["tag", "compound"]).size()
    big = {k for k, v in counts.items() if v >= N_MIN_LAPS}
    grp = np.array([group_key(t, c, big) for t, c in zip(train.tag, train.compound)])
    age = train.age.to_numpy()
    cols: dict[str, np.ndarray] = {}
    curves: dict[str, dict] = {}
    for g in sorted(set(grp)):
        m = grp == g
        t = knots_for(age[m])
        z = basis(age, t)[:, 1:]
        z[~m] = 0.0
        names = [f"z{len(cols) + j}" for j in range(z.shape[1])]
        for j, name in enumerate(names):
            cols[name] = z[:, j]
        curves[g] = {"t": t, "cols": names, "n": int(m.sum())}
    df = pd.DataFrame(cols)
    df["y"] = train.lap_time_s.to_numpy()
    df["race_driver_compound"] = (
        train.race_id + "|" + train.driver_id.astype(str) + "|" + train.compound.astype(str)
    ).to_numpy()
    df["race_lap"] = (train.race_id + "|" + train.lap_number.astype(str)).to_numpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # pyfixest's singleton-drop notice
        model = pf.feols(
            "y ~ " + " + ".join(cols) + " | race_driver_compound + race_lap",
            data=df, fixef_tol=1e-10, fixef_maxiter=100_000,
        )
    coef = model.coef()
    for g, c in curves.items():
        missing = [n for n in c["cols"] if n not in coef.index]
        if missing:
            raise RuntimeError(f"spline group {g}: coefficients dropped by the fit: {missing}")
        c["beta"] = np.r_[0.0, coef[c["cols"]].to_numpy()]
    return curves, big


def evaluate(curve: dict, age: np.ndarray) -> np.ndarray:
    return basis(age, curve["t"]) @ curve["beta"]


def fit_isolation_age_curve(panel: pd.DataFrame) -> pd.DataFrame:
    """Cross-fitted age curve for every (race, compound, age) in `panel`.

    panel columns: race_year, race_id, era, driver_id, stint_id, lap_number, compound,
    age, lap_time_s, in_fit."""
    panel = panel.copy()
    panel["tag"] = era_tag(panel.race_year, panel.era)
    folds = race_folds(panel.race_id)
    panel["fold"] = panel.race_id.map(folds)
    cells = (
        panel.groupby(["race_year", "race_id", "tag", "compound", "age", "fold"], as_index=False)
        .size()
        .drop(columns="size")
    )
    out = []
    fit_sample = panel[panel.in_fit]
    for k in range(K_FOLDS):
        train = fit_sample[fit_sample.fold != k]
        curves, big = fit_curves(train)
        for g, c in sorted(curves.items()):
            ref = np.array([5.0, 10.0, 20.0])
            v = evaluate(c, ref)
            log.info(
                "fold %d  %-18s n=%6d  knots %s  g(5,10,20) = %+.3f %+.3f %+.3f s",
                k, g, c["n"], np.round(c["t"][DEGREE:-DEGREE], 1).tolist(), *v,
            )
        held = cells[cells.fold == k].copy()
        held["fit_group"] = [group_key(t, c, big) for t, c in zip(held.tag, held.compound)]
        absent = sorted(set(held.fit_group) - set(curves))
        if absent:
            raise RuntimeError(
                f"fold {k}: no curve for held-out group(s) {absent}; refusing to emit an "
                "unadjusted (zero) age effect"
            )
        held["age_effect_s"] = np.nan
        held["n_fit_laps_group"] = 0
        held["boundary_lo_age"] = np.nan
        held["boundary_hi_age"] = np.nan
        for g, idx in held.groupby("fit_group").groups.items():
            c = curves[g]
            held.loc[idx, "age_effect_s"] = evaluate(c, held.loc[idx, "age"].to_numpy())
            held.loc[idx, "n_fit_laps_group"] = c["n"]
            held.loc[idx, "boundary_lo_age"] = c["t"][DEGREE]
            held.loc[idx, "boundary_hi_age"] = c["t"][-DEGREE - 1]
        out.append(held)
    res = pd.concat(out, ignore_index=True)
    res["age_in_stint"] = res.age.round().astype(int)
    if not np.allclose(res.age, res.age_in_stint):
        raise RuntimeError("age_in_stint is not integral in the panel")
    res = res[OUTPUT_COLUMNS].sort_values(["race_year", "race_id", "compound", "age_in_stint"])
    if res.duplicated(["race_id", "compound", "age_in_stint"]).any():
        raise RuntimeError("duplicate (race_id, compound, age_in_stint) rows")
    if res.age_effect_s.isna().any():
        raise RuntimeError("NULL age_effect_s emitted")
    log.info(
        "Emitting %d (race, compound, age) rows over %d races; age_effect_s in [%.3f, %.3f].",
        len(res), res.race_id.nunique(), res.age_effect_s.min(), res.age_effect_s.max(),
    )
    return res.reset_index(drop=True)


def run_fit(db_path: Path = DB_PATH) -> pd.DataFrame:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        panel = con.execute(PANEL_QUERY).fetchdf()
    finally:
        con.close()
    log.info(
        "Loaded %d Ω laps (%d in the fit sample: clean air, not recovery) over %d races.",
        len(panel), int(panel.in_fit.sum()), panel.race_id.nunique(),
    )
    out = fit_isolation_age_curve(panel)
    prov = build_provenance(
        fit_method=FIT_METHOD,
        season_min=int(panel.race_year.min()),
        season_max=int(panel.race_year.max()),
    )
    for k, v in prov.items():
        out[k] = v
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fit the cross-fitted tyre-age curve for driver isolation's tier-3 "
        "relative pace (WI-16b)."
    )
    parser.add_argument("--db", type=Path, default=DB_PATH,
                        help="warehouse to read, read-only (default data/dev.duckdb)")
    parser.add_argument("--out", type=Path, default=OUT_PATH,
                        help="parquet to write (default data/fits/isolation_age_curve.parquet)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        log.info("DRY RUN would write %s", args.out)
        return 0
    out = run_fit(args.db)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out, index=False)
    log.info("Wrote %d rows -> %s", len(out), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
