#!/usr/bin/env python3
"""AX-19: freeze the assistant's published snapshot into one verifiable file.

  python scripts/assistant_freeze.py --dry-run                 # gate + show what would be frozen (writes nothing)
  python scripts/assistant_freeze.py --write --ax13-real-pass  # write freeze.json (owner step; see below)
  python scripts/assistant_freeze.py --verify                  # recompute from disk, diff, exit 1 naming the field

freeze.json (default _roadmap/_ai-integration/_evidence/ax-19-freeze/freeze.json) holds manifest.version,
generatedAt, per-partition assistant.cards[] {season, path, rows, sha256}, catalogue/index sha256, catalogue_version,
registry, label_version, model_version, classes_live, classes_held, the row count and sha256 of every card-source
table, and a human line saying which classes launch and which are refused.

Gates (checked by --write and --verify): the manifest has an `assistant` block; generatedAt is after the v16 seal
(2026-10-26, CO-33); classes_live == ["T"] and classes_held == ["T*", "WC", "ML"] (HD5-A); model_version is null
only with "ML" in classes_held. --write also needs --ax13-real-pass, the owner's statement that AX-13's REAL baseline
passed the amended bar including the human read, on this same export (the script cannot see that). It does not run
export or dbt and never touches the warehouse.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "app" / "public" / "data"
DEFAULT_FREEZE = ROOT / "_roadmap" / "_ai-integration" / "_evidence" / "ax-19-freeze" / "freeze.json"
SEAL_DATE = "2026-10-26"
CLASSES_LIVE = ["T"]
CLASSES_HELD = ["T*", "WC", "ML"]
HELD_REASONS = {
    "T*": "dirty-air-dependent transform kinds are held stubs (AX-15a, HD2-C); wake calibration is post-v1",
    "WC": "wake and traffic cost questions are refused: no traffic number reaches a card in v1 (HD5-A)",
    "ML": "no ML cards in v1: model_version is null (HD5-A)",
}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parquet_rows(p: Path) -> int:
    import pyarrow.parquet as pq

    try:
        return pq.ParquetFile(p).metadata.num_rows
    except Exception:  # corrupt file: rows unknown; the sha256 diff still names it
        return None


def _local(data: Path, url_path: str) -> Path:
    """Manifest paths look like /data/assistant/cards/2024.parquet; map onto the data dir."""
    rel = url_path[len("/data/"):] if url_path.startswith("/data/") else url_path.lstrip("/")
    return data / rel


def gate(manifest: dict) -> list[str]:
    """Problems that forbid a freeze. Pure function of the manifest."""
    problems: list[str] = []
    block = manifest.get("assistant")
    if not isinstance(block, dict):
        return ["manifest.assistant: missing (run make app-data)"]
    gen = str(manifest.get("generatedAt", ""))
    if not gen or gen[:10] <= SEAL_DATE:
        problems.append(f"manifest.generatedAt: {gen or 'missing'} is not after the v16 seal {SEAL_DATE}")
    if block.get("classes_live") != CLASSES_LIVE:
        problems.append(f"assistant.classes_live: {block.get('classes_live')!r} != {CLASSES_LIVE!r}")
    held = block.get("classes_held")
    if held != CLASSES_HELD:
        problems.append(f"assistant.classes_held: {held!r} != {CLASSES_HELD!r}")
    if block.get("model_version") is None and "ML" not in (held or []):
        problems.append("assistant.model_version: null is accepted only with ML in classes_held")
    for k in ("catalogue_version", "registry", "label_version", "cards"):
        if not block.get(k):
            problems.append(f"assistant.{k}: empty")
    return problems


def _card_sources(data: Path, cards: list[dict], manifest: dict) -> tuple[list[dict], list[str]]:
    """Distinct source.mart across the card partitions, matched to exported manifest tables."""
    import pyarrow.parquet as pq

    marts: set[str] = set()
    for c in cards:
        p = _local(data, c["path"])
        if not p.exists():
            continue
        try:
            vals = pq.read_table(p, columns=["source"]).column("source").to_pylist()
        except Exception:
            continue
        for s in vals:
            m = (json.loads(s) if s else {}).get("mart")
            if m:
                marts.add(m)
    by_name = {t["name"]: t for t in manifest.get("tables", [])}
    out, unexported = [], []
    for m in sorted(marts):
        t = by_name.get(m)
        if t is None:
            unexported.append(m)
            continue
        paths = [pp["path"] for pp in t["partitions"]] if t.get("partitioned") else [t["path"]]
        files = []
        for up in paths:
            f = _local(data, up)
            files.append({"path": up, "rows": parquet_rows(f) if f.exists() else None,
                          "sha256": sha256_file(f) if f.exists() else None})
        out.append({"name": m, "rows": sum(x["rows"] or 0 for x in files), "files": files})
    return out, unexported


def build(data: Path) -> dict:
    manifest = json.loads((data / "_manifest.json").read_text(encoding="utf-8"))
    problems = gate(manifest)
    if problems:
        raise SystemExit("freeze gate failed:\n  " + "\n  ".join(problems))
    b = manifest["assistant"]
    cards = []
    for c in b["cards"]:
        p = _local(data, c["path"])
        if not p.exists():
            raise SystemExit(f"assistant.cards: missing file {c['path']}")
        cards.append({"season": c.get("season"), "path": c["path"], "rows": parquet_rows(p), "sha256": sha256_file(p)})
    files = {}
    for name in ("catalogue.json", "index.json"):
        p = data / "assistant" / name
        if not p.exists():
            raise SystemExit(f"missing assistant/{name}")
        files[name] = sha256_file(p)
    sources, unexported = _card_sources(data, b["cards"], manifest)
    return {
        "manifest": {"version": manifest["version"], "generatedAt": manifest["generatedAt"]},
        "assistant": {"cards": cards, "catalogue_sha256": files["catalogue.json"], "index_sha256": files["index.json"]},
        "catalogue_version": b["catalogue_version"],
        "registry": b["registry"],
        "label_version": b["label_version"],
        "model_version": b.get("model_version"),
        "classes_live": b["classes_live"],
        "classes_held": b["classes_held"],
        "launch_summary": "Launch: " + ", ".join(b["classes_live"]) + ". Refused: "
        + "; ".join(f"{k} ({HELD_REASONS.get(k, 'held')})" for k in b["classes_held"]) + ".",
        "card_sources": sources,
        "card_sources_not_exported": unexported,
    }


def diff(a, b, path: str = "") -> list[str]:
    """Field paths where frozen (a) and recomputed (b) differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k, "<absent>"), b.get(k, "<absent>"), f"{path}.{k}" if path else k)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            label = x.get("path") or x.get("name") if isinstance(x, dict) else None
            out += diff(x, y, f"{path}[{label or i}]")
        return out
    return [] if a == b else [f"{path}: frozen {a!r} != now {b!r}"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--dry-run", action="store_true", help="gate and print, write nothing")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    ap.add_argument("--ax13-real-pass", action="store_true",
                    help="owner attests AX-13's REAL baseline passed the amended bar on this export")
    a = ap.parse_args(argv)

    if a.write and not a.ax13_real_pass:
        print("refused: --write needs --ax13-real-pass (AX-13 ruling 9, AX-19 ruling 1)", file=sys.stderr)
        return 2
    try:
        now = build(a.data)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    if a.dry_run:
        print(json.dumps(now, indent=2, sort_keys=True))
        return 0
    if a.write:
        a.freeze.parent.mkdir(parents=True, exist_ok=True)
        a.freeze.write_text(json.dumps(now, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {a.freeze}")
        return 0
    if not a.freeze.exists():
        print(f"missing {a.freeze}", file=sys.stderr)
        return 1
    problems = diff(json.loads(a.freeze.read_text(encoding="utf-8")), now)
    for p in problems:
        print("MISMATCH", p, file=sys.stderr)
    print("freeze verified" if not problems else f"{len(problems)} field(s) differ")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
