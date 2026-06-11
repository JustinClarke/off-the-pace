<!--
Thanks for contributing to off-the-pace. Keep the analytics invariants green 
this template's checklist mirrors the CI gates (dbt / ml / docs / app).
-->

## Summary

<!-- What does this change and why? Link any issue or ADR (.github/adr/DECISIONS.md). -->

## Type of change

- [ ] Data pipeline (`transform/`, `ingestion/`)
- [ ] ML (`ml/`)
- [ ] Web app (`app/`)
- [ ] Docs (`docs/`)
- [ ] CI / infra / tooling
- [ ] Other

## Checklist

- [ ] CI is green (dbt, ml, docs, and app gates as applicable)
- [ ] Analytics invariants preserved additive identity, **byte-stability oracle**
      (`make lint-oracle-snapshot` regenerated *only* if model output changed intentionally),
      ML leakage guards, ONNX↔booster parity
- [ ] dbt `schema.yml` descriptions added/updated for any new model or column
- [ ] Reference docs regenerated if the warehouse changed (`python scripts/build_reference.py`)
- [ ] Headline-count facts reconciled (`python scripts/docs_facts.py`)
- [ ] An ADR added/updated if this changes an architectural decision

## Verification

<!-- How did you verify this? Tests added, CDP/headless checks, screenshots for UI. -->

## Deploy impact

<!-- Does this touch the CDN export, manifest, or Firebase deploy? Remember:
     no commits/pushes/deploys without explicit approval. -->
