# Project Plan

> Watch-along product (batch pipeline + historical replay) is now part of this document —
> see [Watch-Along Plan](#watch-along-plan--historical-race-replay--strategy-product) below.
> Deferred live/streaming phases → [STREAMING_PLAN.md](./STREAMING_PLAN.md).
> ML models & in-product AI → [AI_PLAN.md](./AI_PLAN.md).
> Issue register → [ISSUES.md](./ISSUES.md).
> Maintenance runbook → [MAINTENANCE_AND_PIPELINE_SYNC.md](./MAINTENANCE_AND_PIPELINE_SYNC.md).

---

## Status

```
Phase 1 (Docs)     Phase 2 (ML)     Phase 3 (App)          Phase 4 (Fabric)
──────────────────────────────────────────────────────────────────────────
✅ complete        ✅ complete       🚧 in progress         ❌ deferred
```

**Accurate counts:** 59 dbt models (12 staging / 4 reference / 33 intermediate / 10 marts),
5 ML models at **v3** / 41 features, 36 tables exported, 2018–2024.

---

## Phase 3 — Interactive App — 🚧 in progress

31 features implemented in `app/src/features/`. Remaining work:

### Wire stubs to existing features (no build needed)

| Route stub | Feature to wire |
|---|---|
| `ghost-car/standings.tsx` | `features/ghost-race-standings` |
| `ml/blind-test.tsx` | `features/blind-test-scoreboard` |
| `ml/metrics.tsx` | `features/model-metrics` |
| `ml/simulator.tsx` | `features/degradation-simulator` |
| `drivers/consistency.tsx` | `features/driver-consistency` |
| `lap-decomposition/waterfall.tsx` | `features/lap-waterfall` |
| `tyre-strategy/survival.tsx` | `features/tyre-cliff-survival` |
| `tyre-strategy/pit-gantt.tsx` | `features/pit-strategy` |
| `drivers/ratings-timeline.tsx` | `features/era-ratings-timeline` |

### Genuinely unbuilt features

| Route | What it needs |
|---|---|
| `ghost-car/lap-chart.tsx` | Lap-by-lap overlay: `predicted_lap_time_s` vs `actual_lap_time_s` with delta fill. Source: `fct_ghost_car_pace`, `int_circuit_x_constructor_interaction`. |
| `drivers/dna-clusters.tsx` | K-means clustering of driving style from telemetry features. Needs offline UMAP/k-means pipeline → baked coords parquet. |
| `drivers/career-twin.tsx` | Most statistically similar career arcs using `driver_skill_residual_s`. Needs same offline embeddings pipeline as dna-clusters. |
| `deep-dives/telemetry-fingerprint.tsx` | Braking/throttle/speed signature by driver × circuit. Source: `stg_telemetry`. |
| `query.tsx` | DuckDB-Wasm SQL editor against the gold mart with result table and CSV export. |

### Ghost-car arc (PROJECT_PLAN capture)

- **Lap Chart** (`/ghost-car/lap-chart`) — see table above.
- **Waterfall** (`/lap-decomposition/waterfall`) — 🔲 **unbuilt** (route stub exists). Pick a
  driver × race × lap; show the **7-term** additive identity (`fuel + compound + rubber + ambient +
  constructor + dirty_air_tax + driver_skill_residual`) summing to `pace_delta_s`, with a closure
  badge. `track_unexplained_s` surfaces as a non-closing "Track noise" bar — not added to the
  closure. Source: `fct_lap_residuals`; COALESCE the NULL-prone `track_unexplained_s`.

---

## Phase 4 — Fabric (enterprise) — ❌ deferred

Microsoft Fabric: Eventstream (live telemetry ingestion), OneLake (storage), KQL, Fabric Notebooks
(retraining), Azure backend for server-side streaming. Trigger: employer interest in enterprise F1
analytics, or a model ready for production-scale inference. This is a separate, later path from the
GCS + Cloud Run live phases in [STREAMING_PLAN.md](./STREAMING_PLAN.md) — not a prerequisite for them.

---

## Definition of Done

**Per feature:**
- [ ] Renders from real exported parquet (no mock); respects the filter bar.
- [ ] Pure `transform.ts` has vitest unit tests (closure checks, gates, normalisation).
- [ ] Uncertainty rendered where the data carries it (CI ribbon / p10–p90 band / confidence opacity).
- [ ] Methodology drawer deep-links to the exact dbt model or ML card page on the docs site.
- [ ] Provenance footer: fit metadata / `model_version` + fingerprint for fitted values.
- [ ] CSV export works; loading / empty / error via shared feedback components; lazy partition load only.

**Per release:**
- [ ] `assert_additive_identity` reflected in the UI (closure badge green).
- [ ] ML page numbers all trace to `model_card.json` (zero hand-typed); ONNX parity badge green.
- [ ] `app-data --check`, `generate-schemas --check`, `app-build`, vitest, and `ui/charts` import-gate lint all green.
- [ ] Home paints with zero SQL and no `<DataBoundary>`; first child-route nav has no loading screen.
- [ ] No raw `stg_telemetry` in the export; telemetry features show honest NULL-share.
- [ ] Deploys to **Firebase**; cross-links to portfolio + docs resolve.

---

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Docs platform | **Mintlify** (reversed from Docusaurus 3.x, 2026-06) | Hosted docs, `docs.json` nav, MDX components |
| Hosting | App: Firebase · Docs: Mintlify | App static deploy on Firebase; docs served by Mintlify |
| Search | ~~Pagefind~~ — retired (Mintlify built-in search) | |
| Style linter | ~~Vale~~ — retired with Docusaurus | Re-add a Mintlify-compatible linter only if needed |
| Snippet testing | ~~Sybil~~ — retired with Docusaurus | Re-establish under Mintlify if wanted |
| IA framework | Diátaxis | Tutorials / Guides / Reference / Explanation; no numbered folders |
| License — core | AGPL-3.0 | Forces derivative works to stay open |
| License — docs | MIT | Frictionless reuse |
| ML target | Multi-target: degradation rate + cliff risk + remaining stint life | |
| Blind-test holdout | 2025 season withheld until reveal | True out-of-sample; no code change at flip |
| Fabric / streaming | Deferred to Phase 4 | |
| Portfolio integration | Off-The-Pace case study on `justinclarke.dev`, CTA → `offthepace.dev` | |

**Single Source of Truth:** model docs ← `transform/models/schema.yml` + docstrings;
schemas ← `ingestion/schemas/*.json`; CLI ref ← `--help` output. `docs/reference/` is auto-generated,
never hand-edited (CI restores it).

---

## Watch-Along Plan — Historical Race Replay & Strategy Product

> **Canonical plan for the offline/historical watch-along product:** the batch
> prediction pipeline plus the `/replay` dashboard that drives it.
> Live/streaming phases live in [STREAMING_PLAN.md](./STREAMING_PLAN.md).
> Watch-along-specific ML (offline Monte Carlo, §4) detailed in [AI_PLAN.md](./AI_PLAN.md).

Consolidates the former `watchalong/` workstream files (ingestion/transform/ml/app v0.2 +
live-strategy + step-5 scope) **and** the former `replay_simulator_roadmap.md`. This is the
canonical plan for the historical watch-along product: scrub through any 2018–2024 race
lap-by-lap with analytical overlays (pit windows, tyre cliffs, dirty-air tax, finish
probabilities) powered by the existing decomposition models and ONNX inference.

**Sequencing decision (locked 2026-06-11): predictions first, streaming deferred.**
The batch pipeline (below) and the replay dashboard build with **no** live-timing
infrastructure. The Phase 2 validation gate decides whether the *live* phases (in
[STREAMING_PLAN.md](./STREAMING_PLAN.md)) ever get built. Nothing in the live stack
accelerates prediction validation.

### Status (2026-06-23)

```
ingestion v0.2 (telemetry backfill + new surfaces)   ✅ DONE
transform Fix 1–3 + §4 gate + §5.1–5.4               ✅ DONE
ml v0.2 §1 (mart re-sync) + §2 (telemetry features)  ✅ DONE
        │
        ▼
transform §5.7  (race-pack exporter)        🔲 REMAINING — unblocked
ml v0.2 §4      (offline Monte Carlo)        🔲 REMAINING — independent of §5.7
        │
        ▼
replay dashboard Phases 1–5, 7              🔲 BUILDABLE NOW (data exists)
replay Phase 6 (track map)                  🔲 BLOCKED on pos_data ingestion
        │
        ▼
live phases (relay, strategy v2)            ⛔ See STREAMING_PLAN.md — gated on §4
```

**Done, in brief:**
- **Ingestion**: full-session telemetry backfill (phased 2022 → 2018 canary → batch), results,
  track/session status, circuit info, schedule, Jolpica standings + pit stops.
- **Transform**: constructor deg-slopes wired into ghost recombination (hosts now reorder
  drivers); per-constructor cliff-onset shift + linear `cliff_interaction_s`; SE propagation
  (`predicted_mean_lap_se_s`, `p_beats_next`, `finish_pos_se`); §5.1–5.4 staging/intermediates.
- **§4 validation gate**: CONDITIONAL GO. LORO Spearman 0.65 over 145 races on the full
  2018–2024 rebuild (53 models, 336 tests green). Built as `scripts/validate_gate.py` +
  `scripts/mc_finish_order.py` (deliberately not dbt models — kept off the drift gate).
- **ML**: `mart_degradation_predictions` re-synced at v3 (137,447 laps; parity maxAbs 7.6e-6);
  cliff classifier promoted to v3 (41 features, +3.9pp accuracy on 2024 holdout from telemetry).

### Remaining batch work

#### transform §5.7 — Race-pack exporter 🔲

A dbt mart + export extension that assembles the per-circuit priors bundle and writes it to
disk/GCS. This is the contract between the batch pipeline and all downstream consumers
(app loader, offline MC, eventual live relay). All four upstream inputs exist and are populated.

| Input | Table | Supplies |
|---|---|---|
| Deg slopes | `int_constructor_deg_sensitivity` | rate + shrunk slope per (constructor, compound, season) |
| Cliff params | `fct_cliff_prediction_features` / `int_constructor_deg_sensitivity` | onset offset per constructor |
| Pit loss | `int_pit_loss_circuit` | stationary + in/out loss per circuit |
| SC/VSC hazard | `int_sc_hazard_history` | base hazard rate per circuit |
| Fuel effect | embedded in ghost recombination coefficients | pass-through constant |

- **Grain**: `circuit_id` as primary export (static priors, compact); raw per-race slopes stay
  available via the existing `fct_ghost_race_finish` export.
- **Model**: new `transform/models/marts/fct_race_pack_priors.sql`, flat join of the four inputs.
- **Export**: add to `scripts/export_app_data.py` + `app/public/data/_manifest.json`; parquet
  output, `?v=` cache-bust URL.
- **ONNX**: reference the `ml/models/manifest.json` path; do not re-bundle `.onnx` files.

**Acceptance:** passes `dbt test` (not-null + unique on grain); `make app-data` emits
`data/race_pack_priors.parquet`; schema documented in `marts/schema.yml`; app loader validates
it with no KeyErrors.

> **Note:** §5.7 is the contract for the *live* relay, but the replay dashboard does **not**
> require it — full race history is already available client-side. It is sequenced here because
> it is unblocked and feeds the offline Monte Carlo.

#### ml v0.2 §4 — Offline Monte Carlo support 🔲

Transform owns the MC harness; ML supplies the stochastic inputs. The MC core already exists as
`scripts/mc_finish_order.py` (pure-function, SE-aware, `p_beats_next`).

| # | Step | Deliverable |
|---|---|---|
| 4.1 | Per-driver lap-time distributions as pure functions: deg curve (rate + SE from Fix 3) + residual variance + pit-stop duration distributions | sampling module consumed by MC; keep a deterministic seed path for tests |
| 4.2 | Validate MC finish distributions vs actuals (LORO style) | validation report; target Spearman ≥0.65, calibration slope closer to 1.0 than current 0.717 — this is the evidence for the live-gate condition 1 in [STREAMING_PLAN.md](./STREAMING_PLAN.md) |

**Acceptance:** p10/p90 empirical coverage within ±5pp of nominal on holdout; cliff-probability
reliability diagram reviewed.

### Replay Dashboard

> **Architecture target:** new React route `/replay` under `DataLayout`, driven by a
> `ReplayContext` that owns the playback clock. All child components subscribe to "current lap"
> and re-query DuckDB-Wasm with `WHERE lap_number <= :currentLap`. ONNX models score in-browser
> via the existing `ml/infer.ts` pipeline. Every feature is backed by data that already exists
> in the browser layer (or derivable from it with no new ingestion — except Phase 6).

#### Data Availability Audit

What we actually have in `app/public/data/` (last audited 2026-06-22):

##### ✅ Available & Populated

| Dataset | Path | Size | Grain | Key Columns for Replay |
|---------|------|------|-------|----------------------|
| Lap residuals | `facts/fct_lap_residuals/{year}.parquet` | ~4.5 MB | lap | `lap_time_s`, `fuel_component_s`, `compound_component_s`, `rubber_component_s`, `ambient_component_s`, `constructor_component_s`, `dirty_air_tax_s`, `driver_skill_residual_s`, `position`, `compound`, `age_in_stint`, `correction_weight`, `is_safety_car_lap` |
| Cliff features | `facts/fct_cliff_prediction_features/{year}.parquet` | ~11.7 MB | lap | `pct_full_throttle`, `braking_point_drift_m`, `mid_corner_speed_loss_kph`, `traction_wheelspin_proxy`, `throttle_trace_decay`, `lift_coast_share`, `cliff_onset_passed`, `laps_past_cliff`, `laps_until_cliff_class`, `air_state_dominant`, `compound_cliff_onset_laps`, `compound_cliff_severity` |
| Ghost car pace | `facts/fct_ghost_car_pace/{partitioned}` | variable | ego × host × race × lap | `predicted_lap_time_s`, `actual_lap_time_s`, `delta_vs_actual_lap_s`, `deg_interaction_s`, `cliff_interaction_s` |
| Ghost race finish | `facts/fct_ghost_race_finish.parquet` | 1.8 MB | host × ego × race | `predicted_finish_position`, `actual_finish_position`, `p_beats_next`, `finish_pos_se` |
| Stint features | `facts/fct_stint_features.parquet` | 136 KB | stint | `stint_length_laps`, `compound`, `cumulative_dirty_air_tax_s`, `cliff_lap_in_stint`, `tyre_management_score`, `pit_decision_class`, `end_of_stint_pace_falloff_s_per_lap` |
| Driver skill features | `facts/fct_driver_skill_features.parquet` | 215 KB | driver × race | `driver_residual_mean_s`, `driver_residual_stddev_s`, `clean_lap_count`, `driver_skill_proxy_mean_s` |
| Telemetry deltas | `facts/fct_telemetry_deltas/{year}.parquet` + `.parquet` | ~64 MB | driver_a × driver_b × corner × lap | `braking_point_delta_m`, `v_min_delta_kph`, `throttle_point_delta_m` |
| Corner metrics | `intermediates/int_corner_metrics/{year}.parquet` + `.parquet` | ~14 MB | driver × corner × lap | `braking_point_m`, `v_min_kph`, `throttle_point_m` |
| Corner skill residuals | `intermediates/int_corner_skill_residuals/{year}.parquet` + `.parquet` | ~771 KB | lap × corner | braking/mid/exit skill vs field |
| Degradation envelope | `marts/mart_degradation_history_envelope.parquet` | 302 KB | circuit × era × compound × lap_in_stint | `obs_deg_from_fresh_p10_s`, `obs_deg_from_fresh_p50_s`, `obs_deg_from_fresh_p90_s` |
| Corner skill driver | `marts/mart_corner_skill_driver/{year}.parquet` | ~19 KB | race_year × driver | `braking_skill_z`, `mid_corner_skill_z`, `exit_skill_z`, `corner_skill_index` |
| Degradation predictions | `ml/mart_degradation_predictions/{year}.parquet` | ~4.8 MB | lap | pre-scored ONNX outputs (p10/p50/p90 + cliff class + stint life) |
| Air state | `intermediates/int_lap_air_state/{year}.parquet` | ~2 MB | lap | `air_state_dominant`, dirty air thermal loads |
| Sector decomposition | `intermediates/int_sector_residual_decomposed/{year}/{race}.parquet` | ~25 MB | lap × sector | per-sector component split |
| Pit strategy value | `intermediates/int_pit_strategy_value.parquet` | 64 KB | stint | `optimal_pit_lap`, `actual_pit_lap`, `overrun_laps`, `opportunity_cost_s`, `strategy_verdict` |
| Constructor structural pace | `intermediates/int_constructor_structural_pace.parquet` | 55 KB | race × constructor | `constructor_structural_pace_s`, `constructor_structural_pace_se_s` |
| Constructor deg sensitivity | *(in DuckDB warehouse, not yet exported to app)* | — | constructor × compound × year | `deg_slope_s_per_lap`, `cliff_onset_shift_laps` |
| Dimensions | `dimensions/dim_*.parquet` | ~17 KB total | various | circuits, drivers, constructors, compounds, events, race_to_track |

##### ⚠️ Empty Directories (exported but no data)

| Path | Why empty | Impact |
|------|-----------|--------|
| `intermediates/stg_pits/` | Pit stop data not exported to app yet | Blocks pit stop deconstructor entry/exit timing |
| `intermediates/int_overtakes/` | Not exported | Blocks lapped-car identification by position |
| `intermediates/int_lap_line_deviation/` | Not exported | Blocks "Discipline Level" racing-line variance |
| `intermediates/int_race_control_events/` | Not exported | Blocks track limits / blue flag alerts |

##### 🔴 Not Ingested at All

| Data | Why missing | Impact |
|------|-------------|--------|
| **Position data (X, Y, Z)** | `_write_pos_data()` exists in `ingest.py` but `data/bronze/pos_data/` is empty — never run with `--telemetry-full` | **Blocks animated track map** (Phase 6) — the marquee feature |

#### Phase 1: Core Replay Engine

> **Goal:** Race selector → timeline scrubber → basic leaderboard. Get the
> playback loop working before adding analytical overlays.

##### 1.1 ReplayContext (State Manager)

**New file:** `app/src/state/ReplayContext.tsx`

```typescript
interface ReplayState {
  raceId: string          // e.g. "2021_22" (Abu Dhabi)
  raceYear: number
  totalLaps: number       // from MAX(lap_number) in fct_lap_residuals
  currentLap: number      // 1..totalLaps — the scrubber position
  playbackSpeed: number   // 0 (paused), 1, 2, 5, 10
  isPlaying: boolean
  spoilerMode: boolean    // show future data or hide it
}
```

- Owns a `setInterval` that increments `currentLap` at `playbackSpeed`
  laps/second.
- Exposes `setCurrentLap(n)` for the scrubber slider.
- Drives every downstream component via `useReplay()` hook.
- Persists `raceId` in URL params (`/replay?race=2021_22&lap=42`), compatible
  with existing `FilterContext` pattern.

**Data query (race bounds):**
```sql
SELECT race_id, race_year, MAX(lap_number) AS total_laps
FROM fct_lap_residuals
WHERE race_year = ? AND race_id = ?
GROUP BY 1, 2
```

##### 1.2 Race Selector Dropdown

**New file:** `app/src/routes/replay/RaceSelector.tsx`

Populates from existing `dim_events` + `race_to_track` joins. Grouped by
season, sorted by round. Shows circuit name and date.

**Data query:**
```sql
SELECT DISTINCT r.race_year, r.race_id, d.name AS circuit_name
FROM fct_lap_residuals r
JOIN race_to_track rt ON r.race_id = rt.race_id
JOIN dim_circuits d ON rt.track_id = d.circuit_key
ORDER BY r.race_year DESC, r.race_id
```

##### 1.3 Timeline Scrubber & Playback Controls

**New file:** `app/src/routes/replay/TimelineScrubber.tsx`

- A horizontal slider (1..totalLaps) with play/pause and speed buttons.
- Below the slider: lap markers showing SC/VSC/red-flag zones pulled from
  `is_safety_car_lap`, `is_vsc_lap` columns in `fct_lap_residuals`, rendered
  as colored bands on the timeline.
- Pit stop markers per driver from `fct_stint_features` (stint boundaries).

##### 1.4 True Pace Leaderboard

**New file:** `app/src/routes/replay/TruePaceLeaderboard.tsx`

The core analytical insight. For `currentLap`, query all drivers and display
two rankings side-by-side:

| Column | Source |
|--------|--------|
| Actual position | `fct_lap_residuals.position` |
| Actual lap time | `fct_lap_residuals.lap_time_s` |
| True pace (noise-stripped) | `lap_time_s - fuel_component_s - compound_component_s - rubber_component_s - dirty_air_tax_s` |
| Dirty air tax | `fct_lap_residuals.dirty_air_tax_s` |
| Tire compound & age | `fct_lap_residuals.compound`, `age_in_stint` |
| Cliff status | `fct_cliff_prediction_features.laps_until_cliff_class` or live ONNX |

**Data query (per lap):**
```sql
SELECT
  driver_id, constructor_id, position, lap_time_s, compound, age_in_stint,
  fuel_component_s, compound_component_s, rubber_component_s,
  dirty_air_tax_s, driver_skill_residual_s,
  -- True pace = remove everything except driver skill + constructor baseline
  lap_time_s - fuel_component_s - compound_component_s
    - rubber_component_s - dirty_air_tax_s AS true_pace_s
FROM fct_lap_residuals
WHERE race_id = ? AND lap_number = ?
ORDER BY true_pace_s ASC
```

##### 1.5 Route Registration

Add to `App.tsx`:
```typescript
{ path: '/replay', element: lazyRoute(() => import('./routes/replay/index')) },
```

#### Phase 2: Strategy & Tire Intelligence

> **Goal:** Surface the ML models to predict what happens next in the race.
> All data is pre-scored in `ml/mart_degradation_predictions/` — no live
> ONNX needed for V1 (optional upgrade path).

##### 2.1 Tyre Cliff Early Warning System

**New file:** `app/src/routes/replay/TyreCliffWarning.tsx`

For the top 5 drivers in the current battle, display a traffic-light indicator:

| Status | Condition (from `mart_degradation_predictions`) |
|--------|------------------------------------------------|
| 🟢 **Stable** | `cliff_class = 'none_in_stint'` OR `cliff_class = '6_plus'` |
| 🟡 **Degrading** | `cliff_class = '3_to_5'` |
| 🔴 **Cliff Imminent** | `cliff_class = '0_to_2'` |

Also shows `remaining_stint_life_laps` as a countdown bar, and
`degradation_jump_p50_s` as the current expected pace loss per lap.

**Data query:**
```sql
SELECT
  driver_id, compound, age_in_stint,
  degradation_jump_p10_s, degradation_jump_p50_s, degradation_jump_p90_s,
  cliff_class, cliff_class_0_to_2_prob, cliff_class_3_to_5_prob,
  remaining_stint_life_laps
FROM mart_degradation_predictions
WHERE race_id = ? AND lap_number = ?
```

##### 2.2 Degradation Envelope Chart

**New file:** `app/src/routes/replay/DegradationEnvelope.tsx`

For a selected driver, plot their actual `weight_corrected_lap_time` per
`lap_in_stint` against the historical envelope from
`mart_degradation_history_envelope`:

- **p10 band** (best-case degradation) — the management masters
- **p50 line** (median) — expected trajectory
- **p90 band** (worst-case) — pushing too hard
- **Actual dots** — driver's real lap times overlaid

**Data query (envelope):**
```sql
SELECT lap_in_stint, obs_deg_from_fresh_p10_s, obs_deg_from_fresh_p50_s,
       obs_deg_from_fresh_p90_s
FROM mart_degradation_history_envelope
WHERE circuit_id = ? AND era = ? AND compound = ?
ORDER BY lap_in_stint
```

##### 2.3 Ghost Car Pit Stop Simulator

**New file:** `app/src/routes/replay/GhostCarOverlay.tsx`

When a user selects a driver and clicks "What if they pit this lap?", we query
`fct_ghost_car_pace` for the remaining laps of the race where
`host_constructor_id` = the driver's own constructor (self-scenario), then
simulate fresh-tire pace using the degradation envelope.

Shows: "If Norris pits now onto Hards, the model projects he emerges in P3
instead of P5" with a gap-to-leader chart.

**Data sources:**
- `fct_ghost_car_pace` (predicted vs actual lap times)
- `fct_ghost_race_finish` (`predicted_finish_position`, `p_beats_next`)
- `mart_degradation_history_envelope` (fresh-tire trajectory)
- `int_pit_strategy_value` (`optimal_pit_lap`, `opportunity_cost_s`)

#### Phase 3: Dirty Air & Traffic Intelligence

> **Goal:** Quantify the invisible — aero wake, lapped traffic, and the
> "true gap" that strips away traffic noise.

##### 3.1 Traffic Tax Overlay

**New file:** `app/src/routes/replay/TrafficTax.tsx`

For each driver on each lap, show the `dirty_air_tax_s` from
`fct_lap_residuals`. Distinguish between **battle dirty air** (fighting for
position — gap to car ahead < 2s and same lap count) and **traffic dirty air**
(navigating backmarkers — gap to car ahead < 2s but car ahead has fewer laps).

**Backmarker detection query:**
```sql
WITH current_lap AS (
  SELECT driver_id, position, lap_number, dirty_air_tax_s
  FROM fct_lap_residuals
  WHERE race_id = ? AND lap_number = ?
),
gaps AS (
  SELECT
    a.driver_id,
    a.dirty_air_tax_s,
    a.position AS ego_pos,
    b.driver_id AS car_ahead,
    b.position AS ahead_pos,
    -- Lapped if car ahead has completed fewer laps at this point
    CASE WHEN b.position > a.position AND a.dirty_air_tax_s > 0.2
         THEN 'traffic' ELSE 'battle' END AS air_source
  FROM current_lap a
  LEFT JOIN current_lap b ON b.position = a.position - 1
)
SELECT * FROM gaps WHERE dirty_air_tax_s > 0
```

##### 3.2 True Gap vs. Artificial Gap

**New file:** `app/src/routes/replay/TrueGap.tsx`

For any two drivers being compared, show:
- **Actual gap** (cumulative lap time difference)
- **True pace gap** (actual gap adjusted by removing `dirty_air_tax_s` from
  laps where the trailing driver was in traffic)

```sql
SELECT
  lap_number,
  SUM(lap_time_s) OVER (ORDER BY lap_number) AS cumulative_time,
  SUM(lap_time_s - dirty_air_tax_s) OVER (ORDER BY lap_number) AS cumulative_true_pace
FROM fct_lap_residuals
WHERE race_id = ? AND driver_id = ? AND lap_number <= ?
```

##### 3.3 Air State Timeline

**New file:** `app/src/routes/replay/AirStateTimeline.tsx`

Uses `int_lap_air_state` and `fct_cliff_prediction_features.air_state_dominant`
to show a per-driver color-coded strip:

| State | Color | Source |
|-------|-------|--------|
| `free_air` | Green | No aero interference |
| `tow_zone` | Blue | Beneficial slipstream on straight |
| `drs_train` | Yellow | Stuck in DRS queue |
| `dirty_air` | Red | Losing downforce in corners |

#### Phase 4: Telemetry & Driver Micro-Analysis

> **Goal:** Throttle/brake traces, fatigue detection, and discipline scoring.
> Performance-critical — telemetry data is **64 MB** and must be filtered
> aggressively.

##### 4.1 Throttle & Brake Trace Panel

**New file:** `app/src/routes/replay/TelemetryPanel.tsx`

When a driver is selected from a dropdown, show their per-lap telemetry
aggregates from `fct_cliff_prediction_features`:

| Metric | Column | Visualization |
|--------|--------|---------------|
| Full throttle % | `pct_full_throttle` | Horizontal bar (0–100%) |
| DRS active % | `pct_drs_active` | Horizontal bar |
| Lift & coast % | `lift_coast_share` | Horizontal bar |
| Braking point drift | `braking_point_drift_m` | Spark line (metres earlier vs baseline) |
| Mid-corner speed loss | `mid_corner_speed_loss_kph` | Spark line (kph lost vs baseline) |
| Wheelspin proxy | `traction_wheelspin_proxy` | Small gauge |

**Teammate overlay:** When two drivers from the same constructor are selected,
use `fct_telemetry_deltas` to show per-corner deltas:

```sql
SELECT corner_name, braking_point_delta_m, v_min_delta_kph, throttle_point_delta_m
FROM fct_telemetry_deltas
WHERE race_id = ? AND lap_number = ?
  AND ((driver_a = ? AND driver_b = ?) OR (driver_a = ? AND driver_b = ?))
```

##### 4.2 Driver Fatigue Index

**New file:** `app/src/routes/replay/FatigueIndex.tsx`

Computed entirely from existing `fct_lap_residuals` in the browser:

```sql
-- Rolling 5-lap standard deviation of driver_skill_residual_s
-- High variance = inconsistency = potential fatigue
SELECT
  lap_number,
  driver_skill_residual_s,
  STDDEV_SAMP(driver_skill_residual_s)
    OVER (PARTITION BY driver_id ORDER BY lap_number
          ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS skill_variance_5lap
FROM fct_lap_residuals
WHERE race_id = ? AND driver_id = ? AND correction_weight = 1.0
```

**Fatigue classification:**
- `skill_variance_5lap < 0.15` → 🟢 **Locked in**
- `0.15 ≤ skill_variance_5lap < 0.30` → 🟡 **Losing edge**
- `skill_variance_5lap ≥ 0.30` → 🔴 **Fatiguing**

Also includes `braking_point_drift_m` and `mid_corner_speed_loss_kph` from
cliff features as corroborating signals — if all three degrade simultaneously,
fatigue is more certain vs. just tire degradation.

##### 4.3 Discipline Level (Metronome Score)

**New file:** `app/src/routes/replay/DisciplineScore.tsx`

Uses `int_corner_metrics` to measure lap-to-lap consistency at each corner:

```sql
-- Per-corner variance of braking point across the stint
SELECT
  corner_name,
  STDDEV_SAMP(braking_point_m) AS braking_consistency,
  STDDEV_SAMP(v_min_kph) AS apex_consistency,
  STDDEV_SAMP(throttle_point_m) AS exit_consistency
FROM int_corner_metrics
WHERE race_id = ? AND driver_id = ?
  AND lap_number BETWEEN ? AND ?  -- current stint range
GROUP BY corner_name
```

**Metronome Score** = inverse of the summed normalized variances. Lower
variance = higher discipline. Rendered as a single 0–100 gauge per driver.

> **Blocker:** `int_lap_line_deviation` (X,Y deviation from optimal racing
> line) is empty in the app export. The corner-metrics approach above is the
> fallback — it measures *output consistency* (braking point, apex speed) rather
> than *spatial consistency* (racing line). When `int_lap_line_deviation` is
> populated, upgrade to true spatial discipline.

##### 4.4 Corner-by-Corner Skill Highlights

**New file:** `app/src/routes/replay/CornerSkillMap.tsx`

Uses `int_corner_skill_residuals` to show which corners a driver is
gaining/losing time at relative to the field on the current lap.

```sql
SELECT corner_name, braking_skill_s, mid_corner_skill_s, exit_skill_s
FROM int_corner_skill_residuals
WHERE lap_id = ?
```

Rendered as a ranked list or small bar chart showing each corner's net
gain/loss. Negative = faster than field.

#### Phase 5: Pit Stop & Strategy Deconstructor

> **Goal:** Break down the pit stop window into driver phases vs. mechanic
> phases, and evaluate strategy decisions.

##### 5.1 Strategy Verdict Timeline

**New file:** `app/src/routes/replay/StrategyTimeline.tsx`

Uses `int_pit_strategy_value` to show for each stint:

| Field | Use |
|-------|-----|
| `optimal_pit_lap` | Vertical green line on the degradation chart |
| `actual_pit_lap` | Vertical red line |
| `overrun_laps` | Gap between optimal and actual |
| `opportunity_cost_s` | Seconds wasted by pitting late |
| `strategy_verdict` | Badge: `optimal` / `overran` / `undercut_forced` / `early` |

##### 5.2 Pit Decision Comparison Card

**New file:** `app/src/routes/replay/PitDecisionCard.tsx`

For two battling drivers, show their stint data side by side from
`fct_stint_features`:

| Metric | Column |
|--------|--------|
| Stint length | `stint_length_laps` |
| Tire management score | `tyre_management_score` |
| Pace falloff rate | `end_of_stint_pace_falloff_s_per_lap` |
| Cumulative dirty air cost | `cumulative_dirty_air_tax_s` |
| Cliff onset in stint | `cliff_lap_in_stint` |
| Decision class | `pit_decision_class` |

> **Blocker:** `stg_pits` is empty in the app export, so we cannot split
> pit stops into entry braking / stationary / exit launch phases. The
> `fct_stint_features` level of granularity (stint-level timing) is the current
> limit. When `stg_pits` is exported, we can add per-phase breakdowns.

##### 5.3 Micro-Sector Laptime Loss Heatmap

**New file:** `app/src/routes/replay/MicroSectorHeatmap.tsx`

Uses `int_sector_residual_decomposed` (3 sectors per lap, already partitioned
by race) to show a 3-band heatmap for each driver:

```sql
SELECT sector, sector_pace_delta_s, sector_driver_skill_residual_s,
       dominant_component_class
FROM int_sector_residual_decomposed
WHERE race_id = ? AND driver_id = ? AND lap_number = ?
ORDER BY sector
```

Colored as: green (gaining vs field), yellow (neutral), red (losing).
`dominant_component_class` labels tell you *why*: tire compound degradation
vs. dirty air vs. driver error.

#### Phase 6: Animated Track Map

> **🔴 BLOCKED: Position data (X, Y, Z) has never been ingested.**
> The `pos_data/` directory in Bronze is empty. The `_write_pos_data()` function
> exists in `ingest.py` but requires running with `--telemetry-full` flag. This
> is an *ingestion* blocker, not a streaming one — it ships in this offline product
> once the data is pulled.

##### 6.0 Prerequisites (Unblock Track Map)

Before any track map work, we must:

1. **Run a targeted ingestion** for position data:
   ```bash
   python ingestion/src/ingest.py --start-season 2018 --end-season 2024 \
     --session R --skip-telemetry --telemetry-full --force
   ```
   This pulls `session.pos_data` (X, Y, Z at ~4 Hz per driver) into
   `data/bronze/pos_data/season=YYYY/race=<slug>/driver=<DRV>/pos_data.parquet`.

2. **Create a staging model** `stg_pos_data` to rename and type-cast the
   FastF1 position columns (`X`, `Y`, `Z`, `Status`, `Time`).

3. **Create an export** in `scripts/export_app_data.py` to write position data
   to `app/public/data/facts/fct_position_data/{year}.parquet`, partitioned
   by year (estimated ~50–100 MB total, comparable to telemetry).

4. **Performance:** Position data at 4 Hz × 20 drivers × 60 laps × 90s/lap
   = ~430,000 rows per race. Filter to 1 Hz for the map animation (108K rows)
   and lazy-load only the selected race.

##### 6.1 Track Map Renderer

**New file:** `app/src/routes/replay/TrackMap.tsx`

- Render the circuit outline from the X,Y positions of the fastest lap
  (the "reference line").
- Animate 20 driver dots along their X,Y paths, synchronized to `currentLap`.
- Color dots by constructor (use existing `dim_constructors` palette).

##### 6.2 Track Map Overlays

Once the base map works, overlay:

| Overlay | Data Source | Visual |
|---------|-------------|--------|
| Dirty air cone | `dirty_air_tax_s > 0.2` on current lap | Red translucent wake behind each car |
| Tire status dot color | `laps_until_cliff_class` from predictions | Green → Yellow → Red dot glow |
| Corner skill ownership | `int_corner_skill_residuals` | Corner segments colored by best driver |
| Ghost car | `fct_ghost_car_pace` | Semi-transparent second dot per driver |

##### 6.3 Track Limits Detection

> **Blocked:** Requires `int_lap_line_deviation` or raw X,Y positions compared
> against a track-boundary polygon. Neither is currently populated.

**Future approach:** Compute from raw position data — if a driver's X,Y
coordinate exits the track polygon (derived from circuit geometry), flag it.
FIA track limits coordinates could be encoded as a seed/CSV per circuit.

#### Phase 7: Constructor & Driver Macro Analytics

> **Goal:** Season-level and career-level insights that go beyond single-race
> replay. These are separate views accessible from the replay dashboard.

##### 7.1 Constructor Aero Robustness Profile

**New file:** `app/src/routes/replay/ConstructorAeroProfile.tsx`

Cross-season aggregation of `dirty_air_tax_s` by constructor:

```sql
SELECT
  constructor_id, race_year,
  AVG(dirty_air_tax_s) AS avg_dirty_air_cost,
  AVG(CASE WHEN dirty_air_tax_s > 0.3 THEN dirty_air_tax_s END) AS avg_cost_when_following,
  COUNT(CASE WHEN dirty_air_tax_s > 0.3 THEN 1 END)::FLOAT
    / COUNT(*) AS pct_laps_in_dirty_air
FROM fct_lap_residuals
WHERE correction_weight = 1.0
GROUP BY constructor_id, race_year
```

Joined with `int_constructor_deg_sensitivity.deg_slope_s_per_lap` to show
which constructors degrade fastest in dirty air (the "Aero Robustness" score).

##### 7.2 Driver Track Affinity (Specialist Index)

**New file:** `app/src/routes/replay/DriverTrackAffinity.tsx`

Already computed: `int_driver_circuit_affinity.parquet` (62 KB) and
`int_driver_circuit_era_affinity.parquet` (86 KB) are in the app export.

```sql
SELECT driver_id, circuit_key, affinity_s, n_races
FROM int_driver_circuit_affinity
WHERE driver_id = ?
ORDER BY affinity_s ASC  -- most negative = biggest specialist advantage
```

Render as a radar chart or ranked bar chart: "Hamilton's top 5 circuits."

##### 7.3 Junior Formula Scouting (Future — No Data Yet)

This requires:
- New ingestion pipeline for F2/F3 (FastF1 supports F2 via `fastf1.get_session(year, round, 'R', backend='f2')`).
- Applying the same 7-component decomposition to strip away Prema/ART team advantages.
- Longitudinal tracking of `driver_skill_residual_s` growth rate from age 16–22.

**Not planned for V1.** Logged here as the long-term vision.

#### Performance Budget

| Component | Data loaded | Strategy |
|-----------|------------|----------|
| Leaderboard | `fct_lap_residuals` for 1 race (~700 rows) | Load full race on select; filter by lap in DuckDB-Wasm |
| Cliff warnings | `mart_degradation_predictions` for 1 race (~700 rows) | Same — load on race select |
| Degradation envelope | `mart_degradation_history_envelope` for 1 circuit (~200 rows) | Tiny; load on race select |
| Telemetry aggregates | `fct_cliff_prediction_features` for 1 race (~700 rows) | Load on race select |
| Corner metrics | `int_corner_metrics` for 1 race (~15K rows) | **Lazy-load only when driver selected** |
| Telemetry deltas | `fct_telemetry_deltas` for 1 race (~8K rows) | **Lazy-load only for teammate comparison** |
| Sector decomposition | `int_sector_residual_decomposed` for 1 race (~2K rows) | Load per-race partition file |
| Track map positions | `fct_position_data` for 1 race (~100K rows) | **Lazy-load; downsample to 1 Hz** |

**Target:** < 5 MB loaded on race select (excluding position data). Sub-10ms
queries via DuckDB-Wasm on filtered in-memory tables.

#### Implementation Sequencing

```
Batch prereqs (unblocked, in parallel with Phase 1)
  transform §5.7 race-pack exporter + ml §4 offline Monte Carlo
         │
Phase 1 (MVP — ~2 weeks)
  1.1 ReplayContext + 1.2 Race Selector + 1.3 Timeline Scrubber
  1.4 True Pace Leaderboard + 1.5 Route wiring
         │
Phase 2 (Strategy overlays — ~1.5 weeks)
  2.1 Tyre Cliff Warning + 2.2 Degradation Envelope + 2.3 Ghost Car
         │
Phase 3 (Dirty air — ~1 week)
  3.1 Traffic Tax + 3.2 True Gap + 3.3 Air State Timeline
         │
Phase 4 (Telemetry — ~2 weeks)
  4.1 Throttle/Brake Panel + 4.2 Fatigue Index
  4.3 Discipline Score + 4.4 Corner Skill Highlights
         │
Phase 5 (Strategy — ~1 week)
  5.1 Strategy Verdict + 5.2 Pit Decision Card + 5.3 Micro-Sector Heatmap
         │
Phase 6 (Track Map — ~2-3 weeks, BLOCKED on pos_data ingestion)
  6.0 Ingest pos_data + staging model + export
  6.1 Track Map Renderer + 6.2 Overlays
         │
Phase 7 (Macro Analytics — ongoing)
  7.1 Constructor Aero + 7.2 Driver Affinity + 7.3 Junior Scouting (future)
         │
live phases → STREAMING_PLAN.md (gated on §4 conditions)
```

#### Dropped scope (do not revive)

- **FP/Sprint ingestion** (`--session FP1/FP2/FP3/S`) — deprioritized; pre-implementation analysis
  only, never started.
- **FP2 long-run priors** (transform §5.5 / ml §3) — FP2 too corrupted by sandbagging; confound
  treatment costs more than the prior is worth. Race pack ships without FP2 priors.
- **`stg_car_data` telemetry staging** (§5.6) — telemetry features computed lap-internally inside
  the cliff mart; no separate staging model needed.
- **`dim_corners` seed** — broken (~6% circuit coverage); telemetry uses lap-internal speed-minima
  instead.

#### Carried gotchas

- `track_unexplained_s` in `fct_lap_residuals` has NULLs → COALESCE inside AVG.
- App reads ALL data from GCS even in dev: `make app-data` writes disk only — must
  `make app-publish` / `app-deploy` for the app to see it (1 hr edge cache, `?v=` busting).
- `stg_laps.race_id` is NUMERIC, not the slug.
- DuckDB has no `erf()` → SE propagation uses the custom `normal_cdf` macro.
- Field cliff model is **linear**, not quadratic (the old roadmap's squared formula was wrong →
  ±72s error).

---

## Maintenance & ops

Full runbook: [MAINTENANCE_AND_PIPELINE_SYNC.md](./MAINTENANCE_AND_PIPELINE_SYNC.md).

1. **Seed maintenance** — on a new season, log incident windows into `seeds/raw_dim_events.csv`
   (SC/VSC/red-flag boundaries → outlier weights) and Pirelli C1–C5 → Soft/Medium/Hard mappings
   into `seeds/tyre_allocations.csv`, then `dbt seed`.
2. **Coefficient fit → review → promote** — `make coefficients-fit` deposits params in
   `seeds/_pending/`; physically audit plausibility; `make coefficients-promote`; `make dbt-dev-full`.
3. **Reference-drift CI gate** — after editing a model/macro/description, regenerate with the
   `scripts/gen_*_reference.py` family; `docs-ci.yml` re-runs them + `git diff --exit-code` on
   `docs/reference/`. Never hand-edit `_AUTOGENERATED` pages.
4. **Mintlify nav promotion** — new pages must be registered by hand in `docs/docs.json` `navigation`.

---

## Reminders

- **Never commit/push** without an explicit instruction.
- `_roadmap/` is gitignored — read the code and per-directory READMEs for ground truth.
