#!/usr/bin/env python3
"""AX-08 `make app-cards-check`: do the published cards still match the published data?

Rebuilds the cards from the files in --data into a temp folder (symlinks for every table, a copy of
assistant/ without cards) and compares each card file's sha256 and the catalogue_version with the
manifest's `assistant` block. Needs no warehouse and never writes into --data.

  python scripts/check_cards.py [--data app/public/data]     exit 1 on any difference
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assistant_finalize as af  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "app" / "public" / "data")
    args = ap.parse_args(argv)
    data = args.data.resolve()
    manifest = json.loads((data / "_manifest.json").read_text(encoding="utf-8"))
    block = manifest.get("assistant")
    if not block:
        print("manifest has no assistant block: run make app-data")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        for child in data.iterdir():
            if child.name in ("assistant", "_manifest.json"):
                continue
            os.symlink(child, t / child.name)
        (t / "assistant").mkdir()
        for child in (data / "assistant").iterdir():
            if child.name in ("cards", "_staging", "index.json"):
                continue
            os.symlink(child, t / "assistant" / child.name)
        # build-cards reads manifest.version as data_version: the stage-1 version, i.e. the table hash.
        m = {k: v for k, v in manifest.items() if k != "assistant"}
        m["version"] = af.table_hash(data)
        (t / "_manifest.json").write_text(json.dumps(m), encoding="utf-8")
        subprocess.run(["node", "scripts/build-cards.mjs", "--data", str(t), "--stage"], cwd=ROOT / "app", check=True,
                       stdout=subprocess.DEVNULL)
        entries = af.stage_to_parquet(t, ROOT / "app" / "src" / "assistant" / "cards" / "card.schema.json")
    want = {(c["season"], c["sha256"]) for c in block["cards"]}
    got = {(c["season"], c["sha256"]) for c in entries}
    bad = sorted(want ^ got, key=lambda x: (x[0] is None, x[0] or 0))
    if bad:
        print(f"DRIFT: card files differ from a rebuild for seasons {sorted({str(s) for s, _ in bad})}: run make app-data")
        return 1
    if af.catalogue_version_of(data) != block["catalogue_version"]:
        print("DRIFT: catalogue_version differs from the manifest")
        return 1
    print(f"cards current: {len(entries)} files reproduce their manifest sha256")
    return 0


if __name__ == "__main__":
    sys.exit(main())
