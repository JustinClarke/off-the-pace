"""docs_facts: README dbt model/test counts must equal the dbt manifest."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import docs_facts  # noqa: E402


def _manifest(tmp_path, models, tests):
    nodes = {f"model.off_the_pace.m{i}": {"resource_type": "model", "package_name": "off_the_pace"} for i in range(models)}
    nodes.update({f"test.off_the_pace.t{i}": {"resource_type": "test", "package_name": "off_the_pace"} for i in range(tests)})
    nodes["model.dbt_utils.x"] = {"resource_type": "model", "package_name": "dbt_utils"}
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"nodes": nodes}))
    return p


def test_counts_ignore_other_packages(tmp_path):
    assert docs_facts.manifest_counts(_manifest(tmp_path, 3, 5)) == {"dbt models": 3, "dbt tests": 5}


def test_readme_agreeing_with_manifest_passes(tmp_path):
    m = _manifest(tmp_path, 99, 1433)
    texts = {"README.md": "**99** dbt models\nTransform (99 models, 1433 tests)\n"}
    assert docs_facts.check_manifest(texts, m, True, True) == []


def test_stale_readme_fails(tmp_path):
    m = _manifest(tmp_path, 99, 1433)
    texts = {"README.md": "Transform (94 models, 1320 tests)\n"}
    errs = docs_facts.check_manifest(texts, m, True, True)
    assert len(errs) == 2 and "94" in errs[0] and "1320" in errs[1]


def test_missing_manifest_skips_unless_required(tmp_path):
    missing = tmp_path / "nope.json"
    assert docs_facts.check_manifest({}, missing, False, True) == []
    assert docs_facts.check_manifest({}, missing, True, True)
