"""
overview_docs_facts.py   Drift gate for the Overview tab's "by the numbers" snippet.

The Overview tab's headline stats (seasons, races, dbt models/tests, ML models, app
features) are generated, never hand-typed in prose (CONVENTIONS "Hand-written counts in
prose"). This script derives every figure from a real source on disk and regenerates
docs/snippets/overview-numbers.mdx; CI fails if the committed snippet drifts.

Sources (no figure is invented or duplicated as a second literal):
  - seasons / races   <- docs/snippets/bronze-coverage.mdx (itself gated by
                         ingestion_docs_facts.py against live Bronze data)
  - dbt models/tests, \
    ML models/tests    <- the same TARGETED patterns docs_facts.py already reconciles
                         against README.md, so there is exactly one place those four
                         numbers are asserted true
  - app features      <- count of app/src/features/*/methodology.tsx (the same primary
                         key app_docs_audit.py uses for shipped-feature coverage)

Usage:
  python scripts/overview_docs_facts.py          # check; exits 1 on drift
  python scripts/overview_docs_facts.py --write   # regenerate the snippet in place

CI (docs-ci.yml):
  python scripts/overview_docs_facts.py
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNIPPET = ROOT / "docs" / "snippets" / "overview-numbers.mdx"
BRONZE_COVERAGE = ROOT / "docs" / "snippets" / "bronze-coverage.mdx"
README = ROOT / "README.md"
FEATURES_DIR = ROOT / "app" / "src" / "features"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docs_facts import TARGETED  # noqa: E402  (reuse the one place these four numbers are asserted)

SEASON_ROW = re.compile(r"^\|\s*(\d{4})\s*\|\s*(\d+)\s*")


def _bronze_seasons_and_races() -> tuple[int, int, int, int]:
    """Return (season_count, race_count, first_season, last_season) from the coverage table."""
    text = BRONZE_COVERAGE.read_text(encoding="utf-8")
    seasons: list[int] = []
    races = 0
    for line in text.splitlines():
        m = SEASON_ROW.match(line)
        if not m:
            continue
        seasons.append(int(m.group(1)))
        races += int(m.group(2))
    if not seasons:
        raise ValueError(f"no season rows found in {BRONZE_COVERAGE.relative_to(ROOT)}")
    return len(seasons), races, min(seasons), max(seasons)


def _targeted_count(label: str) -> int:
    text = README.read_text(encoding="utf-8", errors="ignore")
    for tlabel, pattern in TARGETED:
        if tlabel == label:
            found = pattern.findall(text)
            if not found:
                raise ValueError(f"README.md has no match for {label!r}")
            return int(found[0])
    raise ValueError(f"no TARGETED pattern named {label!r} in docs_facts.py")


def _app_feature_count() -> int:
    return len(list(FEATURES_DIR.glob("*/methodology.tsx")))


def generate() -> str:
    season_count, race_count, first_season, last_season = _bronze_seasons_and_races()
    dbt_models = _targeted_count("dbt models")
    dbt_tests = _targeted_count("dbt tests")
    ml_models = _targeted_count("ML models")
    feature_count = _app_feature_count()

    return f"""<CardGroup cols={{3}}>
  <Card title="{season_count} seasons" icon="calendar">
    {first_season}–{last_season} of F1 timing data ingested end to end.
  </Card>
  <Card title="{race_count} races" icon="flag">
    Every lap decomposed and verified against the additive identity.
  </Card>
  <Card title="{dbt_models} dbt models" icon="layers">
    {dbt_tests} tests enforce the pipeline on every build.
  </Card>
  <Card title="{ml_models} ML models" icon="brain">
    XGBoost trained, exported to ONNX, running live in the browser.
  </Card>
  <Card title="{feature_count} app features" icon="layout-dashboard">
    Interactive visualizations, zero server, sub-10ms queries.
  </Card>
  <Card title="0ms server" icon="server-off">
    DuckDB-Wasm + ONNX Runtime Web run the whole stack client-side.
  </Card>
</CardGroup>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="Regenerate the snippet in place instead of checking it")
    args = parser.parse_args(argv)

    print("── overview_docs_facts: by-the-numbers snippet ──────────────────────────────")
    fresh = generate()

    if args.write:
        SNIPPET.parent.mkdir(parents=True, exist_ok=True)
        SNIPPET.write_text(fresh, encoding="utf-8")
        print(f"  WROTE  {SNIPPET.relative_to(ROOT)}")
        return 0

    if not SNIPPET.exists():
        print(f"  ERROR  MISSING snippet: {SNIPPET.relative_to(ROOT)}")
        print("\noverview_docs_facts FAILED-run with --write to generate it")
        return 1

    committed = SNIPPET.read_text(encoding="utf-8")
    if committed != fresh:
        print(f"  ERROR  DRIFT: {SNIPPET.relative_to(ROOT)} does not match a fresh regeneration")
        print("  --- committed ---")
        print(committed)
        print("  --- fresh ---")
        print(fresh)
        print("\noverview_docs_facts FAILED-run with --write to refresh the snippet")
        return 1

    print(f"  OK   {SNIPPET.relative_to(ROOT)} matches a fresh regeneration")
    print("\noverview_docs_facts PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
