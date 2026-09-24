# 03 — Driver vs car

**Group:** 03 · **Depends on:** `03a` gates `03c`; `03b` widens it · **Cost:** 1d → 2d → 1–2w

The one question in this programme that needs the **panel** rather than the model, and the one
an F1 team cannot answer with its own data: a team's drivers are perfectly confounded with its
chassis. Drivers move; that is the identification.

## What already exists

- `transform/tasks/coefficients/fit_constructor_car_fe.py` — a two-way fixed-effects
  regression, `pace_delta_s ~ 1 | driver_id + constructor_race`, already separating driver
  from car **on pace level**. Its docstring records why the naive car term hands a weak
  driver's slowness back as skill.
- `int_constructor_deg_sensitivity.sql` — degradation slope per constructor × compound ×
  season, within-stint FE with DerSimonian–Laird empirical-Bayes shrinkage. **Constructor
  only**; driver skill is deliberately absorbed into the stint fixed effect.

**The gap:** pace level is decomposed into driver and car. Degradation *slope* is not. Nobody
has separated driver from car in tyre degradation, and it is one target swap away from
machinery that already exists and is already gated.

---

## 03a — Mover panel · go/no-go

**Objective.** Establish whether the connected set supports a two-way decomposition before any
estimator is written.

**Verified panel dimensions** (from `fct_lap_residuals`, 2026-09-07): 40 drivers, 18
constructors, 7 seasons, 137,447 clean laps, 76 driver-constructor spells, 158
driver × constructor × season cells, **21 movers**.

**The trap, and it is load-bearing.** Six drivers appear to switch teams mid-season. **OCO and
PER in 2018 are the Force India → Racing Point administration rename — the same car, a new
entity.** Counting that as mobility manufactures identification out of a paperwork change.
Excluding it leaves three genuine mid-season events: **GAS ↔ ALB 2019** (a literal crossover —
each drove both cars inside one regulation season), **RUS 2020** (Williams plus one race at
Mercedes), **BEA 2024** (substitute appearances at Ferrari and Haas).

**Method.** Build the driver × constructor × season spell table; drop the rename; compute the
connected set and the mover count per connected component. Report how thin the thinnest
identifying cell is.

**Definition of done.** Connected set characterised with the rename excluded; a stated
go/no-go on `03c` at 2018–2024 alone; the rename exclusion written down where the next session
will meet it.

---

## 03b — Jolpica ingest 2011–2017

**Objective.** Widen the panel where it is the binding constraint.

**Verified.** Bronze timing/telemetry covers **2018–2024 only** — that is FastF1's coverage.
`ingestion/src/jolpica_client.py` exists and currently pulls driver standings, constructor
standings and classified pit stops into `data/bronze/reference/jolpica/`.

**The tiers, and why 2011 is the boundary.**

| Range | Available | Usable for |
| :--- | :--- | :--- |
| 2018–2024 | Compounds, telemetry, weather | Everything |
| **2011–2017** | Lap times + pit stops; no refuelling | **Degradation slope from lap times; stints recoverable from pit data** |
| 1996–2010 | Lap times only; refuelling until 2009 | Pace-level driver-vs-car only — a car getting faster may be burning fuel |

**No compound data exists before 2018 at all**, so none of this feeds the ML feature contract.
Its value is entirely in `03c`'s panel width.

**Definition of done.** 2011–2017 lap times and pit stops ingested to bronze; stint boundaries
reconstructed from pit data and sanity-checked against 2018 (where both methods are available);
mover count recomputed.

---

## 03c — AKM decomposition with leave-out correction · BLOCKED on `03a`, `03b`

**Objective.** Two-way fixed effects with the **degradation slope** as outcome — driver effects
and constructor-season effects, identified off the connected set of movers.

**The part that makes it defensible.** At 21 movers the raw AKM variance components are badly
biased: driver-effect variance biased **up**, driver-car covariance biased **down** (Andrews et
al. 2008, limited mobility bias). The correction is the Kline–Saggio–Sølvsten leave-out
estimator. Running AKM without it on this panel produces a number a competent analyst
dismantles in one question; running it with the correction, and **reporting how much the
correction moved the answer**, is the result.

Note the connection to `01b`: the m = 2 bias there and the limited-mobility bias here are the
same statistical problem, and the leave-out estimator is the fix for both.

**Validation.** The GAS ↔ ALB 2019 crossover is an assumption-light check on an
assumption-heavy estimate. If the FE decomposition and the crossover disagree, the FE result is
wrong.

**Honest caveat to carry in any write-up.** The "firm" is really constructor × season, since
the car changes every year, so the identifying cells thin fast. Standard errors may be wide.
Report them; do not report a point estimate alone.

**Definition of done.** Driver and car variance components with leave-out correction, the
uncorrected numbers reported beside them, the crossover validation, and standard errors on
every published figure.
