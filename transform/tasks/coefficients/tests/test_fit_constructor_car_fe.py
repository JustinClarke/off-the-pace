"""
Unit tests for the de-biased constructor car fixed-effect fit.

A synthetic balanced panel (every driver in every race, every constructor in
every race) is built with a known per-constructor car offset and a known
per-driver skill. The two-way FE fit should recover the *relative* car offsets
(neg = faster) net of driver skill, which is the whole point of the HDFE.
"""

import numpy as np
import pandas as pd
import pytest

pf = pytest.importorskip("pyfixest")

from tasks.coefficients.fit_constructor_car_fe import fit_car_fe


def make_panel(
    *,
    n_races: int = 8,
    car_offsets: dict[str, float] | None = None,
    driver_skill: dict[str, float] | None = None,
    laps_per_cell: int = 12,
    noise_std: float = 0.01,
    seed: int = 1,
) -> pd.DataFrame:
    """Balanced panel where drivers ROTATE across constructors race-to-race.

    Driver mobility makes the driver_id ⊥ constructor_race two-way FE separately
    identifiable (a connected bipartite graph), so the car FE recovers the car
    offset net of skill   the whole point of the HDFE.
    """
    rng = np.random.default_rng(seed)
    car_offsets = car_offsets or {"fast_team": -0.5, "mid_team": 0.0, "slow_team": 0.6}
    driver_skill = driver_skill or {
        "DRV01": -0.2, "DRV02": 0.1, "DRV03": -0.1,
        "DRV04": 0.0, "DRV05": 0.05, "DRV06": -0.05,
    }
    ctors = list(car_offsets)
    drivers = list(driver_skill)
    rows = []
    for race_i in range(n_races):
        race_id = f"2023_{race_i + 1}"
        # Rotate the driver→constructor assignment each race; 2 drivers per team.
        for j, drv in enumerate(drivers):
            ctor = ctors[(j + race_i) % len(ctors)]
            for _ in range(laps_per_cell):
                rows.append({
                    "race_year": 2023,
                    "race_id": race_id,
                    "driver_id": drv,
                    "constructor_id": ctor,
                    "pace_delta_s": (
                        car_offsets[ctor] + driver_skill[drv]
                        + rng.normal(0, noise_std)
                    ),
                })
    panel = pd.DataFrame(rows)
    panel["constructor_race"] = (
        panel.race_year.astype(str) + "_"
        + panel.race_id.astype(str) + "_"
        + panel.constructor_id.astype(str)
    )
    return panel


class TestFitCarFe:
    def test_emits_one_row_per_constructor_race(self):
        panel = make_panel(n_races=8)
        out = fit_car_fe(panel)
        # 3 constructors × 8 races = 24 constructor-races; a reference/singleton
        # FE level may be dropped, so allow one unidentified cell.
        assert set(out.columns) >= {"race_year", "race_id", "constructor_id", "car_fe_s"}
        assert 23 <= len(out) <= 24
        assert out["car_fe_s"].notna().all()

    def test_recovers_relative_car_ranking(self):
        panel = make_panel(n_races=10)
        out = fit_car_fe(panel)
        mean_fe = out.groupby("constructor_id")["car_fe_s"].mean()
        # FE is identified up to a constant; check the ordering is fast < mid < slow.
        assert mean_fe["fast_team"] < mean_fe["mid_team"] < mean_fe["slow_team"]

    def test_recovers_offset_spread(self):
        panel = make_panel(n_races=10)
        out = fit_car_fe(panel)
        mean_fe = out.groupby("constructor_id")["car_fe_s"].mean()
        # True spread fast→slow is 1.1s; the FE spread should be close net of skill.
        spread = mean_fe["slow_team"] - mean_fe["fast_team"]
        assert spread == pytest.approx(1.1, abs=0.1)
