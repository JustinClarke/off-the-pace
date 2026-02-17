"""
build_reference.py   Entry point for all reference doc generation.

Runs all four generators in sequence:
  1. gen_dbt_reference.py    dbt manifest → docs/docs/reference/models/
  2. gen_schema_reference.py   JSON schemas → docs/docs/reference/schemas/
  3. gen_cli_reference.py    --help output → docs/docs/reference/cli/
  4. gen_macro_reference.py   macro docstrings → docs/docs/reference/macros/

Usage:
  python scripts/build_reference.py           # run all generators
  python scripts/build_reference.py --models  # run only dbt model generator
  python scripts/build_reference.py --schemas
  python scripts/build_reference.py --cli
  python scripts/build_reference.py --macros

CI drift check (in GitHub Actions):
  python scripts/build_reference.py
  git diff --exit-code docs/docs/reference/
"""

import argparse
import importlib.util
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def run_generator(module_path: Path) -> bool:
    """Import and run a generator script's main(). Returns True on success."""
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        mod.main()
        return True
    except SystemExit as e:
        if e.code != 0:
            print(f"  ERROR: {module_path.name} exited with code {e.code}")
            return False
        return True
    except Exception as e:
        print(f"  ERROR in {module_path.name}: {e}")
        return False


GENERATORS = [
    ("models",  "gen_dbt_reference.py",    "dbt models"),
    ("schemas", "gen_schema_reference.py", "Bronze schemas"),
    ("cli",     "gen_cli_reference.py",    "CLI commands"),
    ("macros",  "gen_macro_reference.py",  "dbt macros"),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate all Off The Pace reference docs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    for flag, _, label in GENERATORS:
        parser.add_argument(f"--{flag}", action="store_true", help=f"Run only the {label} generator")

    args = parser.parse_args()
    selected_flags = {flag for flag, _, _ in GENERATORS if getattr(args, flag)}
    run_all = not selected_flags

    failures = 0
    start = time.monotonic()

    for flag, filename, label in GENERATORS:
        if not run_all and flag not in selected_flags:
            continue

        script_path = SCRIPTS_DIR / filename
        if not script_path.exists():
            print(f"  ERROR: {script_path} not found")
            failures += 1
            continue

        print(f"\n[{label}] Running {filename}...")
        t0 = time.monotonic()
        ok = run_generator(script_path)
        elapsed = time.monotonic()-t0
        status = "OK" if ok else "FAILED"
        print(f"[{label}] {status} ({elapsed:.1f}s)")
        if not ok:
            failures += 1

    total = time.monotonic()-start
    print(f"\n{'All generators completed' if not failures else f'{failures} generator(s) failed'} in {total:.1f}s")
    sys.exit(failures)


if __name__ == "__main__":
    main()
