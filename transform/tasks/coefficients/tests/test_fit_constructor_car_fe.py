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


# ── T49 (WI-16a): the default path is unchanged; the isolation path re-centres per race ──

def _head_fit_car_fe(panel: pd.DataFrame) -> pd.DataFrame:
    """Frozen copy of fit_car_fe as it stood at HEAD before --panel existed (logging
    removed). int_driver_race_skill_loro and Ghost Standings consume the default fit, so
    the default path must keep producing exactly this."""
    model = pf.feols("pace_delta_s ~ 1 | driver_id + constructor_race", data=panel)
    fe = model.fixef()
    car_fe = pd.Series(fe["C(constructor_race)"])
    car_fe.index = car_fe.index.astype(str)
    grain = (
        panel[["race_year", "race_id", "constructor_id", "constructor_race"]]
        .drop_duplicates()
        .copy()
    )
    grain["car_fe_s"] = grain.constructor_race.map(car_fe)
    return (
        grain.dropna(subset=["car_fe_s"])[["race_year", "race_id", "constructor_id", "car_fe_s"]]
        .sort_values(["race_year", "race_id", "constructor_id"])
        .reset_index(drop=True)
    )


class TestDefaultPanelUnchanged:
    def test_fit_car_fe_equals_head_on_fixture_panel(self):
        panel = make_panel(n_races=8)
        pd.testing.assert_frame_equal(fit_car_fe(panel), _head_fit_car_fe(panel))

    def test_run_fit_keeps_head_provenance_and_columns(self, monkeypatch):
        from tasks.coefficients import fit_constructor_car_fe as m

        panel = make_panel(n_races=6)

        class _Con:
            def close(self):
                pass

        monkeypatch.setattr(m.duckdb, "connect", lambda *a, **k: _Con())
        monkeypatch.setattr(m, "load_panel", lambda con: panel)
        out = m.run_fit()
        assert list(out.columns) == [
            "race_year", "race_id", "constructor_id", "car_fe_s",
            "fit_date", "data_window", "fit_method", "git_sha", "fit_timestamp",
        ]
        assert (out.fit_method == "constructor_car_fe_hdfe_v1").all()
        pd.testing.assert_frame_equal(
            out[["race_year", "race_id", "constructor_id", "car_fe_s"]], _head_fit_car_fe(panel)
        )

    def test_default_panel_and_output_path(self):
        from tasks.coefficients import fit_constructor_car_fe as m

        assert m.main(["--dry-run"]) == 0
        assert m.OUT_PATH.name == "constructor_car_fe.parquet"
        assert m.ISOLATION_OUT_PATH.name == "constructor_car_fe_isolation.parquet"


def make_isolation_panel(
    *,
    eras: dict[str, list[int]] | None = None,
    island: str | None = None,
    island_global_bridge: bool = True,
    seed: int = 3,
) -> pd.DataFrame:
    """Two eras of races over four teams and eight drivers. The two halves of the grid
    rotate at different speeds, so teammate pairs change race to race and each era's
    teammate network is connected (rotating whole pairs would leave every pair its own
    component: nothing identified). Lap counts differ by team so the lap-weighted
    re-centring is actually exercised.

    island: a team whose only drivers in the first era are D0 and D1, who drive nothing
    else there (the Haas 2018-2021 shape). With island_global_bridge, D0 drives it again
    in the second era, which connects it once the driver key is global; without, D0 and
    D1 do not race in the second era at all, so nothing ever connects it."""
    rng = np.random.default_rng(seed)
    eras = eras or {"pre2022": [2020, 2021], "post2022": [2022, 2023]}
    car = {"fast": -0.6, "mid_a": -0.1, "mid_b": 0.2, "slow": 0.5}
    skill = {f"D{i}": s for i, s in enumerate([-0.2, 0.1, -0.1, 0.0, 0.05, -0.05, 0.15, -0.15])}
    laps_per_team = {"fast": 20, "mid_a": 14, "mid_b": 11, "slow": 7}
    teams = list(car)
    others = [t for t in teams if t != island]
    first_era = list(eras)[0]
    rows = []
    lap_id = 0
    for era, years in eras.items():
        for year in years:
            for rnd in range(1, 5):
                race_id = f"{year}_{rnd}"
                s = rnd + year
                for j, drv in enumerate(skill):
                    team = teams[(j + s) % 4] if j < 4 else teams[(j + 2 * s) % 4]
                    if island is not None:
                        if era == first_era:
                            if drv in ("D0", "D1"):
                                team = island
                            elif team == island:
                                team = others[(j + s) % 3]
                        elif drv in ("D0", "D1"):
                            if not island_global_bridge:
                                continue
                            if drv == "D0":
                                team = island
                    for _ in range(laps_per_team[team]):
                        lap_id += 1
                        rows.append({
                            "lap_id": f"L{lap_id}",
                            "race_year": year,
                            "race_id": race_id,
                            "driver_id": drv,
                            "era": era,
                            "driver_era": f"{drv}_{era}",
                            "constructor_id": team,
                            "y_s": car[team] + skill[drv] + rng.normal(0, 0.02),
                        })
    panel = pd.DataFrame(rows)
    panel["constructor_race"] = (
        panel.race_year.astype(str) + "_" + panel.race_id + "_" + panel.constructor_id
    )
    return panel


def _race_weighted_mean(out: pd.DataFrame) -> pd.Series:
    ok = out.car_iso_s.notna()
    return (
        (out.car_iso_s[ok] * out.n_laps[ok]).groupby([out.race_year[ok], out.race_id[ok]]).sum()
        / out.n_laps[ok].groupby([out.race_year[ok], out.race_id[ok]]).sum()
    )


class TestIsolationPanel:
    def test_lap_weighted_mean_is_zero_in_every_race(self):
        from tasks.coefficients.fit_constructor_car_fe import fit_car_fe_isolation

        out, _ = fit_car_fe_isolation(make_isolation_panel())
        assert out.car_iso_s.notna().all()
        assert np.abs(_race_weighted_mean(out)).max() < 1e-9

    def test_recovers_car_differences_within_each_race(self):
        from tasks.coefficients.fit_constructor_car_fe import fit_car_fe_isolation

        out, _ = fit_car_fe_isolation(make_isolation_panel())
        truth = {"fast": -0.6, "mid_a": -0.1, "mid_b": 0.2, "slow": 0.5}
        for _, g in out.groupby(["race_year", "race_id"]):
            fitted = g.set_index("constructor_id").car_iso_s
            gap = fitted - fitted["mid_a"]
            for team, true in truth.items():
                if team in gap:
                    # Lap noise is 0.02 s and reaches a car level through chains of
                    # drivers; noiseless, the fit recovers these to 2e-5.
                    assert gap[team] == pytest.approx(true - truth["mid_a"], abs=0.05)

    def test_connected_eras_keep_the_era_split(self):
        from tasks.coefficients.fit_constructor_car_fe import fit_car_fe_isolation

        out, note = fit_car_fe_isolation(make_isolation_panel())
        assert set(out.car_term_source) == {"driver_era"}
        assert "global_driver" not in note

    def test_single_constructor_island_falls_back_to_global_driver(self):
        """The Haas 2018-2021 shape: one team whose drivers never drive anything else in
        the era. The WI doc's own rule (more than one component holding two or more
        constructors) does not fire -- the island holds one constructor -- but the island
        team's level is not comparable with the rest of any race it is in, so the race-level
        check must send that era to the global driver key."""
        from tasks.coefficients.fit_constructor_car_fe import fit_car_fe_isolation

        panel = make_isolation_panel(island="slow")
        out, note = fit_car_fe_isolation(panel)
        first = out[out.era == "pre2022"]
        second = out[out.era == "post2022"]
        assert set(first.car_term_source) == {"global_driver"}
        assert set(second.car_term_source) == {"driver_era"}
        assert "pre2022" in note and "global_driver" in note
        assert first.car_iso_s.notna().all()
        assert np.abs(_race_weighted_mean(out)).max() < 1e-9

    def test_island_with_no_bridge_is_unidentified_not_guessed(self):
        from tasks.coefficients.fit_constructor_car_fe import fit_car_fe_isolation

        panel = make_isolation_panel(island="slow", island_global_bridge=False)
        out, _ = fit_car_fe_isolation(panel)
        island_rows = out[(out.era == "pre2022") & (out.constructor_id == "slow")]
        assert len(island_rows) > 0
        assert set(island_rows.car_term_source) == {"unidentified"}
        assert island_rows.car_iso_s.isna().all()
        rest = out[out.car_term_source != "unidentified"]
        assert rest.car_iso_s.notna().all()
        assert np.abs(_race_weighted_mean(out)).max() < 1e-9

    def test_noiseless_panel_is_recovered_exactly(self):
        """pyfixest's fixef() solves by LSQR; at its default 1e-6 tolerances the real
        panel's car terms were off the exact solution by up to 6.8e-3 s. The isolation
        path tightens them; noiseless, the within-race car gaps must come back exactly."""
        from tasks.coefficients.fit_constructor_car_fe import fit_car_fe_isolation

        truth = {"fast": -0.6, "mid_a": -0.1, "mid_b": 0.2, "slow": 0.5}
        skill = {f"D{i}": s for i, s in enumerate([-0.2, 0.1, -0.1, 0.0, 0.05, -0.05, 0.15, -0.15])}
        panel = make_isolation_panel()
        panel["y_s"] = panel.constructor_id.map(truth) + panel.driver_id.map(skill)
        out, _ = fit_car_fe_isolation(panel)
        for _, g in out.groupby(["race_year", "race_id"]):
            fitted = g.set_index("constructor_id").car_iso_s
            for team in fitted.index:
                assert fitted[team] - fitted["mid_a"] == pytest.approx(
                    truth[team] - truth["mid_a"], abs=1e-8)

    def test_row_order_does_not_move_the_car_term(self):
        """The warehouse returns the panel in a different physical order after each
        rebuild; the fit (and load_isolation_panel's ORDER BY) must make that irrelevant."""
        from tasks.coefficients.fit_constructor_car_fe import fit_car_fe_isolation

        panel = make_isolation_panel()
        a, _ = fit_car_fe_isolation(panel)
        b, _ = fit_car_fe_isolation(panel.sample(frac=1.0, random_state=7).reset_index(drop=True))
        key = ["race_year", "race_id", "constructor_id"]
        m = a.merge(b, on=key, suffixes=("_a", "_b"))
        assert len(m) == len(a)
        assert np.abs(m.car_iso_s_a - m.car_iso_s_b).max() < 1e-9
