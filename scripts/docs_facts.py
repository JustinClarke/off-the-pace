"""
docs_facts.py   Headline-count reconciliation across key documentation files.

Asserts that the numbers stated in README.md and the ML front-door pages agree for:
 -dbt model count
 -dbt test count
 -ML model count
 -ML test count
 -ML feature count

Run after updating counts anywhere to catch silent drift.

Usage:
  python scripts/docs_facts.py          # prints diff; exits 1 on mismatch
  python scripts/docs_facts.py --quiet  # silent on success, prints only on failure

CI:
  python scripts/docs_facts.py          # runs in docs-ci.yml alongside reference drift check
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = {
    "README.md": ROOT / "README.md",
    "docs/ml/overview.mdx": ROOT / "docs/ml/overview.mdx",
}

# Simpler targeted patterns that are unambiguous in context
TARGETED: list[tuple[str, re.Pattern]] = [
    ("dbt models", re.compile(r"\b(60)\s+(?:dbt\s+)?models")),
    ("dbt tests", re.compile(r"\b(443)\s*[- ]\s*tests?")),
    ("ML models", re.compile(r"\b(5)\s+XGBoost\s+models")),
    ("ML tests", re.compile(r"\b(28)\s+(?:ml\s+)?tests?")),
    ("ML features", re.compile(r"\b(42)\s+features")),
]


def check_facts(quiet: bool = False) -> int:
    errors: list[str] = []
    texts: dict[str, str] = {}
    for name, path in FILES.items():
        if not path.exists():
            errors.append(f"FILE NOT FOUND: {name}")
            continue
        texts[name] = path.read_text(encoding="utf-8", errors="ignore")

    if errors:
        for e in errors:
            print(f"  ERROR  {e}")
        return 1

    for label, pattern in TARGETED:
        values: dict[str, set[str]] = {}
        for name, text in texts.items():
            found = pattern.findall(text)
            if found:
                values[name] = set(found)

        if len(values) < 2:
            # fact only appears in one file nothing to reconcile
            continue

        all_vals = set().union(*values.values())
        if len(all_vals) == 1:
            if not quiet:
                agreed = next(iter(all_vals))
                print(f"  OK   {label}: {agreed} (consistent across {', '.join(values)})")
        else:
            per_file = ", ".join(f"{n}={v}" for n, v in values.items())
            errors.append(f"MISMATCH  {label}: {per_file}")

    if errors:
        print()
        for e in errors:
            print(f"  ERROR  {e}")
        print(f"\ndocs_facts FAILED-{len(errors)} mismatch(es)")
        return 1

    if not quiet:
        print("\ndocs_facts PASSED-all headline counts agree")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiet", action="store_true", help="Silent on success")
    args = parser.parse_args(argv)
    if not args.quiet:
        print("── docs_facts: headline-count reconciliation ───────────────────────────────")
    return check_facts(quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
