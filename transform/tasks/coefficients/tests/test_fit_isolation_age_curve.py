"""
Unit tests for the driver-isolation tyre-age curve (fit_isolation_age_curve, WI-16b).

A synthetic race panel is built with a known LINEAR tyre wear rate, a strong shared
fuel/track trend per lap, per-driver skill and per-(driver, compound) pace. The fit has
to recover the wear rate: that is only possible because some drivers run the same
compound twice (a stint FE with a lap FE could not see a linear age effect at all).
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyfixest")

from tasks.coefficients import fit_isolation_age_curve as F

WEAR_S_PER_LAP = 0.06


def make_panel(n_races: int = 10, n_drivers: int = 10, n_laps: int = 44,
               year: int = 2023, era: str = "post2022", seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    level = {"SOFT": -0.6, "MEDIUM": 0.0, "HARD": 0.4}
    plans = [("MEDIUM", "HARD", "HARD"), ("SOFT", "MEDIUM", "MEDIUM"), ("MEDIUM", "HARD", "MEDIUM")]
    rows = []
    for r in range(n_races):
        race_id = f"{year}_{r + 1}"
        for d in range(n_drivers):
            drv = f"D{d:02d}"
            skill = rng.normal(0, 0.3)
            plan = plans[d % len(plans)]
            stops = sorted(rng.choice(np.arange(10, n_laps - 8), size=2, replace=False))
            bounds = [1, stops[0] + 1, stops[1] + 1, n_laps + 1]
            car_cpd = {c: rng.normal(0, 0.2) for c in level}
            for s, cpd in enumerate(plan):
                start = bounds[s]
                for lap in range(start, bounds[s + 1]):
                    age = lap - start + 1
                    rows.append({
                        "race_year": year, "race_id": race_id, "era": era, "driver_id": drv,
                        "stint_id": f"{race_id}_{drv}_{s}", "lap_number": lap,
                        "compound": cpd, "age": float(age),
                        "lap_time_s": 90.0 - 0.06 * lap + skill + level[cpd] + car_cpd[cpd]
                        + WEAR_S_PER_LAP * age + rng.normal(0, 0.05),
                        "in_fit": True,
                    })
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def small_groups(monkeypatch):
    # The production floor (3000 fit laps per group) is sized for the warehouse.
    monkeypatch.setattr(F, "N_MIN_LAPS", 200)


def _with_tag(panel):
    p = panel.copy()
    p["tag"] = F.era_tag(p.race_year, p.era)
    return p


def test_recovers_linear_wear_through_same_compound_restarts():
    curves, _ = F.fit_curves(_with_tag(make_panel()))
    for g in ("post2022|MEDIUM", "post2022|HARD"):
        v = F.evaluate(curves[g], np.array([5.0, 20.0]))
        assert (v[1] - v[0]) / 15 == pytest.approx(WEAR_S_PER_LAP, abs=0.006), g


def test_race_folds_are_round_robin_and_stable_when_races_are_appended():
    races = [f"2023_{i}" for i in range(12, 0, -1)] + ["2022_3"]
    folds = F.race_folds(races, k=5)
    ordered = sorted(folds, key=F.race_order_key)
    assert ordered[0] == "2022_3" and ordered[1] == "2023_1" and ordered[-1] == "2023_12"
    assert [folds[r] for r in ordered] == [i % 5 for i in range(len(ordered))]
    more = F.race_folds(races + ["2024_1", "2024_2"], k=5)
    assert all(more[r] == folds[r] for r in folds)


def test_a_race_is_never_adjusted_with_a_curve_fitted_on_itself():
    panel = make_panel()
    base = F.fit_isolation_age_curve(panel)
    shocked = panel.copy()
    victim = "2023_3"
    m = shocked.race_id == victim
    shocked.loc[m, "lap_time_s"] += 0.5 * shocked.loc[m, "age"]  # absurd wear, one race only
    after = F.fit_isolation_age_curve(shocked)
    key = ["race_id", "compound", "age_in_stint"]
    b = base.set_index(key).age_effect_s
    a = after.set_index(key).age_effect_s
    own = b.index.get_level_values("race_id") == victim
    np.testing.assert_allclose(a[own], b[own], atol=1e-9)
    assert (a[~own] - b[~own]).abs().max() > 0.05  # the other folds did see the shock


def test_output_grain_covers_every_panel_lap_including_ones_outside_the_fit():
    panel = make_panel()
    panel.loc[panel.index % 7 == 0, "in_fit"] = False
    out = F.fit_isolation_age_curve(panel)
    assert not out.duplicated(["race_id", "compound", "age_in_stint"]).any()
    assert out.age_effect_s.notna().all()
    cells = panel.assign(age_in_stint=panel.age.astype(int))[
        ["race_id", "compound", "age_in_stint"]].drop_duplicates()
    merged = cells.merge(out, how="left", on=["race_id", "compound", "age_in_stint"])
    assert merged.age_effect_s.notna().all()
    assert set(out.fold) == set(range(F.K_FOLDS))


def test_refuses_to_emit_a_zero_curve_for_a_group_no_other_fold_has():
    panel = make_panel()
    legacy = make_panel(n_races=1, year=2018, era="pre2022", seed=9)
    with pytest.raises(RuntimeError, match="no curve for held-out group"):
        F.fit_isolation_age_curve(pd.concat([legacy, panel], ignore_index=True))
