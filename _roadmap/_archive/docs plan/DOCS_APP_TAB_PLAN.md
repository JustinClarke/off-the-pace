# App Tab Documentation Reorganization Plan

**Goal:** Convert the App tab from one flat 31-page group into **5 progressive-disclosure groups**, each (except Concepts) fronted by a family intro page — matching the Transform and ML tabs.

**Hard constraint:** Do **not** rewrite existing feature pages. Only (a) add 4 new family intro pages + 1 concepts page, and (b) reorganize `docs/docs.json`. Existing `app/*.mdx` files keep their current front matter and bodies, and keep their current URL paths (`/app/<slug>`) — so no redirects are needed.

## §0 — Checkpoint / Status

- [ ] Not started

> Discrepancy resolved: brief listed 30 features; disk has **31**. `era-translator` (Era Translator) was missing from the brief and is placed in **Driver Analysis** (skill family, era-adjusted ratings) → Driver Analysis = **8** features. Final counts: 2 + 8 + 8 + 11 + 4 = **33 pages** across 5 groups (App Overview becomes the Concepts group's lead page; no page is created or deleted among features).

---

## §1 — Target Navigation (docs.json excerpt)

Replace the single `"App & Visualizations"` group (lines ~349–388) with the five groups below. The `app/overview` page is repurposed as the lead of **Concepts**; one new concepts page (`app/architecture`) is added beside it.

```jsonc
{
  "tab": "App",
  "icon": "layout-dashboard",
  "groups": [
    {
      "group": "Concepts",
      "icon": "lightbulb",
      "pages": [
        "app/overview",
        "app/architecture"
      ]
    },
    {
      "group": "Driver Analysis",
      "icon": "user",
      "pages": [
        "app/families/driver-analysis",
        "app/era-ratings-timeline",
        "app/era-translator",
        "app/driver-consistency",
        "app/quali-vs-race-skill",
        "app/driver-circuit-affinity",
        "app/driver-workload",
        "app/wet-race-specialist",
        "app/synthetic-teammate"
      ]
    },
    {
      "group": "Strategy & Tyre Dynamics",
      "icon": "timer",
      "pages": [
        "app/families/strategy-tyre",
        "app/pit-strategy",
        "app/tyre-cliff-survival",
        "app/tyre-recovery-forecast",
        "app/stint-degradation-timeline",
        "app/degradation-simulator",
        "app/track-evolution",
        "app/field-pace-curve",
        "app/party-mode"
      ]
    },
    {
      "group": "Race Performance & Technical Analysis",
      "icon": "flag-checkered",
      "pages": [
        "app/families/race-performance",
        "app/ghost-race-standings",
        "app/lap-waterfall",
        "app/hidden-performance",
        "app/dirty-air-cost",
        "app/dirty-air-lap-map",
        "app/sector-decomposition",
        "app/corner-phase-skill",
        "app/race-lost",
        "app/counterfactual-championship",
        "app/constructor-structural-pace",
        "app/constructor-circuit-interaction"
      ]
    },
    {
      "group": "Data & Validation",
      "icon": "shield-check",
      "pages": [
        "app/families/data-validation",
        "app/model-metrics",
        "app/data-quality-audit",
        "app/query-lab",
        "app/blind-test-scoreboard"
      ]
    }
  ]
}
```

Icons are Lucide (the configured library). All 31 existing feature pages appear exactly once; nothing is orphaned.

---

## §2 — New Pages to Create

Five new MDX files. Family intros live in a new `docs/app/families/` subdirectory; the architecture page sits at `app/` root beside `overview`.

| File | sidebarTitle | Scope / what it must explain |
|---|---|---|
| `docs/app/architecture.mdx` | Architecture | Browser-native stack: Parquet → DuckDB-Wasm → ONNX, the runtime manifest, zero-server model, COOP/COEP, the `?v=` cache-bust. Lift the technical half of today's `overview.mdx` "Architecture" section into a proper standalone page so the overview can stay a tour. (You may *reference* overview content; do not delete it from overview.) |
| `docs/app/families/driver-analysis.mdx` | Driver Analysis | The skill-isolation idea: every feature here is a different read of "driver net of car." Map each of the 8 features to its transform source (mostly the **Skill** family — `int_era_normalized_driver_rating`, `int_driver_circuit_affinity`/`_era_affinity`, `int_synthetic_teammate` — plus residual-skill signals). Explain the de-biasing premise and the 2022 era boundary once, so feature pages don't have to. |
| `docs/app/families/strategy-tyre.mdx` | Strategy & Tyre | Degradation & pit-strategy story. Tie the 8 features to the ML degradation model (ONNX, scored in-browser) and the transform marts (`mart_degradation_history_envelope`, `int_pit_strategy_value`, `int_field_pace_curve`, `int_track_evolution`). Distinguish *observed* (timelines, envelopes) from *simulated* (Degradation Simulator, Tyre Recovery Forecast). |
| `docs/app/families/race-performance.mdx` | Race Performance | The seven-term identity in action: ghost recombination, lap waterfall, dirty-air tax, sector/corner decomposition, counterfactual championship, constructor structural pace. Anchor to `fct_lap_residuals`, `fct_ghost_race_finish`, `int_constructor_structural_pace`. This is the largest group (11) — emphasise the decomposition spine that unifies them. |
| `docs/app/families/data-validation.mdx` | Data & Validation | Trust surface: how the app proves its own numbers. Model Metrics (ONNX↔booster parity), Data Quality Audit (pipeline invariants), Query Lab (audit it yourself in SQL), Blind Test Scoreboard (held-out calibration). Link to the ML **Validation & Trust** and Data **Quality & Coverage** doc groups. |

**Family-page front-matter contract** (mirror Transform/ML families):
- `title` — a descriptive sentence, not just the family name.
- `sidebarTitle` — short label (table above).
- `description` — one-line summary used for relevance/search.
- Body sections: `## What this family does` → optional `## How it connects to the pipeline` (link transform/ml docs) → `## Every feature in this family` as a `<CardGroup cols={2}>` of `<Card>`s linking each `/app/<slug>` with its `sidebarTitle` + one-line hook (pull the hook from each feature page's existing `description`).

---

## §3 — Implementation Checklist (ordered)

1. `mkdir docs/app/families/`.
2. Create the 4 family pages + `app/architecture.mdx` (§4 is a ready template for one).
   - For each `<Card>`, copy the hook from the target feature page's existing `description` front matter (already gathered: e.g. Era Translator = "A season leaderboard of era-adjusted driver ratings…", Wet-Race Specialist = "Each driver's wet-weather skill advantage…").
3. Edit `docs/docs.json`: replace the single App group with the 5-group block from §1.
4. (Optional polish, allowed) In `app/overview.mdx`, update the closing `<CardGroup>` "Explore the feature pages" to point at the 4 family pages instead of 4 arbitrary features — keeps the overview a true tour. This is an *additive edit to overview's nav cards only*, not a feature-page rewrite.
5. Validate locally (§5).
6. Stage but **do not commit/push** (user is always git-gated).

---

## §4 — Sample Family Page (template — `docs/app/families/driver-analysis.mdx`)

```mdx
---
title: "Driver Analysis: the same question, asked eight ways"
sidebarTitle: "Driver Analysis"
description: "Eight features that all isolate driver skill from car performance — career ratings, circuit affinity, wet-weather edge, and synthetic-teammate duels — each reading a different signal out of the transform Skill family."
---

## What this family does

Every feature in this group answers one question: **how good is the driver, net of
the car they were given?** That is the hardest thing to measure in Formula 1, because
in any single race the two are almost perfectly confounded — the fastest car usually
carries the fastest lap. The app attacks the confound from several angles at once, and
each feature here is one of those angles made visible.

The signals come almost entirely from the transform **Skill** family
([read how it's built](/transform/families/skill)), which de-biases the car using a
two-way fixed-effects fit and a leave-one-race-out teammate baseline before any rating
is computed. Two ideas recur across every page below, so they're stated once here:

- **Car removal.** A driver's pace is only meaningful relative to what the same machinery
  did in other hands. Ratings subtract a de-biased constructor×race effect, not a raw
  team median — otherwise a fast driver's own laps leak back in as "car pace."
- **The 2022 boundary.** The ground-effect regulation reset is treated as a discrete era
  split, bridged by drivers who raced competitively on both sides. Cross-era numbers
  (Era Ratings Timeline, Era Translator) are only comparable because of that bridge.

## How it connects to the pipeline

These features are direct exports — most read an `int_` model straight from the gold
mart with no intervening marts table. Era ratings come from
`int_era_normalized_driver_rating`; circuit affinity from `int_driver_circuit_affinity`
and its era-split sibling `int_driver_circuit_era_affinity`; the teammate duel from
`int_synthetic_teammate`, the family's one ML-feature input. Consistency, quali-vs-race,
wet-weather, and workload read residual-skill and aggregate signals from
[`fct_lap_residuals`](/reference/models/fct/fct_lap_residuals) and the driver-skill mart.

## Every feature in this family

<CardGroup cols={2}>
  <Card title="Era Ratings Timeline" icon="chart-line" href="/app/era-ratings-timeline">
    Every driver's era-normalized rating over time, on one comparable scale across the
    2022 regulation boundary.
  </Card>
  <Card title="Era Translator" icon="shuffle" href="/app/era-translator">
    A season leaderboard of era-adjusted ratings, anchored by drivers who raced on both
    sides of the 2022 rule change.
  </Card>
  <Card title="Driver Consistency" icon="chart-scatter" href="/app/driver-consistency">
    How reliably each driver extracts pace from the car, lap to lap, using the residual
    skill signal from the seven-term decomposition.
  </Card>
  <Card title="Quali vs Race" icon="gauge" href="/app/quali-vs-race-skill">
    One-lap merchants vs stint drivers: qualifying skill residual plotted against race
    skill residual.
  </Card>
  <Card title="Driver Circuit Affinity" icon="map-pin" href="/app/driver-circuit-affinity">
    Where each driver over- or under-performs their own career average, circuit by circuit.
  </Card>
  <Card title="Driver Workload" icon="activity" href="/app/driver-workload">
    How hard each driver had to work for their lap time — steering, throttle, and brake
    effort behind the pace.
  </Card>
  <Card title="Wet-Race Specialist" icon="cloud-rain" href="/app/wet-race-specialist">
    Each driver's wet-weather edge: race skill in the wet minus their dry baseline.
  </Card>
  <Card title="Synthetic Teammate" icon="user-check" href="/app/synthetic-teammate">
    A lap-by-lap, tyre-state-adjusted duel against a synthesized equal-car teammate.
  </Card>
</CardGroup>
```

(~410 words of prose. Repeat the shape for the other three families, swapping the
transform/ML anchors named in §2.)

---

## §5 — Validation / Success Criteria

Run from `docs/`:

1. **Build is clean:** `mintlify validate` (or the repo's `make docs-validate`) returns **0 errors**.
2. **No broken links:** the broken-links check returns **0** — every `/app/<slug>` in the 4 CardGroups resolves, and every transform/ml cross-link (`/transform/families/skill`, `/reference/models/...`, `/ml/validation`) exists.
3. **No orphans:** all 31 feature pages + 5 new pages appear in `docs.json`; nothing is referenced that isn't on disk and nothing on disk is dropped from nav.
4. **Counts:** App tab shows 5 groups; group sizes 2 / 8 / 8 / 11 / 4.
5. **Parity check:** App tab now visually matches Transform/ML — a Concepts group leads, each feature group opens with a family intro card-deck, progressive disclosure top-to-bottom.
6. **No feature page diff:** `git diff --stat docs/app/` shows only *new* files under `families/` + `architecture.mdx` (and, if §3.4 done, `overview.mdx`); **no existing feature `.mdx` is modified**.
7. **docs_facts / drift gate:** if `scripts/*docs*` count-gates reference App page counts, bump them; otherwise confirm the audit still passes (`make docs-audit` / app_docs_audit.py).
8. Live-preview spot check against https://offthepace.mintlify.app/ after preview deploy.

> Reminder: stage only — the user commits/pushes manually.
