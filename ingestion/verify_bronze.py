#!/usr/bin/env python3
"""
Verification of the Bronze layer: what is on disk against what should be.

Expectations are derived, not hand-typed. The races a season should have are
the rounds on that season's bronze schedule snapshot (schedule/season=YYYY/,
written by ingest.py from FastF1's event schedule) whose race has finished
(bronze_checks.session_is_ready), so a new season is checked as soon as it is
ingested and a part-finished season is not expected to hold future rounds.
Known source-level gaps (bronze_checks.KNOWN_TELEMETRY_GAPS / KNOWN_THIN, e.g.
2018 rounds 1-2 with no telemetry at source, ADR-009) are reported as KNOWN and
do not fail the run; any other gap does.

Sections:
  1. Presence       every finished round has race + qualifying laps, weather,
                    race_control and (race) telemetry files.
  2. Laps DQ        required columns and duplicate lap keys, every laps file.
  3. Completeness   the same thin-load rules ingest.py applies before writing
                    (key-column shares, results vs the field, weather and race
                    control non-empty), per race and qualifying session.
  4. Telemetry      share of each race's laps with merged per-lap telemetry.
  5. Row counts     rows per race per dataset (informational).

Usage:
    python ingestion/verify_bronze.py                  # every season on disk
    python ingestion/verify_bronze.py --season 2026    # one season
    python ingestion/verify_bronze.py --bronze-dir PATH
    python ingestion/verify_bronze.py --markdown       # docs coverage table

Exit 0 = nothing new (known gaps allowed); 1 = a new problem needs attention.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent / "src"))
import bronze_checks  # noqa: E402
from data_quality import DataQualityEngine  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"

# Per-race datasets checked for presence (telemetry: races only).
EXPECTED_DATASETS = ["laps", "weather", "race_control", "telemetry"]

# The --markdown coverage table feeds the committed docs snippet
# (docs/snippets/bronze-coverage.mdx, drift-gated by scripts/ingestion_docs_facts.py).
# It has always covered 2018-2024; adding newer seasons to it changes published
# docs, so that stays a deliberate choice: widen this, then `make docs-coverage`.
MARKDOWN_SEASONS = range(2018, 2025)

@dataclass
class Finding:
    level: str      # "new" (fails the run) | "known" | "info"
    section: str
    season: int
    message: str


# ---------------------------------------------------------------------------
# Disk layout helpers
# ---------------------------------------------------------------------------

def seasons_on_disk(bronze: Path) -> list[int]:
    out = []
    for d in (bronze / "laps").glob("season=*"):
        try:
            out.append(int(d.name.split("=", 1)[1]))
        except (IndexError, ValueError):
            continue
    return sorted(out)


def race_slugs_on_disk(bronze: Path, season: int) -> list[str]:
    season_dir = bronze / "laps" / f"season={season}"
    if not season_dir.exists():
        return []
    return sorted(d.name.split("=", 1)[1] for d in season_dir.glob("race=*") if d.is_dir())


def race_laps_path(bronze: Path, season: int, slug: str) -> Path:
    return bronze / "laps" / f"season={season}" / f"race={slug}" / f"{season}_{slug}_laps.parquet"


def quali_laps_path(bronze: Path, season: int, slug: str) -> Path:
    return (bronze / "laps" / f"season={season}" / f"race={slug}" / "session=Q"
            / f"{season}_{slug}_quali_laps.parquet")


def dataset_file(bronze: Path, dataset: str, season: int, slug: str, quali: bool = False) -> Optional[Path]:
    """The single parquet of a per-race dataset, or None if absent."""
    if dataset == "laps":
        p = quali_laps_path(bronze, season, slug) if quali else race_laps_path(bronze, season, slug)
        return p if p.exists() else None
    d = bronze / dataset / f"season={season}" / f"race={slug}"
    if quali:
        d = d / "session=Q"
    files = sorted(d.glob("*.parquet")) if d.exists() else []
    return files[0] if files else None


def expected_rounds(bronze: Path, season: int, now_utc: datetime) -> Optional[dict]:
    """{slug: {"round", "race_ready", "quali_ready"}} for the season's schedule snapshot,
    only rounds whose race has finished. None when there is no snapshot."""
    path = bronze / "schedule" / f"season={season}" / "schedule.parquet"
    if not path.exists():
        return None
    sched = pd.read_parquet(path)
    out = {}
    for _, row in sched.iterrows():
        rn = row.get("RoundNumber")
        if rn is None or pd.isna(rn) or int(rn) == 0:
            continue
        race_ready = bronze_checks.session_is_ready(
            bronze_checks.session_start_utc(row, "R"), now_utc)
        quali_ready = bronze_checks.session_is_ready(
            bronze_checks.session_start_utc(row, "Q"), now_utc)
        if race_ready is False:
            continue
        out[bronze_checks.event_slug(str(row["EventName"]))] = {
            "round": int(rn), "race_ready": race_ready, "quali_ready": quali_ready,
        }
    return out


def _round_from_laps(path: Path) -> Optional[int]:
    try:
        rid = pq.ParquetFile(path).read(columns=["race_id"]).column("race_id")[0].as_py()
        return int(str(rid).split("_")[1])
    except Exception:
        return None


def _rows(path: Optional[Path]) -> int:
    if path is None:
        return 0
    try:
        return pq.ParquetFile(path).metadata.num_rows
    except Exception:
        return 0


def _read(path: Optional[Path], columns: list[str]) -> Optional[pd.DataFrame]:
    if path is None:
        return None
    available = set(pq.ParquetFile(path).schema_arrow.names)
    return pd.read_parquet(path, columns=[c for c in columns if c in available])


def _n_rows_frame(n: int) -> pd.DataFrame:
    return pd.DataFrame(index=range(n))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def verify_season(bronze: Path, season: int, now_utc: Optional[datetime] = None) -> list[Finding]:
    now_utc = now_utc or datetime.now(timezone.utc)
    findings: list[Finding] = []

    def add(level, section, message):
        findings.append(Finding(level, section, season, message))

    on_disk = race_slugs_on_disk(bronze, season)
    expected = expected_rounds(bronze, season, now_utc)

    # -- 1. Presence ----------------------------------------------------------
    if expected is None:
        add("info", "presence", f"no schedule snapshot (schedule/season={season}/): "
                                f"expected races unknown, checking the {len(on_disk)} on disk")
        rounds = {s: {"round": _round_from_laps(race_laps_path(bronze, season, s)),
                      "race_ready": True, "quali_ready": True} for s in on_disk}
    else:
        rounds = expected
        missing = sorted(set(expected) - set(on_disk), key=lambda s: expected[s]["round"])
        for slug in missing:
            add("new", "presence", f"Rd{expected[slug]['round']} {slug}: finished on the "
                                   f"schedule but has no laps in bronze")
        for slug in sorted(set(on_disk) - set(expected)):
            add("info", "presence", f"{slug}: on disk but not a finished round on the "
                                    f"schedule snapshot")

    for slug, meta in sorted(rounds.items(), key=lambda kv: kv[1]["round"] or 0):
        if slug not in on_disk:
            continue
        rnd = meta["round"]
        tag = f"Rd{rnd} {slug}"
        for dataset in EXPECTED_DATASETS:
            if dataset_file(bronze, dataset, season, slug) is not None:
                continue
            known = bronze_checks.known_telemetry_gap(season, rnd) if dataset == "telemetry" else None
            if known:
                add("known", "presence", f"{tag}: no telemetry, known gap: {known}")
            else:
                add("new", "presence", f"{tag}: missing {dataset}")
        if meta.get("quali_ready") is not False and dataset_file(bronze, "laps", season, slug, quali=True) is None:
            add("new", "presence", f"{tag}: missing qualifying laps")

    # -- 2. Laps DQ + 3. Completeness ------------------------------------------
    for slug, meta in sorted(rounds.items(), key=lambda kv: kv[1]["round"] or 0):
        if slug not in on_disk:
            continue
        rnd = meta["round"]
        for stype in ("R", "Q"):
            quali = stype == "Q"
            laps_path = dataset_file(bronze, "laps", season, slug, quali=quali)
            if laps_path is None:
                continue
            tag = f"Rd{rnd} {stype} {slug}"
            try:
                laps = pd.read_parquet(laps_path)
            except Exception as exc:
                add("new", "dq", f"{tag}: unreadable laps file: {type(exc).__name__}: {exc}")
                continue
            try:
                DataQualityEngine.validate_bronze_schema(laps)
            except ValueError as exc:
                add("new", "dq", f"{tag}: {exc}")
            dupes = DataQualityEngine.check_lap_key_duplicates(laps)
            if dupes:
                add("new", "dq", f"{tag}: {dupes} duplicate lap-key rows")
            if len(laps) < 50:
                add("info", "dq", f"{tag}: only {len(laps)} laps (red-flagged or short session?)")

            results = _read(dataset_file(bronze, "results", season, slug, quali=quali),
                            ["Points", "GridPosition", "Q1", "DriverNumber"])
            weather = _n_rows_frame(_rows(dataset_file(bronze, "weather", season, slug, quali=quali)))
            rc = (_n_rows_frame(_rows(dataset_file(bronze, "race_control", season, slug)))
                  if stype == "R" else None)
            problems = bronze_checks.assess_session(stype, laps, results, weather, rc)
            if rnd is None:
                unexplained, known = problems, None
            else:
                unexplained, known = bronze_checks.split_known_thin(season, rnd, stype, problems)
            if known:
                add("known", "completeness", f"{tag}: {known}")
            if unexplained:
                add("new", "completeness", f"{tag}: thin: {'; '.join(unexplained.values())}")

    # -- 4. Telemetry coverage -----------------------------------------------
    for slug, meta in sorted(rounds.items(), key=lambda kv: kv[1]["round"] or 0):
        tel_path = dataset_file(bronze, "telemetry", season, slug)
        laps_path = dataset_file(bronze, "laps", season, slug)
        if slug not in on_disk or tel_path is None or laps_path is None:
            continue
        rnd = meta["round"]
        n_laps = _rows(laps_path)
        try:
            tel = pd.read_parquet(tel_path, columns=["driver_id", "lap_number"])
            merged = len(tel.drop_duplicates())
        except Exception as exc:
            add("new", "telemetry", f"Rd{rnd} {slug}: unreadable telemetry: {type(exc).__name__}: {exc}")
            continue
        share = merged / n_laps if n_laps else 0.0
        if share >= bronze_checks.TELEMETRY_LOW_COVERAGE:
            continue
        known = bronze_checks.known_telemetry_gap(season, rnd) if rnd is not None else None
        msg = (f"Rd{rnd} {slug}: telemetry on {merged}/{n_laps} laps ({share:.1%}, "
               f"threshold {bronze_checks.TELEMETRY_LOW_COVERAGE:.0%})")
        add("known" if known else "new", "telemetry", msg + (f"; known gap: {known}" if known else ""))

    return findings


def row_count_table(bronze: Path, season: int) -> dict[str, list[int]]:
    counts: dict[str, list[int]] = defaultdict(list)
    for slug in race_slugs_on_disk(bronze, season):
        for dataset in EXPECTED_DATASETS:
            path = dataset_file(bronze, dataset, season, slug)
            if path is not None:
                counts[dataset].append(_rows(path))
    return counts


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

SECTIONS = [
    ("presence", "1. PRESENCE (finished rounds on the schedule snapshot vs files on disk)"),
    ("dq", "2. LAPS DATA QUALITY (required columns, duplicate lap keys)"),
    ("completeness", "3. COMPLETENESS (the thin-load rules ingest.py applies)"),
    ("telemetry", "4. TELEMETRY COVERAGE (laps with merged per-lap telemetry)"),
]
ICON = {"new": "✗ NEW  ", "known": "· KNOWN", "info": "  info "}


def report(bronze: Path, seasons: list[int], now_utc: Optional[datetime] = None) -> int:
    all_findings: list[Finding] = []
    print(f"\nBRONZE LAYER VERIFICATION   {bronze}")
    print(f"Seasons: {', '.join(str(s) for s in seasons) or 'none on disk'}")
    for season in seasons:
        all_findings.extend(verify_season(bronze, season, now_utc))

    for key, title in SECTIONS:
        print("\n" + "=" * 80 + f"\n{title}\n" + "=" * 80)
        rows = [f for f in all_findings if f.section == key]
        for season in seasons:
            season_rows = [f for f in rows if f.season == season]
            n_new = sum(f.level == "new" for f in season_rows)
            n_known = sum(f.level == "known" for f in season_rows)
            status = "✅" if n_new == 0 else "⚠️"
            extra = f", {n_known} known" if n_known else ""
            print(f"{status} {season}: {n_new} new{extra}")
            for f in season_rows:
                print(f"   {ICON[f.level]} {f.message}")

    print("\n" + "=" * 80 + "\n5. ROW COUNTS (rows per race)\n" + "=" * 80)
    for season in seasons:
        table = row_count_table(bronze, season)
        print(f"\n{season}:")
        for dataset in EXPECTED_DATASETS:
            counts = table.get(dataset, [])
            if counts:
                s = sorted(counts)
                print(f"  {dataset:15} {len(s):3} races | median {s[len(s) // 2]:10,} rows/race "
                      f"[{s[0]:10,}–{s[-1]:10,}]")
            else:
                print(f"  {dataset:15} no files found")

    new = [f for f in all_findings if f.level == "new"]
    known = [f for f in all_findings if f.level == "known"]
    print("\n" + "=" * 80 + "\nSUMMARY\n" + "=" * 80)
    if new:
        print(f"⚠️  {len(new)} new problem(s) need attention (marked ✗ NEW above); "
              f"{len(known)} known gap(s) reported as KNOWN.")
        return 1
    print(f"✅ No new problems. {len(known)} known gap(s) reported as KNOWN.")
    return 0


def emit_coverage_markdown(bronze: Path = BRONZE_DIR) -> None:
    """
    Emit the Bronze coverage table as markdown from what is actually on disk.

    Self-updating docs: `make docs-coverage` writes this into
    docs/snippets/bronze-coverage.mdx. Seasons: MARKDOWN_SEASONS (see above).
    """
    print("| Season | Laps | Weather | Race Control | Telemetry |")
    print("|--------|------|---------|--------------|-----------|")
    for season in sorted(s for s in seasons_on_disk(bronze) if s in MARKDOWN_SEASONS):
        season_dir = bronze / "laps" / f"season={season}"
        race_dirs = [d for d in season_dir.iterdir() if d.is_dir()]
        cells = []
        for dataset in EXPECTED_DATASETS:
            n = sum(
                1 for rd in race_dirs
                if (bronze / dataset / f"season={season}" / rd.name).exists()
            )
            cells.append(f"{n} ✓")
        print(f"| {season} | " + " | ".join(cells) + " |")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Bronze layer integrity")
    parser.add_argument("--markdown", action="store_true",
                        help="Emit the coverage table as markdown (for docs) and exit")
    parser.add_argument("--season", type=int, action="append",
                        help="Only this season (repeatable). Default: every season on disk")
    parser.add_argument("--bronze-dir", type=Path, default=BRONZE_DIR,
                        help="Bronze root to verify (default: data/bronze)")
    args = parser.parse_args(argv)

    if args.markdown:
        emit_coverage_markdown(args.bronze_dir)
        return 0

    seasons = seasons_on_disk(args.bronze_dir)
    if args.season:
        missing = [s for s in args.season if s not in seasons]
        if missing:
            print(f"Season(s) {missing} have no laps in {args.bronze_dir}", file=sys.stderr)
            return 1
        seasons = sorted(args.season)
    return report(args.bronze_dir, seasons)


if __name__ == "__main__":
    sys.exit(main())
