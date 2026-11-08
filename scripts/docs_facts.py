"""
docs_facts.py   Headline-count reconciliation across key documentation files.

Asserts that the numbers stated in README.md and the ML front-door pages agree for:
 -dbt model count
 -dbt test count (both also checked against transform/target/manifest.json,
  or --manifest PATH; skipped with a notice when absent unless --require-manifest)
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
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = {
    "README.md": ROOT / "README.md",
    "docs/ml/overview.mdx": ROOT / "docs/ml/overview.mdx",
}

# Context-anchored patterns, one or more per fact.
#
# The number is captured, never matched literally. Every pattern here used to hardcode
# the value it expected -- `\b(28)\s+tests?` -- so the reconciler could only ever confirm
# one specific number. When the truth moved, the pattern stopped matching, the fact
# silently dropped out of the report, and the run still passed. That is how README.md and
# docs/ml/overview.mdx came to agree with each other on 60 dbt models and 443 tests while
# the generated inventory said 67 and 553.
#
# "tests" and "features" each name two different facts in the same file (dbt vs ML tests,
# ML features vs browser features), so the anchors below are what keep them apart.
TARGETED: list[tuple[str, list[re.Pattern]]] = [
    ("dbt models", [re.compile(r"\b(\d+)\s+models\b"),
                    re.compile(r"\b(\d+)-table\s+dbt\s+warehouse")]),
    ("dbt tests", [re.compile(r"(?<!XGBoost )models[ ,·]+\*{0,2}(\d+)\*{0,2}\s+tests\b"),
                   re.compile(r"dbt-test\s+#\s+run\s+(\d+)\s+tests\b")]),
    ("ML models", [re.compile(r"\b(\d+)\s+XGBoost\s+models")]),
    ("ML tests", [re.compile(r"XGBoost models,\s*(\d+)\s+tests\b"),
                  re.compile(r"ml-test\s+#\s*(\d+)\s+tests\b"),
                  re.compile(r"\bAll (\d+) tests\b")]),
    ("ML features", [re.compile(r"\b(\d+)\s+features\b(?!\s*·\s*zero server)")]),
]

# Generated snippets are the source of truth for the facts they carry: they are rebuilt
# from the warehouse and from ml/src/schema.py, so a hand-written page that disagrees with
# one is wrong by definition. Without this, the reconciler only proved the two hand-written
# pages agreed with each other -- which they did, while both were stale.
AUTHORITIES: dict[str, tuple[str, re.Pattern]] = {
    "dbt models": ("docs/snippets/transform-inventory.mdx",
                   re.compile(r'title="(\d+) models"')),
    "dbt tests": ("docs/snippets/transform-inventory.mdx",
                  re.compile(r'title="(\d+) tests"')),
    "ML models": ("docs/snippets/ml-inventory.mdx",
                  re.compile(r'title="(\d+) XGBoost models"')),
    "ML tests": ("docs/snippets/ml-inventory.mdx",
                 re.compile(r'title="(\d+) tests"')),
    "ML features": ("docs/snippets/ml-inventory.mdx",
                    re.compile(r'title="(\d+) features in \d+ groups"')),
}


DEFAULT_MANIFEST = ROOT / "transform" / "target" / "manifest.json"


def manifest_counts(path: Path) -> dict[str, int]:
    """dbt models and data tests as `dbt build` counts them, read from a parsed manifest.

    Models are resource_type "model" in this project's package; data tests are every
    resource_type "test" node (generic + singular). Unit tests are not in the README figure.
    """
    nodes = json.loads(path.read_text(encoding="utf-8"))["nodes"].values()
    return {
        "dbt models": sum(1 for n in nodes if n["resource_type"] == "model" and n.get("package_name") == "off_the_pace"),
        "dbt tests": sum(1 for n in nodes if n["resource_type"] == "test"),
    }


def check_manifest(texts: dict[str, str], manifest: Path, required: bool, quiet: bool) -> list[str]:
    """Every README model/test figure must equal what the dbt manifest says."""
    if not manifest.exists():
        if required:
            return [f"MISSING MANIFEST  {manifest} not found; run dbt parse first"]
        if not quiet:
            print(f"  SKIP dbt manifest check: {manifest} not found (pass --manifest or --require-manifest)")
        return []
    truth = manifest_counts(manifest)
    errors: list[str] = []
    for label, patterns in TARGETED:
        if label not in truth:
            continue
        for name, text in texts.items():
            found = {m for pattern in patterns for m in pattern.findall(text)}
            bad = sorted(v for v in found if int(v) != truth[label])
            if bad:
                errors.append(f"MANIFEST MISMATCH  {label}: {name} says {bad}, dbt manifest has {truth[label]}")
            elif found and not quiet:
                print(f"  OK   {label}: {name} matches dbt manifest ({truth[label]})")
    return errors


def check_facts(quiet: bool = False, manifest: Path = DEFAULT_MANIFEST, require_manifest: bool = False) -> int:
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

    for label, patterns in TARGETED:
        values: dict[str, set[str]] = {}
        for name, text in texts.items():
            found = {m for pattern in patterns for m in pattern.findall(text)}
            if found:
                values[name] = found

        # Pull the generated source of truth for this fact, if it has one.
        authority_name = authority_value = None
        if label in AUTHORITIES:
            rel, auth_pattern = AUTHORITIES[label]
            auth_path = ROOT / rel
            if not auth_path.exists():
                errors.append(f"MISSING AUTHORITY  {label}: {rel} not found")
                continue
            found = auth_pattern.findall(auth_path.read_text(encoding="utf-8", errors="ignore"))
            if not found:
                errors.append(
                    f"UNREADABLE AUTHORITY  {label}: {rel} matched no value for "
                    f"{auth_pattern.pattern!r} — regenerate it (make docs-coverage) or "
                    f"fix the pattern; a silently unmatched authority reconciles nothing")
                continue
            authority_name, authority_value = rel, sorted(set(found))[0]
            values[rel] = {authority_value}

        if len(values) < 2:
            # fact only appears in one file nothing to reconcile
            continue

        all_vals = set().union(*values.values())
        if len(all_vals) == 1:
            if not quiet:
                agreed = next(iter(all_vals))
                suffix = f", authority {authority_name}" if authority_name else ""
                print(f"  OK   {label}: {agreed} (consistent across "
                      f"{', '.join(n for n in values if n != authority_name)}{suffix})")
        else:
            per_file = ", ".join(f"{n}={sorted(v)}" for n, v in values.items())
            hint = (f" — {authority_name} is generated and authoritative"
                    if authority_name else "")
            errors.append(f"MISMATCH  {label}: {per_file}{hint}")

    errors += check_manifest(texts, manifest, require_manifest, quiet)

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
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                        help="dbt manifest.json whose model/test counts the README must match")
    parser.add_argument("--require-manifest", action="store_true", help="Fail if the manifest is missing")
    args = parser.parse_args(argv)
    if not args.quiet:
        print("── docs_facts: headline-count reconciliation ───────────────────────────────")
    return check_facts(quiet=args.quiet, manifest=args.manifest, require_manifest=args.require_manifest)


if __name__ == "__main__":
    sys.exit(main())
