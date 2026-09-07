# Streaming Plan — Live Watch-Along Phases

> **Canonical plan for the deferred live/streaming work.** Everything buildable
> today (batch pipeline + historical replay dashboard) lives in the
> [Watch-Along Plan](./PROJECT_PLAN.md#watch-along-plan--historical-race-replay--strategy-product)
> section of PROJECT_PLAN.md. Enterprise streaming on Microsoft Fabric is tracked
> as Phase 4 in [PROJECT_PLAN.md](./PROJECT_PLAN.md).

**Status: ⛔ DEFERRED — gated.** Nothing here is started. These phases turn the
historical replay product into a real-time watch-along driven by a live timing feed.
The decision to build them is **gated on the §4 validation conditions below clearing**,
and on a live-timing source/licensing decision. Nothing in this live stack accelerates
prediction validation — that is why predictions ship first.

**Core principle (locked):** the v3 models stay **causal/pure**. Telemetry is an
offline accuracy booster only — never on the live critical path. Live scoring reuses
the same ONNX models and the same UI components as the historical replay; only the
data source swaps (DuckDB-Wasm static parquet → real-time WebSocket feed).

---

## Gate conditions — must discharge before any live phase

These are the open conditions from the transform §4 validation gate (CONDITIONAL GO).
The evidence for condition 1 comes from **ml v0.2 §4.2** (offline Monte Carlo
validation) in [PROJECT_PLAN.md](./PROJECT_PLAN.md#watch-along-plan--historical-race-replay--strategy-product).

1. **Recalibrate confidence** — inflate SE by k≈2.77 OR source finish-position SE from
   the Monte Carlo core. (ML §4.2 is the evidence for which route. Note: the k≈2.77
   recipe broke on the full-data rebuild → **favour the MC route**.) Tracked as
   **GATE-1** in [ISSUES.md](./ISSUES.md).
2. **Aggregate reorderings at full-race granularity** — suppress per-stint deg-driven
   swaps. Transform/app concern; ML §4.1 distributions feed it.
3. **Re-run gate after fuller data.** ✅ Discharged — full 2018–2024 rebuild held
   CONDITIONAL GO, LORO stronger (0.65/145 races).

Conditions 1 and 2 remain open.

**Additional prerequisites before live work starts:**
- transform §5.7 (race-pack exporter) done + app race-pack loader proven — see below.
- Live-timing source + licensing decision: **FastF1 live vs OpenF1**.
- Live relay service (Cloud Run + OpenF1/SignalR) — not built.

---

## app 2.4 — Race-pack loader 🔲 (blocked on transform §5.7)

Thin data module, **no UI**. Fetch + validate the §5.7 race-pack bundle against its
schema, hand to the existing ONNX layer; respect the global ONNX run-queue (the
"Session already started" fix). This is the plumbing seam between batch and live — the
historical replay does not need it (full race history is already client-side), but the
live relay does.

**Acceptance:** app loads the race pack from CDN (not just local disk) with no KeyErrors;
schema-validation test passes.

---

## Live phases 4–6

Replay watch-along (live), live relay, strategy engine v2.

**Architecture target:** race pack on GCS + Cloud Run timing relay + in-browser Monte
Carlo roll-forward (extends `scripts/mc_finish_order.py`). **Not** streaming inference —
the models stay causal/pure; telemetry is offline-only.

| Concern | Historical Replay (WATCHALONG_PLAN) | Live (this plan) |
|---------|-------------------------------------|------------------|
| Data source | Static parquet (DuckDB-Wasm) | Live relay (Cloud Run + OpenF1/SignalR) |
| Scoring | Pre-scored `mart_degradation_predictions` + optional ONNX | In-browser ONNX (same models) |
| Finish order | Ghost car pre-computed positions | `mc_finish_order.py` roll-forward |
| Race-pack contract | Not needed — full history available | `fct_race_pack_priors.sql` (§5.7) required |
| Gate conditions | N/A — historical, not predictive | §4 conditions 1 & 2 must clear |

The historical replay's UI components are designed to be reused here by swapping the
data source from DuckDB-Wasm static queries to the real-time WebSocket feed.

---

## Relationship to Fabric (PROJECT_PLAN Phase 4)

[PROJECT_PLAN.md](./PROJECT_PLAN.md) Phase 4 covers an **enterprise** streaming path on
Microsoft Fabric (Eventstream live telemetry, OneLake, KQL, Fabric Notebooks for
retraining, Azure backend for server-side streaming). That is a separate, later
trigger (employer interest in enterprise F1 analytics, or a model ready for
production-scale inference) and is **not** a prerequisite for the live phases here —
the live phases target the GCS + Cloud Run + in-browser MC stack above.
</content>
