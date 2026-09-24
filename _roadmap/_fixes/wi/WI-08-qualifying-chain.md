# WI-08 — Qualifying chain reads race-day data

**Group:** 02 feature expansion · **Depends on:** `WI-02` (shares the same in-race compound seed) ·
**Blocker:** none beyond WI-02.

**Findings folded in:** F10 (Low-Medium).

**Reverification:** CONFIRMED-AS-STATED.

---

## The defect, reconfirmed

`int_lap_residual_decomposed_qualifying.sql:92-94` — the model's **own comment admits it**: "Ambient
/ track evolution: reuse the race-day data for the same event... we use same-event weather as an
approximation," directly above the `weather_proxy` CTE (`:95-104`, a `DISTINCT ON (race_year,
race_id)` with no tiebreak — confirmed to pick a stable-but-arbitrary median lap 4, max lap 50).
`compound_component_s` (`:144-145,167-171`) uses the same in-race compound seed as `WI-02`'s F2,
joined on `race_year = season`. Both feed `quali_skill_session_avg_s`, a contract feature (cliff
family only).

The `schema.yml` exemption at `:1918-1925` ("no column this model SELECTs reads anything
race-scoped") is **directly contradicted by the model's own header comment two lines above the CTE
it's complaining about** — this isn't a subtle mismatch, the model documents the violation of its
own declared exemption in the same file.

## Method

1. Remove `weather_proxy`'s race-day `int_track_evolution` read; substitute either qualifying's own
   session-evolution signal (if one exists) or drop the term and accept a coarser proxy.
2. Once `WI-02` lands (point-in-time or declared-exempt compound seed), the qualifying chain
   inherits the same fix automatically for `compound_component_s` — no separate work needed there
   beyond re-verifying the join still resolves correctly.
3. Correct the `schema.yml` exemption text to match what the model actually does, or make the model
   match the exemption — pick one and make them agree.

## Acceptance

- No column feeding `quali_skill_session_avg_s` reads race-day data.
- The `schema.yml` exemption's claim is true of the model it describes.

## Tests to add

T10 (lineage check: `int_qualifying_driver_summary`'s ancestors, per the compiled manifest's
`parent_map`, exclude race-side models).

## Definition of done

`verify_findings.py`'s F10 check flips to CLEARED; T10 is wired in and would fail against the
pre-fix model.
