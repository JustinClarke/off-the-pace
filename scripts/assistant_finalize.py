"""AX-08 card publish: the --finalize stage of export_app_data.py.

Pipeline order inside `make app-data`:
  1. export_app_data.py            tables, assistant_entities, qv_* views, assistant/catalogue.json, manifest
  2. node app/scripts/build-cards.mjs --data <out> --stage     canonical JSON into <out>/assistant/_staging/
  3. export_app_data.py --finalize     (no warehouse) staged JSON -> ZSTD parquet partitions
                                       assistant/cards/{season}.parquet and _global.parquet, the manifest
                                       `assistant` block with a sha256 per card file, and the new version.

version = sha256(table hash input + canonical JSON of the assistant block)[:16], so a changed card value
changes manifest.version even when the file size does not. Tables keep the existing name+size proxy.
The table hash input excludes assistant/cards/ so build-cards (which stamps data_version = the stage-1
version into every card) reads the same value on a first run and on a re-run.

Determinism: one thread, fixed ORDER BY id, in-memory DuckDB. Parquet bytes are not guaranteed stable
across DuckDB versions; the duckdb version is recorded in the block (`parquet_writer`).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

MAX_FILE_BYTES = 5 * 1024 * 1024
CARD_SCHEMA = "1"

# column -> DuckDB type; order is the stored column order (card.schema.json $comment).
CARD_COLUMNS: dict[str, str] = {
    "id": "VARCHAR", "kind": "VARCHAR", "metric": "VARCHAR", "label": "VARCHAR", "value": "VARCHAR",
    "unit": "VARCHAR", "display": "VARCHAR", "unavailable_reason": "VARCHAR",
    "n_count": "INTEGER", "n_unit": "VARCHAR",
    "interval_low": "DOUBLE", "interval_high": "DOUBLE", "interval_level": "DOUBLE", "interval_kind": "VARCHAR",
    "interval_source_columns": "VARCHAR", "scope": "VARCHAR", "source": "VARCHAR", "versions": "VARCHAR",
    "page": "VARCHAR", "caveats": "VARCHAR", "policy_fields": "VARCHAR",
    "sample": "VARCHAR", "grade": "VARCHAR", "status": "VARCHAR", "held_reason": "VARCHAR", "season": "INTEGER",
}


def _j(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical(obj) -> bytes:
    return _j(obj).encode("utf-8")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def flatten_card(c: dict) -> dict:
    iv = c.get("interval")
    n = c["n"]
    return {
        "id": c["id"], "kind": c["kind"], "metric": c["metric"], "label": c["label"],
        "value": None if c.get("value") is None else _j(c["value"]),
        "unit": c.get("unit"), "display": c.get("display"), "unavailable_reason": c.get("unavailable_reason"),
        "n_count": n["count"], "n_unit": n["unit"],
        "interval_low": iv["low"] if iv else None, "interval_high": iv["high"] if iv else None,
        "interval_level": iv["level"] if iv else None, "interval_kind": iv["kind"] if iv else None,
        "interval_source_columns": _j(iv["source_columns"]) if iv else None,
        "scope": _j(c["scope"]), "source": _j(c["source"]), "versions": _j(c["versions"]),
        "page": _j(c["page"]), "caveats": _j(c.get("caveats", [])), "policy_fields": _j(c.get("policy_fields", {})),
        "sample": c.get("sample"), "grade": c.get("grade"), "status": c["status"],
        "held_reason": c.get("held_reason"), "season": c["scope"].get("season"),
    }


def _check_schema_columns(card_schema_path: Path | None) -> None:
    """The stored columns must be the ones the AX-01 schema comment lists."""
    if card_schema_path is None or not card_schema_path.exists():
        return
    comment = json.loads(card_schema_path.read_text(encoding="utf-8"))["$comment"]
    import re
    named = set(re.findall(r"\b([a-z_]+) (?:VARCHAR|INTEGER|DOUBLE)\b", comment))
    named |= {"interval_source_columns", "scope", "source", "versions", "page", "caveats", "policy_fields"}
    missing = named - set(CARD_COLUMNS)
    if missing:
        raise ValueError(f"card parquet columns drifted from card.schema.json: missing {sorted(missing)}")


def stage_to_parquet(out_root: Path, schema_path: Path | None = None) -> list[dict]:
    import duckdb

    staging = out_root / "assistant" / "_staging"
    cards_json = staging / "cards.json"
    if not cards_json.exists():
        raise FileNotFoundError(f"{cards_json} not found: run `node app/scripts/build-cards.mjs --data {out_root} --stage` first")
    _check_schema_columns(schema_path)
    cards = json.loads(cards_json.read_text(encoding="utf-8"))
    ids = [c["id"] for c in cards]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate card ids in staging")

    cards_dir = out_root / "assistant" / "cards"
    if cards_dir.exists():
        shutil.rmtree(cards_dir)
    cards_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp:
        nd = Path(tmp) / "cards.ndjson"
        with open(nd, "w", encoding="utf-8") as f:
            for c in cards:
                f.write(json.dumps(flatten_card(c), ensure_ascii=False) + "\n")
        conn = duckdb.connect()
        conn.execute("SET threads=1")
        cols = ", ".join(f"'{k}': '{t}'" for k, t in CARD_COLUMNS.items())
        conn.execute(
            f"CREATE TABLE cards AS SELECT * FROM read_json('{nd}', format='newline_delimited', columns={{{cols}}})"
        )
        seasons = [r[0] for r in conn.execute("SELECT DISTINCT season FROM cards ORDER BY season NULLS LAST").fetchall()]
        entries = []
        for s in seasons:
            name = "_global" if s is None else str(s)
            dest = cards_dir / f"{name}.parquet"
            where = "season IS NULL" if s is None else f"season = {int(s)}"
            conn.execute(
                f"COPY (SELECT * FROM cards WHERE {where} ORDER BY id) TO '{dest}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            if dest.stat().st_size > MAX_FILE_BYTES:
                raise ValueError(f"SIZE GATE: {dest.name} is {dest.stat().st_size/1024**2:.2f} MB > 5 MB")
            rows = conn.execute(f"SELECT count(*) FROM cards WHERE {where}").fetchone()[0]
            entries.append({
                "season": s, "path": f"/data/assistant/cards/{dest.name}", "rows": rows, "sha256": sha256_file(dest),
            })
        conn.close()
    return entries


def table_hash(out_root: Path) -> str:
    """Same proxy as export_app_data._content_hash, minus assistant/cards/ (see module docstring)."""
    h = hashlib.sha256()
    skip = out_root / "assistant" / "cards"
    for f in sorted(out_root.rglob("*.parquet")):
        if skip in f.parents:
            continue
        h.update(f.name.encode())
        h.update(str(f.stat().st_size).encode())
    return h.hexdigest()[:16]


def final_version(out_root: Path, block: dict) -> str:
    h = hashlib.sha256()
    h.update(table_hash(out_root).encode())
    h.update(canonical(block))
    return h.hexdigest()[:16]


def catalogue_version_of(out_root: Path) -> str:
    cat = json.loads((out_root / "assistant" / "catalogue.json").read_text(encoding="utf-8"))
    return cat["catalogue_version"]


def build_block(out_root: Path, card_entries: list[dict]) -> dict:
    import duckdb

    build = json.loads((out_root / "assistant" / "_staging" / "build.json").read_text(encoding="utf-8"))
    v = build["versions"]
    return {
        "card_schema": CARD_SCHEMA,
        "catalogue_version": catalogue_version_of(out_root),
        "registry": v.get("registry"),
        "label_version": v.get("label_version"),
        "model_version": v.get("model_version"),  # null until the ML cards exist (HD8)
        "cards": card_entries,
        "classes_live": build["classes_live"],
        "classes_held": build["classes_held"],
        "parquet_writer": f"duckdb {duckdb.__version__}",
    }


def verify_assistant(out_root: Path, manifest: dict) -> list[str]:
    """Problems found re-hashing every file the manifest's assistant block names. Needs no warehouse."""
    block = manifest.get("assistant")
    if not block:
        return ["manifest has no assistant block: run --finalize"]
    problems = []
    for c in block.get("cards", []):
        p = out_root / c["path"].removeprefix("/data/")
        if not p.exists():
            problems.append(f"missing card file {c['path']}")
        elif sha256_file(p) != c["sha256"]:
            problems.append(f"card file {c['path']} does not match its manifest sha256")
    cat = out_root / "assistant" / "catalogue.json"
    if not cat.exists():
        problems.append("missing assistant/catalogue.json")
    else:
        from assistant_query_views import canonical_bytes
        d = json.loads(cat.read_text(encoding="utf-8"))
        stated = d.pop("catalogue_version", None)
        if stated != block.get("catalogue_version"):
            problems.append("catalogue.json catalogue_version differs from the manifest")
        if hashlib.sha256(canonical_bytes(d)).hexdigest() != stated:
            problems.append("catalogue.json content does not hash to its catalogue_version")
    if manifest.get("version") != final_version(out_root, block):
        problems.append("manifest.version is not the hash of the tables plus the assistant block: run --finalize")
    return problems


def finalize(out_root: Path, schema_path: Path | None = None, check: bool = False) -> int:
    """Returns a process exit code. check=True verifies only."""
    out_root = Path(out_root).resolve()
    mpath = out_root / "_manifest.json"
    if not mpath.exists():
        print(f"ERROR: {mpath} not found: run the table export first")
        return 1
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    if check:
        problems = verify_assistant(out_root, manifest)
        for p in problems:
            print(f"  DRIFT: {p}")
        print("  assistant block is current." if not problems else "  Run: make app-data")
        return 1 if problems else 0
    entries = stage_to_parquet(out_root, schema_path)
    block = build_block(out_root, entries)
    manifest["assistant"] = block
    manifest["version"] = final_version(out_root, block)
    mpath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.rmtree(out_root / "assistant" / "_staging")
    print(f"  finalized: {len(entries)} card files, {sum(e['rows'] for e in entries)} cards, "
          f"catalogue {block['catalogue_version'][:12]}, version {manifest['version']}")
    return 0
