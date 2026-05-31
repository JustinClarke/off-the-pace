"""
docs_audit.py   Documentation health checks-three guards in one pass.

  1. README presence -every catalogued directory has a README.md (hard error).
  2. Tour footer      -every tour-stop README carries a ← prev / next → line (hard error).
  3. File-header lint -authored .py / dbt .sql / app .ts(x) files open with a header
                         (warning by default; use --strict to gate).

Usage:
  python scripts/docs_audit.py            # README + footer errors; header warnings
  python scripts/docs_audit.py --strict   # all findings become errors (exit 1)
  python scripts/docs_audit.py --headers  # add file-header findings to the run

CI (docs-ci.yml):
  python scripts/docs_audit.py
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 1. README-presence catalogue ────────────────────────────────────────────────
README_REQUIRED: list[str] = [
    "ingestion",
    "data",
    "transform",
    "transform/models/staging",
    "transform/models/intermediate",
    "transform/models/marts",
    "transform/models/reference",
    "transform/macros",
    "transform/seeds",
    "transform/tests",
    "ml",
    "ml/tests",
    "app",
    "docs",
    "scripts",
    "agents",
    ".agents",
    ".github/workflows",
    "_roadmap",
]

# ── 2. Tour-stop READMEs that must carry a prev/next footer ─────────────────────
# Pattern: line containing "← " or "Previous in tour" (case-insensitive)
TOUR_STOP_READMES: list[str] = [
    "ingestion/README.md",
    "data/README.md",
    "transform/README.md",
    "ml/README.md",
    "app/README.md",
    "docs/README.md",
    "scripts/README.md",
    "agents/README.md",
    "_roadmap/README.md",
]
FOOTER_RE = re.compile(r"(←|Previous in tour|Next in tour|→)", re.IGNORECASE)

# ── 3. File-header lint ─────────────────────────────────────────────────────────
# Directories/globs to scan-intentionally excludes generated, vendored, data.
PY_GLOBS = [
    "ingestion/src/*.py",
    "ml/src/*.py",
    "scripts/*.py",
    "transform/tasks/**/*.py",
]
SQL_GLOBS = [
    "transform/models/**/*.sql",
    "transform/macros/*.sql",
    "transform/tests/*.sql",
]
TS_GLOBS = [
    "app/src/**/*.ts",
    "app/src/**/*.tsx",
]
# Files exempt from header lint (test helpers, inits, type stubs, etc.)
HEADER_EXEMPT_SUFFIXES = ("__init__.py", "conftest.py", "types.ts", "vite-env.d.ts")
HEADER_EXEMPT_DIRS = {"__pycache__", "node_modules", ".venv", "dist", "target"}


def _exempt(path: Path) -> bool:
    if any(part in HEADER_EXEMPT_DIRS for part in path.parts):
        return True
    return path.name in HEADER_EXEMPT_SUFFIXES or path.name.startswith("_")


def _has_python_header(path: Path) -> bool:
    """True if a Python file opens with a docstring or a meaningful # comment."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return True  # unreadable-don't flag
    for line in lines[:5]:
        stripped = line.strip()
        if stripped.startswith("#!"):
            continue  # shebang-skip, don't judge
        if stripped.startswith('"""') or stripped.startswith("'''"):
            return True
        if stripped.startswith("#"):
            return True
        if stripped:  # non-blank, non-header → no header
            return False
    return False


def _has_sql_header(path: Path) -> bool:
    """True if a SQL/Jinja file opens with a -- comment, {# block, or {% macro declaration."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return True
    for line in lines[:5]:
        stripped = line.strip()
        if stripped.startswith("--") or stripped.startswith("{#") or stripped.startswith("{%"):
            return True
        if stripped:
            return False
    return False


def _has_ts_header(path: Path) -> bool:
    """True if a TS/TSX file opens with a // comment."""
    try:
        first = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except (OSError, IndexError):
        return True
    return first.strip().startswith("//")


# ── Runner ───────────────────────────────────────────────────────────────────────

def check_readme_presence() -> list[str]:
    errors = []
    for rel in README_REQUIRED:
        readme = ROOT / rel / "README.md"
        if not readme.exists():
            errors.append(f"MISSING README: {rel}/README.md")
    return errors


def check_tour_footers() -> list[str]:
    errors = []
    for rel in TOUR_STOP_READMES:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"MISSING tour-stop README: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not FOOTER_RE.search(text):
            errors.append(f"NO tour footer in: {rel}")
    return errors


def check_file_headers() -> list[str]:
    warnings = []

    def scan(globs, checker):
        for glob in globs:
            for path in sorted(ROOT.glob(glob)):
                if _exempt(path):
                    continue
                if not checker(path):
                    warnings.append(f"NO header: {path.relative_to(ROOT)}")

    scan(PY_GLOBS, _has_python_header)
    scan(SQL_GLOBS, _has_sql_header)
    scan(TS_GLOBS, _has_ts_header)
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true", help="Treat header warnings as errors")
    parser.add_argument("--headers", action="store_true", help="Include file-header lint pass")
    args = parser.parse_args(argv)

    errors: list[str] = []
    warnings: list[str] = []

    print("── docs_audit: README presence ────────────────────────────────────────")
    readme_errors = check_readme_presence()
    if readme_errors:
        for e in readme_errors:
            print(f"  ERROR  {e}")
        errors.extend(readme_errors)
    else:
        print(f"  OK  all {len(README_REQUIRED)} required READMEs present")

    print("── docs_audit: tour footers ────────────────────────────────────────────")
    footer_errors = check_tour_footers()
    if footer_errors:
        for e in footer_errors:
            print(f"  ERROR  {e}")
        errors.extend(footer_errors)
    else:
        print(f"  OK  all {len(TOUR_STOP_READMES)} tour-stop READMEs carry a footer")

    if args.headers or args.strict:
        print("── docs_audit: file-header lint ────────────────────────────────────────")
        header_warnings = check_file_headers()
        if header_warnings:
            for w in header_warnings:
                level = "ERROR" if args.strict else "WARN "
                print(f"  {level}  {w}")
            if args.strict:
                errors.extend(header_warnings)
            else:
                warnings.extend(header_warnings)
        else:
            print("  OK  all scanned files carry headers")

    print()
    if errors:
        print(f"docs_audit FAILED-{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    if warnings:
        print(f"docs_audit PASSED-0 errors, {len(warnings)} warning(s) (run --strict to gate)")
    else:
        print("docs_audit PASSED-0 errors, 0 warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
