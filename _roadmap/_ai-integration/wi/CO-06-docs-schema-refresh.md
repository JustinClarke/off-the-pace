# CO-06 — Docs and schema text: the removed 2018 offset, the old severity method

**Group:** D carry-over · **Depends on:** `CO-02` · **Blocker:** none.

**Sources:** `transform/models/marts/schema.yml`, `transform/models/intermediate/schema.yml`, `docs/reference/models/`.

**Audit finding:** 9 (schema and generated docs). The SQL and macro headers change with CO-02's code.

---

## What exists today (checked 2026-10-15)

The 2018 +0.37 s pure-rating offset was removed (`dbt_project.yml:244` is `{}`), but five `schema.yml` descriptions still state it, not the two the audit named:

- `transform/models/marts/schema.yml` lines 1743, 2058, 2244
- `transform/models/intermediate/schema.yml` lines 3576, 3737
- generated pages under `docs/reference/models/` (`fct_driver_isolation_*`, `int_driver_isolation_lap_values`, `index.md`)

Any description of severity as a pre/post window-mean difference is also stale once CO-02 lands.

## Method

1. Rewrite the descriptions to match what the code does after CO-02.
2. Regenerate the reference docs with the docs build. Do not hand-edit generated pages.
3. Grep for `0.37`, `window mean` / `window-mean` and `2018_to_2024`.

## Acceptance

- The grep finds nothing that describes the old behaviour.
- The docs build passes.

## Definition of done

Grep clean, docs build. Do not commit.
