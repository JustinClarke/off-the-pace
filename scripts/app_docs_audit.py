"""
app_docs_audit.py   Coverage gate for the app's end-user feature documentation.

Every shipped `app/src/features/<dir>/` module (one that exports a `methodologyHref`)
must ship a matching public docs page. This audit is the enforcement; it mirrors the
shape of docs_audit.py.

Primary key = the feature directories under app/src/features/ that export a
methodologyHref. That set IS the rendered feature set, and it is the only place the
link-to-validate physically lives. A feature is "documented" when all of:

  1. docs/app/<dir>.mdx exists,
  2. "app/<dir>" is listed in the docs.json "App & Visualizations" group,
  3. its methodologyHref equals  CANONICAL_DOCS_BASE + "/app/" + <dir>,
  4. the page carries the required section headings + complete frontmatter.

Reconciliations (drift guards):
  - every feature dir is imported somewhere under app/src (it is navigable),
  - the count of shipped featureId routes in nav/routes.ts equals the feature-dir count,
  - Query Lab is an explicit exception: a shipped, non-FeaturePage feature documented by a
    hand-written docs/app/query-lab.mdx (nav entry only; no methodologyHref to validate).

Usage:
  python scripts/app_docs_audit.py            # report mode: prints the checklist, exits 0
  python scripts/app_docs_audit.py --strict   # hard-fail: any gap is an error (exit 1)

CI (docs-ci.yml): report mode during backfill, --strict once coverage is complete.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Kept in sync with app/src/config.ts CANONICAL_DOCS_BASE.
CANONICAL_DOCS_BASE = "https://offthepace.mintlify.app/"

FEATURES_DIR = ROOT / "app" / "src" / "features"
APP_SRC = ROOT / "app" / "src"
DOCS_APP = ROOT / "docs" / "app"
DOCS_JSON = ROOT / "docs" / "docs.json"
ROUTES_TS = APP_SRC / "nav" / "routes.ts"

APP_TAB_NAME = "App"

# Query Lab is the one bespoke shipped feature: not a FeaturePage, no methodologyHref.
QUERY_LAB_SLUG = "query-lab"

# methodologyHref is a template literal: `${CANONICAL_DOCS_BASE}/app/<dir>`. Capture the
# quote char (backtick / single / double) and the body, then resolve the constant.
HREF_RE = re.compile(r"methodologyHref\s*=\s*([`'\"])(.*?)\1", re.DOTALL)


def _resolve_href(raw: str) -> str:
    return raw.replace("${CANONICAL_DOCS_BASE}", CANONICAL_DOCS_BASE)

# Required section headings flexible enough for the three pre-existing pages and the
# canonical _TEMPLATE.mdx layout.
SECTION_CHECKS: list[tuple[str, re.Pattern]] = [
    ("a \"What … shows\" intro", re.compile(r"(?im)^#{2,3}\s+what\b")),
    ("a usage/interpretation section", re.compile(r"(?im)^#{2,3}\s+(how to|reading|inputs)\b")),
    ("a Data source section", re.compile(r"(?im)^#{2,3}\s+data sources?\b")),
]
FRONTMATTER_KEYS = ("title", "sidebarTitle", "description")


def feature_dirs() -> list[tuple[str, str]]:
    """Return (dir_name, methodologyHref) for every features/<dir> that exports one."""
    out = []
    for meth in sorted(FEATURES_DIR.glob("*/methodology.tsx")):
        text = meth.read_text(encoding="utf-8", errors="ignore")
        m = HREF_RE.search(text)
        out.append((meth.parent.name, _resolve_href(m.group(2)) if m else ""))
    return out


def nav_app_pages() -> set[str]:
    """The page slugs registered under any group within the App tab in docs.json."""
    data = json.loads(DOCS_JSON.read_text(encoding="utf-8"))
    found: set[str] = set()

    def collect_pages(node):
        """Recursively collect all page slugs from a node."""
        if isinstance(node, dict):
            for p in node.get("pages", []):
                if isinstance(p, str):
                    found.add(p)
                elif isinstance(p, dict):
                    collect_pages(p)
            for v in node.values():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            collect_pages(item)
        elif isinstance(node, list):
            for item in node:
                collect_pages(item)

    # Find the App tab and collect all pages within it.
    for tab_entry in data.get("navigation", {}).get("tabs", []):
        if tab_entry.get("tab") == APP_TAB_NAME:
            for group in tab_entry.get("groups", []):
                collect_pages(group)
            break

    return found


def frontmatter_ok(text: str) -> list[str]:
    """Return the list of frontmatter keys that are missing or empty."""
    fm = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    block = fm.group(1) if fm else ""
    missing = []
    for key in FRONTMATTER_KEYS:
        m = re.search(rf"(?m)^{key}:\s*(.+?)\s*$", block)
        if not m or not m.group(1).strip().strip("\"'"):
            missing.append(key)
    return missing


def page_problems(slug: str) -> list[str]:
    """Structural problems with docs/app/<slug>.mdx (assumes the file exists)."""
    text = (DOCS_APP / f"{slug}.mdx").read_text(encoding="utf-8", errors="ignore")
    problems = []
    missing_fm = frontmatter_ok(text)
    if missing_fm:
        problems.append(f"frontmatter missing/empty: {', '.join(missing_fm)}")
    for label, pat in SECTION_CHECKS:
        if not pat.search(text):
            problems.append(f"missing {label}")
    return problems


def imported_somewhere(dir_name: str) -> bool:
    """True if features/<dir> is imported anywhere under app/src (i.e. it is navigable)."""
    needle = f"features/{dir_name}'"
    for path in APP_SRC.rglob("*.ts*"):
        if f"features/{dir_name}/" in path.as_posix():
            continue  # skip the feature's own files
        if needle in path.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


def shipped_featureid_route_count() -> int:
    """Count routes in nav/routes.ts that carry a featureId and are not shipped: false."""
    count = 0
    for line in ROUTES_TS.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "featureId:" in line and "shipped: false" not in line:
            count += 1
    return count


def audit() -> tuple[list[str], list[str], int, int]:
    """Return (errors, ok_lines, documented_count, total_feature_dirs)."""
    errors: list[str] = []
    ok: list[str] = []

    nav_pages = nav_app_pages()
    dirs = feature_dirs()

    # ── 1. Per-feature coverage ──────────────────────────────────────────────
    documented = 0
    for dir_name, href in dirs:
        slug_path = f"app/{dir_name}"
        expected_href = f"{CANONICAL_DOCS_BASE}/app/{dir_name}"
        feature_errs: list[str] = []

        page = DOCS_APP / f"{dir_name}.mdx"
        if not page.exists():
            feature_errs.append("no docs/app/%s.mdx" % dir_name)
        else:
            feature_errs.extend(page_problems(dir_name))

        if slug_path not in nav_pages:
            feature_errs.append(f"'{slug_path}' not in docs.json App tab")

        if href != expected_href:
            feature_errs.append(f"methodologyHref is '{href or '∅'}', expected '{expected_href}'")

        if not imported_somewhere(dir_name):
            feature_errs.append("feature dir is not imported anywhere under app/src (orphan)")

        if feature_errs:
            for e in feature_errs:
                errors.append(f"[{dir_name}] {e}")
        else:
            documented += 1
            ok.append(f"{dir_name}")

    # ── 2. Query Lab exception ───────────────────────────────────────────────
    ql_page = DOCS_APP / f"{QUERY_LAB_SLUG}.mdx"
    if not ql_page.exists():
        errors.append(f"[{QUERY_LAB_SLUG}] no docs/app/{QUERY_LAB_SLUG}.mdx (bespoke shipped feature)")
    elif f"app/{QUERY_LAB_SLUG}" not in nav_pages:
        errors.append(f"[{QUERY_LAB_SLUG}] 'app/{QUERY_LAB_SLUG}' not in docs.json App tab")
    else:
        ok.append(QUERY_LAB_SLUG)

    # ── 3. Count reconciliation against routes.ts ────────────────────────────
    shipped_routes = shipped_featureid_route_count()
    if shipped_routes != len(dirs):
        errors.append(
            f"[reconcile] {shipped_routes} shipped featureId routes in nav/routes.ts "
            f"but {len(dirs)} feature dirs export a methodologyHref (drift)"
        )
    else:
        ok.append(f"reconcile: {shipped_routes} shipped routes == {len(dirs)} feature dirs")

    return errors, ok, documented, len(dirs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--strict", action="store_true", help="Treat any gap as an error (exit 1)")
    args = parser.parse_args(argv)

    print("── app_docs_audit: feature-page coverage ───────────────────────────────")
    errors, ok, documented, total = audit()

    for line in ok:
        print(f"  OK    {line}")
    print(f"  ── {documented}/{total} feature pages complete ──")

    if errors:
        print()
        for e in errors:
            level = "ERROR" if args.strict else "TODO "
            print(f"  {level} {e}")

    print()
    if errors and args.strict:
        print(f"app_docs_audit FAILED-{len(errors)} gap(s)")
        return 1
    if errors:
        print(
            f"app_docs_audit REPORT-{len(errors)} gap(s) remaining "
            f"(report mode; run --strict to gate)"
        )
        return 0
    print("app_docs_audit PASSED-every shipped feature is documented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
