"""Regenerate the Degradation Simulator's P3 basket fixtures from mart_degradation_history_envelope.

Writes two files to app/src/features/degradation-simulator/__fixtures__/, from ONE read of the
envelope, so they always describe the same warehouse:

  accuracy_basket.json  The P3 truth. For each basket cell, obs_deg_from_fresh_p{10,50,90}_s and
                        n_observations at laps 5/10/15/20/25/30, plus the cell's ref_green_pace_s.
  fitted_basket.json    Every envelope row of each basket cell, in the shape the app's
                        queryHistoryEnvelope (queries.ts) returns: the same columns and the same
                        COALESCE defaults on the modulation coefficients. This is what
                        recomposeLapTimes consumes.

Consumers (re-run them after regenerating):
  app/.../accuracy.test.ts    both: the shipped isotonic term vs the truth (P3.1-P3.4)
  app/.../powerLaw.test.ts    both: WI-17 criterion 1 fits fitted_basket rows; 4b grades against
                              accuracy_basket
  app/.../transform.test.ts   accuracy_basket
  ml/src/powerlaw.py          accuracy_basket, for the basket's cell list only

Regenerate after any rebuild of mart_degradation_history_envelope or of
data/fits/degradation_isotonic.parquet (W54: the June fixtures silently outlived a rebuild, and the
tests kept passing because both files were the same stale snapshot). `--check` makes that drift
visible without writing anything.

The basket is fixed here, not read back from the fixture: five well-populated cells. A basket cell
must exist under its own compound; the app's compound='_all' fallback is deliberately NOT applied,
because a silent fallback would change what the truth means.

Usage (from the repo root):
    ./.venv/bin/python scripts/generate_fitted_fixture.py            # write both fixtures
    ./.venv/bin/python scripts/generate_fitted_fixture.py --check    # exit 1 if they are stale
    ./.venv/bin/python scripts/generate_fitted_fixture.py --duckdb data/dev.duckdb
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DUCKDB = REPO_ROOT / "data" / "dev.duckdb"
FIXTURES = REPO_ROOT / "app" / "src" / "features" / "degradation-simulator" / "__fixtures__"
ACCURACY_PATH = FIXTURES / "accuracy_basket.json"
FITTED_PATH = FIXTURES / "fitted_basket.json"

MART = "mart_degradation_history_envelope"

# (circuit_id, era, compound), in fixture order. Changing this list changes the P3 gates and the
# WI-17 criterion 4b basket (ml/src/powerlaw.py reads the cell list from accuracy_basket.json).
BASKET: tuple[tuple[str, str, str], ...] = (
    ("red_bull_ring", "post2022", "HARD"),
    ("autodromo_nazionale_monza", "post2022", "HARD"),
    ("red_bull_ring", "post2022", "MEDIUM"),
    ("yas_marina_circuit", "post2022", "HARD"),
    ("istanbul_park", "pre2022", "INTERMEDIATE"),
)
SAMPLE_LAPS: tuple[int, ...] = (5, 10, 15, 20, 25, 30)
TRUTH_DECIMALS = 4

# fitted_basket.json row keys, in file order (the June fixture's order).
FITTED_COLUMNS: tuple[str, ...] = (
    "lap_in_stint",
    "obs_deg_from_fresh_p10_mono_s",
    "obs_deg_from_fresh_p50_mono_s",
    "obs_deg_from_fresh_p90_mono_s",
    "dirty_air_deg_mult",
    "temp_headroom_c",
    "temp_penalty_s_per_deg",
    "ref_green_pace_s",
    "n_observations",
    "obs_fuel_removed_pace_p10_s",
    "obs_fuel_removed_pace_p50_s",
    "obs_fuel_removed_pace_p90_s",
    "obs_deg_from_fresh_p10_s",
    "obs_deg_from_fresh_p50_s",
    "obs_deg_from_fresh_p90_s",
)
INT_COLUMNS = frozenset({"lap_in_stint", "n_observations"})

# queries.ts queryHistoryEnvelope, minus the '_all' fallback. Keep the COALESCE defaults in step
# with it: the fixture must be what the app would receive.
CELL_QUERY = f"""
    SELECT
        lap_in_stint, n_observations, ref_green_pace_s,
        obs_fuel_removed_pace_p10_s, obs_fuel_removed_pace_p50_s, obs_fuel_removed_pace_p90_s,
        obs_deg_from_fresh_p10_s, obs_deg_from_fresh_p50_s, obs_deg_from_fresh_p90_s,
        obs_deg_from_fresh_p10_mono_s, obs_deg_from_fresh_p50_mono_s, obs_deg_from_fresh_p90_mono_s,
        COALESCE(dirty_air_deg_mult, 1.0)      AS dirty_air_deg_mult,
        COALESCE(temp_headroom_c, 8.0)         AS temp_headroom_c,
        COALESCE(temp_penalty_s_per_deg, 0.01) AS temp_penalty_s_per_deg
    FROM {MART}
    WHERE circuit_id = ? AND era = ? AND compound = ?
    ORDER BY lap_in_stint
"""

ACCURACY_DOC = (
    "Ground-truth accuracy basket for the Degradation Simulator (P3). Five well-populated "
    "circuit x era x compound cells. Each cell records obs_deg_from_fresh_p{10,50,90}_s and "
    "n_observations at laps {5,10,15,20,25,30}, read from mart_degradation_history_envelope "
    "together with fitted_basket.json. The p50 values are the regression sentinels: the shipped "
    "monotone curve must reproduce them within MAE <= 0.5 s at neutral inputs. Generated by "
    "scripts/generate_fitted_fixture.py; regenerate after any envelope or isotonic-fit rebuild "
    "(--check reports drift)."
)
FITTED_DOC = (
    "Every mart_degradation_history_envelope row of each P3 basket cell, in the shape the app's "
    "queryHistoryEnvelope returns (queries.ts): the input to recomposeLapTimes in accuracy.test.ts, "
    "and the observed curve WI-17 criterion 1 fits in powerLaw.test.ts. Generated by "
    "scripts/generate_fitted_fixture.py together with accuracy_basket.json; regenerate after any "
    "envelope or isotonic-fit rebuild (--check reports drift)."
)


def _num(col: str, v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return int(v) if col in INT_COLUMNS else float(v)


def read_cells(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """One query per basket cell; every row, in FITTED_COLUMNS order. Fails on a missing cell or
    a missing sample lap rather than writing a basket that means something else."""
    cells = []
    for circuit_id, era, compound in BASKET:
        res = con.execute(CELL_QUERY, [circuit_id, era, compound])
        names = [d[0] for d in res.description]
        raw = [dict(zip(names, r)) for r in res.fetchall()]
        label = f"{circuit_id}/{compound}/{era}"
        if not raw:
            raise SystemExit(f"basket cell {label} has no rows in {MART}")
        laps = {r["lap_in_stint"] for r in raw}
        missing = [lap for lap in SAMPLE_LAPS if lap not in laps]
        if missing:
            raise SystemExit(f"basket cell {label} has no envelope row at sample lap(s) {missing}")
        rows = [{c: _num(c, r[c]) for c in FITTED_COLUMNS} for r in raw]
        cells.append({"circuit_id": circuit_id, "era": era, "compound": compound, "rows": rows})
    return cells


def accuracy_cells(cells: list[dict]) -> list[dict]:
    """The truth, sliced from the same rows fitted_basket.json carries."""
    out = []
    for c in cells:
        by_lap = {r["lap_in_stint"]: r for r in c["rows"]}
        samples = []
        for lap in SAMPLE_LAPS:
            r = by_lap[lap]
            samples.append({
                "lap_in_stint": lap,
                "n_observations": r["n_observations"],
                **{f"obs_deg_from_fresh_p{q}_s": round(r[f"obs_deg_from_fresh_p{q}_s"], TRUTH_DECIMALS)
                   for q in (10, 50, 90)},
            })
        out.append({"circuit_id": c["circuit_id"], "era": c["era"], "compound": c["compound"],
                    "ref_green_pace_s": round(c["rows"][0]["ref_green_pace_s"], TRUTH_DECIMALS),
                    "samples": samples})
    return out


def _accuracy_text(doc: dict) -> str:
    """indent-2 JSON with one sample per line, like the hand-kept June file."""
    head = {k: v for k, v in doc.items() if k != "basket"}
    lines = ["{"]
    lines += [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in head.items()]
    lines.append('  "basket": [')
    for i, c in enumerate(doc["basket"]):
        lines.append("    {")
        for k in ("circuit_id", "era", "compound", "ref_green_pace_s"):
            lines.append(f"      {json.dumps(k)}: {json.dumps(c[k])},")
        lines.append('      "samples": [')
        for j, s in enumerate(c["samples"]):
            body = ", ".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in s.items())
            lines.append(f"        {{ {body} }}{',' if j < len(c['samples']) - 1 else ''}")
        lines.append("      ]")
        lines.append(f"    }}{',' if i < len(doc['basket']) - 1 else ''}")
    lines += ["  ]", "}"]
    return "\n".join(lines) + "\n"


def build(duckdb_path: Path) -> tuple[dict, dict]:
    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        cells = read_cells(con)
    finally:
        con.close()
    try:
        source = str(duckdb_path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        source = str(duckdb_path)
    meta = {"generated": date.today().isoformat(), "source": source}
    accuracy = {"_doc": ACCURACY_DOC, **meta, "basket": accuracy_cells(cells)}
    fitted = {"_doc": FITTED_DOC, "generated_from": MART, **meta, "cells": cells}
    return accuracy, fitted


# ─── --check ────────────────────────────────────────────────────────────────────────────────
def _drift(label: str, old_cells: list[dict], new_cells: list[dict], rows_key: str) -> list[str]:
    """Human-readable differences between two cell lists (data only; _doc/dates are ignored)."""
    key = lambda c: (c["circuit_id"], c["era"], c["compound"])  # noqa: E731
    old = {key(c): c for c in old_cells}
    out = []
    for c in new_cells:
        k = key(c)
        name = "/".join((k[0], k[2], k[1]))
        if k not in old:
            out.append(f"{label}: {name} missing from the fixture")
            continue
        o = old[k]
        if json.loads(json.dumps(c)) == o:
            continue
        o_rows = {r["lap_in_stint"]: r for r in o[rows_key]}
        n_rows = {r["lap_in_stint"]: r for r in c[rows_key]}
        if set(o_rows) != set(n_rows):
            out.append(f"{label}: {name} laps {min(o_rows)}-{max(o_rows)} ({len(o_rows)} rows) -> "
                       f"{min(n_rows)}-{max(n_rows)} ({len(n_rows)} rows)")
        shared = sorted(set(o_rows) & set(n_rows))
        worst = max(((abs((n_rows[lap]["obs_deg_from_fresh_p50_s"] or 0) -
                          (o_rows[lap]["obs_deg_from_fresh_p50_s"] or 0)), lap) for lap in shared),
                    default=(0.0, None))
        out.append(f"{label}: {name} differs (largest p50 move {worst[0]:.3f} s at lap {worst[1]})")
    for k in old.keys() - {key(c) for c in new_cells}:
        out.append(f"{label}: {'/'.join((k[0], k[2], k[1]))} is in the fixture but not the basket")
    return out


def check(accuracy: dict, fitted: dict) -> int:
    problems = []
    for path, new, cells_key, rows_key in ((ACCURACY_PATH, accuracy, "basket", "samples"),
                                           (FITTED_PATH, fitted, "cells", "rows")):
        if not path.exists():
            problems.append(f"{path.name}: missing")
            continue
        old = json.loads(path.read_text())
        problems += _drift(path.name, old.get(cells_key, []), new[cells_key], rows_key)
    if problems:
        print("P3 basket fixtures are STALE against the warehouse:")
        for p in problems:
            print(f"  - {p}")
        print("Regenerate: ./.venv/bin/python scripts/generate_fitted_fixture.py")
        return 1
    print(f"P3 basket fixtures match {MART} ({len(fitted['cells'])} cells).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duckdb", type=Path, default=DEFAULT_DUCKDB, help="warehouse (default %(default)s)")
    ap.add_argument("--check", action="store_true", help="compare only; exit 1 if the fixtures are stale")
    args = ap.parse_args(argv)

    accuracy, fitted = build(args.duckdb)
    if args.check:
        return check(accuracy, fitted)

    ACCURACY_PATH.write_text(_accuracy_text(accuracy))
    FITTED_PATH.write_text(json.dumps(fitted, indent=2) + "\n")
    for c in fitted["cells"]:
        laps = [r["lap_in_stint"] for r in c["rows"]]
        print(f"  {c['circuit_id']}/{c['compound']}/{c['era']}: {len(laps)} rows, laps {min(laps)}-{max(laps)}")
    print(f"wrote {ACCURACY_PATH.relative_to(REPO_ROOT)} and {FITTED_PATH.relative_to(REPO_ROOT)} "
          f"from {accuracy['source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
