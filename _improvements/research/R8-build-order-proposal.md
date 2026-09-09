# R8 — What the round changes about the build order

**Status: PROMOTED 2026-09-07.** Groups `08`, `09`, `10` and `11` exist in
[`../status/build-log.json`](../status/build-log.json) with 12 new items; `04b` is CLOSED; `01b`
is rescoped; `05b`/`05c` are extracted; `02a`'s criterion is corrected; the pointer is on `08a`.
Four new leaf docs written, four existing ones edited, `board.py --check` passes.

> **One deviation from this proposal, logged per the standing rule.** The text below says `02a`
> is *"absorbed into `08b`"*. **It was not, and should not have been.** `08b` is the general
> auditor extension — it *finds* aggregation-scope leaks; `02a` still has to *rule* on
> `int_corner_skill_residuals` specifically, and `02c` still gates on that ruling. Absorbing
> `02a` would have marked it terminal and silently unblocked `02c` on a question nobody had
> answered. `02a` was instead kept live with its acceptance criterion corrected, and `work/02`
> now carries the block-bucket finding with a pointer to `08b` for the class. The rest of the
> proposal was promoted as written.

---

## The problem with the current order

It is dependency-correct and it starts in the wrong place. The pointer sits on `02a` — a leakage
check on one feature — and the ladder then spends roughly a fortnight measuring things
(`04`, `01a`, `01b`) on a substrate that this round showed has **two defects nobody knew about
this morning**:

- **2018 has no compound physics at all** (7,622 rows, 6.30%, all 2018) — and the missing column
  `compound_cliff_onset_laps` is the **#1 feature** on the headline model. `01a`'s season arm
  starts at 2018–19, so its first data point is measured on a crippled base. [R7](R7-data-quality-and-shipped-surface.md)
- **The leakage auditor is blind to aggregation scope**, and both known suspects sit in the gap.
  If extending it finds more, the feature contract moves and everything downstream re-runs. [R5](R5-representation-and-transform.md)

And two instrument changes are queued behind measurements that would have to be redone in light
of them: CRPS ([R1](R1-instruments.md) §3) is the score the learning curves should be read in, and
e-values ([R1](R1-instruments.md) §2) dissolve `04b` rather than solving it.

## The ordering principle

> **Anything that changes *what you would measure* goes before the measurements.**
> Substrate → scorer → measurement → model.

The current order runs measurement first. That is the change.

---

## Proposed: three new groups, three rescopes, one closure

### New group `08` — Foundations repair. Goes to the front.

| id | task | cost | deps | why here |
| :--- | :--- | :--- | :--- | :--- |
| `08a` | Backfill `dim_compounds_season` for SUPERSOFT / ULTRASOFT / HYPERSOFT, or map them to C-number equivalents | hours | — | Repairs the #1 feature for a whole season. **Cheapest item in the round.** Every later measurement sits on better data. |
| `08b` | Extend `audit_forward_window` to aggregation scope: every `GROUP BY` feeding `FEATURE_COLUMNS` must carry a time key at or below label grain, or be declared exempt with a reason in `schema.yml` | 2–3d | — | May find more leaks. Finding them now is cheaper than finding them after `01b`. |
| `08c` | Explain the 325 lap-1 NULL `tyre_life` rows; declare `ahead_identity_stability`'s null semantics (undefined, not zero) in `schema.yml` | hours | — | Both are documentation-grade, both are currently silent assumptions. |

**`02a` is absorbed into `08b`** as one instance of the class it generalises — and its acceptance
criterion needs rewriting regardless, because the SQL is a `FLOOR(lap/5)*5` **block bucket**,
neither of the two branches the item names. See [R5](R5-representation-and-transform.md) Part 2.

### New group `09` — Scoring instruments. Before the measurements, not after.

| id | task | cost | deps |
| :--- | :--- | :--- | :--- |
| `09a` | Report CRPS alongside the pinball trio, with the calibration / resolution / **uncertainty** decomposition | hours | — |
| `09b` | e-value pre-registration per arm + campaign-level e-BH, written into `gates.md` | 0.5d | — |

`09a` before `01a`: learning curves read in pinball then re-read in CRPS is the same work twice.
The decomposition's **uncertainty** term is also an independent read on `01b`'s own quantity.

### New group `10` — Competing risks. The round's highest-value modelling work.

| id | task | cost | deps |
| :--- | :--- | :--- | :--- |
| `10a` | End-regime label per stint: green / SC / VSC / red / retirement | hours | — |
| `10b` | Cause-specific AFT arm — refit with non-green endings treated as **censored**; compare under `gates.md` against the family's own reseed floor | days | `10a` |
| `10c` | Competing-risks evaluation: cause-specific IPCW-Brier + a calibration check, with the dependent-censoring caveat stated | days | `10b` |

**`10a` and `02d` share the same label** — build once, use twice. Sequence them together.

### Rescopes

- **`01b`** — from a k-NN sweep in 33-D to **difference-based / U-statistic variance estimation,
  stratified in ≤ 3 dimensions, published as a bracket.** Three of `work/01`'s five defects
  dissolve; defect 4 (the metric) becomes the binding constraint. Cost drops from 2–3d to ~1–2d.
- **`05a`** — stays `BLOCKED` as a *shipping* decision, but two cheap pieces come out from behind
  it:
  - **`05b` — monotone constraints arm** (`age_in_stint`, `lap_in_stint`, `laps_past_cliff`,
    `cumulative_push_load_*`). Hours, no deps, stays inside XGBoost, ONNX untouched. Answers half
    of `work/05`'s structural case. **Should never have been behind a "days-weeks" block.**
  - **`05c` — GPBoost variance-components probe**, measurement-only, never shipped. 1–2d. Its
    fitted `σ²_residual` is a third bracket leg for `01`, so it belongs *inside* `01`, not after it.
- **`04a` / `04c`** — keep, but label the output what it is: a **descriptive audit** of how many
  CLEARS would survive a correction, explicitly not an FDR-controlled statement.

### Closure

- **`04b` — CLOSE.** "Decide the floor-ratio to p-value conversion" is dissolved, not solved: an
  e-value is built directly from the reseed distribution, needing no distributional assumption and
  no df on n=5. Record the reason so it is not re-opened.

### Parallel — no ladder dependency, runnable any time

| id | task | cost |
| :--- | :--- | :--- |
| `11a` | Mondrian-conformal recalibration keyed on circuit, measured **out of sample** | 1–2d |
| `11b` | Assemble the stochastic DP over pit timing from the tables that already exist | days |

`06a`–`06c` stay parallel as they are. **`D2` (CDN publish) stays the user's decision** — but
[R7](R7-data-quality-and-shipped-surface.md) raises its stakes: if production is on v6 it is
serving a different target and a different cliff label from everything the model card documents.

---

## The resulting front of the queue

```
08a  backfill 2018 compounds          hours   ← start here
09a  CRPS + decomposition             hours
05b  monotone constraints arm         hours
10a  stint end-regime label           hours
08c  null semantics + lap-1 nulls     hours
─────────────────────────────────────────────  ~1 day, five items, no dependencies
08b  aggregation-scope audit          2-3d
09b  e-value protocol into gates.md   0.5d
04b  CLOSE with reason                —
─────────────────────────────────────────────  substrate + scorer now sound
01a  learning curves (on repaired data)
01b  rescoped noise floor  +  05c GPBoost leg
10b  cause-specific AFT arm  +  02d
─────────────────────────────────────────────  then the rest of the existing ladder
```

**Five items totalling about a day sit in front of everything**, none of them dependent on
anything, all of them fixing or sharpening something the current order would have measured
around.

## To execute

Adding items requires a `cost`, real `depends_on`, and a leaf doc per group
(`status/BUILD-ORDER.md`'s rules). That means: three new leaf docs (`work/08`, `work/09`,
`work/10`, plus `work/11` for the parallel pair), edits to `work/01` and `work/05`, the `04b`
closure, then `board.py --check` and `board.py --write-order`. One pass, but a real one —
and it is a commitment, which is why it has not been made here.
