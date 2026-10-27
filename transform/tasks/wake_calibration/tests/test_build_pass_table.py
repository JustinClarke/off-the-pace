"""Synthetic tests for the WC-01 pass table builder. No bronze data is read."""

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import build_pass_table as bpt
from tasks.wake_calibration.build_pass_table import (
    CAR_AHEAD_MAX_S,
    ApexEvent,
    ApexIndex,
    CarTrace,
    gap_offsets,
    gap_to_leader,
    neutral_intervals,
    overlaps_any,
    within_restart_skip,
)


def _trace(t0: float, speed_ms: float = 50.0, length_m: float = 5000.0, step_m: float = 5.0) -> CarTrace:
    cum = np.arange(0.0, length_m + step_m, step_m)
    n = len(cum)
    return CarTrace(
        cum=cum,
        t=t0 + cum / speed_ms,
        v=np.full(n, speed_ms * 3.6),
        brake=np.zeros(n, dtype=bool),
        on_track=np.ones(n, dtype=bool),
        x=cum.copy(),
        y=np.zeros(n),
    )


def _event(driver: str, t: float, lap: int = 10, cum: float = 2000.0, brake: float = -100.0) -> ApexEvent:
    return ApexEvent(driver=driver, lap=lap, corner="1", cum_apex=cum, t_apex=t, apex_kph=100.0, brake_offset=brake)


# ---------------------------------------------------------------- (a) exclusions


def test_neutral_intervals_and_restarts():
    ts = pd.DataFrame(
        {"Status": ["1", "2", "1", "4", "1", "6", "7", "1"],
         "session_time_s": [0.0, 100.0, 120.0, 500.0, 700.0, 900.0, 950.0, 1000.0]}
    )
    neutral, restarts = neutral_intervals(ts)
    # Track status 2 (yellow) no longer neutralises the whole lap: only SC, red and VSC do.
    assert neutral == [(500.0, 700.0), (900.0, 950.0), (950.0, 1000.0)]
    assert neutral_intervals(ts, {bpt.YELLOW_STATUS})[0] == [(100.0, 120.0)]
    # SC ends at 700; VSC ends at 950 (start of "ending"), VSC-ending ends at 1000. Yellow is not a restart.
    assert restarts == [700.0, 950.0, 1000.0]


def test_neutral_intervals_unsorted_input_and_final_open_interval():
    ts = pd.DataFrame({"Status": ["5", "1"], "session_time_s": [300.0, 10.0]})
    neutral, restarts = neutral_intervals(ts)
    assert neutral == [(300.0, np.inf)]
    assert restarts == []  # red never ended inside the data


def test_overlaps_any():
    intervals = [(100.0, 120.0), (500.0, 700.0)]
    assert overlaps_any(90.0, 101.0, intervals)
    assert overlaps_any(600.0, 690.0, intervals)
    assert overlaps_any(400.0, 800.0, intervals)
    assert not overlaps_any(120.0, 200.0, intervals)  # touching the end is not overlapping
    assert not overlaps_any(0.0, 100.0, intervals)  # touching the start is not overlapping
    assert not overlaps_any(130.0, 490.0, intervals)
    assert not overlaps_any(np.nan, np.nan, intervals)


def test_within_restart_skip_takes_first_two_laps_after_each_restart():
    starts = [0.0, 90.0, 180.0, 270.0, 360.0, 450.0, 540.0]
    restarts = [200.0]
    flagged = [s for s in starts if within_restart_skip(s, restarts, starts)]
    assert flagged == [270.0, 360.0]
    # A lap that starts exactly at the restart counts as the first lap after it.
    assert [s for s in starts if within_restart_skip(s, [180.0], starts)] == [180.0, 270.0]
    assert not within_restart_skip(np.nan, restarts, starts)
    assert not any(within_restart_skip(s, [], starts) for s in starts)


# ---------------------------------------------------------------- (b) windows do not overlap


@pytest.mark.parametrize("seg_offset", [-250.0, -120.0, -35.0, 0.0])
def test_gap_window_ends_before_the_segment_starts(seg_offset):
    offsets = gap_offsets(seg_offset)
    assert offsets.size == int((bpt.GAP_LOOKBACK_M - bpt.GAP_NEAREST_M) / bpt.GAP_STEP_M) + 1
    assert offsets.min() == pytest.approx(seg_offset - bpt.GAP_LOOKBACK_M)
    assert offsets.max() == pytest.approx(seg_offset - bpt.GAP_NEAREST_M)
    assert offsets.max() < seg_offset


def test_gap_offsets_empty_without_a_segment_start():
    assert gap_offsets(np.nan).size == 0
    tr = _trace(0.0)
    assert gap_to_leader(2000.0, tr, 2000.0, tr, np.nan) == (pytest.approx(np.nan, nan_ok=True), 0)


def test_outcome_window_starts_at_the_segment_start():
    trace = _trace(t0=0.0, speed_ms=50.0)
    seg_offset = -120.0
    table = pd.DataFrame({"driver": ["A"], "cum_apex": [2000.0], "seg_offset_m": [seg_offset]})
    out = bpt.attach_outcomes(table, {"A": trace})
    start_cum = 2000.0 + seg_offset
    assert out["seg_start_t"].iloc[0] == pytest.approx(start_cum / 50.0)
    assert out["seg_time_s"].iloc[0] == pytest.approx((-seg_offset + bpt.SEGMENT_AFTER_APEX_M) / 50.0)
    # The last gap sample lies strictly before the first outcome sample.
    assert 2000.0 + gap_offsets(seg_offset).max() < start_cum


def test_outcome_nan_without_a_segment_start():
    out = bpt.attach_outcomes(
        pd.DataFrame({"driver": ["A"], "cum_apex": [2000.0], "seg_offset_m": [np.nan]}), {"A": _trace(0.0)}
    )
    assert out[["seg_start_t", "seg_end_t", "seg_time_s", "min_speed_kph"]].isna().all(axis=None)


# ---------------------------------------------------------------- (c) car ahead


def test_car_ahead_is_latest_prior_apex_by_another_car():
    events = [_event("A", 100.0), _event("B", 101.0), _event("C", 101.5), _event("F", 102.0)]
    index = ApexIndex(events)
    assert index.car_ahead(events[-1]).driver == "C"


def test_car_ahead_skips_the_followers_own_earlier_apex():
    f_prev = _event("F", 10.0, lap=9)
    a = _event("A", 20.0)
    f = _event("F", 25.0)
    # The follower's own previous-lap apex is the latest within the window only if later than A's; here make it so.
    f_prev_late = _event("F", 22.0, lap=9)
    index = ApexIndex([f_prev, a, f_prev_late, f])
    assert index.car_ahead(f).driver == "A"


def test_car_ahead_respects_the_time_limit():
    a = _event("A", 0.0)
    f_in = _event("F", CAR_AHEAD_MAX_S)
    f_out = _event("G", CAR_AHEAD_MAX_S + 0.01)
    assert ApexIndex([a, f_in]).car_ahead(f_in).driver == "A"
    assert ApexIndex([a, f_out]).car_ahead(f_out) is None


def test_car_ahead_none_for_the_first_car_and_within_behind():
    a, b = _event("A", 50.0), _event("B", 50.8)
    index = ApexIndex([b, a])
    assert index.car_ahead(a) is None
    assert index.within_behind(a, 1.0)
    assert not index.within_behind(a, 0.5)
    assert not index.within_behind(b, 1.0)


# ---------------------------------------------------------------- (d) gap


def test_gap_to_leader_constant_offset():
    leader = _trace(t0=100.0, speed_ms=60.0)
    follower = _trace(t0=101.0, speed_ms=60.0)
    gap, n = gap_to_leader(2500.0, follower, 2500.0, leader, -120.0)
    assert gap == pytest.approx(1.0, abs=1e-9)
    assert n == gap_offsets(-120.0).size


def test_gap_to_leader_uses_each_cars_own_apex_anchor():
    # Same physical place, different cumulative distance on each car's axis (e.g. different lap lengths).
    leader = _trace(t0=100.0, speed_ms=60.0)
    follower = _trace(t0=101.0 - 30.0 / 60.0, speed_ms=60.0)  # follower's axis is 30 m longer before here
    gap, _ = gap_to_leader(2530.0, follower, 2500.0, leader, -100.0)
    assert gap == pytest.approx(1.0, abs=1e-9)


def test_gap_to_leader_outside_the_trace_is_nan():
    leader = _trace(t0=0.0, length_m=500.0)
    follower = _trace(t0=1.0, length_m=500.0)
    gap, n = gap_to_leader(100.0, follower, 100.0, leader, -100.0)  # window lies before cum 0
    assert np.isnan(gap) and n == 0


# ---------------------------------------------------------------- (e) reference rule


def _ref_table() -> pd.DataFrame:
    rows = []
    for lap in range(10, 21):
        rows.append(
            {"driver": "A", "corner_id": "3", "stint": 2.0, "compound": "MEDIUM", "lap": lap,
             "seg_time_s": float(lap), "reason": None, "tag": None, "clear_ahead": True, "gap_s": np.nan,
             "behind_1s": False}
        )
    t = pd.DataFrame(rows)
    extra = [
        # Other stint, other compound, other corner, other driver: never donors for A/3/2/MEDIUM.
        dict(driver="A", corner_id="3", stint=3.0, compound="MEDIUM", lap=15, seg_time_s=99.0),
        dict(driver="A", corner_id="3", stint=2.0, compound="HARD", lap=15, seg_time_s=99.0),
        dict(driver="A", corner_id="4", stint=2.0, compound="MEDIUM", lap=15, seg_time_s=99.0),
        dict(driver="B", corner_id="3", stint=2.0, compound="MEDIUM", lap=15, seg_time_s=99.0),
    ]
    for e in extra:
        e.update(reason=None, tag=None, clear_ahead=True, gap_s=np.nan, behind_1s=False)
    t = pd.concat([t, pd.DataFrame(extra)], ignore_index=True)
    # Lap 14: excluded. Lap 16: a car 1.5 s ahead (not clean). Lap 17: car within 1 s behind.
    # Lap 18: yielding. Lap 19: 4 s behind a car (clean).
    a3 = (t["driver"] == "A") & (t["corner_id"] == "3") & (t["stint"] == 2.0) & (t["compound"] == "MEDIUM")
    t.loc[a3 & (t["lap"] == 14), "reason"] = "pit_lap"
    t.loc[a3 & (t["lap"] == 16), ["clear_ahead", "gap_s"]] = [False, 1.5]
    t.loc[a3 & (t["lap"] == 17), "behind_1s"] = True
    t.loc[a3 & (t["lap"] == 18), "tag"] = "yielding"
    t.loc[a3 & (t["lap"] == 19), ["clear_ahead", "gap_s"]] = [False, 4.0]
    return t


def test_reference_donors_same_driver_corner_stint_compound_within_window():
    out = bpt.references(_ref_table())
    a3 = out[(out["driver"] == "A") & (out["corner_id"] == "3") & (out["stint"] == 2.0) & (out["compound"] == "MEDIUM")]
    row = a3.set_index("lap")
    assert row.loc[[14, 16, 17, 18], "clean"].tolist() == [False, False, False, False]
    assert row.loc[19, "clean"]
    # Lap 15: window 11..19, minus self (15), minus 14, 16, 17, 18 -> donors 11, 12, 13, 19.
    assert row.loc[15, "ref_n"] == 4
    assert row.loc[15, "ref_time_s"] == pytest.approx(np.median([11, 12, 13, 19]))
    assert row.loc[15, "ref_status"] == "measured"
    assert row.loc[15, "delta_time_s"] == pytest.approx(15 - np.median([11, 12, 13, 19]))
    # Lap 16 (not clean itself) still gets a reference: window 12..20 minus 14,16,17,18 -> 12,13,15,19,20.
    assert row.loc[16, "ref_n"] == 5
    # Excluded passes get no reference.
    assert row.loc[14, "ref_status"] == "excluded" and row.loc[14, "ref_n"] == 0
    assert np.isnan(row.loc[14, "ref_time_s"])


def test_reference_never_includes_self_or_other_groups():
    out = bpt.references(_ref_table())
    # The 99 s rows in other groups have no donors of their own and never leak into group A/3/2/MEDIUM.
    a3 = out[(out["driver"] == "A") & (out["corner_id"] == "3") & (out["stint"] == 2.0) & (out["compound"] == "MEDIUM")]
    assert a3["ref_time_s"].max() < 99.0
    others = out[out["seg_time_s"] == 99.0]
    assert (others["ref_n"] == 0).all()
    assert (others["ref_status"] == "no_clean_reference").all()


def test_reference_below_min_n_is_no_clean_reference():
    t = _ref_table()
    a3 = (t["driver"] == "A") & (t["corner_id"] == "3") & (t["stint"] == 2.0) & (t["compound"] == "MEDIUM")
    # Leave only lap 10 and lap 11 clean: lap 10's only donor is lap 11.
    t.loc[a3 & (t["lap"] > 11), "behind_1s"] = True
    out = bpt.references(t).set_index(["driver", "corner_id", "stint", "compound", "lap"])
    r10 = out.loc[("A", "3", 2.0, "MEDIUM", 10)]
    assert r10["ref_n"] == 1 and r10["ref_status"] == "no_clean_reference" and np.isnan(r10["ref_time_s"])
    assert bpt.REF_MIN_N == 2


# ---------------------------------------------------------------- loading


def _write_ci(root, season, race, frame):
    folder = root / "circuit_info" / f"season={season}" / f"race={race}"
    folder.mkdir(parents=True)
    frame.to_parquet(folder / "circuit_info.parquet", index=False)


def test_circuit_info_falls_back_to_a_neighbouring_season(tmp_path):
    good = pd.DataFrame({"X": [1.0, 2.0], "Y": [3.0, 4.0], "Number": [1, 1], "Letter": ["", "A"]})
    _write_ci(tmp_path, 2024, "x_gp", pd.DataFrame({"index": [], "season": []}))  # no X/Y/Number columns
    _write_ci(tmp_path, 2025, "x_gp", good)
    ci, source = bpt.load_circuit_info(2024, "x_gp", tmp_path)
    assert source == 2025
    assert bpt.corner_table(ci)["corner_id"].tolist() == ["1", "1A"]


def test_circuit_info_missing_everywhere_skips_the_race(tmp_path):
    _write_ci(tmp_path, 2020, "y_gp", pd.DataFrame({"X": [], "Y": [], "Number": [], "Letter": []}))
    with pytest.raises(bpt.SkipRace):
        bpt.load_circuit_info(2020, "y_gp", tmp_path)


def test_choose_circuit_replaces_a_misaligned_frame():
    trace = _trace(0.0, length_m=3000.0)  # runs along y=0, x = 0..3000
    trace.lap_span = {lap: (0, len(trace.cum)) for lap in range(1, 12)}
    trace.lap_complete = set(range(2, 11))
    aligned = pd.DataFrame({"X": [500.0, 1500.0], "Y": [10.0, -10.0], "Number": [1, 2], "Letter": ["", ""]})
    shifted = aligned.assign(Y=aligned["Y"] + 5000.0)
    _, season, match = bpt.choose_circuit([(shifted, 2022), (aligned, 2021)], trace)
    assert (season, match) == (2021, 1.0)
    _, season, _ = bpt.choose_circuit([(aligned, 2022), (shifted, 2021)], trace)
    assert season == 2022  # own season kept when it matches


# ---------------------------------------------------------------- flat-out corners


def _layout_input() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for lap in range(5, 15):
        # Corner "1" brakes on every pass; corner "2" never brakes (flat out); corner "3" brakes on 1 in 10.
        rows.append(dict(corner_id="1", brake_offset_m=-80.0 - lap, apex_kph=110.0))
        rows.append(dict(corner_id="2", brake_offset_m=np.nan, apex_kph=290.0))
        rows.append(dict(corner_id="3", brake_offset_m=-60.0 if lap == 5 else np.nan, apex_kph=250.0))
        for r in rows[-3:]:
            r.update(driver="A", lap=lap, lap_t0=lap * 90.0, lap_t1=lap * 90.0 + 90.0, has_lap=True, pit=False,
                     leader_pit=False, clear_ahead=True, apex_dt_s=np.nan)
    table = pd.DataFrame(rows)
    laps = pd.DataFrame({"driver": ["A"] * 10, "t0": [lap * 90.0 for lap in range(5, 15)]})
    ts = pd.DataFrame({"Status": ["1"], "session_time_s": [0.0]})
    return table, ts, laps


def test_flat_out_corner_gets_a_fixed_segment_start():
    table, ts, laps = _layout_input()
    out = bpt.corner_layout(table, ts, laps).drop_duplicates("corner_id").set_index("corner_id")
    assert out.loc["1", "segment_basis"] == "brake_onset"
    assert out.loc["1", "seg_offset_m"] == pytest.approx(np.median([-80.0 - lap for lap in range(5, 15)]))
    for corner in ("2", "3"):  # under FLAT_KINK_BRAKE_SHARE of passes brake
        assert out.loc[corner, "segment_basis"] == "fixed_before_apex"
        assert out.loc[corner, "seg_offset_m"] == -bpt.FLAT_SEGMENT_BEFORE_APEX_M


def test_flat_out_corner_gap_window_does_not_overlap_its_outcome_window():
    seg = -bpt.FLAT_SEGMENT_BEFORE_APEX_M
    offsets = gap_offsets(seg)
    assert offsets.min() == pytest.approx(seg - bpt.GAP_LOOKBACK_M)
    assert offsets.max() == pytest.approx(seg - bpt.GAP_NEAREST_M) and offsets.max() < seg
    trace = _trace(t0=0.0, speed_ms=80.0)
    out = bpt.attach_outcomes(pd.DataFrame({"driver": ["A"], "cum_apex": [2000.0], "seg_offset_m": [seg]}), {"A": trace})
    assert out["seg_time_s"].iloc[0] == pytest.approx((bpt.FLAT_SEGMENT_BEFORE_APEX_M + bpt.SEGMENT_AFTER_APEX_M) / 80.0)
    assert trace.t[np.searchsorted(trace.cum, 2000.0 + offsets.max())] < out["seg_start_t"].iloc[0]


# ---------------------------------------------------------------- track limits and reason order


def test_track_limits_laps_reads_deleted_and_reason():
    laps = pd.DataFrame(
        {
            "Deleted": [True, True, False, True, None, True],
            "DeletedReason": ["TRACK LIMITS AT TURN 4 LAP 12", "track limits at turn 10 (next lap)",
                              "TRACK LIMITS AT TURN 4 LAP 3", "OTHER", None, None],
        }
    )
    assert bpt.track_limits_laps(laps).tolist() == [True, True, False, False, False, False]
    assert bpt.track_limits_laps(pd.DataFrame({"LapNumber": [1, 2]})).tolist() == [False, False]


def _flag_table(**overrides) -> pd.DataFrame:
    base = dict(
        driver="A", number="1", compound="MEDIUM", lap=10, lap_t0=900.0, lap_t1=990.0, cum_apex=2000.0,
        leader="B", leader_cum_apex=2000.0, leader_lap=10.0, seg_offset_m=-100.0, gap_s=1.0, gap_n=26,
        f_lap1=False, f_no_lap=False, f_no_time=False, f_neutral=False, f_yellow_sector=False, f_ts_yellow=False,
        f_restart=False,
        pit=False, leader_pit=False, track_limits=False,
    )
    base.update(overrides)
    return pd.DataFrame([base])


def _flags(table: pd.DataFrame) -> pd.DataFrame:
    traces = {"A": _trace(0.0), "B": _trace(-1.0)}
    empty_w = pd.DataFrame({"session_time_s": [], "rainfall_flag": []})
    empty_b = pd.DataFrame({"t": [], "RacingNumber": []})
    return bpt.attach_flags(table, traces, None, None, empty_w, empty_b)


def test_reason_order_places_track_limits_after_wet_and_pit():
    assert bpt.REASONS.index("wet") < bpt.REASONS.index("track_limits") < bpt.REASONS.index("off_track")
    assert "flat_kink" not in bpt.REASONS
    assert _flags(_flag_table(track_limits=True))["reason"].iloc[0] == "track_limits"
    assert _flags(_flag_table(track_limits=True, pit=True))["reason"].iloc[0] == "pit_lap"
    assert _flags(_flag_table(track_limits=True, compound="WET"))["reason"].iloc[0] == "wet"
    assert _flags(_flag_table())["reason"].iloc[0] is None


def test_no_segment_reason_when_a_corner_has_no_start():
    assert _flags(_flag_table(seg_offset_m=np.nan))["reason"].iloc[0] == "no_segment"


def test_yellow_sector_reason_and_priority():
    assert bpt.REASONS.index("neutralised") < bpt.REASONS.index("yellow_sector") < bpt.REASONS.index("restart")
    assert _flags(_flag_table(f_yellow_sector=True))["reason"].iloc[0] == "yellow_sector"
    assert _flags(_flag_table(f_yellow_sector=True, f_neutral=True))["reason"].iloc[0] == "neutralised"
    # Track status 2 on the lap is a diagnostic only: it no longer excludes.
    out = _flags(_flag_table(f_ts_yellow=True))
    assert out["reason"].iloc[0] is None and out["ts_yellow_on_lap"].iloc[0]


def test_neutral_intervals_without_yellow():
    ts = pd.DataFrame({"Status": ["1", "2", "1", "4", "1"], "session_time_s": [0.0, 100.0, 120.0, 500.0, 700.0]})
    hard, restarts = neutral_intervals(ts)
    assert hard == [(500.0, 700.0)] and restarts == [700.0]
    assert "2" not in bpt.NEUTRAL_STATUS


# ---------------------------------------------------------------- sector yellows


def _rc(rows):
    return pd.DataFrame(rows, columns=["t", "Flag", "Scope", "Sector"])


def test_sector_yellow_intervals_clear_track_clear_and_open():
    rc = _rc([
        (100.0, "YELLOW", "Sector", 4.0), (110.0, "CLEAR", "Sector", 4.0),
        (200.0, "DOUBLE YELLOW", "Sector", 7.0), (205.0, "YELLOW", "Sector", 7.0),  # still the same yellow
        (230.0, "CLEAR", "Track", np.nan),
        (300.0, "YELLOW", "Sector", 2.0),  # never cleared
        (50.0, "CLEAR", "Sector", 9.0),  # a CLEAR with no yellow open is ignored
    ])
    ts = pd.DataFrame({"Status": ["1"], "session_time_s": [0.0]})
    assert bpt.sector_yellow_intervals(rc, ts) == [(4, 100.0, 110.0), (7, 200.0, 230.0), (2, 300.0, np.inf)]


def test_sector_yellow_same_timestamp_keeps_message_order():
    # YELLOW and CLEAR logged in the same second: the CLEAR (second in the feed) closes the yellow.
    rc = _rc([(100.0, "YELLOW", "Sector", 4.0), (100.0, "CLEAR", "Sector", 4.0)])
    ts = pd.DataFrame({"Status": ["1"], "session_time_s": [0.0]})
    assert bpt.sector_yellow_intervals(rc, ts) == [(4, 100.0, 100.0)]


def test_sector_yellow_ends_at_the_next_track_status_all_clear():
    rc = _rc([(100.0, "DOUBLE YELLOW", "Sector", 3.0), (900.0, "CLEAR", "Sector", 3.0),
              (1000.0, "YELLOW", "Sector", 5.0)])
    ts = pd.DataFrame({"Status": ["1", "2", "1", "2", "1"], "session_time_s": [0.0, 99.5, 101.0, 999.0, 1004.0]})
    assert bpt.sector_yellow_intervals(rc, ts) == [(3, 100.0, 101.0), (5, 1000.0, 1004.0)]
    # A yellow issued again after the AllClear opens a new interval.
    again = _rc([(100.0, "DOUBLE YELLOW", "Sector", 3.0), (102.0, "DOUBLE YELLOW", "Sector", 3.0),
                 (900.0, "CLEAR", "Sector", 3.0)])
    assert bpt.sector_yellow_intervals(again, ts) == [(3, 100.0, 101.0), (3, 102.0, 900.0)]


def test_corner_marshal_sectors_even_spacing():
    corners = pd.DataFrame({"corner_id": ["1", "2", "3", "4"], "Distance": [0.0, 999.0, 1000.0, 4999.0]})
    out = bpt.corner_marshal_sectors(corners, 5000.0, 5)
    assert out == {"1": 1.0, "2": 1.0, "3": 2.0, "4": 5.0}
    assert all(np.isnan(v) for v in bpt.corner_marshal_sectors(corners, 5000.0, 0).values())
    no_dist = bpt.corner_marshal_sectors(pd.DataFrame({"corner_id": ["1"]}), 5000.0, 5)
    assert np.isnan(no_dist["1"])


def test_in_sector_yellow_affected_and_following_sector_only():
    sectors = np.array([1.0, 2.0, 3.0, 4.0, 5.0, np.nan])
    t0, t1 = np.full(6, 100.0), np.full(6, 190.0)
    hit = bpt.in_sector_yellow(t0, t1, sectors, [(3, 150.0, 160.0)], 5)
    assert hit.tolist() == [False, False, True, True, False, False]
    # The last sector wraps to sector 1.
    assert bpt.in_sector_yellow(t0, t1, sectors, [(5, 150.0, 160.0)], 5).tolist() == [True, False, False, False, True, False]
    # A yellow outside the lap does not count; touching the lap end is not overlapping.
    assert not bpt.in_sector_yellow(t0, t1, sectors, [(3, 190.0, 200.0)], 5).any()
    assert not bpt.in_sector_yellow(t0, t1, sectors, [(3, 150.0, 160.0)], 0).any()


# ---------------------------------------------------------------- layout flag (DD-WC6)


def _corners(points, ids=None) -> pd.DataFrame:
    ids = ids or [str(i + 1) for i in range(len(points))]
    return pd.DataFrame({"corner_id": ids, "X": [p[0] for p in points], "Y": [p[1] for p in points]})


_SQUARE = [(0.0, 0.0), (10000.0, 0.0), (10000.0, 10000.0), (0.0, 10000.0)]  # X/Y in 1/10 m


def _info(season, corners=None, lap=5000.0, ci_season=None, race="x_gp", circuit="X", month=6):
    return {"season": season, "race": race, "circuit": circuit, "date": pd.Timestamp(f"{season}-{month:02d}-01"),
            "corners": _corners(_SQUARE) if corners is None else corners,
            "circuit_info_season": season if ci_season is None else ci_season, "lap_len_m": lap}


def test_rigid_shift_separates_a_frame_shift_from_a_moved_corner():
    a = _corners(_SQUARE)
    shifted = a.assign(X=a["X"] + 3000.0, Y=a["Y"] - 2000.0)  # whole frame moved about 360 m
    raw, aligned = bpt.rigid_shift_m(a, shifted)
    assert raw == pytest.approx(np.hypot(300.0, 200.0)) and aligned == pytest.approx(0.0, abs=1e-6)
    moved = a.copy()
    moved.loc[2, "X"] += 2000.0  # one corner 200 m away
    assert bpt.rigid_shift_m(a, moved)[1] > bpt.LAYOUT_CORNER_MOVE_M
    assert np.isnan(bpt.rigid_shift_m(a.head(2), a.head(2))[0])


def test_layout_flags_first_race_same_layout_and_frame_shift_are_not_flagged():
    shifted = _corners(_SQUARE).assign(X=lambda c: c["X"] + 5000.0)
    flags, detail = bpt.layout_flags([_info(2018), _info(2019, lap=5030.0), _info(2020, corners=shifted)])
    assert flags[(2018, "x_gp")] == (False, "first race at X in bronze; nothing to compare")
    assert flags[(2019, "x_gp")] == (False, "same layout as 2018 x_gp")
    changed, note = flags[(2020, "x_gp")]
    assert not changed and "whole frame" in note
    assert detail["layout_changed"].tolist() == [False, False, False]


def test_layout_flags_corner_count_moved_corner_and_fallback():
    three = _corners(_SQUARE[:3])
    flags, _ = bpt.layout_flags([
        _info(2018), _info(2019, corners=three), _info(2020, corners=three, ci_season=2019),
        _info(2021, corners=_corners(_SQUARE[:3]).assign(Y=lambda c: c["Y"] + np.array([0.0, 3000.0, 0.0]))),
    ])
    assert flags[(2019, "x_gp")][0] and "corner count 4 -> 3 vs 2018 x_gp" in flags[(2019, "x_gp")][1]
    assert flags[(2020, "x_gp")] == (True, "corners taken from circuit_info season 2019 (fallback)")
    # A 300 m move of one of three corners is spread by the rigid fit, but stays far over the 40 m limit.
    assert flags[(2021, "x_gp")][0] and "a corner moved" in flags[(2021, "x_gp")][1]
    # An unflagged race at a circuit with a change carries a note naming it.
    assert "circuit layout changes at 2019 x_gp, 2021 x_gp" in flags[(2018, "x_gp")][1]
    assert not flags[(2018, "x_gp")][0]


def test_layout_flags_lap_length_uses_previous_races_since_the_last_change():
    flags, detail = bpt.layout_flags([
        _info(2018, lap=5000.0), _info(2019, lap=5040.0), _info(2020, lap=4980.0),  # noise under 50 m
        _info(2021, lap=4800.0),  # -200 m vs the 5000 m median: a change
        _info(2022, lap=4810.0),  # compared with 2021 only (new epoch), so not flagged
    ])
    assert [flags[(s, "x_gp")][0] for s in range(2018, 2023)] == [False, False, False, True, False]
    assert "-200 m" in flags[(2021, "x_gp")][1]
    row = detail.set_index("season").loc[2022]
    assert row["ref_races"] == 1 and row["ref_lap_len_m"] == 4800.0


def test_layout_flags_fallback_does_not_start_a_new_epoch_and_circuits_stay_apart():
    flags, _ = bpt.layout_flags([
        _info(2018, lap=5000.0), _info(2019, lap=5000.0, ci_season=2018), _info(2020, lap=5010.0),
        _info(2019, lap=3500.0, race="y_gp", circuit="Y"), None,
    ])
    assert flags[(2019, "x_gp")][0] and not flags[(2020, "x_gp")][0]
    assert "fallback" not in flags[(2020, "x_gp")][1]
    assert flags[(2019, "y_gp")] == (False, "first race at Y in bronze; nothing to compare")


def test_layout_flags_same_season_repeat_race_compares_by_date():
    flags, _ = bpt.layout_flags([
        _info(2020, race="b_gp", month=7), _info(2020, race="a_gp", month=8, lap=5300.0),
    ])
    assert flags[(2020, "b_gp")][1].startswith("first race")
    assert flags[(2020, "a_gp")][0] and "vs 5000 m" in flags[(2020, "a_gp")][1]


def test_apply_layout_flags_adds_both_columns_and_keeps_the_reason():
    frame = pd.DataFrame({c: [None] for c in bpt.RACE_COLUMNS}).assign(season=2023, race="x_gp", reason="wet")
    out = bpt.apply_layout_flags(frame, {(2023, "x_gp"): (True, "corner count 16 -> 14 vs 2022 x_gp")})
    assert list(out.columns) == bpt.PASS_COLUMNS
    assert out["layout_changed"].iloc[0] is True or out["layout_changed"].iloc[0] == True  # noqa: E712
    assert out["reason"].iloc[0] == "wet"
    assert bpt.apply_layout_flags(frame, {})["layout_note"].iloc[0] == "layout not checked"
    assert bpt.LAYOUT_COLUMNS == ["layout_changed", "layout_note"] and not set(bpt.LAYOUT_COLUMNS) & set(bpt.RACE_COLUMNS)


def test_race_calendar_merges_location_aliases(tmp_path):
    folder = tmp_path / "schedule" / "season=2019"
    folder.mkdir(parents=True)
    pd.DataFrame({
        "EventName": ["Monaco Grand Prix", "Sakhir Grand Prix", "São Paulo Grand Prix"],
        "Location": ["Monte Carlo", "Sakhir", "São Paulo"],
        "EventDate": pd.to_datetime(["2019-05-26", "2019-12-06", "2019-11-17"]), "season": [2019] * 3,
    }).to_parquet(folder / "schedule.parquet", index=False)
    cal = bpt.race_calendar(tmp_path)
    assert cal[(2019, "monaco_grand_prix")][0] == "Monaco"
    assert cal[(2019, "sakhir_grand_prix")][0] == "Sakhir (outer)"
    assert (2019, "são_paulo_grand_prix") in cal
