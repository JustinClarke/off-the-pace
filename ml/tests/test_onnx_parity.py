"""ONNX parity gate (the D1/R1 contract): each .bst and its .onnx must agree on a
NaN-bearing sample. Runs against whatever version is present (smoke in CI, v1 locally).

Combined tolerance atol=1e-5, rtol=1e-5-relative error (~1e-6) is the real fidelity
proof; see ml/src/export_onnx.py. A real conversion failure shows far larger diffs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ml.src import export_onnx as E
from ml.src import schema as S

MODELS_DIR = Path("ml/models")


def _present_version() -> str | None:
    # v6 = current production (v5's frame and cliff label, stint life moved to
    # survival:aft). v5…v1 onnx are kept for diffing and rollback; v3 and earlier have
    # different feature counts so are never really the parity target.
    # MODEL_VERSION_DEFAULT is tried first. Note the explicit list below must keep
    # naming every retained version: when MODEL_VERSION_DEFAULT moved v5 -> v6, v5 fell
    # out of this tuple entirely and the fallback silently skipped the rollback target.
    for version in (S.MODEL_VERSION_DEFAULT, "v5", "v4", "v3", "v2", "v1", "smoke"):
        if all((MODELS_DIR / f"{S.artefact_name(t, version)}.onnx").exists()
               for t in S.PRODUCTION_TARGETS):
            return version
    return None


VERSION = _present_version()
pytestmark = pytest.mark.skipif(
    VERSION is None, reason="no complete .onnx set (run `make ml-onnx` / export_onnx --all)")


@pytest.fixture(scope="module")
def sample():
    return E.nan_bearing_sample()


@pytest.mark.parametrize("target", [t.name for t in S.PRODUCTION_TARGETS])
def test_onnx_parity(target, sample):
    r = E.parity(target, VERSION, sample)
    assert r["pass"], (f"{target}: ONNX≠bst (abs={r['max_abs_diff']:.2e}, "
                       f"rel={r['max_rel_diff']:.2e})-do NOT loosen atol; escalate R1.")
