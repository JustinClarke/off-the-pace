# R5 — Representation and the transform layer: has it been outgrown?

**Track:** T6 + T8 · **Prices:** `02a`, `02c`, `02d`, and the transform layer generally
**Status:** DRAFTED, reconciled against the dbt models and `ml/src/features.py`

The user's question was whether the transform layer has been outgrown. Two separate answers:
**it has been outgrown as a feature *representation*, and it has a structural gap as a *leakage
guard*.** The second is the more urgent of the two and the cheaper to fix.

---

## Part 1 — The representation, and the evidence already in the repo

The campaign has run an experiment that answers this question and has not been read as answering
it.

**Verified, from `ml/src/schema.py`'s own Phase 9 and Phase 10a notes:**

- Phase 9 dropped 18 of 42 feature columns on a noise-floor group ablation. Among the dropped
  groups were `powertrain` (6) and `telemetry_cliff` (5) — which were, in `schema.py`'s words,
  *"the mart's entire consumption of `int_lap_telemetry_aggregates`"*. Every group dropped
  "cleared in none" of the three families.
- Phase 10a then added the 9-column `proximity` group and it **cleared** — p50 pinball at 1.54×
  its floor, cliff macro-F1 at 2.17×, with the permutation-null arm attributing the classifier's
  win unambiguously to information.
- `schema.py` names why: proximity is *"the first group in either series sourced from a DIFFERENT
  SENSOR rather than from a further transform of the car channel or of lap times."*

Put those together and the finding is sharper than "a new sensor helped":

> **Hand-crafted scalar aggregation of the car channel produced nothing that survived ablation.**
> 24.5M rows in `fct_telemetry_deltas`, 137,447 rows of `int_lap_telemetry_aggregates`, reduced to
> eleven summary statistics, and all eleven were dropped as adding no information. The channel
> that *did* pay was one that had never been aggregated at all before.

The natural reading is that the channel is not information-poor — the **aggregation** is
lossy. A lap's speed/throttle/brake trace is a path with a few hundred samples; collapsing it to
means and maxima is close to the worst available summary of a path.

### Option A — Path signatures. Recommended, because it fits the pipeline unchanged

A lap is a path in `(distance, speed, throttle, brake, gear, DRS)` space. The **signature
transform** from rough path theory maps such a path to a graded sequence of iterated integrals
that is a **universal, faithful, reparameterisation-invariant** feature set — universal in the
precise sense that linear functionals of the signature approximate any continuous function of the
path arbitrarily well.

Why it fits *this* repo specifically, better than the alternatives:

- **It is a deterministic transform, not a learned one.** A truncated log-signature at depth 3–4
  over 5–6 channels is on the order of 100 numbers, computed from the raw path with no fitting,
  no training loop, no checkpoint. It goes in the transform layer as a UDF or a Python model and
  comes out as columns in the mart. The `.bst`/`.onnx` export path, the parity gate and
  `behaviour_audit` are all untouched.
- **It is invariant to reparameterisation**, which is exactly the invariance wanted here: two
  laps driven the same way at different sample rates or slightly different speeds through a
  sector should map near each other.
- **It handles irregular sampling natively** — which matters, because telemetry sampling is not
  uniform.
- **It is testable under `gates.md` unchanged.** Add-ablation on the identical split, delta
  against the family's own reseed floor, permutation-null arm. A signature group either clears
  or it does not, and either way it is a real answer to whether the aggregation was the problem.

References: [A Generalised Signature Method for Multivariate Time Series Feature
Extraction](https://arxiv.org/pdf/2006.00873) (Morrill et al.) is the practical recipe — it
enumerates the augmentation / window / transform / rescaling choices and gives a defensible
default; [Scalable Machine Learning Algorithms using Path Signatures
(2025)](https://arxiv.org/abs/2506.17634) and [Path Signatures for Feature Extraction
(2025)](https://arxiv.org/pdf/2506.01815) cover current practice. A close analogue in a sport
setting: [The path to a goal: understanding soccer possessions via path
signatures](https://arxiv.org/pdf/2508.12930).

### Option B — Functional PCA on the speed trace. Nearly free, because the grid already exists

A lap is also a curve, `speed(relative_distance)`. FPCA decomposes a sample of such curves into
orthogonal modes of variation; the per-lap scores on the leading modes are the features. It gives
interpretable output — mode 1 is typically "overall pace", mode 2 something like "braking earlier
vs later into the heavy stops" — which is a better fit for the publication track (`06`) than a
signature coefficient.

**And the hard part is already done.** `int_lap_proximity` already cuts each lap into **100
fractions of `relative_distance`** from the position channel. That is a registered functional
grid. Registration — aligning curves so that modes describe shape rather than phase — is the step
that usually sinks FPCA on this kind of data, and this repo has it built for another purpose.
References: [a functional analysis of speed profiles](https://arxiv.org/pdf/1312.2252) (smoothing
with derivative information, curve registration, functional boxplots) is almost exactly this
problem on road vehicles.

### Option C — Self-supervised time-series embeddings. Not yet

TS2Vec, T-Rep, TimesURL and the newer JEPA-style variants learn representations without labels
and would likely beat both of the above on raw predictive power. They also require a training
pipeline, a checkpoint to version, an embedding to export, and they break the "a feature is a
column computed by SQL" contract the whole transform layer rests on. **Do A or B first**, because
if a deterministic path transform clears the gate, the question of whether a learned one clears it
by more is a Phase-N question, not a now question.

---

## Part 2 — The leakage guard has a structural gap, and both known live leaks sit in it

`ml/src/features.py::audit_forward_window` is better than most production stacks have. It parses
every compiled dbt model with `sqlglot` and flags two shapes:

- **`_expr_is_forward_looking`** — a `LEAD()`, or a window frame with a `FOLLOWING` bound.
- **`_self_join_inequality`** — an inequality between same-named columns under different
  qualifiers, in a `JOIN ... ON` or a `WHERE`. The docstring is explicit about why this exists:
  *"a window is not the only way to see another row."*

It also refuses to swallow unparsed models, turning them into violations. That is genuinely good
design.

**But both of the programme's known live leakage suspects have neither shape.** Verified by
reading the SQL:

| model | the construct | `LEAD`? | `FOLLOWING` frame? | self-join inequality? | **detected?** |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `int_corner_skill_residuals` | `FLOOR(lap_number / 5.0) * 5.0 AS lap_window`, then `GROUP BY race_year, race_id, corner_name, lap_window` | no | no | no | **no** |
| `int_sc_hazard_history` | `GROUP BY race_year, race_id` → aggregated to one row per `circuit_slug`, pooling every season | no | no | no | **no** |

Neither uses a window function at all. The forward reach — where there is one — lives in **the
scope of a `GROUP BY`**, which the walker never inspects because it is not looking for it.

> **The gap, named:** the audit detects **row-referencing** leakage and is blind to
> **aggregation-scope** leakage. An aggregate whose grouping key carries no time ordering, or
> whose scope spans the label's future, passes silently.

That is a class, not two instances. Every `int_*` model that computes a rate, a median or a
baseline by `GROUP BY` is in it, and there are dozens.

### A note on `02a` specifically — the item's framing may not fit its own SQL

`02a` asks whether the 5-lap field-median bucket is *centred* (reaches forward → leaks) or
*backward-looking* (safe → `02c` unblocks). Reading the SQL, **it is neither**: `FLOOR(lap/5)*5`
is a **fixed block**. A lap at position 0 of a block is compared against a median that includes up
to four laps that had not yet run; a lap at position 4 is compared against one that includes none.
The forward reach is real but **position-dependent within the block**, and it averages to about
two laps.

This is not a ruling — `02a` is the pointer item and running it is the next session's job, not
this round's. It is a flag that the item's binary acceptance criterion admits a third answer, and
that whichever way it lands, the fix is likely "recompute the median as a trailing window" rather
than either branch as written.

### What the literature says to do about the class

The framing that generalises is **point-in-time correctness**: a training row must see feature
values *as of* the label's timestamp and no later. The mature statement of it is the feature-store
one — an `ASOF LEFT JOIN` between the label spine and the feature history, which is
[first-class in DuckDB](https://duckdb.org/docs/sql/query_syntax/from#asof-joins) and therefore
available here at no infrastructure cost.

A useful taxonomy is in [a 2026 PLOS One paper on temporal leakage in build
prediction](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0340167), which
splits leakage into **direct outcome encoding**, **execution-dependent metrics** and **future
information leakage**. Mapped onto this repo: the barred `driver_skill_*` columns are the first
(and `schema.py` documents the `driver_skill_loro_s` case exhaustively); `02a`/`02d` are the
third. The second — metrics generated during the event being predicted — is the one nobody has
audited here, and `is_training_eligible` plus the anomaly flags are where it would live.
See also [Leakage and the reproducibility crisis in ML-based
science](https://www.sciencedirect.com/science/article/pii/S2666389923001599) (Kapoor & Narayanan)
for why this class of bug survives peer review so reliably.

### Recommendation — three changes, in increasing cost

1. **Extend `audit_forward_window` to aggregation scope.** For every `GROUP BY` in a model that
   feeds `FEATURE_COLUMNS`, require that the grouping key set either (a) includes a time key at or
   below the label's grain, or (b) is declared exempt in the model's `schema.yml` with a written
   reason. This is a walker over `exp.Group` and a meta property — days, not weeks — and it
   converts a class of silent bug into a build failure. **This is the highest-value item in this
   entire research round on a cost-adjusted basis**, because it is the only one that prevents
   future defects rather than measuring past ones.
2. **Make the trailing-window pattern a macro.** `02d` needs `int_sc_hazard_history` rebuilt as a
   season-lagged expanding rate; `02a` may need the same for the corner medians. Write it once as
   a dbt macro (`{{ expanding_rate(...) }}` / `{{ trailing_median(...) }}`) so the third instance
   is a call rather than a rediscovery, and so the auditor has one shape to whitelist.
3. **Do not migrate the stack.** SQLMesh's incremental-by-time-range semantics with explicit
   `@start_ds`/`@end_ds` would structurally prevent some of this, and its column-level lineage is
   better than dbt's. It is not worth a migration: 70 models, a working `.sqlfluff`, a working
   test suite and a working SQL-AST auditor is a lot of sunk correctness to re-earn for a property
   that item 1 buys directly. **Verdict: the transform layer has not been outgrown as
   infrastructure.** It has been outgrown as a *representation* (Part 1) and it has one specific,
   fixable hole in its guard (Part 2).
