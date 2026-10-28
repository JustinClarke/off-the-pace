"""Synthetic tests for the report-only pieces (report.py, decision records L5-L6): coverage and contest per team,
§12b counts, Table 2 text. Nothing on disk is read except a tiny parquet written to pytest's tmp_path."""

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import contest as C
from tasks.wake_calibration import estimator as E
from tasks.wake_calibration import report as RP
from tasks.wake_calibration.tests.test_contest import world


def _teams(prepared):
    k = prepared[["season", "race_id", "driver"]].drop_duplicates()
    return k.assign(team=k["driver"].map(lambda d: "T" + str(int(d[1:]) // 2)))


def test_team_map_takes_the_most_frequent_team_and_dash_when_none():
    li = pd.DataFrame({"season": [2025] * 4, "race_id": ["2025_1"] * 4, "driver": ["AAA", "AAA", "AAA", "BBB"],
                       "lap": [1, 2, 3, 1], "team": ["X", "X", "Y", None], "position": [1, 1, 1, 2]})
    t = RP.team_map(li).set_index("driver")["team"]
    assert t["AAA"] == "X" and t["BBB"] == "—"


def test_coverage_per_team_counts_following_braking_passes_and_measured_share():
    prepared, panel, _, _ = world(seed=41, races_per_season=1, n_drivers=4)
    tm = _teams(prepared)
    cov = RP.coverage_per_team(prepared, tm)
    f = prepared[RP.following_braking(prepared)]
    assert cov["following_braking_passes"].sum() == len(f)
    assert cov["measured"].sum() == int((f["ref_status"] == "measured").sum())
    assert ((cov["share_following_measured"] >= 0) & (cov["share_following_measured"] <= 1)).all()
    # no_car_ahead and flat-out passes are not following braking passes
    assert not (f["reason_wc03"] == E.NO_CAR_AHEAD).any() and (f["segment_basis"] == E.BRAKING_BASIS).all()


def test_contest_per_team_is_the_section_8b_score_on_each_teams_laps():
    prepared, panel, _, _ = world(seed=42, races_per_season=2, n_drivers=4)
    held = sorted(panel.loc[panel["race_year"] == 2025, "race_id"].unique())
    res = C.run_era(prepared, panel, held, n_draws=3)
    one = _teams(prepared).assign(team="ALL")
    per = RP.contest_per_team(res, one)
    assert len(per) == 1 and per["laps"].iloc[0] == int(res.contest.point[C.SET_ALL]["laps"])
    assert per["r_flat"].iloc[0] == pytest.approx(res.contest.point[C.SET_ALL]["r_flat"], abs=1e-12)
    per2 = RP.contest_per_team(res, _teams(prepared))
    assert per2["laps"].sum() == per["laps"].iloc[0]
    cov = RP.coverage_per_team(prepared, _teams(prepared), res.scored.laps)
    assert cov["scored_laps"].sum() == len(res.scored.laps)


def test_no_car_ahead_counts_with_and_without_race_leader_positions():
    prepared, _, _, _ = world(seed=43, races_per_season=1, n_drivers=4)
    out = RP.no_car_ahead_counts(prepared)
    assert out["no_car_ahead_passes"].sum() == int((prepared["reason_wc03"] == E.NO_CAR_AHEAD).sum())
    assert (out["of_which_race_leader"] == "—").all()
    k = prepared[["season", "race_id", "driver", "lap"]].drop_duplicates()
    li = k.assign(team="T", position=np.where(k["driver"] == "D0", 1.0, 2.0))
    out = RP.no_car_ahead_counts(prepared, li)
    want = int(((prepared["reason_wc03"] == E.NO_CAR_AHEAD) & (prepared["driver"] == "D0")).sum())
    assert out["of_which_race_leader"].sum() == want


def test_table2_text_refuses_pass_or_fail_and_shows_dashes():
    txt = RP.table2_text([{"item": "a", "value": "— (no laps)"}, {"item": "b", "value": "0.1234"}])
    assert "| a | — (no laps) |" in txt and RP.TABLE2_TITLE in txt
    with pytest.raises(E.EstimatorError):
        RP.table2_text([{"item": "W1", "value": "W1 pass"}])
    assert RP.older_rows(None, "not run")[0]["value"].startswith("—")


def test_lap_info_from_bronze_reads_race_laps_only(tmp_path):
    d = tmp_path / "laps/season=2025/race=x"
    (d / "session=Q").mkdir(parents=True)
    frame = pd.DataFrame({"Driver": ["AAA", "BBB"], "LapNumber": [1.0, 1.0], "Team": ["X", "Y"],
                          "Position": [1.0, 2.0], "race_id": ["2025_1", "2025_1"], "season": [2025, 2025]})
    frame.to_parquet(d / "laps.parquet")
    frame.to_parquet(d / "session=Q" / "q.parquet")
    li = RP.lap_info_from_bronze(tmp_path, [2025])
    assert len(li) == 2 and set(li["team"]) == {"X", "Y"}
    assert RP.lap_info_from_bronze(tmp_path, [2024]).empty
