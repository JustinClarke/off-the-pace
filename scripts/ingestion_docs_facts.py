"""
ingestion_docs_facts.py   Drift gate for the Bronze coverage snippet.

The Bronze coverage table at docs/snippets/bronze-coverage.mdx is generated, not
hand-maintained: it always reflects what is actually on disk. This script re-runs
the generator and fails if the committed snippet has drifted from a fresh
regeneration, so a stale coverage table can never ship.

Usage:
  python scripts/ingestion_docs_facts.py          # check; exits 1 on drift
  python scripts/ingestion_docs_facts.py --write   # regenerate the snippet in place

CI (docs-ci.yml):
  python scripts/ingestion_docs_facts.py
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNIPPET = ROOT / "docs" / "snippets" / "bronze-coverage.mdx"
VERIFY_SCRIPT = ROOT / "ingestion" / "verify_bronze.py"


def generate() -> str:
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--markdown"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="Regenerate the snippet in place instead of checking it")
    args = parser.parse_args(argv)

    print("── ingestion_docs_facts: Bronze coverage snippet ────────────────────────────")
    fresh = generate()

    if args.write:
        SNIPPET.parent.mkdir(parents=True, exist_ok=True)
        SNIPPET.write_text(fresh, encoding="utf-8")
        print(f"  WROTE  {SNIPPET.relative_to(ROOT)}")
        return 0

    if not SNIPPET.exists():
        print(f"  ERROR  MISSING snippet: {SNIPPET.relative_to(ROOT)}")
        print("\ningestion_docs_facts FAILED-run with --write to generate it")
        return 1

    committed = SNIPPET.read_text(encoding="utf-8")
    if committed != fresh:
        print(f"  ERROR  DRIFT: {SNIPPET.relative_to(ROOT)} does not match a fresh regeneration")
        print("  --- committed ---")
        print(committed)
        print("  --- fresh ---")
        print(fresh)
        print("\ningestion_docs_facts FAILED-run with --write to refresh the snippet")
        return 1

    print(f"  OK   {SNIPPET.relative_to(ROOT)} matches a fresh regeneration")
    print("\ningestion_docs_facts PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
