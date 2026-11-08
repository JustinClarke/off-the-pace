"""AX-02: the `assistant_entities` table behind the assistant's list_values tool.

One row per (domain, code): drivers, constructor lineages, races, circuits,
seasons, compounds, caution statuses and stint end causes. Columns:
domain, code, display, aliases (JSON list), seasons (JSON list),
parent_code, extra (JSON object).

This is the one export that is NOT built from other published files: the
display names live in bronze reference data (Jolpica driver standings, FastF1
results, the FastF1 schedule), so it reads those parquet globs directly next to
the warehouse tables. The result is reference data and is itself published.

HD7 (ruled 2026-11-07): driver names come from the Jolpica reference when it
covers every dim_drivers code, with FastF1 results filling any gap. The export
fails, naming the codes, if a driver has no name from either source. Display
is "Given Family (CODE)" pending the owner's confirmation.

Hand-made aliases (nicknames, constructor renames, circuit nicknames) live in
app/src/assistant/entities/aliases.json and are merged into `aliases`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRONZE = ROOT / "data" / "bronze"
ALIASES_JSON = ROOT / "app" / "src" / "assistant" / "entities" / "aliases.json"

# Mirrors the CASE in export_app_data.DERIVED_TABLES["race_caution_timeline"].
CAUTION_STATUSES = [
    ("green", "Green flag running", []),
    ("safety_car", "Safety car", ["sc", "safety car"]),
    ("vsc", "Virtual safety car", ["virtual safety car"]),
    ("red_flag", "Red flag", ["red flag", "red"]),
]



class EntityBuildError(RuntimeError):
    pass


def _load_aliases(path: Path = ALIASES_JSON) -> dict[str, dict[str, list[str]]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = v.strip().lower()
        if v and key not in seen:
            seen.add(key)
            out.append(v.strip())
    return out


def build_rows(conn, bronze: Path = BRONZE, aliases: dict | None = None) -> tuple[list[dict], dict]:
    """Return (rows, report). report carries the name-coverage numbers."""
    aliases = _load_aliases() if aliases is None else aliases
    jol = (bronze / "reference" / "jolpica" / "driver_standings").as_posix() + "/**/*.parquet"
    res = (bronze / "results").as_posix() + "/**/*.parquet"
    sched = (bronze / "schedule").as_posix() + "/**/*.parquet"
    rows: list[dict] = []

    # ── drivers ──────────────────────────────────────────────────────────────
    codes = [r[0] for r in conn.execute("SELECT driver_id FROM dim_drivers ORDER BY driver_id").fetchall()]
    jol_names = {
        r[0]: (r[1], r[2])
        for r in conn.execute(f"""
            SELECT driver_code, arg_max(given_name, season * 100 + round),
                   arg_max(family_name, season * 100 + round)
            FROM read_parquet('{jol}', hive_partitioning = false)
            WHERE driver_code IS NOT NULL GROUP BY 1""").fetchall()
    }
    f1_names = {
        r[0]: (r[1], r[2])
        for r in conn.execute(f"""
            SELECT Abbreviation, arg_max(FirstName, race_id), arg_max(LastName, race_id)
            FROM read_parquet('{res}', hive_partitioning = false)
            WHERE Abbreviation IS NOT NULL GROUP BY 1""").fetchall()
    }
    seasons_by_driver = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT driver_id, list(DISTINCT race_year ORDER BY race_year) FROM fct_lap_residuals GROUP BY 1"
        ).fetchall()
    }
    numbers = dict(conn.execute("SELECT driver_id, driver_number FROM dim_drivers").fetchall())
    from_jol = from_f1 = 0
    missing: list[str] = []
    for code in codes:
        if code in jol_names and all(jol_names[code]):
            (given, family), source = jol_names[code], "jolpica"
            from_jol += 1
        elif code in f1_names and all(f1_names[code]):
            (given, family), source = f1_names[code], "fastf1_results"
            from_f1 += 1
        else:
            missing.append(code)
            continue
        full = f"{given} {family}"
        rows.append({
            "domain": "driver", "code": code, "display": f"{full} ({code})",
            "aliases": _dedupe([full, family, given, code, *aliases.get("driver", {}).get(code, [])]),
            "seasons": [int(s) for s in seasons_by_driver.get(code, [])],
            "parent_code": None,
            "extra": {"given_name": given, "family_name": family,
                      "driver_number": numbers.get(code), "name_source": source},
        })
    if missing:
        raise EntityBuildError(
            f"assistant_entities: no driver name from Jolpica or FastF1 results for {len(missing)} "
            f"dim_drivers code(s): {', '.join(missing)}"
        )

    # ── constructors (one row per lineage) ───────────────────────────────────
    lineage = conn.execute(
        "SELECT constructor_id, constructor_lineage_id FROM dim_constructors ORDER BY 2, 1").fetchall()
    cseasons: dict[str, set[int]] = {}
    latest: dict[str, tuple[int, str]] = {}
    for cid, yr in conn.execute(
        "SELECT constructor_id, race_year FROM fct_lap_residuals GROUP BY 1, 2"
    ).fetchall():
        cseasons.setdefault(cid, set()).add(int(yr))
    by_lineage: dict[str, list[str]] = {}
    for cid, lin in lineage:
        by_lineage.setdefault(lin, []).append(cid)
    for lin, cids in sorted(by_lineage.items()):
        yrs = sorted(set().union(*(cseasons.get(c, set()) for c in cids)))
        newest = max(cids, key=lambda c: max(cseasons.get(c, {0})))
        rows.append({
            "domain": "constructor", "code": lin, "display": newest,
            "aliases": _dedupe([*cids, lin.replace("_", " "), *aliases.get("constructor", {}).get(lin, [])]),
            "seasons": yrs, "parent_code": None,
            "extra": {"constructor_lineage_id": lin, "constructor_ids": sorted(cids)},
        })

    # ── circuits and races ───────────────────────────────────────────────────
    circuits = conn.execute(
        "SELECT circuit_key, circuit_id, circuit_name FROM dim_circuits ORDER BY circuit_key").fetchall()
    race_rows = conn.execute(f"""
        SELECT r.race_id, CAST(split_part(r.race_id, '_', 1) AS INTEGER) AS season,
               CAST(split_part(r.race_id, '_', 2) AS INTEGER) AS rnd, r.track_id,
               s.EventName, s.Location, s.Country
        FROM race_to_track r
        LEFT JOIN read_parquet('{sched}', hive_partitioning = false) s
          ON s.season = CAST(split_part(r.race_id, '_', 1) AS INTEGER)
         AND s.RoundNumber = CAST(split_part(r.race_id, '_', 2) AS INTEGER)
        ORDER BY season, rnd""").fetchall()
    circuit_name = {c[0]: c[2] for c in circuits}
    c_seasons: dict[str, set[int]] = {}
    c_extra: dict[str, set[str]] = {}
    for rid, season, rnd, track, event, loc, country in race_rows:
        c_seasons.setdefault(track, set()).add(season)
        c_extra.setdefault(track, set()).update(x for x in (event, loc, country) if x)
    for key, cid, name in circuits:
        rows.append({
            "domain": "circuit", "code": key, "display": name,
            "aliases": _dedupe([name, cid, key.replace("_", " "), *sorted(c_extra.get(key, [])),
                                *aliases.get("circuit", {}).get(key, [])]),
            "seasons": sorted(c_seasons.get(key, [])), "parent_code": None,
            "extra": {"circuit_id": cid},
        })
    for rid, season, rnd, track, event, loc, country in race_rows:
        gp = event or track.replace("_", " ").title()
        rows.append({
            "domain": "race", "code": rid, "display": f"{season} {gp} (round {rnd})",
            "aliases": _dedupe([gp, circuit_name.get(track, ""), loc or "", country or "",
                                *aliases.get("circuit", {}).get(track, [])]),
            "seasons": [season], "parent_code": track,
            "extra": {"season": season, "round": rnd, "circuit_key": track,
                      "circuit_name": circuit_name.get(track), "grand_prix": gp},
        })

    # ── seasons, compounds, caution statuses, stint end causes ───────────────
    for (yr,) in conn.execute("SELECT DISTINCT race_year FROM fct_lap_residuals ORDER BY 1").fetchall():
        rows.append({"domain": "season", "code": str(yr), "display": f"{yr} season", "aliases": [str(yr)],
                     "seasons": [int(yr)], "parent_code": None, "extra": {}})
    for comp, yrs in conn.execute(
        "SELECT compound_code, list(DISTINCT season ORDER BY season) FROM dim_compounds_season GROUP BY 1 ORDER BY 1"
    ).fetchall():
        rows.append({"domain": "compound", "code": comp, "display": comp.title(),
                     "aliases": _dedupe([comp, *aliases.get("compound", {}).get(comp, [])]),
                     "seasons": [int(y) for y in yrs], "parent_code": None, "extra": {}})
    for code, display, al in CAUTION_STATUSES:
        rows.append({"domain": "caution_status", "code": code, "display": display,
                     "aliases": _dedupe([code, code.replace("_", " "), *al]),
                     "seasons": [], "parent_code": None, "extra": {}})
    for (cause,) in conn.execute(
        "SELECT DISTINCT stint_end_cause FROM fct_stint_features WHERE stint_end_cause IS NOT NULL ORDER BY 1"
    ).fetchall():
        rows.append({"domain": "stint_end_cause", "code": cause, "display": cause.replace("_", " "),
                     "aliases": _dedupe([cause, cause.replace("_", " "), *aliases.get("stint_end_cause", {}).get(cause, [])]),
                     "seasons": [], "parent_code": None, "extra": {}})

    # An alias file key that matches no row is a typo; fail loudly.
    known = {(r["domain"], r["code"]) for r in rows}
    bad = [f"{d}:{c}" for d, m in aliases.items() if not d.startswith("_") for c in m if (d, c) not in known]
    if bad:
        raise EntityBuildError(f"aliases.json keys match no entity: {', '.join(sorted(bad))}")

    report = {"drivers": len(codes), "names_from_jolpica": from_jol, "names_from_fastf1_results": from_f1,
              "rows": len(rows)}
    return rows, report


def export_assistant_entities(conn, out_root: Path, size_report: list) -> dict:
    """Write dimensions/assistant_entities.parquet and return its manifest entry."""
    import duckdb

    try:
        rows, report = build_rows(conn)
    except EntityBuildError as e:
        print(f"\n  FAILED: {e}")
        sys.exit(1)
    dest = out_root / "dimensions"
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "assistant_entities.parquet"
    mem = duckdb.connect()
    mem.execute("""CREATE TABLE assistant_entities (domain VARCHAR, code VARCHAR, display VARCHAR,
                   aliases VARCHAR, seasons VARCHAR, parent_code VARCHAR, extra VARCHAR)""")
    mem.executemany(
        "INSERT INTO assistant_entities VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(r["domain"], r["code"], r["display"], json.dumps(r["aliases"], ensure_ascii=False),
          json.dumps(r["seasons"]), r["parent_code"], json.dumps(r["extra"], ensure_ascii=False))
         for r in rows],
    )
    mem.execute(f"COPY (SELECT * FROM assistant_entities ORDER BY domain, code) TO '{out}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD)")
    mem.close()
    size_report.append(("assistant_entities", out.stat().st_size))
    print(f"  assistant_entities  ->  {out.name}  ({report['rows']} rows; driver names: "
          f"{report['names_from_jolpica']} Jolpica, {report['names_from_fastf1_results']} FastF1 results)")
    return {"name": "assistant_entities", "path": f"/data/dimensions/{out.name}", "partitioned": False}
