"""
Coefficient fitting pipeline for Off the Pace transform layer.

Entry points:
    python -m tasks.coefficients.fit_compound_cliff [--dry-run] [--seasons 2023]
    python -m tasks.coefficients.fit_weight_penalty [--dry-run]
    python -m tasks.coefficients.check_freshness
    python -m tasks.coefficients.seed_writer promote --all --confirm

All modules read from the dbt-built dev.duckdb warehouse (../data/dev.duckdb).
Output goes to seeds/_pending/ for human review before promotion to seeds/.
"""
