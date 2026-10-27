"""
Phase 0 of wake-calibration (WC-01): the per-corner pass table.

One row per driver, corner and lap, built from the bronze parquet. It holds the
approach gap, the two outcomes, the driver's own clean reference and an exclusion
reason where one applies. It counts and excludes only: no coefficient, curve or
gate is computed here, and nothing is written into data/dev.duckdb.

    python -m tasks.wake_calibration.build_pass_table --out <scratch dir> [--seasons 2024] [--race slug] [--workers 6]

Bronze is read-only. Output goes wherever --out points: one pass_table_<season>.parquet
per season, plus races.csv (one line per race: passes built, or the reason it was skipped).

Segments are built per race (one circuit layout per race): the segment starts at the
corner's median braking point over clear-air passes (metres before the apex) and ends
SEGMENT_AFTER_APEX_M after the apex. A corner where most clear-air passes have no brake
onset is a flat-out corner: it has no braking point, so its segment starts a fixed
FLAT_SEGMENT_BEFORE_APEX_M before the apex instead (segment_basis "fixed_before_apex").
Its passes are kept, and segment_basis keeps them separable from braking corners.

Neutralised laps. SC, VSC and red (track status 4, 5, 6, 7) exclude the whole lap ("neutralised").
Yellow flags do NOT exclude the whole lap any more (owner ruling 2026-10-27): a race_control message with
Scope == "Sector" and Flag YELLOW or DOUBLE YELLOW in marshal sector k, active at any time during the
follower's lap, excludes only the passes whose corner lies in sector k (the affected sector) or in the
following sector k+1 (wrapping from the last sector to 1) - reason "yellow_sector". A sector yellow ends at a
CLEAR in that sector, at a Track CLEAR / GREEN / CHEQUERED message, or at the first track status 1
(AllClear) after it started, whichever is first; the last one catches sector yellows whose CLEAR message
is missing or carries the same timestamp as the yellow.

LIMIT - the corner-to-sector mapping is APPROXIMATE. Bronze has no marshal-sector positions (circuit_info
holds corner positions only). Marshal sectors are taken as EVENLY SPACED along the lap: the count is the
highest race_control Sector number seen for the race slug over all bronze seasons, and the corner's
sector is floor(count * corner Distance / median telemetry lap length) + 1. A real marshal sector is not
of equal length, so a corner near a sector boundary can be assigned to the neighbouring sector. The exact
rule needs the marshal-sector positions re-ingested from FastF1 circuit_info.

Layout flag (owner ruling DD-WC6, 2026-10-27). The sector layout is assumed constant across seasons, but a
race whose corner layout changed is FLAGGED (never excluded): columns layout_changed and layout_note on every
pass row. Each race is compared with the previous race at the same circuit (schedule Location, aliases
merged; same-season repeat races such as Austria/Styria count) on: the corner set actually used (count, and
positions after a rigid alignment, so a pure coordinate-frame shift is noted but not flagged), the median
telemetry lap length against the previous up-to-LAYOUT_LAP_REF_RACES races since the last change, and the
circuit_info fallback (corners taken from another season). The marshal-sector COUNT is not compared: bronze
holds no sector count, and the highest race_control Sector of one race only shows where incidents happened.
"""

from __future__ import annotations

import argparse
import bisect
import functools
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

BRONZE = Path(__file__).resolve().parents[3] / "data" / "bronze"

# Gap is averaged from GAP_LOOKBACK_M before the segment start down to GAP_NEAREST_M before it.
GAP_LOOKBACK_M = 300.0
GAP_NEAREST_M = 50.0
GAP_STEP_M = 10.0
MIN_GAP_SAMPLES = 5
# Outcomes run from the segment start (braking point) to this many metres after the apex.
SEGMENT_AFTER_APEX_M = 100.0
BRAKE_LOOKBACK_M = 300.0
# A corner counts as found on a lap when a sample lies this close to the apex (X/Y units, 1/10 m).
APEX_MAX_XY = 400.0
# A corner is flat-out when fewer than this share of its clear-air passes have a brake onset.
FLAT_KINK_BRAKE_SHARE = 0.5
# A flat-out corner has no braking point: its segment starts this far before the apex (the same
# distance as the segment runs after it), fixed per corner and independent of any driver input.
FLAT_SEGMENT_BEFORE_APEX_M = 100.0
# A lap is a track-limits lap when laps.Deleted is true and DeletedReason contains this text.
TRACK_LIMITS_TEXT = "TRACK LIMITS"

CAR_AHEAD_MAX_S = 30.0
CLEAN_AHEAD_GAP_S = 3.0
CLEAN_BEHIND_GAP_S = 1.0
LAPPED_GAP_S = 3.0
REF_HALF_WINDOW_LAPS = 4
REF_MIN_N = 2
RESTART_SKIP_LAPS = 2
CLASS_BOUNDS_KPH = (120.0, 200.0)

# Track status codes: 1 green, 2 yellow, 4 safety car, 5 red, 6 VSC, 7 VSC ending.
# Whole-lap neutralisation: SC, red, VSC only. Yellow (2) is handled per marshal sector from race_control.
NEUTRAL_STATUS = {"4", "5", "6", "7"}
YELLOW_STATUS = "2"
ALL_CLEAR_STATUS = "1"
RESTART_ENDS_STATUS = {"4", "5", "6", "7"}
WET_COMPOUNDS = {"INTERMEDIATE", "WET"}
# race_control sector yellows: these flags open one, CLEAR in the same sector or these track flags end it.
YELLOW_FLAGS = {"YELLOW", "DOUBLE YELLOW"}
TRACK_END_FLAGS = {"CLEAR", "GREEN", "CHEQUERED"}

# Exclusion reasons, in priority order: a pass carries the first that applies.
REASONS = [
    "lap_1", "no_lap_record", "no_lap_time", "neutralised", "yellow_sector", "restart", "pit_lap",
    "pit_lap_leader", "wet", "track_limits", "no_segment", "off_track", "no_gap",
]

PASS_COLUMNS = [
    "season", "race_id", "race", "driver", "lap", "stint", "compound", "tyre_life", "corner_id",
    "corner_number", "corner_class", "segment_basis", "apex_kph", "brake_offset_m", "seg_offset_m",
    "seg_start_t", "seg_end_t", "seg_time_s", "min_speed_kph", "leader", "leader_lap", "apex_dt_s", "gap_s",
    "gap_n", "clear_ahead", "behind_1s", "tag", "reason", "clean", "ref_n", "ref_time_s", "delta_time_s",
    "ref_status", "circuit_info_season", "circuit_match",
    # Diagnostics for owner rulings; they do not change the reason above.
    # marshal_sector: the corner's APPROXIMATE marshal sector (even spacing); ts_yellow_on_lap: track status 2
    # overlapped the lap (the old whole-lap yellow rule).
    "leader_track_limits", "marshal_sector", "ts_yellow_on_lap",
    # Layout flag (DD-WC6): set after all races are built, by comparing each race with the previous race at
    # the same circuit. A flag only; it never excludes.
    "layout_changed", "layout_note",
]
LAYOUT_COLUMNS = ["layout_changed", "layout_note"]
# What build_race returns; the layout columns are added across races by apply_layout_flags.
RACE_COLUMNS = [c for c in PASS_COLUMNS if c not in LAYOUT_COLUMNS]

# Layout-change detection (DD-WC6). A corner that moves more than this after a rigid alignment of the two
# corner sets is a moved corner (the same 40 m tolerance as APEX_MAX_XY, in metres).
LAYOUT_CORNER_MOVE_M = APEX_MAX_XY / 10.0
# Median telemetry lap length differing by more than this from the previous races' median is a change.
# Season-to-season noise on an unchanged layout is up to about 50 m (2018-2025 bronze).
LAYOUT_LAP_LENGTH_M = 50.0
LAYOUT_LAP_REF_RACES = 3
# schedule Location spellings that name the same circuit in different seasons.
CIRCUIT_ALIASES = {"Monte Carlo": "Monaco", "Yas Marina": "Yas Island", "Miami Gardens": "Miami",
                   "Singapore": "Marina Bay"}
# Race slugs that run a different layout of a shared Location (2020 Sakhir GP used the Bahrain outer loop).
SEPARATE_LAYOUT_SLUGS = {"sakhir_grand_prix": "Sakhir (outer)"}


class SkipRace(Exception):
    """A race that cannot be built from bronze, with the reason."""


def _seconds(values: pd.Series) -> np.ndarray:
    """Session time as float seconds, from a duration column or a float column."""
    if pd.api.types.is_timedelta64_dtype(values):
        return values.dt.total_seconds().to_numpy(dtype=float)
    return pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)


# --------------------------------------------------------------------------- exclusions


def neutral_intervals(
    track_status: pd.DataFrame, codes: set[str] = NEUTRAL_STATUS
) -> tuple[list[tuple[float, float]], list[float]]:
    """Session-time intervals with any of `codes` (default yellow, SC, red or VSC), and the times each
    SC/red/VSC period ended."""
    ts = track_status.dropna(subset=["session_time_s"]).sort_values("session_time_s")
    times = ts["session_time_s"].to_numpy(dtype=float)
    status = ts["Status"].astype(str).to_numpy()
    ends = np.append(times[1:], np.inf)
    neutral = []
    restarts = []
    for start, end, code in zip(times, ends, status):
        if code in codes:
            neutral.append((start, end))
        if code in RESTART_ENDS_STATUS and np.isfinite(end):
            restarts.append(end)
    return neutral, restarts


def overlaps_any(start: float, end: float, intervals: list[tuple[float, float]]) -> bool:
    return any(start < iv_end and end > iv_start for iv_start, iv_end in intervals)


def within_restart_skip(lap_start: float, restarts: list[float], lap_starts: list[float]) -> bool:
    """True when the lap is one of the driver's first RESTART_SKIP_LAPS laps starting at or after a restart.

    lap_starts holds the start times of all the driver's laps.
    """
    if not np.isfinite(lap_start):
        return False
    starts = np.sort(np.asarray([s for s in lap_starts if np.isfinite(s)], dtype=float))
    for end in restarts:
        after = starts[starts >= end][:RESTART_SKIP_LAPS]
        if np.any(np.isclose(after, lap_start)):
            return True
    return False


def sector_yellow_intervals(rc: pd.DataFrame, track_status: pd.DataFrame) -> list[tuple[int, float, float]]:
    """(marshal sector, start, end) for each race_control sector yellow, in session seconds.

    rc needs columns t (session seconds), Flag, Scope, Sector, in message order: messages that share a
    timestamp keep their order (a YELLOW and its CLEAR are often logged in the same second). A yellow
    ends at CLEAR in that sector, at a Track CLEAR / GREEN / CHEQUERED, or at a track status AllClear
    (no yellow anywhere), whichever comes first; a yellow issued again after that opens a new interval.
    A yellow never closed runs to +inf.
    """
    rc = rc.dropna(subset=["t"])
    events = [
        (float(t), 0, i, str(flag).upper(), scope, sector)
        for i, (flag, scope, sector, t) in enumerate(rc[["Flag", "Scope", "Sector", "t"]].itertuples(index=False, name=None))
    ]
    if track_status is not None and len(track_status):
        ts = track_status.dropna(subset=["session_time_s"])
        for t in ts.loc[ts["Status"].astype(str) == ALL_CLEAR_STATUS, "session_time_s"].to_numpy(dtype=float):
            events.append((float(t), 1, 0, "ALLCLEAR", "TrackStatus", np.nan))
    events.sort(key=lambda e: (e[0], e[1], e[2]))  # time, then race_control before track status, then feed order
    open_: dict[int, float] = {}
    out: list[tuple[int, float, float]] = []
    for t, _, _, flag, scope, sector in events:
        if scope == "Sector" and pd.notna(sector):
            k = int(sector)
            if flag in YELLOW_FLAGS:
                open_.setdefault(k, t)
            elif flag == "CLEAR" and k in open_:
                out.append((k, open_.pop(k), t))
        elif (scope == "Track" and flag in TRACK_END_FLAGS) or flag == "ALLCLEAR":
            out += [(k, t0, t) for k, t0 in open_.items()]
            open_ = {}
    out += [(k, t0, np.inf) for k, t0 in open_.items()]
    return out


def marshal_sector_count(race: str, bronze: Path = BRONZE) -> int:
    """Highest race_control Sector number seen for this race slug in any bronze season (0 if none)."""
    n = 0
    for path in sorted((bronze / "race_control").glob(f"season=*/race={race}/race_control.parquet")):
        names = set(pq.read_schema(path).names)
        if not {"Scope", "Sector"} <= names:
            continue
        rc = pq.read_table(path, columns=["Scope", "Sector"]).to_pandas()
        s = rc.loc[rc["Scope"] == "Sector", "Sector"].max()
        if pd.notna(s):
            n = max(n, int(s))
    return n


def corner_marshal_sectors(corners: pd.DataFrame, lap_length_m: float, n_sectors: int) -> dict[str, float]:
    """APPROXIMATE marshal sector per corner (1..n), assuming n evenly spaced sectors along the lap.

    Bronze has no marshal-sector positions, so this is an estimate: sector = floor(n * Distance / lap
    length) + 1. NaN when the corner has no Distance, the lap length is unknown or n is 0.
    """
    if "Distance" not in corners or not n_sectors or not np.isfinite(lap_length_m) or lap_length_m <= 0:
        return {c: np.nan for c in corners["corner_id"]}
    frac = (pd.to_numeric(corners["Distance"], errors="coerce") / lap_length_m).clip(0.0, 0.999999)
    sector = np.floor(frac.to_numpy(dtype=float) * n_sectors) + 1
    return dict(zip(corners["corner_id"], sector))


def in_sector_yellow(
    t0: np.ndarray, t1: np.ndarray, sector: np.ndarray, intervals: list[tuple[int, float, float]], n_sectors: int
) -> np.ndarray:
    """True where a sector yellow in k overlaps the lap [t0, t1] and the corner is in sector k or k+1."""
    hit = np.zeros(len(t0), dtype=bool)
    if not n_sectors:
        return hit
    for k, a, b in intervals:
        following = (k % n_sectors) + 1
        hit |= (t0 < b) & (t1 > a) & ((sector == k) | (sector == following))
    return hit


# --------------------------------------------------------------------------- car traces


@dataclass
class CarTrace:
    """One car's race on a single distance axis, so windows can reach back over the line."""

    cum: np.ndarray  # cumulative distance, metres, non-decreasing
    t: np.ndarray  # session seconds
    v: np.ndarray  # speed, km/h
    brake: np.ndarray  # bool
    on_track: np.ndarray  # bool, Status == OnTrack
    x: np.ndarray
    y: np.ndarray
    lap_span: dict[int, tuple[int, int]] = field(default_factory=dict)  # lap -> [i0, i1)
    lap_complete: set[int] = field(default_factory=set)  # laps L with L-1 and L+1 also present


def build_car_trace(samples: pd.DataFrame) -> CarTrace:
    # Sort by lap, then time: the last sample of a lap and the first of the next often share a
    # timestamp, and a time-only sort can interleave them, which corrupts the distance axis.
    samples = samples.sort_values(["lap_number", "t"], kind="stable").reset_index(drop=True)
    laps = samples["lap_number"].to_numpy(dtype=float)
    dist = samples["distance_m"].to_numpy(dtype=float)
    lap_span: dict[int, tuple[int, int]] = {}
    lap_max: dict[int, float] = {}
    for lap in np.unique(laps):
        idx = np.flatnonzero(laps == lap)
        lap_span[int(lap)] = (int(idx[0]), int(idx[-1]) + 1)
        lap_max[int(lap)] = float(np.nanmax(dist[idx]))
    # Lap distance restarts at each line crossing, so add the lengths of the laps before it.
    cum = np.zeros_like(dist)
    running = 0.0
    for lap in sorted(lap_span):
        i0, i1 = lap_span[lap]
        cum[i0:i1] = running + dist[i0:i1]
        running += lap_max[lap]
    # Distance is noisy at the line; keep the axis non-decreasing for interpolation.
    cum = np.maximum.accumulate(np.nan_to_num(cum))
    complete = {lap for lap in lap_span if lap - 1 in lap_span and lap + 1 in lap_span}
    return CarTrace(
        cum=cum,
        t=samples["t"].to_numpy(dtype=float),
        v=samples["speed_kph"].to_numpy(dtype=float),
        brake=samples["brake"].fillna(False).to_numpy(dtype=bool),
        on_track=samples["Status"].astype(str).to_numpy() == "OnTrack",
        x=samples["X"].to_numpy(dtype=float),
        y=samples["Y"].to_numpy(dtype=float),
        lap_span=lap_span,
        lap_complete=complete,
    )


def interp_time(trace: CarTrace, cum_points: np.ndarray) -> np.ndarray:
    """Session time at each cumulative distance; NaN outside the trace."""
    return np.interp(cum_points, trace.cum, trace.t, left=np.nan, right=np.nan)


def all_on_track(trace: CarTrace, lo: float, hi: float) -> bool:
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return True
    i0 = int(np.searchsorted(trace.cum, lo))
    i1 = int(np.searchsorted(trace.cum, hi, side="right"))
    return bool(trace.on_track[i0:i1].all()) if i1 > i0 else False


# --------------------------------------------------------------------------- apex events


@dataclass
class ApexEvent:
    driver: str
    lap: int
    corner: str
    cum_apex: float
    t_apex: float
    apex_kph: float
    brake_offset: float  # last brake onset, metres relative to the apex (negative); NaN if none
    apex_xy_dist: float = np.nan  # distance from the corner point to the trace, X/Y units


def _refine_apex(trace: CarTrace, j: int, px: float, py: float) -> tuple[float, float, float]:
    """Project the corner point onto the trace segments either side of sample j: (cum, t, distance)."""
    best = (float(trace.cum[j]), float(trace.t[j]), float(np.hypot(trace.x[j] - px, trace.y[j] - py)))
    for a, b in ((j - 1, j), (j, j + 1)):
        if a < 0 or b >= len(trace.cum):
            continue
        dx, dy = trace.x[b] - trace.x[a], trace.y[b] - trace.y[a]
        seg2 = dx * dx + dy * dy
        if not np.isfinite(seg2) or seg2 <= 0:
            continue
        u = min(max(((px - trace.x[a]) * dx + (py - trace.y[a]) * dy) / seg2, 0.0), 1.0)
        d = float(np.hypot(trace.x[a] + u * dx - px, trace.y[a] + u * dy - py))
        if d < best[2]:
            cum = float(trace.cum[a] + u * (trace.cum[b] - trace.cum[a]))
            t = float(trace.t[a] + u * (trace.t[b] - trace.t[a]))
            best = (cum, t, d)
    return best


def corner_table(circuit_info: pd.DataFrame) -> pd.DataFrame:
    """Corners with a string id (number plus letter, e.g. "12A") and X/Y."""
    ci = circuit_info.dropna(subset=["Number", "X", "Y"]).copy()
    letter = ci["Letter"].fillna("").astype(str).str.strip() if "Letter" in ci else ""
    ci["corner_number"] = ci["Number"].astype(int)
    ci["corner_id"] = ci["corner_number"].astype(str) + letter
    cols = ["corner_id", "corner_number", "X", "Y"] + (["Distance"] if "Distance" in ci else [])
    return ci.sort_values(["corner_number", "corner_id"]).drop_duplicates("corner_id")[cols]


def find_apex_events(driver: str, trace: CarTrace, corners: pd.DataFrame) -> list[ApexEvent]:
    events = []
    cx = corners["X"].to_numpy(dtype=float)
    cy = corners["Y"].to_numpy(dtype=float)
    ids = corners["corner_id"].tolist()
    for lap in sorted(trace.lap_complete):
        i0, i1 = trace.lap_span[lap]
        xs, ys = trace.x[i0:i1], trace.y[i0:i1]
        if not (np.isfinite(xs) & np.isfinite(ys)).any():
            continue
        for corner_id, px, py in zip(ids, cx, cy):
            dist_xy = np.hypot(xs - px, ys - py)
            k = int(np.nanargmin(dist_xy))
            if dist_xy[k] > APEX_MAX_XY:
                continue
            j = i0 + k
            cum_apex, t_apex, d = _refine_apex(trace, j, px, py)
            # Braking point: the last rising edge of the brake signal in the lookback before the apex.
            lo = max(int(np.searchsorted(trace.cum, cum_apex - BRAKE_LOOKBACK_M)), 1)
            onsets = np.flatnonzero(trace.brake[lo : j + 1] & ~trace.brake[lo - 1 : j]) + lo
            brake_offset = float(trace.cum[onsets[-1]] - cum_apex) if len(onsets) else np.nan
            events.append(
                ApexEvent(
                    driver=driver,
                    lap=lap,
                    corner=corner_id,
                    cum_apex=cum_apex,
                    t_apex=t_apex,
                    apex_kph=float(trace.v[j]),
                    brake_offset=min(brake_offset, 0.0) if np.isfinite(brake_offset) else np.nan,
                    apex_xy_dist=d,
                )
            )
    return events


class ApexIndex:
    """One corner's apex events sorted by time, so the car ahead and behind are found by bisection."""

    def __init__(self, events: list[ApexEvent]):
        self.events = sorted(events, key=lambda e: e.t_apex)
        self.times = [e.t_apex for e in self.events]

    def car_ahead(self, f: ApexEvent) -> ApexEvent | None:
        """Latest apex by another car before the follower's, within CAR_AHEAD_MAX_S."""
        i = bisect.bisect_left(self.times, f.t_apex) - 1
        while i >= 0 and f.t_apex - self.times[i] <= CAR_AHEAD_MAX_S:
            if self.events[i].driver != f.driver:
                return self.events[i]
            i -= 1
        return None

    def within_behind(self, f: ApexEvent, seconds: float) -> bool:
        """True when another car's apex falls in the window just after the follower's."""
        i = bisect.bisect_right(self.times, f.t_apex)
        while i < len(self.times) and self.times[i] <= f.t_apex + seconds:
            if self.events[i].driver != f.driver:
                return True
            i += 1
        return False


def gap_offsets(seg_offset: float) -> np.ndarray:
    """Offsets from the apex where the gap is sampled: GAP_LOOKBACK_M to GAP_NEAREST_M before the segment start."""
    if not np.isfinite(seg_offset):
        return np.empty(0)
    return np.arange(seg_offset - GAP_LOOKBACK_M, seg_offset - GAP_NEAREST_M + 1e-9, GAP_STEP_M)


def gap_to_leader(
    f_cum_apex: float, follower: CarTrace, lead_cum_apex: float, leader: CarTrace, seg_offset: float
) -> tuple[float, int]:
    """Mean time gap (follower minus leader at the same place) over the gap window, and the valid sample count."""
    offsets = gap_offsets(seg_offset)
    if offsets.size == 0 or not (np.isfinite(f_cum_apex) and np.isfinite(lead_cum_apex)):
        return np.nan, 0
    diff = interp_time(follower, f_cum_apex + offsets) - interp_time(leader, lead_cum_apex + offsets)
    valid = np.isfinite(diff)
    if not valid.any():
        return np.nan, 0
    return float(diff[valid].mean()), int(valid.sum())


# --------------------------------------------------------------------------- one race


CIRCUIT_COLUMNS = ["X", "Y", "Number", "Letter", "Distance"]
# When a race's circuit_info is missing or has no corners, the same race slug's circuit_info from
# these neighbouring seasons is used instead (in this order), and the source season is recorded.
CIRCUIT_FALLBACK_SEASONS = (-1, 1)


def load_circuit_info(season: int, race: str, bronze: Path = BRONZE) -> tuple[pd.DataFrame, int]:
    """Corner positions for the race, and the season they came from (fallback to ±1 season, same slug)."""
    candidates = circuit_candidates(season, race, bronze)
    if not candidates:
        raise SkipRace(f"no circuit_info corners for this race slug in seasons {season - 1}-{season + 1}")
    return candidates[0]


def circuit_candidates(season: int, race: str, bronze: Path = BRONZE) -> list[tuple[pd.DataFrame, int]]:
    """Usable circuit_info tables for the race: own season first, then the fallback seasons."""
    out = []
    for delta in (0, *CIRCUIT_FALLBACK_SEASONS):
        folder = bronze / "circuit_info" / f"season={season + delta}" / f"race={race}"
        path = next(iter(sorted(folder.glob("*.parquet"))), None)
        if path is None:
            continue
        names = set(pq.read_schema(path).names)
        if not {"X", "Y", "Number"} <= names:
            continue
        ci = pq.read_table(path, columns=[c for c in CIRCUIT_COLUMNS if c in names]).to_pandas()
        if "Letter" not in ci:
            ci["Letter"] = ""
        if not corner_table(ci).empty:
            out.append((ci, season + delta))
    return out


# The race's own circuit_info is replaced by a fallback season's only when fewer than this share of
# corner points lie within APEX_MAX_XY of the telemetry (a different coordinate frame or layout).
CIRCUIT_MATCH_MIN = 0.9
# Below this share even for the best candidate, the race is skipped.
CIRCUIT_MATCH_SKIP = 0.5


def circuit_match(corners: pd.DataFrame, trace: CarTrace, n_laps: int = 5) -> float:
    """Share of (lap, corner) pairs with a telemetry sample within APEX_MAX_XY, over a few complete laps."""
    laps = sorted(trace.lap_complete)
    laps = laps[len(laps) // 2 : len(laps) // 2 + n_laps]
    hits, total = 0, 0
    for lap in laps:
        i0, i1 = trace.lap_span[lap]
        for px, py in corners[["X", "Y"]].itertuples(index=False, name=None):
            d = np.hypot(trace.x[i0:i1] - px, trace.y[i0:i1] - py)
            total += 1
            hits += bool(np.isfinite(d).any() and np.nanmin(d) <= APEX_MAX_XY)
    return hits / total if total else 0.0


def choose_circuit(candidates: list[tuple[pd.DataFrame, int]], trace: CarTrace) -> tuple[pd.DataFrame, int, float]:
    """The race's own corners unless they match the telemetry poorly and a fallback matches better."""
    scored = [(corner_table(ci), s, circuit_match(corner_table(ci), trace)) for ci, s in candidates]
    own = scored[0]
    if own[2] >= CIRCUIT_MATCH_MIN:
        return own
    return max(scored, key=lambda c: c[2])


def _race_files(season: int, race: str, bronze: Path) -> dict[str, Path]:
    files = {}
    for dataset, name in [
        ("laps", None), ("telemetry", "telemetry.parquet"), ("track_status", "track_status.parquet"),
        ("race_control", "race_control.parquet"), ("weather", "weather.parquet"),
    ]:
        folder = bronze / dataset / f"season={season}" / f"race={race}"
        path = next(iter(sorted(folder.glob("*.parquet"))), None) if name is None else folder / name
        if path is None or not path.exists():
            raise SkipRace(f"no {dataset} parquet in bronze")
        files[dataset] = path
    return files


def load_race(season: int, race: str, bronze: Path = BRONZE) -> dict[str, pd.DataFrame]:
    columns = {
        "telemetry": TELEMETRY_COLUMNS,
        "laps": [
            "race_id", "Driver", "DriverNumber", "LapNumber", "Stint", "Compound", "TyreLife", "PitInTime",
            "PitOutTime", "LapStartTime", "LapStartDate", "Time", "LapTime", "Deleted", "DeletedReason",
        ],
        "track_status": ["Status", "session_time_s"],
        "race_control": ["index", "Time", "Flag", "Scope", "Sector", "RacingNumber"],
        "weather": ["rainfall_flag", "session_time_s"],
    }
    files = _race_files(season, race, bronze)
    data = {}
    for name, path in files.items():
        present = set(pq.read_schema(path).names)
        data[name] = pq.read_table(path, columns=[c for c in columns[name] if c in present]).to_pandas()
    if "index" in data["race_control"]:  # keep the feed's message order for messages sharing a timestamp
        data["race_control"] = data["race_control"].sort_values("index", kind="stable").reset_index(drop=True)
    data["circuit_candidates"] = circuit_candidates(season, race, bronze)
    data["marshal_sectors"] = marshal_sector_count(race, bronze)
    if not data["circuit_candidates"]:
        raise SkipRace(f"no circuit_info corners for this race slug in seasons {season - 1}-{season + 1}")
    return data


def track_limits_laps(laps: pd.DataFrame) -> np.ndarray:
    """True for laps deleted for track limits (Deleted and a DeletedReason naming track limits).

    The flagged lap itself is excluded, also for "(NEXT LAP)" reasons; a missing column means no deletions.
    """
    if "Deleted" not in laps or "DeletedReason" not in laps:
        return np.zeros(len(laps), dtype=bool)
    deleted = laps["Deleted"].astype("boolean").fillna(False).to_numpy(dtype=bool)
    reason = laps["DeletedReason"].fillna("").astype(str).str.upper()
    return deleted & reason.str.contains(TRACK_LIMITS_TEXT, regex=False).to_numpy(dtype=bool)


def lap_table(laps: pd.DataFrame) -> pd.DataFrame:
    table = pd.DataFrame(
        {
            "driver": laps["Driver"].astype(str),
            "number": laps["DriverNumber"].astype(str),
            "lap": pd.to_numeric(laps["LapNumber"], errors="coerce"),
            "stint": pd.to_numeric(laps["Stint"], errors="coerce"),
            "compound": laps["Compound"].fillna("UNKNOWN").astype(str).str.upper()
            .replace({"NAN": "UNKNOWN", "NONE": "UNKNOWN", "": "UNKNOWN"}),
            "tyre_life": pd.to_numeric(laps["TyreLife"], errors="coerce"),
            "pit": (laps["PitInTime"].notna() | laps["PitOutTime"].notna()).to_numpy(),
            "t0": _seconds(laps["LapStartTime"]),
            "t1": _seconds(laps["Time"]),
            "lap_seconds": _seconds(laps["LapTime"]),
            "track_limits": track_limits_laps(laps),
        }
    ).dropna(subset=["lap"])
    table["lap"] = table["lap"].astype(int)
    return table.drop_duplicates(["driver", "lap"])


def race_control_session_seconds(race_control: pd.DataFrame, laps: pd.DataFrame) -> np.ndarray:
    """Race-control messages in session seconds.

    Bronze race_control.session_time_s is the time of day, not session time, so it is rebuilt from the
    message timestamp minus the session start (median of LapStartDate - LapStartTime from the laps).
    """
    start = (laps["LapStartDate"] - laps["LapStartTime"]).median()
    if pd.isna(start) or race_control.empty:
        return np.full(len(race_control), np.nan)
    return (pd.to_datetime(race_control["Time"]) - start).dt.total_seconds().to_numpy(dtype=float)


TELEMETRY_COLUMNS = ["SessionTime", "driver_id", "lap_number", "distance_m", "speed_kph", "brake", "Status", "X", "Y"]


def race_geometry(telemetry: pd.DataFrame, candidates: list[tuple[pd.DataFrame, int]]):
    """Car traces, the corner set used (own season unless misaligned), its season and match share, and the
    median telemetry lap length. Shared by build_race and layout_info so both pick the same corners."""
    tel = telemetry.dropna(subset=["lap_number", "distance_m", "SessionTime"]).copy()
    tel["t"] = _seconds(tel.pop("SessionTime"))
    traces = {str(driver): build_car_trace(g) for driver, g in tel.groupby("driver_id")}
    if not traces:
        raise SkipRace("telemetry has no usable samples")
    busiest = max(traces.values(), key=lambda tr: len(tr.lap_complete))
    corners, circuit_season, match = choose_circuit(candidates, busiest)
    if match < CIRCUIT_MATCH_SKIP:
        raise SkipRace(f"circuit_info corners match telemetry poorly (best {match:.2f} from season {circuit_season})")
    lap_len = float(tel.groupby(["driver_id", "lap_number"])["distance_m"].max().median())
    return traces, corners, int(circuit_season), float(match), lap_len


def build_race(season: int, race: str, bronze: Path = BRONZE, info: dict | None = None) -> pd.DataFrame:
    """The race's pass table (RACE_COLUMNS). When `info` is given it is filled with the race's layout
    signature (see layout_info) so the cross-race layout flag needs no second read of the telemetry."""
    data = load_race(season, race, bronze)
    if data["laps"].empty:
        raise SkipRace("laps parquet is empty")
    if data["telemetry"].empty:
        raise SkipRace("telemetry parquet is empty")
    race_id = str(data["laps"]["race_id"].iloc[0])
    laps = lap_table(data["laps"])

    traces, corners, circuit_season, match, lap_len = race_geometry(data["telemetry"], data["circuit_candidates"])
    if info is not None:
        info.update(layout_signature(season, race, corners, circuit_season, lap_len, bronze))
    events = [e for driver, trace in traces.items() for e in find_apex_events(driver, trace, corners)]
    if not events:
        raise SkipRace("no apex events found in telemetry")

    rc = data["race_control"].copy()
    rc["t"] = race_control_session_seconds(rc, data["laps"])
    blue = rc[rc["Flag"].astype(str).str.upper().eq("BLUE")].dropna(subset=["t"])
    weather = data["weather"].dropna(subset=["session_time_s"])
    n_sectors = int(data["marshal_sectors"])
    yellows = sector_yellow_intervals(rc, data["track_status"]) if {"Scope", "Sector"} <= set(rc) else []
    sector_of = corner_marshal_sectors(corners, lap_len, n_sectors)

    table = pass_events(events, corners)
    table = attach_laps(table, laps)
    table["marshal_sector"] = table["corner_id"].map(sector_of).astype(float)
    table["f_yellow_sector"] = in_sector_yellow(
        table["lap_t0"].to_numpy(dtype=float), table["lap_t1"].to_numpy(dtype=float),
        table["marshal_sector"].to_numpy(dtype=float), yellows, n_sectors,
    )
    table = corner_layout(table, data["track_status"], laps)
    table = attach_gaps(table, traces)
    table = attach_flags(table, traces, data["track_status"], laps, weather, blue)
    table = attach_outcomes(table, traces)
    table = references(table)
    table.insert(0, "season", season)
    table.insert(1, "race_id", race_id)
    table.insert(2, "race", race)
    table["circuit_info_season"] = int(circuit_season)
    table["circuit_match"] = round(float(match), 3)
    return table[RACE_COLUMNS]


def pass_events(events: list[ApexEvent], corners: pd.DataFrame) -> pd.DataFrame:
    """One row per apex event, with the car ahead by apex crossing order and a car-behind flag."""
    number_of = dict(zip(corners["corner_id"], corners["corner_number"]))
    rows = []
    for corner_id in corners["corner_id"]:
        index = ApexIndex([e for e in events if e.corner == corner_id])
        for f in index.events:
            lead = index.car_ahead(f)
            rows.append(
                {
                    "driver": f.driver,
                    "lap": int(f.lap),
                    "corner_id": corner_id,
                    "corner_number": int(number_of[corner_id]),
                    "apex_kph": f.apex_kph,
                    "apex_xy_dist": f.apex_xy_dist,
                    "brake_offset_m": f.brake_offset,
                    "cum_apex": f.cum_apex,
                    "t_apex": f.t_apex,
                    "leader": None if lead is None else lead.driver,
                    "leader_lap": np.nan if lead is None else float(lead.lap),
                    "leader_cum_apex": np.nan if lead is None else lead.cum_apex,
                    "apex_dt_s": np.nan if lead is None else f.t_apex - lead.t_apex,
                    "clear_ahead": lead is None,
                    "behind_1s": index.within_behind(f, CLEAN_BEHIND_GAP_S),
                }
            )
    return pd.DataFrame(rows)


def attach_laps(table: pd.DataFrame, laps: pd.DataFrame) -> pd.DataFrame:
    own = laps.rename(columns={"t0": "lap_t0", "t1": "lap_t1"})[
        ["driver", "lap", "number", "stint", "compound", "tyre_life", "pit", "track_limits", "lap_t0", "lap_t1"]
    ].assign(has_lap=True)
    table = table.merge(own, on=["driver", "lap"], how="left")
    for col in ("has_lap", "pit", "track_limits"):
        table[col] = table[col].astype("boolean").fillna(False).astype(bool)
    lead = laps[["driver", "lap", "pit", "track_limits"]].rename(
        columns={"driver": "leader", "pit": "leader_pit", "track_limits": "leader_track_limits"}
    )
    lead["leader_lap"] = lead.pop("lap").astype(float)
    table = table.merge(lead, on=["leader", "leader_lap"], how="left")
    for col in ("leader_pit", "leader_track_limits"):
        table[col] = table[col].astype("boolean").fillna(False).astype(bool)
    return table


def lap_exclusions(table: pd.DataFrame, track_status: pd.DataFrame, laps: pd.DataFrame) -> pd.DataFrame:
    """Lap-level flags: lap 1, no lap record, no lap time, neutralised (SC/VSC/red), restart, and whether
    track status 2 (yellow anywhere) overlapped the lap (diagnostic; it no longer excludes)."""
    neutral, restarts = neutral_intervals(track_status)
    ts_yellow, _ = neutral_intervals(track_status, {YELLOW_STATUS})
    starts_of = {d: g["t0"].tolist() for d, g in laps.groupby("driver")}
    keys = table[["driver", "lap", "lap_t0", "lap_t1"]].drop_duplicates(["driver", "lap"])
    flags = []
    for driver, lap, t0, t1 in keys.itertuples(index=False, name=None):
        timed = bool(np.isfinite(t0) and np.isfinite(t1))
        flags.append(
            {
                "driver": driver,
                "lap": lap,
                "f_neutral": timed and overlaps_any(t0, t1, neutral),
                "f_ts_yellow": timed and overlaps_any(t0, t1, ts_yellow),
                "f_restart": within_restart_skip(t0, restarts, starts_of.get(driver, [])),
            }
        )
    out = table.merge(pd.DataFrame(flags), on=["driver", "lap"], how="left")
    out["f_lap1"] = out["lap"] < 2
    out["f_no_lap"] = ~out["has_lap"]
    out["f_no_time"] = out["has_lap"] & ~(np.isfinite(out["lap_t0"]) & np.isfinite(out["lap_t1"]))
    return out


def corner_layout(table: pd.DataFrame, track_status: pd.DataFrame, laps: pd.DataFrame) -> pd.DataFrame:
    """Per corner: segment start, segment basis and class, from clear-air passes.

    Braking corners start at the median brake offset. Flat-out corners (fewer than FLAT_KINK_BRAKE_SHARE of
    clear-air passes brake) start FLAT_SEGMENT_BEFORE_APEX_M before the apex.

    Clear air here means no car ahead within CLEAN_AHEAD_GAP_S at the apex, on a lap with no lap-level
    exclusion (the gap is not known yet because it is measured relative to the segment start).
    """
    table = lap_exclusions(table, track_status, laps)
    # The layout basis still drops any lap with track status 2 (any yellow), as before the sector-yellow
    # ruling, so segment starts and classes are unchanged by it.
    lap_ok = ~(table["f_lap1"] | table["f_no_lap"] | table["f_no_time"] | table["f_neutral"] | table["f_ts_yellow"]
               | table["f_restart"] | table["pit"] | table["leader_pit"])
    clear = lap_ok & (table["clear_ahead"] | (table["apex_dt_s"] > CLEAN_AHEAD_GAP_S))
    basis = table[clear] if clear.any() else table
    g = basis.groupby("corner_id")
    layout = pd.DataFrame(
        {
            "seg_offset_m": g["brake_offset_m"].median(),
            "brake_share": g["brake_offset_m"].apply(lambda s: float(np.isfinite(s).mean())),
            "class_kph": g["apex_kph"].median(),
        }
    )
    layout["flat_kink"] = layout["brake_share"] < FLAT_KINK_BRAKE_SHARE
    slow, fast = CLASS_BOUNDS_KPH
    layout["corner_class"] = np.select(
        [layout["class_kph"] < slow, layout["class_kph"] >= fast], ["slow", "fast"], default="medium"
    )
    layout.loc[layout["flat_kink"], "seg_offset_m"] = -FLAT_SEGMENT_BEFORE_APEX_M
    layout["segment_basis"] = np.where(layout["flat_kink"], "fixed_before_apex", "brake_onset")
    table = table.merge(layout[["seg_offset_m", "segment_basis", "corner_class"]], left_on="corner_id",
                        right_index=True, how="left")
    table["segment_basis"] = table["segment_basis"].fillna("none")
    return table


def attach_gaps(table: pd.DataFrame, traces: dict[str, CarTrace]) -> pd.DataFrame:
    gap_s, gap_n = [], []
    for driver, f_cum, leader, l_cum, seg in table[
        ["driver", "cum_apex", "leader", "leader_cum_apex", "seg_offset_m"]
    ].itertuples(index=False, name=None):
        if leader is None or not isinstance(leader, str) or leader not in traces:
            gap_s.append(np.nan)
            gap_n.append(0)
            continue
        s, n = gap_to_leader(f_cum, traces[driver], l_cum, traces[leader], seg)
        gap_s.append(s)
        gap_n.append(n)
    table = table.copy()
    table["gap_s"] = gap_s
    table["gap_n"] = gap_n
    return table


def _any_in(times: np.ndarray, flags: np.ndarray, t0: float, t1: float) -> bool:
    if not (np.isfinite(t0) and np.isfinite(t1)) or times.size == 0:
        return False
    mask = (times >= t0) & (times <= t1)
    return bool(flags[mask].any())


def attach_flags(table, traces, track_status, laps, weather, blue) -> pd.DataFrame:
    """Exclusion reason (first in REASONS that applies) and the lapped / yielding tags."""
    table = table.copy()
    rain_t = weather["session_time_s"].to_numpy(dtype=float)
    rain_on = weather["rainfall_flag"].fillna(False).to_numpy(dtype=bool)
    blue_t = blue["t"].to_numpy(dtype=float)
    blue_no = blue["RacingNumber"].astype(str).to_numpy()

    wet, off, yielding = [], [], []
    for row in table[
        ["driver", "number", "compound", "lap_t0", "lap_t1", "cum_apex", "leader", "leader_cum_apex", "seg_offset_m"]
    ].itertuples(index=False, name=None):
        driver, number, compound, t0, t1, f_cum, leader, l_cum, seg = row
        wet.append(compound in WET_COMPOUNDS or _any_in(rain_t, rain_on, t0, t1))
        start = seg if np.isfinite(seg) else 0.0
        lo, hi = start - GAP_LOOKBACK_M, SEGMENT_AFTER_APEX_M
        bad = not all_on_track(traces[driver], f_cum + lo, f_cum + hi)
        if not bad and isinstance(leader, str) and leader in traces:
            bad = not all_on_track(traces[leader], l_cum + lo, l_cum + hi)
        off.append(bad)
        yielding.append(_any_in(blue_t, blue_no == str(number), t0, t1) if isinstance(number, str) else False)

    has_leader = table["leader"].apply(lambda x: isinstance(x, str))
    conditions = {
        "lap_1": table["f_lap1"],
        "no_lap_record": table["f_no_lap"],
        "no_lap_time": table["f_no_time"],
        "neutralised": table["f_neutral"].fillna(False).astype(bool),
        "yellow_sector": table["f_yellow_sector"].fillna(False).astype(bool),
        "restart": table["f_restart"].fillna(False).astype(bool),
        "pit_lap": table["pit"],
        "pit_lap_leader": table["leader_pit"],
        "wet": pd.Series(wet, index=table.index),
        "track_limits": table["track_limits"],
        # The corner had no clear-air pass in this race, so no segment start could be set.
        "no_segment": ~np.isfinite(table["seg_offset_m"].to_numpy(dtype=float)),
        "off_track": pd.Series(off, index=table.index),
        "no_gap": has_leader & (table["gap_n"] < MIN_GAP_SAMPLES),
    }
    assert list(conditions) == REASONS
    reason = np.select([np.asarray(c, dtype=bool) for c in conditions.values()], REASONS, default="")
    table["reason"] = pd.Series(reason, index=table.index).replace("", None)

    table["ts_yellow_on_lap"] = table["f_ts_yellow"].fillna(False).astype(bool)

    lapped = (table["leader_lap"] < table["lap"]) & (table["gap_s"] < LAPPED_GAP_S)
    yielding = pd.Series(yielding, index=table.index)
    tag = np.select([lapped & yielding, lapped, yielding], ["lapped+yielding", "lapped", "yielding"], default="")
    table["tag"] = pd.Series(tag, index=table.index).replace("", None)
    return table


def attach_outcomes(table: pd.DataFrame, traces: dict[str, CarTrace]) -> pd.DataFrame:
    """Segment time from the driver's own trace only, and minimum speed over the segment."""
    start, end, seg_time, min_speed = [], [], [], []
    for driver, f_cum, seg in table[["driver", "cum_apex", "seg_offset_m"]].itertuples(index=False, name=None):
        if not np.isfinite(seg):
            start.append(np.nan)
            end.append(np.nan)
            seg_time.append(np.nan)
            min_speed.append(np.nan)
            continue
        trace = traces[driver]
        cum_start = f_cum + seg
        cum_end = f_cum + SEGMENT_AFTER_APEX_M
        t_start, t_end = interp_time(trace, np.array([cum_start, cum_end]))
        i0 = int(np.searchsorted(trace.cum, cum_start))
        i1 = int(np.searchsorted(trace.cum, cum_end, side="right"))
        start.append(t_start)
        end.append(t_end)
        seg_time.append(t_end - t_start)
        min_speed.append(float(np.nanmin(trace.v[i0:i1])) if i1 > i0 else np.nan)
    table = table.copy()
    table["seg_start_t"] = start
    table["seg_end_t"] = end
    table["seg_time_s"] = seg_time
    table["min_speed_kph"] = min_speed
    return table


def references(table: pd.DataFrame) -> pd.DataFrame:
    """Own clean passes of the same corner within REF_HALF_WINDOW_LAPS, same stint and compound.

    Clean = no exclusion reason, no yielding tag, clear ahead or gap over CLEAN_AHEAD_GAP_S, no car
    within CLEAN_BEHIND_GAP_S behind, and a segment time. The pass itself is never its own donor.
    """
    table = table.copy()
    tag = table["tag"].fillna("").astype(str)
    clean = (
        table["reason"].isna()
        & ~tag.str.contains("yielding")
        & (table["clear_ahead"].astype(bool) | (table["gap_s"] > CLEAN_AHEAD_GAP_S))
        & ~table["behind_1s"].astype(bool)
        & table["seg_time_s"].notna()
    )
    table["clean"] = clean.to_numpy(dtype=bool)
    ref_n = np.zeros(len(table), dtype=int)
    ref_time = np.full(len(table), np.nan)
    pos = pd.Series(np.arange(len(table)), index=table.index)
    keys = ["driver", "corner_id", "stint", "compound"]
    for _, g in table.groupby(keys, dropna=True, sort=False):
        laps = g["lap"].to_numpy()
        donor = g["clean"].to_numpy()
        seg = g["seg_time_s"].to_numpy()
        for i, lap in enumerate(laps):
            m = donor & (np.abs(laps - lap) <= REF_HALF_WINDOW_LAPS) & (laps != lap)
            if m.any():
                j = pos[g.index[i]]
                ref_n[j] = int(m.sum())
                ref_time[j] = float(np.median(seg[m]))
    excluded = table["reason"].notna().to_numpy()
    ref_n[excluded] = 0
    ref_time[excluded] = np.nan
    table["ref_n"] = ref_n
    table["ref_time_s"] = np.where(ref_n >= REF_MIN_N, ref_time, np.nan)
    table["ref_status"] = np.where(excluded, "excluded", np.where(ref_n >= REF_MIN_N, "measured", "no_clean_reference"))
    table["delta_time_s"] = table["seg_time_s"] - table["ref_time_s"]
    return table


# --------------------------------------------------------------------------- layout flag (DD-WC6)


def _slug(name: str) -> str:
    return re.sub(r"[^\w]+", "_", str(name).strip().lower()).strip("_")


@functools.lru_cache(maxsize=4)
def race_calendar(bronze: Path = BRONZE) -> dict[tuple[int, str], tuple[str, pd.Timestamp]]:
    """(season, race slug) -> (circuit key, event date), from bronze schedule. The circuit key is the
    schedule Location with CIRCUIT_ALIASES merged; SEPARATE_LAYOUT_SLUGS get their own key."""
    out = {}
    for path in sorted((bronze / "schedule").glob("season=*/schedule.parquet")):
        sched = pq.read_table(path, columns=["EventName", "Location", "EventDate", "season"]).to_pandas()
        for name, loc, date, season in sched.itertuples(index=False, name=None):
            slug = _slug(name)
            key = SEPARATE_LAYOUT_SLUGS.get(slug, CIRCUIT_ALIASES.get(str(loc), str(loc)))
            out[(int(season), slug)] = (key, pd.Timestamp(date))
    return out


def layout_signature(season: int, race: str, corners: pd.DataFrame, circuit_season: int, lap_len: float,
                     bronze: Path = BRONZE) -> dict:
    """What the layout flag compares: the corner set used, its circuit_info season and the lap length."""
    circuit, date = race_calendar(bronze).get((season, race), (race, pd.Timestamp(f"{season}-01-01")))
    return {
        "season": int(season), "race": race, "circuit": circuit, "date": date,
        "corners": corners[["corner_id", "X", "Y"]].reset_index(drop=True),
        "circuit_info_season": int(circuit_season), "lap_len_m": float(lap_len),
    }


def layout_info(season: int, race: str, bronze: Path = BRONZE) -> dict | None:
    """The layout signature of a race not built in this run (None when it cannot be built)."""
    try:
        folder = bronze / "telemetry" / f"season={season}" / f"race={race}" / "telemetry.parquet"
        candidates = circuit_candidates(season, race, bronze)
        if not folder.exists() or not candidates:
            return None
        present = set(pq.read_schema(folder).names)
        tel = pq.read_table(folder, columns=[c for c in TELEMETRY_COLUMNS if c in present]).to_pandas()
        if tel.empty:
            return None
        _, corners, circuit_season, _, lap_len = race_geometry(tel, candidates)
        return layout_signature(season, race, corners, circuit_season, lap_len, bronze)
    except SkipRace:
        return None


def rigid_shift_m(a: pd.DataFrame, b: pd.DataFrame) -> tuple[float, float]:
    """Largest corner move between two corner sets (same corner_id), in metres: raw, and after the best
    rigid alignment (rotation + translation, Kabsch). NaN when fewer than 3 corners are shared."""
    common = a.merge(b, on="corner_id", suffixes=("_a", "_b"))
    if len(common) < 3:
        return np.nan, np.nan
    p = common[["X_a", "Y_a"]].to_numpy(dtype=float)
    q = common[["X_b", "Y_b"]].to_numpy(dtype=float)
    raw = float(np.hypot(*(p - q).T).max()) / 10.0
    p0, q0 = p - p.mean(0), q - q.mean(0)
    u, _, vt = np.linalg.svd(p0.T @ q0)
    d = np.sign(np.linalg.det(u @ vt))
    rot = u @ np.diag([1.0, d]) @ vt
    aligned = float(np.hypot(*(p0 @ rot - q0).T).max()) / 10.0
    return raw, aligned


def layout_flags(infos: list[dict]) -> tuple[dict[tuple[int, str], tuple[bool, str]], pd.DataFrame]:
    """(season, race) -> (layout_changed, layout_note), and one detail row per race.

    Each race is compared with the previous race at the same circuit (by event date). Flagged when (a) the
    corners came from another season's circuit_info (fallback), (b) the corner count differs, (c) a shared
    corner moved more than LAYOUT_CORNER_MOVE_M after a rigid alignment, or (d) the median telemetry lap
    length differs by more than LAYOUT_LAP_LENGTH_M from the median of the previous up-to
    LAYOUT_LAP_REF_RACES races since the last change. (b)-(d) start a new layout epoch; (a) does not.
    """
    flags: dict[tuple[int, str], tuple[bool, str]] = {}
    rows = []
    by_circuit: dict[str, list[dict]] = {}
    for info in infos:
        if info is not None:
            by_circuit.setdefault(info["circuit"], []).append(info)
    for circuit, races in by_circuit.items():
        races = sorted(races, key=lambda r: (r["date"], r["race"]))
        epoch: list[dict] = []
        changes: list[str] = []
        local: list[tuple[tuple[int, str], list[str], list[str]]] = []
        for r in races:
            key = (r["season"], r["race"])
            reasons, notes = [], []
            structural = False
            if r["circuit_info_season"] != r["season"]:
                reasons.append(f"corners taken from circuit_info season {r['circuit_info_season']} (fallback)")
            prev = epoch[-1] if epoch else None
            detail = {"season": r["season"], "race": r["race"], "circuit": circuit,
                      "date": r["date"].date().isoformat(), "circuit_info_season": r["circuit_info_season"],
                      "n_corners": len(r["corners"]), "lap_len_m": round(r["lap_len_m"], 1)}
            if prev is None:
                notes.append(f"first race at {circuit} in bronze; nothing to compare")
            else:
                n0, n1 = len(prev["corners"]), len(r["corners"])
                raw, aligned = rigid_shift_m(prev["corners"], r["corners"])
                refs = [p["lap_len_m"] for p in epoch[-LAYOUT_LAP_REF_RACES:] if np.isfinite(p["lap_len_m"])]
                ref = float(np.median(refs)) if refs else np.nan
                d_len = r["lap_len_m"] - ref
                detail.update(prev_season=prev["season"], prev_race=prev["race"], prev_n_corners=n0,
                              raw_shift_m=round(raw, 1), aligned_shift_m=round(aligned, 1),
                              ref_lap_len_m=round(ref, 1), ref_races=len(refs), lap_len_diff_m=round(d_len, 1))
                vs = f"{prev['season']} {prev['race']}"
                if n0 != n1:
                    reasons.append(f"corner count {n0} -> {n1} vs {vs}")
                    structural = True
                elif np.isfinite(aligned) and aligned > LAYOUT_CORNER_MOVE_M:
                    reasons.append(f"a corner moved {aligned:.0f} m (after rigid alignment) vs {vs}")
                    structural = True
                elif np.isfinite(raw) and raw > LAYOUT_CORNER_MOVE_M:
                    notes.append(f"corner coordinates shifted {raw:.0f} m as a whole frame vs {vs} "
                                 f"({aligned:.0f} m after rigid alignment): not a layout change")
                if np.isfinite(d_len) and abs(d_len) > LAYOUT_LAP_LENGTH_M:
                    reasons.append(f"telemetry lap length {r['lap_len_m']:.0f} m vs {ref:.0f} m "
                                   f"(median of previous {len(refs)}), {d_len:+.0f} m")
                    structural = True
                if not reasons and not notes:
                    notes.append(f"same layout as {vs}")
            if structural:
                changes.append(f"{r['season']} {r['race']}")
                epoch = [r]
            else:
                epoch.append(r)
            detail.update(layout_changed=bool(reasons), structural_change=structural,
                          layout_note="; ".join(reasons + notes))
            rows.append(detail)
            local.append((key, reasons, notes))
        for key, reasons, notes in local:
            if not reasons and changes:
                notes = notes + [f"circuit layout changes at {', '.join(changes)} (marshal-sector count pooled per slug)"]
            flags[key] = (bool(reasons), "; ".join(reasons + notes))
    detail_rows = pd.DataFrame(rows)
    if not detail_rows.empty:
        detail_rows["layout_note"] = [flags[(s, r)][1] for s, r in zip(detail_rows["season"], detail_rows["race"])]
        detail_rows = detail_rows.sort_values(["circuit", "date", "race"]).reset_index(drop=True)
    return flags, detail_rows


def apply_layout_flags(frame: pd.DataFrame, flags: dict[tuple[int, str], tuple[bool, str]]) -> pd.DataFrame:
    """Add layout_changed / layout_note to one race's pass rows (a flag only; reason is untouched)."""
    season, race = int(frame["season"].iloc[0]), str(frame["race"].iloc[0])
    changed, note = flags.get((season, race), (False, "layout not checked"))
    frame = frame.copy()
    frame["layout_changed"] = bool(changed)
    frame["layout_note"] = note
    return frame[PASS_COLUMNS]


# --------------------------------------------------------------------------- all races


def race_slugs(season: int, bronze: Path = BRONZE) -> list[str]:
    return sorted(p.name.removeprefix("race=") for p in (bronze / "laps" / f"season={season}").glob("race=*"))


def _run_one(season: int, race: str) -> tuple[int, str, pd.DataFrame | None, str, float, dict | None]:
    t0 = time.perf_counter()
    info: dict = {}
    try:
        frame = build_race(season, race, info=info)
        return season, race, frame, "ok", time.perf_counter() - t0, info
    except SkipRace as exc:
        return season, race, None, f"skipped: {exc}", time.perf_counter() - t0, None
    except Exception as exc:  # noqa: BLE001 - a failed race is logged, the run carries on
        return season, race, None, f"failed: {type(exc).__name__}: {exc}", time.perf_counter() - t0, None


def _layout_inputs(built: dict[tuple[int, str], dict | None], bronze: Path = BRONZE) -> list[dict]:
    """Signatures of the built races plus every earlier race at the same circuits that this run did not
    attempt (a --seasons or --race subset), so each race is still compared with its true predecessor."""
    calendar = race_calendar(bronze)
    circuits = {calendar.get(k, (k[1], None))[0] for k in built}
    latest = max((calendar[k][1] for k in built if k in calendar), default=None)
    infos = [i for i in built.values() if i]
    for key, (circuit, date) in sorted(calendar.items()):
        if key in built or circuit not in circuits or latest is None or date > latest:
            continue
        if not (bronze / "laps" / f"season={key[0]}" / f"race={key[1]}").exists():
            continue
        infos.append(layout_info(*key, bronze))
    return infos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="scratch folder for the pass table (not data/)")
    parser.add_argument("--seasons", type=int, nargs="*", default=list(range(2018, 2026)))
    parser.add_argument("--race", help="build one race slug only, for checking")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    if args.out.resolve().is_relative_to(BRONZE.parent.resolve()):
        parser.error("--out must not be inside data/")
    args.out.mkdir(parents=True, exist_ok=True)

    jobs = [(s, r) for s in args.seasons for r in ([args.race] if args.race else race_slugs(s))]
    started = time.perf_counter()
    frames: dict[int, list[pd.DataFrame]] = {s: [] for s in args.seasons}
    log = []
    built: dict[tuple[int, str], dict | None] = {}
    with ProcessPoolExecutor(max_workers=max(args.workers, 1)) as pool:
        futures = [pool.submit(_run_one, s, r) for s, r in jobs]
        for fut in as_completed(futures):
            season, race, frame, status, secs, info = fut.result()
            n = 0 if frame is None else len(frame)
            print(f"{season} {race}: {status}, {n} passes, {secs:.1f}s", flush=True)
            log.append({"season": season, "race": race, "status": status, "passes": n, "seconds": round(secs, 1)})
            built[(season, race)] = info
            if frame is not None:
                frames[season].append(frame)
    # Layout flag across races (DD-WC6): needs every race's signature, so it runs after the builds.
    flags, layout_detail = layout_flags(_layout_inputs(built))
    frames = {s: [apply_layout_flags(f, flags) for f in parts] for s, parts in frames.items()}
    for row in log:
        changed, note = flags.get((row["season"], row["race"]), (None, ""))
        row["layout_changed"] = changed
        row["layout_note"] = note
    layout_detail.to_csv(args.out / "layout_checks.csv", index=False)
    for season, parts in frames.items():
        if parts:
            out = pd.concat(parts, ignore_index=True).sort_values(["race", "driver", "lap", "corner_number", "corner_id"])
            out.to_parquet(args.out / f"pass_table_{season}.parquet", index=False)
    pd.DataFrame(log).sort_values(["season", "race"]).to_csv(args.out / "races.csv", index=False)
    print(f"total {time.perf_counter() - started:.1f}s over {len(jobs)} races", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
