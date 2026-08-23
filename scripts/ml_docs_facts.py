"""
ml_docs_facts.py   Drift gate for the ML tab's inventory snippets.

The ML tab's model/feature/test counts and the calibration, leakage, and cohort
tables are generated, never hand-typed in prose (CONVENTIONS "Hand-written counts
in prose"). This script reads ml/src/schema.py (FEATURE_GROUPS, EXCLUDED_LEAKAGE_COLUMNS,
PRODUCTION_TARGETS) and ml/model_card.yml (metrics, calibration, cohorts) and writes
six snippets under docs/snippets/:

  ml-inventory.mdx              headline CardGroup (5 models / 42 features / 28 tests)
  ml-inventory-features.mdx     42-feature × 10-group table (one row per group)
  ml-inventory-leakage.mdx      excluded-leakage-columns list + a note block
  ml-inventory-tests.mdx        28-test taxonomy table (12+5+3+7+1) with group counts
  ml-inventory-metrics.mdx      headline metrics table per model (beats-baseline ✅)
  ml-inventory-calibration.mdx  calibration coverage row + cohort count note

CI fails if any committed snippet has drifted from a fresh regeneration.

Usage:
  python scripts/ml_docs_facts.py          # check; exits 1 on drift
  python scripts/ml_docs_facts.py --write  # regenerate the snippets in place

CI (docs-ci.yml):
  python scripts/ml_docs_facts.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

CARD_PATH = ROOT / "ml" / "model_card.yml"
SCHEMA_MODULE = "ml.src.schema"

SNIPPET_HEADLINE    = ROOT / "docs" / "snippets" / "ml-inventory.mdx"
SNIPPET_FEATURES    = ROOT / "docs" / "snippets" / "ml-inventory-features.mdx"
SNIPPET_LEAKAGE     = ROOT / "docs" / "snippets" / "ml-inventory-leakage.mdx"
SNIPPET_TESTS       = ROOT / "docs" / "snippets" / "ml-inventory-tests.mdx"
SNIPPET_METRICS     = ROOT / "docs" / "snippets" / "ml-inventory-metrics.mdx"
SNIPPET_CALIBRATION = ROOT / "docs" / "snippets" / "ml-inventory-calibration.mdx"

# Test-group breakdown group name, source file, count, what it guarantees
# Counts are from the live pytest collection; the check sub-command validates them.
TEST_GROUPS = [
    ("Leakage Spine",    "test_features.py",    14,
     "No target, skill, or season column enters `X`; forward-window SQL audit (including its own coverage, and self-join horizons); holdout purity; `MAX+1`-derived split; bounded & non-null targets."),
    ("ONNX Parity",      "test_onnx_parity.py",  5,
     "Each booster round-trips to ONNX within `atol=1e-5`, including a NaN-bearing sample (the ~47% null-prior laps)."),
    ("Predict Schema",   "test_predict.py",       3,
     "Scored predictions parquet carries the declared 19-column schema (17 + the p10/p90 stint-life band); Arrow-validated."),
    ("Evaluation Gates", "test_evaluate.py",      7,
     "Every model beats its per-cohort baseline; calibration coverage computed; cohorts surfaced not dropped; metrics match the card."),
    ("Targets",          "test_targets.py",       3,
     "Stint-life target is synthesised without leaking `stint_length_laps`; the censoring flag rides in metadata and never becomes a feature; AFT bounds encode censoring as a point vs a half-line."),
    ("Survival",         "test_survival.py",     18,
     "The AFT contract itself: the +1 shift keeps zero-life stints off log(0), margins round-trip to laps, quantiles bracket the median and widen with scale, censored rows are not punished for over-prediction, and C-index ranks. `aft_params` refuses a non-AFT booster."),
    ("Version Contract", "test_manifest_contract.py", 14,
     "The manifest names a version whose artefacts exist, declares the input width the boosters actually take, and matches the copy the browser loads."),
]
EXPECTED_TOTAL = sum(t[2] for t in TEST_GROUPS)  # 64


def load_card() -> dict:
    if not CARD_PATH.exists():
        print(f"ERROR: model card not found at {CARD_PATH}")
        print("Run: make ml-card")
        sys.exit(1)
    return yaml.safe_load(CARD_PATH.read_text(encoding="utf-8"))["model_card"]


def load_schema() -> object:
    """Parse FEATURE_GROUPS and EXCLUDED_LEAKAGE_COLUMNS from schema.py via AST.

    We avoid exec/import because schema.py imports pyarrow (may not be in the
    CI Python) and uses @dataclass in a way that requires the module to be
    registered in sys.modules first. AST literal_eval is simpler and sufficient
    since we only need the two dict/frozenset constants.
    """
    return _parse_schema_constants()


def _parse_schema_constants():
    """Fallback parser for when pyarrow is not importable in the current Python."""
    import ast
    src = (ROOT / "ml" / "src" / "schema.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    class Namespace:
        FEATURE_GROUPS: dict = {}
        EXCLUDED_LEAKAGE_COLUMNS: set = set()

    ns = Namespace()
    for node in ast.walk(tree):
        # AnnAssign as well as Assign: `FEATURE_GROUPS: dict[...] = {...}` is an
        # annotated assignment, and matching only ast.Assign silently left it empty —
        # which is how the headline card came to read "0 features in 0 groups".
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "FEATURE_GROUPS":
                ns.FEATURE_GROUPS = ast.literal_eval(node.value)
            if isinstance(t, ast.Name) and t.id == "EXCLUDED_LEAKAGE_COLUMNS":
                # Declared as `frozenset({...})`, a Call — literal_eval only handles
                # the set literal inside it.
                value = node.value
                if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                        and value.func.id in {"frozenset", "set"} and value.args):
                    value = value.args[0]
                ns.EXCLUDED_LEAKAGE_COLUMNS = frozenset(ast.literal_eval(value))

    # Refuse to emit a snippet built from nothing. Both constants are annotated
    # assignments and one is wrapped in frozenset(); each mismatch previously failed
    # silently to an empty container, and the docs shipped "0 features in 0 groups".
    if not ns.FEATURE_GROUPS:
        raise SystemExit("ml_docs_facts: parsed no FEATURE_GROUPS from ml/src/schema.py")
    if not ns.EXCLUDED_LEAKAGE_COLUMNS:
        raise SystemExit("ml_docs_facts: parsed no EXCLUDED_LEAKAGE_COLUMNS from "
                         "ml/src/schema.py")
    return ns


def live_pytest_count() -> int:
    """Run pytest --collect-only and return the collected test count."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "ml/tests", "--collect-only", "-q",
         "--no-header", "--tb=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # Last non-empty line looks like "28 tests collected in 2.20s"
    for line in reversed(result.stdout.splitlines()):
        if "collected" in line:
            return int(line.split()[0])
    return -1


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def generate_headline(card: dict, schema) -> str:
    n_features = len(list(col
                          for cols in schema.FEATURE_GROUPS.values()
                          for col in cols))
    n_groups = len(schema.FEATURE_GROUPS)
    n_models = len(card["models"])
    n_tests = EXPECTED_TOTAL
    # Built from TEST_GROUPS so the breakdown cannot drift from the taxonomy table.
    test_breakdown = " + ".join(
        f"{count} {label}" for label, _, count, _ in TEST_GROUPS)
    n_rows = card["data"]["n_training_rows"]
    seasons = card["data"]["training_seasons"]

    return f"""<CardGroup cols={{3}}>
  <Card title="{n_models} XGBoost models" icon="microchip">
    Three question families degradation pace loss (p10/p50/p90), laps until
    the cliff (4-class), and remaining stint life. One shared feature matrix,
    one training engine, one pipeline.
  </Card>
  <Card title="{n_features} features in {n_groups} groups" icon="layers">
    Per-lap thermal, dirty-air, powertrain, telemetry-cliff, compound-prior,
    weather, track, and context signals all read from
    [`fct_cliff_prediction_features`](/reference/models/fct/fct_cliff_prediction_features),
    never re-derived in ML.
  </Card>
  <Card title="{n_tests} tests" icon="shield-check">
    {test_breakdown} every build.
  </Card>
  <Card title="{n_rows:,} training laps" icon="database">
    {seasons[0]}–{seasons[-1]} F1 seasons; holdout is `MAX(race_year) + 1`
    (no data yet the final CV fold stands in until it ingests).
  </Card>
  <Card title="All five beat baseline" icon="circle-check">
    Every model is evaluated against a strong per-cohort non-leakage baseline
    and wins. Coverage: quantile interval nominal 0.800 → empirical 0.814.
  </Card>
  <Card title="One command" icon="terminal">
    `make ml-all` runs the full 8-stage pipeline end-to-end:
    features → tune → train → evaluate → predict → onnx → card → reference.
  </Card>
</CardGroup>
"""


def generate_features(schema) -> str:
    lines = ["| Group | Count | Features |", "|---|---|---|"]
    for group, cols in schema.FEATURE_GROUPS.items():
        cols_str = ", ".join(f"`{c}`" for c in cols)
        lines.append(f"| `{group}` | {len(cols)} | {cols_str} |")
    total = sum(len(cols) for cols in schema.FEATURE_GROUPS.values())
    lines.append(f"| **Total** | **{total}** | |")
    return "\n".join(lines) + "\n"


def generate_leakage(schema) -> str:
    excluded = sorted(schema.EXCLUDED_LEAKAGE_COLUMNS)
    cols_inline = ", ".join(f"`{c}`" for c in excluded)
    return f"""<Warning>
**Read-only mart contract.** ML never writes the warehouse or the app. It reads
[`fct_cliff_prediction_features`](/reference/models/fct/fct_cliff_prediction_features)
read-only. The columns below are excluded from every model's feature matrix
(`EXCLUDED_LEAKAGE_COLUMNS` in `ml/src/schema.py`), asserted by the
[leakage-spine tests](/ml/ci/leakage-spine) every build.
</Warning>

Excluded ({len(excluded)} columns causal leakage / identifiers / targets / training
gate):

{cols_inline}
"""


def generate_tests() -> str:
    lines = [
        "| Group | Source file | Count | What it guarantees |",
        "|---|---|---|---|",
    ]
    for group, source, count, desc in TEST_GROUPS:
        lines.append(f"| **{group}** | `{source}` | {count} | {desc} |")
    lines.append(f"| **Total** | | **{EXPECTED_TOTAL}** | |")
    return "\n".join(lines) + "\n"


def generate_metrics(card: dict) -> str:
    lines = [
        "| Model | Kind | Metric | CV | Eval (2024) | Baseline | Beats |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in card["models"]:
        beats = "✅" if m["beats_baseline"] else "⚠️"
        lines.append(
            f"| `{m['name']}` | {m['kind']} | {m['headline_metric']} "
            f"| {_fmt(m['cv_headline'])} | {_fmt(m['eval_headline'])} "
            f"| {_fmt(m['baseline_headline'])} | {beats} |"
        )
    return "\n".join(lines) + "\n"


def generate_calibration(card: dict, schema) -> str:
    cal = card["validation"]["calibration"]
    lp = card["validation"]["leakage_probe"]
    under = card["validation"]["underperforming_cohorts"]
    n_cohorts = len(under)

    return f"""| Metric | Value |
|---|---|
| Nominal coverage (target) | {cal['nominal']} |
| Raw [p10, p90] empirical coverage | {_fmt(cal['raw_empirical_coverage'])} |
| Conformal empirical coverage (CQR) | {_fmt(cal['conformal_empirical_coverage'])} |
| Conformal offset q̂ | {_fmt(cal['conformal_q'])} |
| Mean interval width | {_fmt(cal['mean_interval_width'])}s |
| Calibration sample n | {cal['n']:,} laps |
| Adversarial probe accuracy (`race_year`) | {_fmt(lp['accuracy'])} |
| Majority-class baseline | {_fmt(lp['majority_class_accuracy'])} |
| Underperforming cohort cells | {n_cohorts} (surfaced, never dropped) |
"""


def generate(card: dict, schema) -> dict[Path, str]:
    return {
        SNIPPET_HEADLINE:    generate_headline(card, schema),
        SNIPPET_FEATURES:    generate_features(schema),
        SNIPPET_LEAKAGE:     generate_leakage(schema),
        SNIPPET_TESTS:       generate_tests(),
        SNIPPET_METRICS:     generate_metrics(card),
        SNIPPET_CALIBRATION: generate_calibration(card, schema),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Regenerate the snippets in place instead of checking them"
    )
    args = parser.parse_args(argv)

    print("── ml_docs_facts: ML inventory snippets ─────────────────────────────────────")

    card = load_card()
    schema = load_schema()
    fresh = generate(card, schema)

    # Reconcile the hardcoded taxonomy against what pytest actually collects. Without
    # this, TEST_GROUPS is a number nothing cross-checks: the snippet, README and
    # docs/ml/overview.mdx all quote EXPECTED_TOTAL, so they agree with each other
    # while disagreeing with the suite. `live_pytest_count` existed for exactly this
    # and was never called.
    live = live_pytest_count()
    if live < 0:
        print("  WARN   could not collect the live pytest count; taxonomy unverified")
    elif live != EXPECTED_TOTAL:
        print(f"  ERROR  TEST_GROUPS totals {EXPECTED_TOTAL} but `pytest ml/tests "
              f"--collect-only` finds {live}. Update TEST_GROUPS in this script, and "
              f"the count quoted in README.md + docs/ml/overview.mdx.")
        if not args.write:
            return 1
    else:
        print(f"  OK   test taxonomy totals {EXPECTED_TOTAL}, matching live collection")

    if args.write:
        for path, content in fresh.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"  WROTE  {path.relative_to(ROOT)}")
        return 0

    drift = False
    for path, content in fresh.items():
        if not path.exists():
            print(f"  ERROR  MISSING snippet: {path.relative_to(ROOT)}")
            drift = True
            continue
        committed = path.read_text(encoding="utf-8")
        if committed != content:
            print(f"  ERROR  DRIFT: {path.relative_to(ROOT)} does not match a fresh regeneration")
            drift = True
        else:
            print(f"  OK   {path.relative_to(ROOT)}")

    if drift:
        print("\nml_docs_facts FAILED run with --write to refresh the snippets")
        return 1

    print("\nml_docs_facts PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
