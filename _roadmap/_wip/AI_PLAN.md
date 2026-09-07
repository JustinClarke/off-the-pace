# AI Plan — ML Models & In-Product AI

Consolidates the ML/AI roadmap: the current model family, the locked ML scope decision, the
in-product AI co-strategist, and backlog AI ideas.

> Watch-along-specific ML (offline Monte Carlo, §4) lives in the [Watch-Along Plan](../PROJECT_PLAN.md#watch-along-plan--historical-race-replay--strategy-product) section of PROJECT_PLAN.md.

---

## ML scope decision (locked 2026-06-11) — read before adding any model

**ML stays concentrated on tyre cliff + degradation.** Everything else stays deterministic/statistical.

| Feature | ML? | Rationale |
|---|---|---|
| Tyre cliff (classifier + onset) | **Yes — primary** | lap time alone can't separate "driver managing pace" from "tyre gone"; telemetry leading indicators are exactly what a model captures |
| Degradation (p10/p50/p90, stint life) | **Yes** | same feature space; richer inputs → better cliff-point and deg-rate estimates |
| Ghost-car pace / race finish | **No** | lap/sector times + stint metadata; stays statistical |
| Residual decomposition, event corrections | **No** | structural/accounting; ML adds nothing but drift surface |

Every ML-ified feature costs an ONNX export, a parity check, training-data deps, and a
silent-drift channel — the stale-mart incident is the standing proof. Don't pay that cost where a
GROUP BY does the job.

---

## Current model inventory (v3)

`cliff_classifier_v3`, `degradation_regressor_{p10,p50,p90}_v3`, `stint_life_regressor_v3` — all
with `.bst` + `.onnx`, Optuna studies, ablation/calibration artefacts, `manifest.json` +
`model_card.json`.

- **41 features** (38 base + 3 telemetry groups). Telemetry at `data/bronze/telemetry/`,
  98.8% coverage 2018–2024, computed **lap-internally** (not via the broken `dim_corners` seed).
- Telemetry win: **+3.9pp** cliff accuracy (69.7 → 73.6%) on 2024 holdout; deg/stint-life neutral.
  Results in `ml/artefacts/ablation_telemetry.json`.
- Predictions read a single mart (`fct_cliff_prediction_features`); `schema.py` asserts the
  feature list at export time (fail-loud guard). ONNX parity proven (maxAbs 7.6e-6).
- All telemetry features are causal — offline accuracy booster only, never on a live critical path.

**Holdout discipline:** 2025 is the designated blind-test holdout (ingested post-launch). Headline
reports on the final TimeSeriesSplit fold (2024 interim) and flips to a true holdout the moment
2025 ingests — no code change.

---

## In-product AI co-strategist (future, not started)

An embedded chat assistant: text-to-SQL over the client-side DuckDB-Wasm engine + a repo guide.

**Architecture:**
```
User Prompt → React Chat UI → Firebase Cloud Function (proxy) → Claude API
                                                                     ↓
                                              execute_local_sql tool call
                                                                     ↓
                                        DuckDB-Wasm (client-side) → rows back → final answer
```

**Implementation steps:**
1. **API & security** — Claude API key in Firebase Secret Manager (`CLAUDE_API_KEY`); Cloud Function
   proxy (`api/askClaude`); Firebase App Check to restrict to `off-the-pace.web.app` only.
2. **Schema context** — `scripts/gen_agent_schema.py` compiles mart schemas into a compact system
   prompt block. Feed `docs/repo-tour.md` as static codebase context.
3. **Chat UI** — floating drawer in `AppShell` (Radix UI Dialog / Framer Motion);
   `ui/feedback/ChatAssistant.tsx`; streaming message bubbles; syntax-highlighted SQL blocks +
   "Run Query" button.
4. **Client-side SQL loop** — define `execute_local_sql(sql: string)` as a tool; Claude calls it
   when it needs data; React passes SQL to `data/duckdb/client.ts`, returns rows, Claude explains.

**Model:** Claude (`claude-sonnet-4-6` or latest at build time) via Anthropic API. Re-evaluate at build time.

**Quality gates:**
- Zero key leakage in client bundle.
- `season` / `race_id` partition enforcement in generated SQL (prevent full-scan).
- Read-only SQL validation before execution.
- Graceful empty-result fallback.

---

## Backlog AI ideas

- **Panic Meter** — per-corner `stddev(throttle_delta)` / `stddev(steering_delta)` from telemetry
  as a driver-instability proxy and early cliff predictor. Candidate: `int_lap_instability_proxy.sql`.
- **Wind-Trap predictor** — dot-product of weather wind vector with per-sector car heading as a
  covariate for the residual decomposition. Candidate: `int_lap_wind_aero_load.sql`.

---

## Explicitly deferred (do not build)

New model families (no NN, no sequence models), team-radio NLP, circuit-affinity ML features
(double-count issue documented), and any streaming/live inference redesign of the v3 models.
