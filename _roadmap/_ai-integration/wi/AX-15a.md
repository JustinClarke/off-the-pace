# AX-15a — Dirty-air-dependent card kinds published as HELD stubs (ratings, ghost car, constructor); isolation marts exported; dirty-air components held

**Group:** 5 held classes · **Depends on:** `AX-07` · **Model / cost:** `opus-5`, 1d · **Gates:** `AX-19` (the freeze must list every T\* kind as held, with its reason)
**Blocker:** none. **HD2 was ruled C on 2026-11-07:** whether wake calibration replaces the flat tax is undecided, so every dirty-air-dependent (T\*) card is held in v1. The live switch-over is AX-15b, which waits on wake calibration (XW).
Split from the old AX-15 on 2026-11-07, so that a transform-only v1 does not wait on wake calibration. This item computes no number into a published card.

**Sources (verified):**
- `transform/models/marts/` (`mart_race_driver_summary.sql`, `mart_driver_season_summary.sql`, `mart_metric_benchmark.sql`, `fct_driver_isolation_race.sql`, `fct_driver_isolation_stint.sql`, `fct_lap_residuals.sql`, `fct_ghost_race_finish.sql`) and `intermediate/int_dirty_air_tax_component.sql`.
- `app/src/features/*/`, `scripts/export_app_data.py` (TX-12 flags), and AX-07's lineage evidence `_evidence/ax-07-lineage/lineage.json`.
- `_evidence/ax-audit-2026-11-07/audit-transform.md:165-180` (what does and does not depend on dirty air), the HD13 ruling, and design 2.2-2.4.

---

## A held stub

A held stub is one card per kind and scope: `status:"held"`, `value:null`, `interval:null`, `n.count:0`, a non-empty `held_reason`, and `page` (AX-03 route and params) so the assistant can link the page. AX-01 already allows this shape. `get_fact_cards` and AX-21's bundles return stubs like any other card, so the model sees the reason in place of a number.

## Held in v1, and the reason the model gives

| Kinds (feature or mart) | `held_reason` (plain words) | Why T\* |
| :-- | :-- | :-- |
| race-lost, lap-waterfall components (skill, fuel, compound, car) | "The time-loss breakdown includes the dirty-air term, a flat 0.331 s per lap estimate that has not been validated; held until wake calibration reports." | `total_explained_s` contains `dirty_air_tax_s`; skill is the remainder |
| sector-decomposition | same, plus "sector attribution waits on CO-16" | sector dirty air (WC) |
| ghost-race-standings, counterfactual-championship, hidden-performance | "Built on ghost-car pace, which includes the unvalidated dirty-air term." | `fct_ghost_car_pace` / `fct_ghost_race_finish` carry `dirty_air_tax_s` directly |
| race mart `mean_*_component_s`, `mean_dirty_air_tax_s`; benchmark `driver_skill` and `dirty_air` rows | "Measured net of the unvalidated dirty-air term." | the residual is net of the tax |
| `fct_driver_isolation_race` / `_stint` (pure and relative pace) | "Isolation prices thin-cell traffic with the flat dirty-air rule." | CO-30, `int_driver_isolation_lap_panel.sql:119-153` |
| driver-consistency, wet-race-specialist | as for the lap residual | `fct_driver_skill_features` is built on the residual |
| constructor-structural-pace, party-mode, constructor-circuit-interaction, constructor-team-averages | "The car term shares the dirty-air-adjusted residual." | `constructor_component_s`, CO-30 |
| **Any dirty-air price** (the tax, `cumulative_dirty_air_tax_s`, dirty-air bars) | "Traffic cost is being re-measured; no number is available yet." | `price_kind:true`. Stays held even after AX-15b, until AX-16 (rule 9: no archived DA-03 number) |

**Not decided by this table; AX-07a decides (HD13).** These are:
- `rating_s` with its paired n, TX-01's CI and `rating_trust_label`;
- era-ratings-timeline and era-translator, which are built on `rating_s`;
- driver-circuit-affinity, synthetic-teammate, quali-vs-race, track-evolution and corner-phase-skill.

The transform audit reads `rating_s` and the era rating as not dirty-air dependent (audit-transform.md:176-177). If AX-07a's column lineage shows they use `int_lap_air_state` only as a lap filter, they are T: they go live in AX-07 with the `AIR_STATE_FILTER` caveat. If any of them is price-downstream, it becomes a stub here. The old AX-15 put the ratings in T\* by a model-level rule. That is superseded.

## Method

1. Read `lineage.json`. The T\* kind list is the table rows, plus AX-07a's T\* verdicts, minus AX-07a's T verdicts. Write it, with every difference from this doc, to `_evidence/ax-15a/classes.md`. Together with AX-07 this closes AXW11.
2. **Registry.** Each kind gets `class:'T*'`, `status:'held'` and `held_reason` from the table, so AX-09's `HELD_CARD_WORDING` has a reason to require. It also gets `pageParams` from AX-03, `skill_measure` where AX-21's glossary names one, and `price_kind:true` on price kinds. The stub builder reads only scope keys, never a value column.
3. **Scopes.** Enumerate from published scope tables (results, `race_to_track`, drivers, constructors):
   - race-grain kinds per (driver, race);
   - season kinds per (driver, season);
   - constructor kinds per (constructor, race or season).

   Keep each card partition under 5 MB.
4. **Exports.** TX-11 exports the rating marts and `fct_driver_isolation_race`. Add `fct_driver_isolation_stint` to `TABLES` (TX-11 left it out), so AX-15b is a build and a switch, not an export change. Use scratch exports only (`--db/--out`, TX-12). The one real export is the HD12 run.
5. **Manifest.** Through AX-08's block: `classes_live:["T"]`, `classes_held:["T*","WC","ML"]`.
6. Give AX-21 the stub kind list, so its held links resolve.

## Acceptance

- 100% of T\* cards are `held`, with `value` and `interval` null, `n.count` 0, a non-empty `held_reason` and `page.route` set, and `validateCard` passes on all of them.
- No stub's `source.columns` contains a value column. A deny-list test fails on any card, of any status, whose columns include `dirty_air_tax_s`, `cumulative_dirty_air_tax_s` or a `*dirty_air*` price.
- Every T\* kind in `classes.md` has a stub, and every AX-21 held link resolves to one.
- `HELD_CARD_WORDING` fires on a stub fixture. A draft answer that quotes a number for a stub fails the checker.
- No kind reads `flag_chance_lookup.json` (AD5) or an archived DA-03 artefact.
- On a scratch export, `export_app_data.py --db … --out … --check` is stable on re-run.

## Tests to add

`registry.held.test.ts`, `stub.no-value.test.ts`, `deny-list.test.ts`, `held-links.test.ts` (shared with AX-21), and an export-list test for `fct_driver_isolation_stint`.

## Definition of done

Stubs build for every T\* kind, the tests pass, and `_evidence/ax-15a/classes.md` is saved. Nothing under `app/public/data/` changed. Do not commit.
