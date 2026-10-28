"""Synthetic tests for the §11 pit-stop figure (pitstop.py; decision record L3). Report-only figure."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import estimator as E
from tasks.wake_calibration import pitstop as P

CLASSES = ["slow", "medium", "fast", "slow"]
LAPS = range(10, 31)
L = 20


def _base(race_id="2023_7", drivers=("A", "F", "G", "B"), season=2023):
    rows = []
    for d in drivers:
        for lap in LAPS:
            for c in range(1, 5):
                rows.append(dict(season=season, race_id=race_id, driver=d, lap=lap, stint=1.0, compound="HARD",
                                 corner_id=str(c), corner_class=CLASSES[c - 1], segment_basis="brake_onset",
                                 reason=None, reason_wc03=E.NO_CAR_AHEAD, clear_ahead=True, leader=None,
                                 leader_lap=np.nan, gap_s=np.nan, seg_time_s=10.0, clean=True))
    return pd.DataFrame(rows)


def _follow(df, f, leader, laps, gap, extra, lap_offset=0, corners=None):
    m = (df["driver"] == f) & df["lap"].isin(laps)
    if corners is not None:
        m &= df["corner_id"].isin(corners)
    df.loc[m, ["leader", "gap_s", "clean", "clear_ahead", "reason_wc03"]] = [leader, gap, False, False, None]
    df.loc[m, "leader_lap"] = df.loc[m, "lap"].astype(float) + lap_offset
    df.loc[m, "seg_time_s"] += extra
    return df


def _pits(race_id="2023_7", season=2023, extra=()):
    rows = [dict(season=season, race_id=race_id, driver="A", lap=L, pit_in=True, pit_out=False),
            dict(season=season, race_id=race_id, driver="A", lap=L + 1, pit_in=False, pit_out=True)]
    rows += [dict(season=season, race_id=race_id, driver=d, lap=lap, pit_in=True, pit_out=False) for d, lap in extra]
    return pd.DataFrame(rows)


def _race(race_id="2023_7", event_extra=0.3, comp=((0.7, 0.1, 19),), event_gap=0.6, season=2023):
    """A pits on L=20; F follows A on 18, 19 (gap event_gap, +event_extra). Each comparison (gap, extra, P):
    G follows B on P-2, P-1 (B never pits)."""
    df = _base(race_id, season=season)
    _follow(df, "F", "A", [L - 2, L - 1], event_gap, event_extra)
    for gap, extra, big_p in comp:
        _follow(df, "G", "B", [big_p - 2, big_p - 1], gap, extra)
    return df


def _curve(k=1.0):
    return np.full((3, E.N_BINS), k)


def _draws(n, k=1.0):
    return np.full((n, 3, E.N_BINS), k)


# ---------------------------------------------------------------- comparison pairs


def test_comparison_pair_found_and_jump():
    df = _race()
    c = P.comparison_jumps(df, _pits(), "2023_7", 2023, set(range(14, 27)))
    g = c[c["follower"] == "G"]
    assert list(g["P"]) == [19] and g["leader"].iloc[0] == "B" and g["band"].iloc[0] == 1
    assert g["jump_s"].iloc[0] == pytest.approx(0.1)


@pytest.mark.parametrize("who,lap", [("G", 20), ("B", 21), ("B", 17), ("G", 17)])
def test_comparison_excluded_when_either_car_pits(who, lap):
    df = _race()
    c = P.comparison_jumps(df, _pits(extra=[(who, lap)]), "2023_7", 2023, {19})
    assert c[c["follower"] == "G"].empty


def test_comparison_excluded_on_different_lap():
    df = _base()
    _follow(df, "F", "A", [18, 19], 0.6, 0.3)
    _follow(df, "G", "B", [17, 18], 0.7, 0.1, lap_offset=1)
    c = P.comparison_jumps(df, _pits(), "2023_7", 2023, {19})
    assert c[c["follower"] == "G"].empty


def test_event_never_its_own_comparison():
    df = _race()
    c = P.comparison_jumps(df, _pits(), "2023_7", 2023, set(range(14, 27)))
    assert not ((c["leader"] == "A") & ((c["P"] - L).abs() <= 2)).any()


def test_band_of():
    assert P.band_of(0.0) == 0 and P.band_of(0.49) == 0 and P.band_of(0.5) == 1 and P.band_of(1.49) == 2
    assert P.band_of(-0.01) is None and P.band_of(1.5) is None


# ---------------------------------------------------------------- events, cells, drops


def test_adjusted_jump_is_jump_minus_mean_comparison_in_cell():
    df = _base()
    _follow(df, "F", "A", [18, 19], 0.6, 0.3)
    _follow(df, "G", "B", [17, 18], 0.7, 0.1)  # P = 19
    df2 = _base(drivers=("H", "C"))
    _follow(df2, "H", "C", [21, 22], 0.8, 0.2)  # P = 23
    fig = P.pit_figure(pd.concat([df, df2], ignore_index=True), _pits(), [2023], _curve(), _draws(5), n_draws=5)
    e = fig.events.iloc[0]
    assert e["jump_s"] == pytest.approx(0.3)
    assert e["n_comparison"] == 2 and e["comparison_jump_s"] == pytest.approx(0.15)
    assert e["adjusted_jump_s"] == pytest.approx(0.15)


def test_cell_needs_same_band_within_5_laps_same_race():
    # comparison in another band, one 7 laps away, and one in another race: none is in the cell
    df = _race(comp=((1.2, 0.1, 19), (0.7, 0.1, 27)))
    other = _race(race_id="2023_8", comp=((0.7, 0.1, 19),))
    other = other[other["driver"].isin(["G", "B"])]
    fig = P.pit_figure(pd.concat([df, other], ignore_index=True), _pits(), [2023], _curve(), _draws(5), n_draws=5)
    assert fig.events.empty
    assert fig.drops.set_index("reason")["count"]["no_comparison"] == 1


def test_no_band_drop_counted():
    df = _race(event_gap=-0.2)
    fig = P.pit_figure(df, _pits(), [2023], _curve(), _draws(5), n_draws=5)
    d = fig.drops.set_index("reason")["count"]
    assert fig.events.empty and d["no_band"] == 1 and d["no_comparison"] == 0


def test_candidate_drops_carried_from_pit_stop_events():
    fig = P.pit_figure(_race(), _pits(extra=[("F", 21)]), [2023], _curve(), _draws(5), n_draws=5)
    assert fig.drops.set_index("reason")["count"]["follower_pits"] == 1


# ---------------------------------------------------------------- predicted drop


def test_predicted_drop_constant_curve_and_stack():
    df = _race()
    g = df[df["driver"] == "F"]
    assert P.predicted_drop(g, L, _curve(0.4)) == pytest.approx(0.4)
    out = P.predicted_drop(g, L, np.stack([_curve(0.1), _curve(0.3)]))
    assert out.shape == (2,) and np.allclose(out, [0.1, 0.3])


def test_predicted_drop_uses_jump_corners_and_section6_rules():
    df = _race()
    f = df["driver"] == "F"
    # corner 4 loses its outside reference -> out of the jump and of the prediction
    df.loc[f & (df["corner_id"] == "4") & ~df["lap"].isin([18, 19]), "clean"] = False
    # pre corner 1 on lap 18 at gap -0.1 -> first bin; post corner 2 behind a car at 3.5 s -> 0
    df.loc[f & (df["corner_id"] == "1") & (df["lap"] == 18), "gap_s"] = -0.1
    _follow(df, "F", "Z", [21], 3.5, 0.0, corners=["2"])
    df.loc[f & (df["lap"] == 21), "clean"] = True  # keep the timed post rows (clean does not matter there)
    curve = np.zeros((3, E.N_BINS))
    curve[:, 0] = 1.0  # first bin
    curve[:, 2] = 0.5  # gap 0.6
    curve[:, 7] = 9.0  # would only matter if gap 3.5 were priced
    # pre rows: corners 1-3 on laps 18, 19: [1.0, 0.5, 0.5] and [0.5, 0.5, 0.5] -> mean 3.5/6; post all 0
    assert P.predicted_drop(df[f], L, curve) == pytest.approx(3.5 / 6)


def test_no_prediction_when_priced_row_lacks_gap():
    df = _race()
    _follow(df, "F", "Z", [21], np.nan, 0.0, corners=["1"])
    g = df[df["driver"] == "F"]
    assert np.isnan(P.predicted_drop(g, L, _curve()))
    fig = P.pit_figure(df, _pits(), [2023], _curve(), _draws(5), n_draws=5)
    assert fig.events.empty and fig.drops.set_index("reason")["count"]["no_prediction"] == 1


def test_excluded_row_in_clear_air_is_priced_zero():
    df = _race()
    m = (df["driver"] == "F") & (df["lap"] == 21)
    df.loc[m, ["reason", "reason_wc03"]] = ["pit_lap_leader", None]  # clear_ahead stays True
    assert P.predicted_drop(df[df["driver"] == "F"], L, _curve(0.4)) == pytest.approx(0.4)


# ---------------------------------------------------------------- minimum, bootstrap, Table 2


def test_under_200_stops_not_testable():
    fig = P.pit_figure(_race(), _pits(), [2023], _curve(), _draws(5), n_draws=5)
    s = fig.summary
    assert s["n_stops"] == 1 and s["status"] == P.NOT_TESTABLE
    assert s["mean_adjusted_jump_s"] is None and s["ratio"] is None and s["ratio_ci_lower"] is None
    rows = fig.table2_rows()
    assert any(P.UNAVAILABLE in r["value"] for r in rows)


def _many(n_races=200):
    frames, pits = [], []
    for i in range(n_races):
        rid = f"2023_{i}"
        frames.append(_race(race_id=rid, event_extra=0.3 + 0.001 * (i % 7)))
        pits.append(_pits(race_id=rid))
    return pd.concat(frames, ignore_index=True), pd.concat(pits, ignore_index=True)


@pytest.fixture(scope="module")
def many():
    return _many()


def test_bootstrap_uses_draw_i_curve_and_is_deterministic(many):
    passes, pits = many
    n = 20
    k = np.linspace(0.05, 0.25, n)
    draws = k[:, None, None] * np.ones((n, 3, E.N_BINS))
    f1 = P.pit_figure(passes, pits, [2023], _curve(0.1), draws, n_draws=n)
    f2 = P.pit_figure(passes, pits, [2023], _curve(0.1), draws, n_draws=n)
    s = f1.summary
    assert s["status"] == P.OK and s["n_stops"] == 200
    assert s["mean_predicted_s"] == pytest.approx(0.1)
    assert (s["predicted_ci_lower"], s["predicted_ci_upper"]) == pytest.approx(tuple(np.percentile(k, [2.5, 97.5])))
    assert s == f2.summary
    adj = f1.events["adjusted_jump_s"].to_numpy()
    assert s["mean_adjusted_jump_s"] == pytest.approx(adj.mean())
    assert s["adjusted_ci_lower"] <= s["mean_adjusted_jump_s"] <= s["adjusted_ci_upper"]
    assert s["ratio"] == pytest.approx(0.1 / adj.mean())
    row = [r for r in f1.table2_rows() if "share of jump" in r["item"]][0]["value"]
    assert row.startswith("predicted drop is ") and "% of the observed jump" in row


def test_nan_curve_draw_gives_unavailable_interval(many):
    passes, pits = many
    draws = _draws(10, 0.1)
    draws[3, 0, 0] = np.nan
    s = P.pit_figure(passes, pits, [2023], _curve(0.1), draws, n_draws=10).summary
    assert s["predicted_ci_lower"] is None and s["ratio_ci_lower"] is None
    assert s["adjusted_ci_lower"] is not None and "not computable" in s["ratio_ci_reason"]


def test_table2_never_says_pass_or_fail(many):
    passes, pits = many
    for fig in (P.pit_figure(passes, pits, [2023], _curve(0.1), _draws(5, 0.1), n_draws=5),
                P.pit_figure(_race(), _pits(), [2023], _curve(), _draws(5), n_draws=5)):
        text = " ".join(r["item"] + " " + r["value"] for r in fig.table2_rows()).lower()
        assert "pass" not in text.replace("passes", "") and "fail" not in text


def test_curve_draw_count_must_match():
    with pytest.raises(E.EstimatorError):
        P.pit_figure(_race(), _pits(), [2023], _curve(), _draws(4), n_draws=5)


# ---------------------------------------------------------------- pit laps from bronze


def test_pit_laps_from_bronze(tmp_path):
    def write(season, race, name, sub=None):
        d = tmp_path / "laps" / f"season={season}" / f"race={race}"
        if sub:
            d = d / sub
        d.mkdir(parents=True)
        pd.DataFrame({"Driver": ["VER", "VER", "HAM", None], "LapNumber": [1.0, 2.0, 2.0, 3.0],
                      "PitInTime": pd.to_timedelta([None, 5, None, None], unit="s"),
                      "PitOutTime": pd.to_timedelta([None, None, 9, None], unit="s"),
                      "race_id": [f"{season}_1"] * 4, "season": [season] * 4}).to_parquet(d / name)
    write(2023, "bahrain_grand_prix", "laps.parquet")
    write(2023, "bahrain_grand_prix", "q.parquet", sub="session=Q")
    write(2019, "bahrain_grand_prix", "laps.parquet")
    out = P.pit_laps_from_bronze(tmp_path, [2023])
    assert len(out) == 3 and set(out["season"]) == {2023}
    r = out.set_index(["driver", "lap"])
    assert bool(r.loc[("VER", 2), "pit_in"]) and not bool(r.loc[("VER", 2), "pit_out"])
    assert bool(r.loc[("HAM", 2), "pit_out"]) and not bool(r.loc[("VER", 1), "pit_in"])
