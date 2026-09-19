# 10e — re-tune `stint_life_regressor` under the honest split (v12 re-run, 2026-09-19)

The reasoning, the pre-registration and the verdict live in
[`../../work/10-competing-risks.md`](../../work/10-competing-risks.md) under `## 10e`. This
directory holds only what the run produced.

| file | what it is |
| :--- | :--- |
| `arms_10e_honest_retune.json` | every gate, arm, floor, e-value and bootstrap draw summary |
| `arms_10e_honest_retune.log` | the run's own transcript, in order |

Produced by [`scripts/arms_10e_honest_retune.py`](../../../scripts/arms_10e_honest_retune.py),
which imports `scripts/arms_10d_calibration_arms.py`'s instrument rather than re-implementing it,
so `10d`'s and `10e`'s numbers come from the same code. Runtime 2,381s, of which the 200-draw
paired bootstrap is 2,095s.

**Reproduce.** The two searches first — they write to a scratch directory and republish nothing:

```bash
python -m ml.src.tune --target stint_life_regressor --trials 50 --folds 4 --honest-split \
  --censoring-variant standard --objective green_pit_brier --no-refit \
  --version 10e_v12_S1 --studies-dir <scratch>/studies --best-params-out <scratch>/S1_best_params.json
python -m ml.src.tune --target stint_life_regressor --trials 50 --folds 4 --honest-split \
  --censoring-variant standard --objective green_pit_calibration --no-refit \
  --version 10e_v12_S2 --studies-dir <scratch>/studies --best-params-out <scratch>/S2_best_params.json
```

then the arms:

```bash
PYTHONPATH=. python3 scripts/arms_10e_honest_retune.py \
  --s1-params <scratch>/S1_best_params.json --s2-params <scratch>/S2_best_params.json \
  --studies-dir <scratch>/studies
```

The arms script reads the warehouse read-only and writes nothing outside this directory. The
**landing** that followed is a separate sequence and is listed in the leaf doc's landing note.

**The headline, in one line.** The parameter set this item found on 2026-09-10 survives a warehouse
rebuild, a target repair and a fresh independent search — green-pit IPCW-Brier 0.1904 → 0.1689,
paired race-cluster bootstrap +0.0226 95% [+0.0073, +0.0353], 200/200 draws — and the fresh search
loses to it on the fresh search's own inner-fold objective.

**What this run could not settle, for the fourth time.** The calibration slope: 0.6736 → 0.8754 at
paired-bootstrap P(improves) = 0.945, interval straddling zero. 24 eval races resolve a per-row
proper score and do not resolve a slope fitted through five binned points.
