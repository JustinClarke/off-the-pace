"""Synthetic tests for the WC-10b sidecar table. No real bronze or pass-table data is read."""

import unicodedata

import numpy as np
import pandas as pd
import pytest

from tasks.wake_calibration import build_pass_table as bpt
from tasks.wake_calibration import sidecar as sc
from tasks.wake_calibration.sidecar import Channels

LAP_M = 1000.0
SPEED_MS = 50.0  # time axis: constant 50 m/s, so t = lap start + distance / 50
APEX_D = 500.0  # the corner sits at 500 m on every lap


def _ch(cum, v=None, throttle=None, brake=None, drs=None) -> Channels:
    cum = np.asarray(cum, dtype=float)
    n = len(cum)
    return Channels(
        cum=cum,
        t=cum / SPEED_MS,
        v=np.asarray(v if v is not None else np.full(n, 200.0), dtype=float),
        throttle=np.asarray(throttle if throttle is not None else np.full(n, 100.0), dtype=float),
        brake=np.asarray(brake if brake is not None else np.zeros(n, dtype=bool), dtype=bool),
        drs=np.asarray(drs if drs is not None else np.zeros(n), dtype=float),
    )


# ---------------------------------------------------------------- PASS_COLUMNS untouched


def test_pass_columns_unchanged():
    assert bpt.PASS_COLUMNS == [
        "season", "race_id", "race", "driver", "lap", "stint", "compound", "tyre_life", "corner_id",
        "corner_number", "corner_class", "segment_basis", "apex_kph", "brake_offset_m", "seg_offset_m",
        "seg_start_t", "seg_end_t", "seg_time_s", "min_speed_kph", "leader", "leader_lap", "apex_dt_s", "gap_s",
        "gap_n", "clear_ahead", "behind_1s", "tag", "reason", "clean", "ref_n", "ref_time_s", "delta_time_s",
        "ref_status", "circuit_info_season", "circuit_match",
        "leader_track_limits", "marshal_sector", "ts_yellow_on_lap",
        "layout_changed", "layout_note",
    ]
    assert set(sc.SIDECAR_COLUMNS).isdisjoint(set(bpt.PASS_COLUMNS) - set(sc.KEY))


# ---------------------------------------------------------------- exit speed interpolation


def test_exit_speed_interpolates_across_a_sample_gap():
    # Samples at 580 and 620 m (a 40 m gap, wider than the 13 m median); target 600 m lies between them.
    cum = np.array([500.0, 513.0, 580.0, 620.0, 633.0])
    v = np.array([100.0, 110.0, 150.0, 190.0, 200.0])
    value, bracket = sc.value_at(cum, v, 600.0)
    assert bracket == pytest.approx(40.0)
    assert value == pytest.approx(170.0)
    # A quarter of the way along the gap.
    assert sc.value_at(cum, v, 590.0)[0] == pytest.approx(160.0)
    # Exactly on a sample: that sample's value.
    assert sc.value_at(cum, v, 580.0)[0] == pytest.approx(150.0)
    assert sc.value_at(cum, v, 633.0)[0] == pytest.approx(200.0)


def test_exit_speed_refused_beyond_the_max_bracket_and_outside_the_trace():
    cum = np.array([0.0, 10.0, 10.0 + sc.EXIT_MAX_BRACKET_M + 1.0])
    v = np.array([100.0, 100.0, 200.0])
    value, bracket = sc.value_at(cum, v, 30.0)
    assert np.isnan(value) and bracket == pytest.approx(sc.EXIT_MAX_BRACKET_M + 1.0)
    assert np.isnan(sc.value_at(cum, v, -1.0)[0])
    assert np.isnan(sc.value_at(cum, v, 1e6)[0])
    assert np.isnan(sc.value_at(np.array([0.0, 10.0]), np.array([1.0, np.nan]), 5.0)[0])


# ---------------------------------------------------------------- DRS


@pytest.mark.parametrize("code", [10, 12, 14])
def test_drs_codes_10_12_14_are_open(code):
    ch = _ch([100.0, 150.0, 200.0], drs=[0, code, 0])
    assert sc.drs_open(ch, 100.0, 200.0) == (True, 3)


@pytest.mark.parametrize("code", [0, 1, 2, 3, 8, 9])
def test_other_drs_codes_are_not_open(code):
    ch = _ch([100.0, 150.0, 200.0], drs=[code, code, code])
    assert sc.drs_open(ch, 100.0, 200.0) == (False, 3)


def test_drs_open_only_counts_samples_inside_the_window_and_none_without_samples():
    ch = _ch([50.0, 150.0, 450.0], drs=[12, 0, 14])
    assert sc.drs_open(ch, 100.0, 400.0) == (False, 1)
    assert sc.drs_open(ch, 200.0, 400.0) == (None, 0)
    assert sc.drs_open(_ch([150.0], drs=[np.nan]), 100.0, 200.0) == (None, 0)
    assert sc.drs_open(ch, np.nan, 400.0) == (None, 0)


# ---------------------------------------------------------------- coast and throttle


def test_coast_time_runs_from_first_coasting_sample_to_the_brake_onset():
    cum = np.arange(300.0, 520.0, 12.5)  # 4 Hz-like spacing at 50 m/s = 0.25 s
    thr = np.where(cum < 350.0, 100.0, 0.0)
    brake = (cum >= 400.0) & (cum < 480.0)
    ch = _ch(cum, throttle=thr, brake=brake)
    onset = sc.brake_onset(ch, cum_apex=500.0)
    assert ch.cum[onset] == pytest.approx(400.0)
    assert sc.coast_time(ch, onset) == pytest.approx((400.0 - 350.0) / SPEED_MS)


def test_coast_time_zero_when_no_coasting_sample_and_null_without_onset():
    cum = np.arange(300.0, 520.0, 12.5)
    brake = (cum >= 400.0) & (cum < 480.0)
    ch = _ch(cum, throttle=np.where(brake, 0.0, 100.0), brake=brake)
    assert sc.coast_time(ch, sc.brake_onset(ch, 500.0)) == 0.0
    no_brake = _ch(cum)
    assert sc.brake_onset(no_brake, 500.0) is None
    assert np.isnan(sc.coast_time(no_brake, None))
    # Brake already on at the start of the lookback: no rising edge, so no onset.
    always = _ch(cum, brake=np.ones(len(cum), dtype=bool))
    assert sc.brake_onset(always, 500.0, lookback_m=150.0) is None


def test_coast_time_null_when_a_dropout_lies_inside_the_coast_run():
    cum = np.array([300.0, 337.5, 350.0, 362.5, 375.0, 387.5, 400.0, 412.5])
    thr = np.array([100.0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    brake = cum >= 400.0
    ch = _ch(cum, throttle=thr, brake=brake)
    onset = sc.brake_onset(ch, 450.0)
    assert sc.coast_time(ch, onset) == pytest.approx(50.0 / SPEED_MS)
    ch.t[3:] += 5.0  # a 5 s hole between the 350 m and 362.5 m samples
    assert np.isnan(sc.coast_time(ch, onset))


def test_partial_throttle_share_and_minimum_samples():
    ch = _ch([0.0, 10.0, 20.0, 30.0, 40.0], throttle=[100.0, 50.0, 0.0, 99.0, 20.0])
    share, n = sc.partial_throttle_share(ch, 0.0, 40.0)
    assert n == 5 and share == pytest.approx(2 / 5)  # 50 and 20 are partial; 0 is coast; 99, 100 are full
    assert np.isnan(sc.partial_throttle_share(ch, 0.0, 10.0)[0])
    assert np.isnan(sc.partial_throttle_share(ch, np.nan, 10.0)[0])


# ---------------------------------------------------------------- previous lap


def _passes(**over) -> pd.DataFrame:
    base = {
        "season": [2023] * 4, "race_id": ["2023_1"] * 4, "driver": ["AAA"] * 4, "lap": [2, 3, 5, 6],
        "corner_id": ["1"] * 4, "gap_s": [0.8, 0.6, np.nan, 1.2], "clear_ahead": [False, False, True, False],
        "reason": [None, None, None, "pit_lap"],
    }
    base.update(over)
    return pd.DataFrame(base)


def test_missing_previous_lap_is_null_never_zero():
    prev = sc.previous_lap(_passes()).set_index("lap")
    assert np.isnan(prev.loc[2, "prev_lap_gap_s"]) and pd.isna(prev.loc[2, "prev_lap_clear_ahead"])
    assert prev.loc[3, "prev_lap_gap_s"] == pytest.approx(0.8)
    # Lap 4 has no pass, so lap 5's previous lap is missing: null, not 0.
    assert np.isnan(prev.loc[5, "prev_lap_gap_s"]) and pd.isna(prev.loc[5, "prev_lap_clear_ahead"])
    # Lap 5 had no car ahead: gap null but clear_ahead True, so the two cases stay apart.
    assert np.isnan(prev.loc[6, "prev_lap_gap_s"]) and bool(prev.loc[6, "prev_lap_clear_ahead"]) is True
    assert (prev["prev_lap_gap_s"].fillna(-1) != 0).all()


def test_previous_lap_never_crosses_driver_corner_or_race():
    p = pd.concat([_passes(), _passes(driver=["BBB"] * 4, lap=[1, 2, 3, 4]),
                   _passes(corner_id=["2"] * 4, lap=[1, 2, 3, 4], gap_s=[9.0] * 4)], ignore_index=True)
    prev = sc.previous_lap(p)
    aaa = prev[(prev["driver"] == "AAA") & (prev["corner_id"] == "1")].set_index("lap")
    assert aaa.loc[3, "prev_lap_gap_s"] == pytest.approx(0.8)  # never the corner-2 9.0
    assert len(prev) == len(p)


# ---------------------------------------------------------------- one synthetic race on disk


def _telemetry(drivers=("AAA", "BBB"), laps=(1, 2, 3, 4), drs_lap=3) -> pd.DataFrame:
    """A straight 'track' (X = 10 x distance), corner at 500 m. Car rows every 13 m except a 40 m gap across
    apex + 100 m (580-620 m); pos rows every 6.5 m in between. Speed = 100 + 0.1 x distance (linear)."""
    rows = []
    car_d = np.concatenate([np.arange(0.0, 580.0, 13.0), [580.0, 620.0], np.arange(633.0, LAP_M, 13.0)])
    pos_d = np.arange(3.25, LAP_M, 6.5)
    for k, drv in enumerate(drivers):
        for lap in laps:
            t0 = (lap - 1) * LAP_M / SPEED_MS + k * 2.0
            for d, src in [(d, "car") for d in car_d] + [(d, "pos") for d in pos_d]:
                brake = 400.0 <= d < 480.0
                thr = 100.0 if d < 350.0 else (0.0 if d < 480.0 else (50.0 if d < 560.0 else 100.0))
                drs = 12 if (lap == drs_lap and 150.0 <= d < 300.0) else 0
                rows.append({
                    "SessionTime": t0 + d / SPEED_MS, "driver_id": drv,
                    "lap_number": float(lap), "distance_m": d, "speed_kph": 100.0 + 0.1 * d, "brake": brake,
                    "Status": "OnTrack", "X": d * 10.0, "Y": 0.0, "throttle_pct": thr, "DRS": drs, "Source": src,
                })
    frame = pd.DataFrame(rows)
    frame["SessionTime"] = pd.to_timedelta(frame["SessionTime"], unit="s")
    return frame.sort_values(["driver_id", "SessionTime"]).reset_index(drop=True)


def _write_race(root, season, race, tel):
    folder = root / "telemetry" / f"season={season}" / f"race={race}"
    folder.mkdir(parents=True)
    tel.to_parquet(folder / "telemetry.parquet", index=False)
    ci = root / "circuit_info" / f"season={season}" / f"race={race}"
    ci.mkdir(parents=True)
    pd.DataFrame({"X": [APEX_D * 10.0], "Y": [0.0], "Number": [1], "Letter": [""], "Distance": [APEX_D]}).to_parquet(
        ci / "circuit_info.parquet", index=False)


def _race_passes(season, race, drivers=("AAA", "BBB"), laps=(2, 3), race_no=9) -> pd.DataFrame:
    rows = []
    for k, drv in enumerate(drivers):
        for lap in laps:
            t0 = (lap - 1) * LAP_M / SPEED_MS + k * 2.0
            rows.append({"season": season, "race_id": f"{season}_{race_no}", "race": race, "driver": drv, "lap": lap,
                         "corner_id": "1", "corner_class": "slow", "seg_offset_m": -100.0,
                         "seg_end_t": t0 + (APEX_D + 100.0) / SPEED_MS, "gap_s": 0.5 if k else np.nan,
                         "clear_ahead": not k, "reason": None})
    return pd.DataFrame(rows)


def test_race_sidecar_end_to_end_on_a_synthetic_race(tmp_path):
    _write_race(tmp_path, 2023, "x_gp", _telemetry())
    passes = _race_passes(2023, "x_gp")
    out, check = sc.race_sidecar(2023, "x_gp", passes, tmp_path)
    assert len(out) == len(passes) and list(out[sc.KEY].itertuples(index=False)) == \
        list(passes[sc.KEY].itertuples(index=False))
    assert check["apex_found"] == 4 and check["seg_end_agree"] == check["seg_end_compared"] == 4
    # Exit speed at 600 m interpolated across the 580-620 m car-row gap; the pos rows are not used.
    assert out["exit_speed_kph"].to_numpy() == pytest.approx(np.full(4, 100.0 + 0.1 * 600.0))
    assert out["exit_bracket_m"].to_numpy() == pytest.approx(np.full(4, 40.0))
    # Onset at the first car-row brake sample (403 m: 0, 13, ..., 403), coasting from the first car row >= 350 m.
    first_coast = 13.0 * np.ceil(350.0 / 13.0)
    onset = 13.0 * np.ceil(400.0 / 13.0)
    assert out["brake_onset_m"].to_numpy() == pytest.approx(np.full(4, onset - APEX_D))
    assert out["coast_time_s"].to_numpy() == pytest.approx(np.full(4, (onset - first_coast) / SPEED_MS))
    # Segment 400-600 m: car rows 403..559 + 580 + 600? (no: 620 > 600). Partial throttle 480-560 m.
    seg = np.array([d for d in np.concatenate([np.arange(0.0, 580.0, 13.0), [580.0, 620.0]]) if 400.0 <= d <= 600.0])
    thr = np.where(seg < 480.0, 0.0, np.where(seg < 560.0, 50.0, 100.0))
    assert out["partial_throttle_share"].to_numpy() == pytest.approx(np.full(4, np.mean(thr == 50.0)))
    # DRS 12 inside the approach (100-400 m) on lap 3 only.
    assert out.set_index(["driver", "lap"])["drs_open_approach"].to_dict() == {
        ("AAA", 2): False, ("AAA", 3): True, ("BBB", 2): False, ("BBB", 3): True}


def test_race_sidecar_pass_without_apex_gets_null_channels(tmp_path):
    _write_race(tmp_path, 2023, "x_gp", _telemetry())
    passes = pd.concat([_race_passes(2023, "x_gp"), _race_passes(2023, "x_gp", drivers=("ZZZ",), laps=(2,))])
    out, check = sc.race_sidecar(2023, "x_gp", passes, tmp_path)
    z = out[out["driver"] == "ZZZ"].iloc[0]
    assert np.isnan(z["exit_speed_kph"]) and np.isnan(z["coast_time_s"]) and z["drs_open_approach"] is None
    assert check["apex_found"] == 4


def test_nfd_race_path_is_found_from_an_nfc_slug(tmp_path):
    nfc_slug = unicodedata.normalize("NFC", "são_paulo_grand_prix")
    nfd_slug = unicodedata.normalize("NFD", nfc_slug)
    assert nfc_slug != nfd_slug
    _write_race(tmp_path, 2023, nfd_slug, _telemetry())
    found = sc.race_dir(tmp_path, "telemetry", 2023, nfc_slug)
    assert found is not None and sc.nfc(found.name) == f"race={nfc_slug}"
    assert sc.race_dir(tmp_path, "telemetry", 2023, nfd_slug) == found
    assert sc.race_dir(tmp_path, "telemetry", 2024, nfc_slug) is None
    out, check = sc.race_sidecar(2023, nfc_slug, _race_passes(2023, nfc_slug), tmp_path)
    assert check["apex_found"] == 4 and out["exit_speed_kph"].notna().all()
    assert set(out["race_id"]) == {"2023_9"}  # keyed by race_id, never by the slug's byte form


def test_race_sidecar_skips_without_telemetry(tmp_path):
    with pytest.raises(bpt.SkipRace):
        sc.race_sidecar(2023, "nowhere_gp", _race_passes(2023, "nowhere_gp"), tmp_path)


# ---------------------------------------------------------------- the CLI: rows, sums, coverage only


def test_main_writes_sidecar_sums_and_coverage_only(tmp_path):
    bronze = tmp_path / "bronze"
    _write_race(bronze, 2023, "x_gp", _telemetry())
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    full = _race_passes(2023, "x_gp", laps=(1, 2, 3, 4))  # laps 1 and 4 have no apex (not complete laps)
    missing = _race_passes(2023, "gone_gp", race_no=10)  # a race with no bronze telemetry: kept, null channels
    pd.concat([full, missing], ignore_index=True).to_parquet(pass_dir / "pass_table_2023.parquet", index=False)
    out, ev = tmp_path / "out", tmp_path / "ev"
    assert sc.main(["--pass-table", str(pass_dir), "--out", str(out), "--evidence", str(ev),
                    "--bronze", str(bronze), "--seasons", "2023"]) == 0
    side = pd.read_parquet(out / "sidecar_2023.parquet")
    assert list(side.columns) == sc.SIDECAR_COLUMNS
    assert len(side) == len(full) + len(missing) and not side.duplicated(sc.KEY).any()
    assert side.loc[side["race_id"] == "2023_9", "exit_speed_kph"].notna().sum() == 4
    sums = (out / "SHA256SUMS").read_text()
    assert "sidecar_2023.parquet" in sums and "races.csv" in sums
    cov = pd.read_csv(ev / "sidecar_coverage.csv")
    assert set(cov.columns) == {"scope", "season", "corner_class", "column", "passes", "non_null", "share"}
    row = cov[(cov["scope"] == "all") & (cov["corner_class"] == "all") & (cov["column"] == "exit_speed_kph")]
    assert row["passes"].item() == len(side) and row["non_null"].item() == 4
    prov = (ev / "PROVENANCE.txt").read_text()
    assert "W9" in prov and "gone_gp" in prov
    for word in ("mean", "median", "quantile"):
        assert word not in prov.lower().replace("median 0.24 s", "")


def test_range_check_reports_counts_not_values():
    side = pd.DataFrame({"exit_speed_kph": [100.0, np.nan, 999.0], "coast_time_s": [0.0, 0.5, np.nan],
                         "partial_throttle_share": [0.1, 0.2, 0.3],
                         "drs_open_approach": pd.array([True, None, False], dtype="boolean")})
    res = {r["column"]: r for r in sc.range_check(side)}
    assert res["exit_speed_kph"]["out_of_range"] == 1 and not res["exit_speed_kph"]["ok"]
    assert res["coast_time_s"]["nan"] == 1 and res["coast_time_s"]["ok"]
    assert set(res["exit_speed_kph"]) == {"column", "range", "nan", "out_of_range", "ok"}
