"""
transform_docs_facts.py   Drift gate for the Transform tab's test-inventory snippets.

The Transform tab's model/family counts and CI-test breakdown are generated, never
hand-typed in prose (CONVENTIONS "Hand-written counts in prose"). This script reads
transform/target/manifest.json (the dbt parse output) and transform/tests/README.md
(the authored category-and-status record for the 29 singular tests) and writes four
snippets under docs/snippets/:

  transform-inventory.mdx              headline CardGroup (models, families, test taxonomy)
  transform-inventory-structural.mdx   every model x its structural test count (339)
  transform-inventory-range-and-domain.mdx   every model x its range/categorical/pairwise count (75)
  transform-inventory-singular-tests.mdx     all 29 singular tests, grouped exactly as
                                              tests/README.md groups them, with
                                              Active/Placeholder status read off the
                                              dbt `placeholder` tag

CI fails if any committed snippet has drifted from a fresh regeneration.

Usage:
  python scripts/transform_docs_facts.py          # check; exits 1 on drift
  python scripts/transform_docs_facts.py --write   # regenerate the snippets in place

CI (docs-ci.yml):
  python scripts/transform_docs_facts.py
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "transform" / "target" / "manifest.json"
TESTS_README = ROOT / "transform" / "tests" / "README.md"

SNIPPET_HEADLINE = ROOT / "docs" / "snippets" / "transform-inventory.mdx"
SNIPPET_STRUCTURAL = ROOT / "docs" / "snippets" / "transform-inventory-structural.mdx"
SNIPPET_RANGE = ROOT / "docs" / "snippets" / "transform-inventory-range-and-domain.mdx"
SNIPPET_SINGULAR = ROOT / "docs" / "snippets" / "transform-inventory-singular-tests.mdx"

# Generic test kinds, grouped into the two CI Contract pages.
STRUCTURAL_KINDS = ["not_null", "unique", "unique_combination_of_columns"]
RANGE_KINDS = [
    "expect_column_values_to_be_between",
    "accepted_range",
    "expect_table_row_count_to_be_between",
    "accepted_values",
    "expect_column_pair_values_A_to_be_greater_than_B",
]

FAMILY_ORDER = [
    "staging",
    "reference",
    "physics",
    "pace-baselines",
    "skill",
    "residual",
    "strategy",
    "marts",
]

# Section headings in transform/tests/README.md, in the order singular tests are grouped.
README_SECTIONS = [
    ("## Identity-Closure Tests", "Identity-Closure"),
    ("## Domain Constraint Tests", "Domain Constraint"),
    ("## Regression Gates", "Regression Gate"),
]
README_ROW_RE = re.compile(r"^\|\s*`(?P<file>assert_[a-zA-Z0-9_]+\.sql)`")


def family_label(family: str) -> str:
    return family.replace("-", " ").title()


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        print(f"ERROR: manifest not found at {MANIFEST_PATH}")
        print("Run: cd transform && dbt parse --profiles-dir profiles")
        sys.exit(1)
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def model_nodes(manifest: dict) -> dict[str, dict]:
    return {
        k: v
        for k, v in manifest["nodes"].items()
        if v["resource_type"] == "model" and v.get("package_name") == "off_the_pace"
    }


def family_of(node: dict) -> str:
    family = (node.get("meta") or {}).get("family")
    if not family:
        raise ValueError(f"model {node['name']} has no meta.family (transform/models/**/schema.yml)")
    return family


def generic_tests(manifest: dict) -> list[dict]:
    return [v for v in manifest["nodes"].values() if v["resource_type"] == "test" and v.get("test_metadata")]


def singular_tests(manifest: dict) -> list[dict]:
    return [
        v
        for v in manifest["nodes"].values()
        if v["resource_type"] == "test" and not v.get("test_metadata") and v.get("package_name") == "off_the_pace"
    ]


def guarded_model_names(test_node: dict, nodes: dict) -> list[str]:
    deps = test_node.get("depends_on", {}).get("nodes", [])
    return sorted(nodes[d]["name"] for d in deps if d in nodes and nodes[d]["resource_type"] == "model")


def parse_readme_categories() -> dict[str, str]:
    """file.sql -> category label, read off the README's own section headings."""
    text = TESTS_README.read_text(encoding="utf-8")
    lines = text.splitlines()
    categories: dict[str, str] = {}
    current_label: str | None = None
    for line in lines:
        for heading, label in README_SECTIONS:
            if line.strip() == heading:
                current_label = label
                break
        m = README_ROW_RE.match(line)
        if m and current_label:
            categories[m.group("file")] = current_label
    return categories


def seed_nodes(manifest: dict) -> dict[str, dict]:
    return {
        k: v
        for k, v in manifest["nodes"].items()
        if v["resource_type"] == "seed" and v.get("package_name") == "off_the_pace"
    }


def node_test_counts(uid: str, generic: list[dict], kinds: list[str]) -> dict[str, int]:
    counts = {k: 0 for k in kinds}
    for t in generic:
        if uid not in t.get("depends_on", {}).get("nodes", []):
            continue
        kind = t["test_metadata"]["name"]
        if kind in counts:
            counts[kind] += 1
    return counts


def generate_headline(manifest: dict) -> str:
    nodes = manifest["nodes"]
    models = model_nodes(manifest)
    generic = generic_tests(manifest)
    singular = singular_tests(manifest)

    family_counts: dict[str, int] = {f: 0 for f in FAMILY_ORDER}
    for node in models.values():
        family_counts[family_of(node)] += 1

    kind_counts: dict[str, int] = {}
    for t in generic:
        kind = t["test_metadata"]["name"]
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    structural_n = sum(kind_counts.get(k, 0) for k in STRUCTURAL_KINDS)
    range_n = sum(kind_counts.get(k, 0) for k in RANGE_KINDS)

    categories = parse_readme_categories()
    singular_by_category: dict[str, int] = {"Identity-Closure": 0, "Domain Constraint": 0, "Regression Gate": 0}
    placeholder_n = 0
    for t in singular:
        file = Path(t["path"]).name
        label = categories.get(file)
        if label is None:
            raise ValueError(f"singular test {file} has no category in {TESTS_README.relative_to(ROOT)}")
        singular_by_category[label] += 1
        if "placeholder" in t.get("tags", []):
            placeholder_n += 1

    total_models = len(models)
    total_tests = len(generic) + len(singular)
    intermediate_n = sum(family_counts[f] for f in ["physics", "pace-baselines", "skill", "residual", "strategy"])

    family_lines = "\n".join(
        f"  <Card title=\"{family_counts[f]} {family_label(f)}\" icon=\"layers\" href=\"/transform/families/{f}\" />"
        for f in FAMILY_ORDER
    )

    return f"""<CardGroup cols={{3}}>
  <Card title="{total_models} models" icon="database">
    Staging ({family_counts['staging']}) + Reference ({family_counts['reference']}) + {intermediate_n}
    intermediate models across 5 families + Marts ({family_counts['marts']}).
  </Card>
  <Card title="{total_tests} tests" icon="shield-check">
    {len(generic)} generic column contracts + {len(singular)} hand-written mathematical
    assertions, every build.
  </Card>
  <Card title="{structural_n} structural" icon="key">
    `not_null`, `unique`, and unique-combination tests guard every model's grain.
  </Card>
  <Card title="{range_n} range &amp; domain" icon="ruler">
    Bounded shares, honest envelopes, enum integrity, and cross-column monotonicity.
  </Card>
  <Card title="{singular_by_category['Identity-Closure']} identity-closure" icon="equal">
    Additive identities and shrinkage bounds that close to tolerance on every lap.
  </Card>
  <Card title="{singular_by_category['Domain Constraint']} domain + {singular_by_category['Regression Gate']} regression" icon="check-check">
    Physical/statistical invariants, plus baseline-comparison gates on headline statistics.
    {placeholder_n} singular tests are placeholders ({"`SELECT 1 WHERE FALSE`"}), wired up once
    their upstream model lands.
  </Card>
</CardGroup>

<CardGroup cols={{4}}>
{family_lines}
</CardGroup>
"""


def generate_kind_table(manifest: dict, kinds: list[str]) -> str:
    nodes = manifest["nodes"]
    models = model_nodes(manifest)
    seeds = seed_nodes(manifest)
    generic = generic_tests(manifest)

    header = "| Model | Family | " + " | ".join(f"`{k}`" for k in kinds) + " | Total |"
    sep = "|---|---|" + "---|" * len(kinds) + "---|"
    lines = [header, sep]

    totals = {k: 0 for k in kinds}
    grand_total = 0

    def emit_row(name: str, family: str, uid: str) -> None:
        nonlocal grand_total
        counts = node_test_counts(uid, generic, kinds)
        row_total = sum(counts.values())
        if row_total == 0:
            return
        grand_total += row_total
        for k in kinds:
            totals[k] += counts[k]
        cells = " | ".join(str(counts[k]) if counts[k] else " " for k in kinds)
        lines.append(f"| `{name}` | {family} | {cells} | {row_total} |")

    ordered = sorted(models.values(), key=lambda n: (FAMILY_ORDER.index(family_of(n)), n["name"]))
    for node in ordered:
        emit_row(node["name"], family_label(family_of(node)), node["unique_id"])

    # The two reference seeds carry their own column tests (validating the raw fitted
    # coefficients), outside the 60-model DAG but still part of the Reference family's input.
    for seed in sorted(seeds.values(), key=lambda n: n["name"]):
        emit_row(seed["name"], "Reference (seed)", seed["unique_id"])

    totals_cells = " | ".join(str(totals[k]) for k in kinds)
    lines.append(f"| **Total** |  | {totals_cells} | **{grand_total}** |")
    return "\n".join(lines) + "\n"


def generate_singular_table(manifest: dict) -> str:
    nodes = manifest["nodes"]
    singular = singular_tests(manifest)
    categories = parse_readme_categories()

    by_file = {Path(t["path"]).name: t for t in singular}
    lines = ["| Category | Test | Status | Guarded model(s) |", "|---|---|---|---|"]

    for heading, label in README_SECTIONS:
        files_in_category = sorted(f for f, lbl in categories.items() if lbl == label)
        for file in files_in_category:
            t = by_file.get(file)
            if t is None:
                raise ValueError(f"{TESTS_README.relative_to(ROOT)} lists {file}, not found in manifest singular tests")
            status = "Placeholder" if "placeholder" in t.get("tags", []) else "Active"
            guarded = ", ".join(f"`{m}`" for m in guarded_model_names(t, nodes)) or " "
            lines.append(f"| {label} | `{file}` | {status} | {guarded} |")

    missing = set(by_file) - set(categories)
    if missing:
        raise ValueError(f"singular tests with no category in {TESTS_README.relative_to(ROOT)}: {sorted(missing)}")

    return "\n".join(lines) + "\n"


def generate(manifest: dict) -> dict[Path, str]:
    return {
        SNIPPET_HEADLINE: generate_headline(manifest),
        SNIPPET_STRUCTURAL: generate_kind_table(manifest, STRUCTURAL_KINDS),
        SNIPPET_RANGE: generate_kind_table(manifest, RANGE_KINDS),
        SNIPPET_SINGULAR: generate_singular_table(manifest),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="Regenerate the snippets in place instead of checking them")
    args = parser.parse_args(argv)

    print("── transform_docs_facts: test-inventory snippets ────────────────────────────")
    manifest = load_manifest()
    fresh = generate(manifest)

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
            print(f"  OK   {path.relative_to(ROOT)} matches a fresh regeneration")

    if drift:
        print("\ntransform_docs_facts FAILED-run with --write to refresh the snippets")
        return 1

    print("\ntransform_docs_facts PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
