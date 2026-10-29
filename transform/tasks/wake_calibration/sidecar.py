"""
WC-10 Stage 0 (WC-10b): the sidecar table, one row per pass of the WC-01 pass table.

Keyed by the pass key (season, race_id, driver, lap, corner_id) and joined 1:1 to the pass-table rows. It adds
five derived columns that the pass table does not carry, without changing it (build_pass_table.PASS_COLUMNS
and build_pass_table.py are untouched; this module only calls its functions):

    exit_speed_kph          speed at apex + EXIT_AFTER_APEX_M, linearly interpolated in distance between the two
                            car samples either side (null when they are more than EXIT_MAX_BRACKET_M apart)
    coast_time_s            time with throttle below COAST_THROTTLE_PCT and brake off immediately before the
                            driver's own brake onset on this pass (0.0 when no coasting sample precedes the
                            onset; null when there is no brake onset in the BRAKE_LOOKBACK_M before the apex)
    partial_throttle_share  share of car samples in the pass-table segment (apex + seg_offset_m to apex +
                            SEGMENT_AFTER_APEX_M) with COAST_THROTTLE_PCT <= throttle < FULL_THROTTLE_PCT
    drs_open_approach       any car sample in the APPROACH_M before the segment start has DRS in DRS_OPEN_CODES
    prev_lap_gap_s          the pass table's gap_s for the same driver and corner on lap - 1 (null when that
                            pass is missing or had no car ahead; never 0)

plus quality columns (exit_bracket_m, brake_onset_m, throttle_n, drs_n, prev_lap_clear_ahead, prev_lap_reason).

Channel values come from telemetry rows with Source == "car" only (the ~4 Hz car stream: median 0.24 s / 13 m,
p90 0.40 s / 25 m). The `pos` rows only carry merged copies of those channels. The apex position is
recomputed with build_pass_table.race_geometry + find_apex_events on the full merged trace, exactly as the pass
table found it, and checked against the pass table's seg_end_t (time at apex + 100 m).

    python -m tasks.wake_calibration.sidecar [--seasons 2018 ... 2025] [--race slug] [--workers 8] \
        [--out <artifacts dir>] [--evidence <evidence dir>]

W9 (prereg-first): exit speed, coast time and throttle share are outcome-adjacent. This module writes them to
the parquet only. The evidence it writes is coverage (non-null shares) and a pass/fail range check with counts;
no mean, quantile, minimum, maximum or distribution of those columns is written or printed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from tasks.wake_calibration import build_pass_table as bpt

REPO = Path(__file__).resolve().parents[3]
BRONZE = bpt.BRONZE
WC = REPO / "_roadmap" / "_wake-calibration"
DEFAULT_PASS_DIR = WC / "_artifacts" / "WC-03-run" / "pass-table"
DEFAULT_OUT = WC / "_artifacts" / "WC-10" / "sidecar"

KEY = ["season", "race_id", "driver", "lap", "corner_id"]

# Exit speed is read where the pass-table segment ends.
EXIT_AFTER_APEX_M = bpt.SEGMENT_AFTER_APEX_M
# Interpolation is refused when the car samples either side of the target are further apart than this. Car-row
# spacing in 2022-25 is median 13 m, p90 25 m, p99 37-38 m (review note); 50 m keeps the p99 and drops dropouts.
EXIT_MAX_BRACKET_M = 50.0
# Brake onset: last rising edge of the car-row brake signal in this many metres before the apex (as the pass table).
BRAKE_LOOKBACK_M = bpt.BRAKE_LOOKBACK_M
# A car sample is coasting when throttle is below this and the brake is off.
COAST_THROTTLE_PCT = 5.0
# The coast run is followed back from the onset at most this far.
COAST_LOOKBACK_M = 300.0
# Two car samples further apart in time than this are a dropout (p90 spacing is 0.40 s): a coast run that spans
# one has an unknown length and is null.
COAST_MAX_DT_S = 1.0
# Partial throttle: COAST_THROTTLE_PCT <= throttle < FULL_THROTTLE_PCT (full throttle reads 99-100, some 104).
FULL_THROTTLE_PCT = 98.0
# Fewest valid car samples in the segment for a throttle share.
MIN_SHARE_SAMPLES = 3
# The approach is the same window the pass table measures the gap over: this many metres before the segment start.
APPROACH_M = bpt.GAP_LOOKBACK_M
# FastF1 DRS codes: 10, 12, 14 = flap open; 8 = eligible (detected), not open; 0/1 off.
DRS_OPEN_CODES = (10, 12, 14)

SIDECAR_COLUMNS = KEY + [
    "exit_speed_kph", "exit_bracket_m",
    "coast_time_s", "brake_onset_m",
    "partial_throttle_share", "throttle_n",
    "drs_open_approach", "drs_n",
    "prev_lap_gap_s", "prev_lap_clear_ahead", "prev_lap_reason",
]
# The five columns the coverage report is about.
FEATURE_COLUMNS = ["exit_speed_kph", "coast_time_s", "partial_throttle_share", "drs_open_approach", "prev_lap_gap_s"]
# Pass-table columns read: key, join check and structure only (no segment time, minimum speed or reference).
PASS_READ_COLUMNS = KEY + ["race", "corner_class", "seg_offset_m", "seg_end_t", "gap_s", "clear_ahead", "reason"]
TELEMETRY_COLUMNS = bpt.TELEMETRY_COLUMNS + ["throttle_pct", "DRS", "Source"]

# Sanity range (pass/fail with counts only; W9). prev_lap_gap_s is a copy of the pass table's own gap_s, so it
# is not range-checked here.
RANGES = {"exit_speed_kph": (0.0, 400.0), "coast_time_s": (0.0, 30.0), "partial_throttle_share": (0.0, 1.0)}


# --------------------------------------------------------------------------- paths (NFC-safe)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", str(text))


def race_dir(bronze: Path, dataset: str, season: int, race: str) -> Path | None:
    """The bronze folder of a race, matched by NFC-normalised name: glob and the pass table can return the
    same slug in NFC or NFD form (são_paulo_grand_prix), and a byte comparison would miss it."""
    parent = bronze / dataset / f"season={season}"
    if not parent.is_dir():
        return None
    want = nfc(f"race={race}")
    for child in sorted(parent.iterdir()):
        if child.is_dir() and nfc(child.name) == want:
            return child
    return None


def race_slug_on_disk(bronze: Path, dataset: str, season: int, race: str) -> str:
    """The slug as spelled on disk for this dataset and season (the given slug if not found)."""
    found = race_dir(bronze, dataset, season, race)
    return found.name.removeprefix("race=") if found is not None else race


# --------------------------------------------------------------------------- car channels


@dataclass
class Channels:
    """One car's ~4 Hz car-stream samples on the pass table's cumulative distance axis."""

    cum: np.ndarray
    t: np.ndarray
    v: np.ndarray
    throttle: np.ndarray
    brake: np.ndarray  # bool
    drs: np.ndarray  # float (NaN = missing)


def car_channels(telemetry: pd.DataFrame, traces: dict[str, bpt.CarTrace]) -> dict[str, Channels]:
    """Car-row channels per driver, aligned with build_pass_table's traces.

    Repeats race_geometry's filter and build_car_trace's sort, then takes the trace's cumulative distance for
    each row, so the car rows sit on exactly the axis the pass table's apexes were found on.
    """
    tel = telemetry.dropna(subset=["lap_number", "distance_m", "SessionTime"]).copy()
    tel["t"] = bpt._seconds(tel.pop("SessionTime"))
    for col in ("throttle_pct", "DRS", "Source"):
        if col not in tel:
            tel[col] = np.nan
    out = {}
    for driver, g in tel.groupby("driver_id"):
        driver = str(driver)
        if driver not in traces:
            continue
        g = g.sort_values(["lap_number", "t"], kind="stable").reset_index(drop=True)
        trace = traces[driver]
        if len(g) != len(trace.t) or not np.array_equal(g["t"].to_numpy(dtype=float), trace.t, equal_nan=True):
            raise RuntimeError(f"car channels for {driver} do not align with the pass-table trace")
        car = g["Source"].astype(str).to_numpy() == "car"
        out[driver] = Channels(
            cum=trace.cum[car],
            t=trace.t[car],
            v=g.loc[car, "speed_kph"].to_numpy(dtype=float),
            throttle=pd.to_numeric(g.loc[car, "throttle_pct"], errors="coerce").to_numpy(dtype=float),
            brake=g.loc[car, "brake"].astype("boolean").fillna(False).to_numpy(dtype=bool),
            drs=pd.to_numeric(g.loc[car, "DRS"], errors="coerce").to_numpy(dtype=float),
        )
    return out


# --------------------------------------------------------------------------- per-pass measures (pure)


def value_at(cum: np.ndarray, values: np.ndarray, x: float, max_bracket_m: float = EXIT_MAX_BRACKET_M
             ) -> tuple[float, float]:
    """(value, bracket metres) at distance x: linear interpolation between the samples either side.

    NaN value when x is outside the samples, a bracketing value is missing, or the two samples are more than
    max_bracket_m apart (the bracket is still returned so the refusal is visible).
    """
    n = len(cum)
    if n == 0 or not np.isfinite(x):
        return np.nan, np.nan
    i = int(np.searchsorted(cum, x, side="right"))  # cum[i-1] <= x < cum[i]
    if i == 0:
        return np.nan, np.nan
    if i == n:
        if x == cum[-1]:
            return float(values[-1]), 0.0
        return np.nan, np.nan
    a, b = i - 1, i
    bracket = float(cum[b] - cum[a])
    va, vb = float(values[a]), float(values[b])
    if bracket > max_bracket_m or not (np.isfinite(va) and np.isfinite(vb)):
        return np.nan, bracket
    if bracket <= 0:
        return va, bracket
    return va + (vb - va) * (x - cum[a]) / bracket, bracket


def brake_onset(ch: Channels, cum_apex: float, lookback_m: float = BRAKE_LOOKBACK_M) -> int | None:
    """Index of the last rising edge of the car-row brake signal in [apex - lookback, apex]; None if none."""
    if not np.isfinite(cum_apex) or len(ch.cum) < 2:
        return None
    i0 = max(int(np.searchsorted(ch.cum, cum_apex - lookback_m)), 1)
    i1 = int(np.searchsorted(ch.cum, cum_apex, side="right"))
    if i1 <= i0:
        return None
    rising = np.flatnonzero(ch.brake[i0:i1] & ~ch.brake[i0 - 1 : i1 - 1]) + i0
    return int(rising[-1]) if len(rising) else None


def coast_time(ch: Channels, onset: int | None, lookback_m: float = COAST_LOOKBACK_M) -> float:
    """Seconds from the first sample of the coasting run that ends just before the onset, to the onset sample.

    Coasting = brake off and a valid throttle below COAST_THROTTLE_PCT. 0.0 when the sample before the onset is
    not coasting (none observed); NaN without an onset. Resolution is one car-sample interval (~0.24 s).
    """
    if onset is None:
        return np.nan
    lo = ch.cum[onset] - lookback_m
    first = None
    k = onset - 1
    while k >= 0 and ch.cum[k] >= lo and not ch.brake[k] and np.isfinite(ch.throttle[k]) \
            and ch.throttle[k] < COAST_THROTTLE_PCT:
        if not ch.t[k + 1] - ch.t[k] <= COAST_MAX_DT_S:
            return np.nan  # a dropout inside the coast run: its length is unknown
        first = k
        k -= 1
    return 0.0 if first is None else float(ch.t[onset] - ch.t[first])


def _window(cum: np.ndarray, lo: float, hi: float) -> slice:
    return slice(int(np.searchsorted(cum, lo)), int(np.searchsorted(cum, hi, side="right")))


def partial_throttle_share(ch: Channels, lo: float, hi: float) -> tuple[float, int]:
    """(share, valid samples) of car samples in [lo, hi] with COAST_THROTTLE_PCT <= throttle < FULL_THROTTLE_PCT.

    NaN when the window is undefined or holds fewer than MIN_SHARE_SAMPLES valid throttle samples.
    """
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi < lo:
        return np.nan, 0
    thr = ch.throttle[_window(ch.cum, lo, hi)]
    thr = thr[np.isfinite(thr)]
    if len(thr) < MIN_SHARE_SAMPLES:
        return np.nan, int(len(thr))
    return float(np.mean((thr >= COAST_THROTTLE_PCT) & (thr < FULL_THROTTLE_PCT))), int(len(thr))


def drs_open(ch: Channels, lo: float, hi: float) -> tuple[bool | None, int]:
    """(any open, valid samples) over car samples in [lo, hi]; None when no valid DRS sample lies there."""
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi < lo:
        return None, 0
    codes = ch.drs[_window(ch.cum, lo, hi)]
    codes = codes[np.isfinite(codes)]
    if len(codes) == 0:
        return None, 0
    return bool(np.isin(codes, DRS_OPEN_CODES).any()), int(len(codes))


def pass_measures(ch: Channels | None, cum_apex: float, seg_offset_m: float) -> dict:
    """The channel-derived sidecar columns for one pass (all null when the pass has no channels or apex)."""
    out = {"exit_speed_kph": np.nan, "exit_bracket_m": np.nan, "coast_time_s": np.nan, "brake_onset_m": np.nan,
           "partial_throttle_share": np.nan, "throttle_n": 0, "drs_open_approach": None, "drs_n": 0}
    if ch is None or not np.isfinite(cum_apex):
        return out
    out["exit_speed_kph"], out["exit_bracket_m"] = value_at(ch.cum, ch.v, cum_apex + EXIT_AFTER_APEX_M)
    onset = brake_onset(ch, cum_apex)
    if onset is not None:
        out["brake_onset_m"] = float(min(ch.cum[onset] - cum_apex, 0.0))
    out["coast_time_s"] = coast_time(ch, onset)
    if np.isfinite(seg_offset_m):
        start = cum_apex + seg_offset_m
        out["partial_throttle_share"], out["throttle_n"] = partial_throttle_share(
            ch, start, cum_apex + bpt.SEGMENT_AFTER_APEX_M)
        out["drs_open_approach"], out["drs_n"] = drs_open(ch, start - APPROACH_M, start)
    return out


# --------------------------------------------------------------------------- previous lap (pass table only)


def previous_lap(passes: pd.DataFrame) -> pd.DataFrame:
    """prev_lap_gap_s / prev_lap_clear_ahead / prev_lap_reason from the same driver and corner on lap - 1.

    Missing previous pass: all three null (never 0, never False). No car ahead on lap - 1: gap null, clear True.
    """
    prev = passes[KEY + ["gap_s", "clear_ahead", "reason"]].copy()
    prev["lap"] = prev["lap"] + 1
    prev = prev.rename(columns={"gap_s": "prev_lap_gap_s", "clear_ahead": "prev_lap_clear_ahead",
                                "reason": "prev_lap_reason"})
    out = passes[KEY].merge(prev, on=KEY, how="left", validate="one_to_one")
    out["prev_lap_gap_s"] = pd.to_numeric(out["prev_lap_gap_s"], errors="coerce").astype(float)
    out["prev_lap_clear_ahead"] = out["prev_lap_clear_ahead"].astype("boolean")
    out["prev_lap_reason"] = out["prev_lap_reason"].astype("string")
    return out


# --------------------------------------------------------------------------- one race


def race_sidecar(season: int, race: str, passes: pd.DataFrame, bronze: Path = BRONZE) -> tuple[pd.DataFrame, dict]:
    """Sidecar rows for one race's pass-table rows (same rows, same order), and a check record.

    `passes` holds the race's pass-table rows (PASS_READ_COLUMNS). The apex of each pass is recomputed from
    bronze with build_pass_table's own functions; a pass whose apex is not found again gets null channels.
    """
    folder = race_dir(bronze, "telemetry", season, race)
    path = None if folder is None else folder / "telemetry.parquet"
    if path is None or not path.exists():
        raise bpt.SkipRace("no telemetry parquet in bronze")
    present = set(pq.read_schema(path).names)
    tel = pq.read_table(path, columns=[c for c in TELEMETRY_COLUMNS if c in present]).to_pandas()
    if tel.empty:
        raise bpt.SkipRace("telemetry parquet is empty")
    candidates = bpt.circuit_candidates(season, race_slug_on_disk(bronze, "circuit_info", season, race), bronze)
    if not candidates:
        raise bpt.SkipRace("no circuit_info corners")
    traces, corners, _, _, _ = bpt.race_geometry(tel, candidates)
    channels = car_channels(tel, traces)
    events = pd.DataFrame(
        [(e.driver, int(e.lap), e.corner, e.cum_apex) for d, tr in traces.items()
         for e in bpt.find_apex_events(d, tr, corners)],
        columns=["driver", "lap", "corner_id", "cum_apex"],
    )
    rows = passes.reset_index(drop=True).merge(events, on=["driver", "lap", "corner_id"], how="left",
                                               validate="one_to_one")
    measures = [pass_measures(channels.get(d), c, s) for d, c, s in
                rows[["driver", "cum_apex", "seg_offset_m"]].itertuples(index=False, name=None)]
    out = pd.concat([rows[KEY], pd.DataFrame(measures, index=rows.index)], axis=1)

    # Join check: the recomputed apex + 100 m must land on the pass table's seg_end_t.
    t_end = np.array([bpt.interp_time(traces[d], np.array([c + bpt.SEGMENT_AFTER_APEX_M]))[0]
                      if d in traces and np.isfinite(c) else np.nan
                      for d, c in rows[["driver", "cum_apex"]].itertuples(index=False, name=None)])
    ref = rows["seg_end_t"].to_numpy(dtype=float)
    both = np.isfinite(t_end) & np.isfinite(ref)
    check = {
        "passes": int(len(rows)), "events": int(len(events)), "apex_found": int(rows["cum_apex"].notna().sum()),
        "seg_end_compared": int(both.sum()),
        "seg_end_agree": int((np.abs(t_end[both] - ref[both]) <= 1e-6).sum()),
    }
    return out, check


def _run_one(season: int, race: str, passes: pd.DataFrame, bronze: Path):
    t0 = time.perf_counter()
    try:
        frame, check = race_sidecar(season, race, passes, bronze)
        return season, race, frame, "ok", check, time.perf_counter() - t0
    except bpt.SkipRace as exc:
        return season, race, None, f"skipped: {exc}", {"passes": len(passes)}, time.perf_counter() - t0
    except Exception as exc:  # noqa: BLE001 - logged; the race gets null channels and the run carries on
        return season, race, None, f"failed: {type(exc).__name__}: {exc}", {"passes": len(passes)}, \
            time.perf_counter() - t0


def null_rows(passes: pd.DataFrame) -> pd.DataFrame:
    """Sidecar rows with every channel column null (a race that could not be rebuilt)."""
    m = pass_measures(None, np.nan, np.nan)
    out = passes[KEY].reset_index(drop=True).copy()
    for k, v in m.items():
        out[k] = v
    return out


def finalise(frame: pd.DataFrame, prev: pd.DataFrame) -> pd.DataFrame:
    """Attach the previous-lap columns, fix dtypes, order the columns and sort by key."""
    frame = frame.merge(prev, on=KEY, how="left", validate="one_to_one")
    frame["drs_open_approach"] = frame["drs_open_approach"].astype("boolean")
    for col in ("throttle_n", "drs_n"):
        frame[col] = frame[col].fillna(0).astype(int)
    for col in ("exit_speed_kph", "exit_bracket_m", "coast_time_s", "brake_onset_m", "partial_throttle_share"):
        frame[col] = frame[col].astype(float)
    return frame[SIDECAR_COLUMNS].sort_values(KEY, kind="stable").reset_index(drop=True)


# --------------------------------------------------------------------------- coverage (W9: no values)


def coverage(sidecar: pd.DataFrame, passes: pd.DataFrame) -> pd.DataFrame:
    """Non-null share per feature column, by season and corner class, for all passes and kept passes.

    Only counts: the values of the feature columns are never summarised.
    """
    joined = passes[KEY + ["corner_class", "reason"]].merge(sidecar[KEY + FEATURE_COLUMNS], on=KEY, how="left")
    joined["corner_class"] = joined["corner_class"].fillna("none")
    rows = []
    for scope, frame in (("all", joined), ("kept", joined[joined["reason"].isna()])):
        for (season, cls), g in [((s, "all"), g) for s, g in frame.groupby("season")] + \
                [((s, c), g) for (s, c), g in frame.groupby(["season", "corner_class"])]:
            for col in FEATURE_COLUMNS:
                n_non = int(g[col].notna().sum())
                rows.append({"scope": scope, "season": int(season), "corner_class": cls, "column": col,
                             "passes": int(len(g)), "non_null": n_non,
                             "share": round(n_non / len(g), 4) if len(g) else np.nan})
    return pd.DataFrame(rows)


def range_check(sidecar: pd.DataFrame) -> list[dict]:
    """Pass/fail per column with NaN and out-of-range COUNTS only (no minimum, maximum or other value)."""
    out = []
    for col, (lo, hi) in RANGES.items():
        x = sidecar[col].to_numpy(dtype=float)
        fin = np.isfinite(x)
        bad = int(((x[fin] < lo) | (x[fin] > hi)).sum())
        out.append({"column": col, "range": f"[{lo}, {hi}]", "nan": int((~fin).sum()), "out_of_range": bad,
                    "ok": bad == 0})
    drs = sidecar["drs_open_approach"]
    out.append({"column": "drs_open_approach", "range": "boolean", "nan": int(drs.isna().sum()), "out_of_range": 0,
                "ok": True})
    return out


# --------------------------------------------------------------------------- main


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sums(folder: Path) -> tuple[int, int]:
    """(files listed, files matching) for a SHA256SUMS file in folder."""
    sums = folder / "SHA256SUMS"
    if not sums.exists():
        return 0, 0
    listed = ok = 0
    for line in sums.read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        listed += 1
        ok += (folder / name.strip()).exists() and sha256_file(folder / name.strip()) == digest
    return listed, ok


def write_sums(folder: Path) -> None:
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (folder / "SHA256SUMS").write_text("".join(f"{sha256_file(p)}  {p.name}\n" for p in files))


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pass-table", type=Path, default=DEFAULT_PASS_DIR, help="pass-table folder (read only)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--evidence", type=Path, help="folder for sidecar_coverage.csv and PROVENANCE.txt")
    parser.add_argument("--bronze", type=Path, default=BRONZE)
    parser.add_argument("--seasons", type=int, nargs="*", default=list(range(2018, 2026)))
    parser.add_argument("--race", help="one race slug only, for checking")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if out.is_relative_to(BRONZE.parent.resolve()) or out.is_relative_to(args.bronze.resolve()) \
            or out == args.pass_table.resolve():
        parser.error("--out must not be inside data/ or the pass-table folder")
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    listed, matching = verify_sums(args.pass_table)

    log, checks, all_side, all_pass = [], [], [], []
    for season in args.seasons:
        path = args.pass_table / f"pass_table_{season}.parquet"
        if not path.exists():
            print(f"{season}: no pass table", flush=True)
            continue
        passes = pq.read_table(path, columns=PASS_READ_COLUMNS).to_pandas()
        if args.race:
            passes = passes[passes["race"].map(nfc) == nfc(args.race)]
        if passes.duplicated(KEY).any():
            raise SystemExit(f"{season}: pass-table key is not unique")
        prev = previous_lap(passes)
        frames = []
        with ProcessPoolExecutor(max_workers=max(args.workers, 1)) as pool:
            futures = [pool.submit(_run_one, season, race, g[PASS_READ_COLUMNS], args.bronze)
                       for race, g in passes.groupby("race", sort=True)]
            for fut in as_completed(futures):
                s, race, frame, status, check, secs = fut.result()
                print(f"{s} {race}: {status}, {check.get('passes', 0)} passes, {secs:.1f}s", flush=True)
                log.append({"season": s, "race": nfc(race), "status": status, **check, "seconds": round(secs, 1)})
                frames.append(frame if frame is not None else null_rows(passes[passes["race"] == race]))
        side = finalise(pd.concat(frames, ignore_index=True), prev)
        if len(side) != len(passes) or side.duplicated(KEY).any():
            raise SystemExit(f"{season}: sidecar rows do not join 1:1 to the pass table")
        side.to_parquet(out / f"sidecar_{season}.parquet", index=False)
        checks.append({"season": season, "pass_rows": len(passes), "sidecar_rows": len(side),
                       "key_unique": not side.duplicated(KEY).any(),
                       "joined_1to1": len(passes.merge(side[KEY], on=KEY, how="inner")) == len(passes)})
        all_side.append(side)
        all_pass.append(passes[KEY + ["corner_class", "reason"]])
    races = pd.DataFrame(log).sort_values(["season", "race"])
    races.to_csv(out / "races.csv", index=False)
    write_sums(out)
    print(f"total {time.perf_counter() - started:.1f}s", flush=True)
    if args.evidence and all_side:
        side = pd.concat(all_side, ignore_index=True)
        passes = pd.concat(all_pass, ignore_index=True)
        write_evidence(args, side, passes, races, pd.DataFrame(checks), (listed, matching), argv)
    return 0


def write_evidence(args, side, passes, races, checks, sums, argv) -> None:
    ev = args.evidence
    ev.mkdir(parents=True, exist_ok=True)
    cov = coverage(side, passes)
    cov.to_csv(ev / "sidecar_coverage.csv", index=False)
    wide = cov[(cov["scope"] == "all") & (cov["corner_class"] == "all")].pivot(
        index="season", columns="column", values="share")[FEATURE_COLUMNS]
    wide_kept = cov[(cov["scope"] == "kept") & (cov["corner_class"] == "all")].pivot(
        index="season", columns="column", values="share")[FEATURE_COLUMNS]
    rng = range_check(side)
    ok_races = races[races["status"] == "ok"]
    lines = [
        "WC-10b sidecar table: PROVENANCE (coverage only; W9)",
        f"written: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"command: python -m tasks.wake_calibration.sidecar {' '.join(argv if argv is not None else sys.argv[1:])}",
        f"git HEAD: {_git_head()} (sidecar.py is uncommitted working-tree code)",
        f"sidecar.py sha256: {sha256_file(Path(__file__))}",
        f"build_pass_table.py sha256: {sha256_file(Path(bpt.__file__))} (unchanged; used read-only)",
        f"pass table: {args.pass_table} ; SHA256SUMS {sums[1]}/{sums[0]} files match (read only)",
        f"pass-table columns read: {', '.join(PASS_READ_COLUMNS)} (no segment time, minimum speed, reference or delta)",
        f"bronze: {args.bronze}/telemetry (car rows: Source == 'car') and circuit_info, read only; data/dev.duckdb not touched",
        f"artifacts: {args.out} (sidecar_<season>.parquet, races.csv, SHA256SUMS; git-ignored)",
        "",
        "Row counts and join (key season, race_id, driver, lap, corner_id):",
        checks.to_string(index=False),
        f"total pass rows {int(checks['pass_rows'].sum())}, sidecar rows {int(checks['sidecar_rows'].sum())}",
        "",
        f"Races: {len(races)} in the pass table; {len(ok_races)} rebuilt; others got null channel columns:",
        races.loc[races["status"] != "ok", ["season", "race", "status"]].to_string(index=False)
        if (races["status"] != "ok").any() else "  (none)",
        f"apex recomputed for {int(ok_races['apex_found'].sum())} of {int(ok_races['passes'].sum())} passes in rebuilt races; "
        f"seg_end_t agrees (|dt| <= 1e-6 s) for {int(ok_races['seg_end_agree'].sum())} of "
        f"{int(ok_races['seg_end_compared'].sum())} compared",
        "",
        "Coverage, all passes: share of rows with the column non-null, per season",
        wide.to_string(float_format=lambda x: f"{x:.4f}"),
        "",
        "Coverage, kept passes (reason is null)",
        wide_kept.to_string(float_format=lambda x: f"{x:.4f}"),
        "",
        "By corner class and scope: sidecar_coverage.csv (same folder).",
        "",
        "Sanity range check (pass/fail and counts only; no value is summarised, W9):",
        pd.DataFrame(rng).to_string(index=False),
        "",
        "Definitions (constants in sidecar.py; the registration WC-10d fixes them):",
        f"  exit_speed_kph: car-row speed at apex + {EXIT_AFTER_APEX_M:.0f} m, linear in distance; null if the "
        f"bracketing car samples are > {EXIT_MAX_BRACKET_M:.0f} m apart",
        f"  coast_time_s: brake off and throttle < {COAST_THROTTLE_PCT:.0f} % run immediately before the driver's own "
        f"car-row brake onset (last rising edge in {BRAKE_LOOKBACK_M:.0f} m before apex), first coast sample to "
        f"onset sample, capped {COAST_LOOKBACK_M:.0f} m; 0 if none observed; null without an onset or when a car-sample "
        f"gap > {COAST_MAX_DT_S} s lies inside the run",
        f"  partial_throttle_share: share of car samples in the pass-table segment with {COAST_THROTTLE_PCT:.0f} <= "
        f"throttle < {FULL_THROTTLE_PCT:.0f}; null below {MIN_SHARE_SAMPLES} samples or without a segment start",
        f"  drs_open_approach: any car sample with DRS in {DRS_OPEN_CODES} in the {APPROACH_M:.0f} m before the "
        f"segment start (the gap window); null without samples or a segment start",
        "  prev_lap_gap_s: pass-table gap_s, same driver and corner, lap - 1; null if that pass is missing or had "
        "no car ahead (prev_lap_clear_ahead tells them apart); never 0",
        "",
        "Caveats: car rows are ~4 Hz (median 0.24 s / 13 m; p90 0.40 s / 25 m). Exit speed interpolates across "
        "that spacing; coast time resolves to one sample interval (~0.24 s) and is a lower bound; brake is on/off "
        "only, so onset shifts under one sample spacing are invisible; throttle share is a sample share, not "
        "time-weighted. coast_time_s is null where the driver did not brake (flat corners), by definition.",
    ]
    (ev / "PROVENANCE.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
