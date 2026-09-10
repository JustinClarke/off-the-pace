# E-value construction for a reseed-floor arm

**Who this is for:** the next person who has to satisfy [`gates.md`](../foundations/gates.md)
step 7. Read it before you run the arm, fill in the block at the bottom, paste that into your
leaf doc, *then* run.

**Why it exists:** the programme's CLEARS verdicts are floor ratios, not p-values, and the family
they belong to was assembled adaptively. `04b` closed on the finding that there is no honest
retrospective conversion from one to the other. An e-value goes the other way — it is declared
before the arm runs, and it composes with every other declared e-value under arbitrary dependence
and at any stopping time. Evidence and citations: [`../research/R1-instruments.md`](../research/R1-instruments.md) §2.

---

## 1. What an e-value is, in one paragraph

A non-negative number `E` computed from the arm's output, whose **expectation under the null is at
most 1**. That is the whole definition. It reads as a betting payoff: you staked £1 against the
null before seeing the data and came away with £E. `E = 20` means the null had to be unlucky at
odds of 20:1 to produce what you saw; `E = 1.4` means almost nothing happened; `E < 1` means you
lost money betting against the null, which is a legitimate outcome and must still be reported.

Two consequences that matter here, and are the only reasons this instrument was chosen:

- **e-BH controls FDR under arbitrary dependence.** The add-ablation totals and their
  permutation-null halves are arithmetically linked. BH needs independence or PRDS; e-BH needs
  nothing.
- **Stopped e-BH is anytime-valid.** FDR holds at any data-dependent stopping time, so the
  campaign can add arms, or stop, for reasons related to what it has already found.

Neither survives if `E` is chosen after seeing the delta. **The construction is only an e-value
because it was fixed in advance.** Everything below is machinery in service of that one rule.

---

## 2. The null, and which delta to feed it

The tempting null — "the arm scores no better than the baseline" — is the wrong one, because
adding columns changes model capacity whether or not they carry signal, so a raw
arm-minus-baseline delta has no reason to be mean-zero under it. Phase 10a's 1.54× group is the
worked example of exactly that failure.

Use the contrast [`gates.md`](../foundations/gates.md) step 4 already isolates:

> **H₀: the new columns carry no information.** Under H₀, row-shuffling them in train *and* eval
> leaves the fitting problem exchangeable with the real one — capacity is preserved exactly and
> only the signal is destroyed — so the real-minus-shuffled delta is mean-zero.

So the quantity the e-value scores is the **information delta**, oriented so that positive is
improvement:

```
delta_i = score(shuffled, seed_i) - score(real, seed_i)      # for a loss (CRPS, pinball)
```

The capacity delta (`shuffled − baseline`) is a nuisance parameter here, and pairing on the seed
removes the shared seed noise, which is where most of the power comes from. Report both deltas as
step 4 already requires; the e-value is built on the information one.

`attribution.py::annotate_noise` compares `abs(delta)` to the floor — two-sided. **An e-value is
one-sided by direction**: you pre-register which sign counts as improvement, and a delta in the
wrong direction produces a small `E`, not a large one. That is intended.

---

## 3. Construction A — one delta, one bet  *(cheap; read the validity condition)*

The single-fit case, mapped directly onto the floor language the gate already uses.

Let `sd` be the seed-only standard deviation of the headline (`refit_noise_floor`'s
`headline_sd`), so the null scale of a difference of two independently-seeded fits is
`sqrt(2)*sd` and the gate's floor is `F = 2*sqrt(2)*sd`. Write the delta in null-sd units:

```
z = delta / (sqrt(2) * sd)          equivalently  z = 2 * (delta / F)
```

Pre-register a scale `s = c * sqrt(2) * sd` (`c >= 1`, see below) and a betting fraction `lambda >= 0`. The
e-value is

```
E = exp( lambda * (delta / s) - lambda^2 / 2 )
```

**Validity.** `E[E] <= 1` whenever `delta/s` is sub-Gaussian with variance proxy 1 and mean `<= 0`
under H₀ — that is the *definition* of sub-Gaussian at scale `s`, so the assumption is a stated
bound on the tail of refit noise, not a distributional family and not a df on n = 5. That is the
part `04b` could not get from a p-value conversion.

**Choosing `lambda`.** Growth-rate optimal against a pre-registered alternative `delta*`: `lambda = delta*/s`.
Taking the gate's own floor as the smallest effect worth shipping (`delta* = F`) gives `lambda = 2/c`, and the
whole construction collapses to one line:

```
E = exp( (2 / c^2) * (z - 1) )
```

| `delta / F` | `z` | `E` at `c = 1` | `E` at `c = 1.5` |
| ---: | ---: | ---: | ---: |
| 0.0 | 0.0 | 0.14 | 0.41 |
| 0.8 | 1.6 | 3.3 | 1.7 |
| 1.0 | 2.0 | 7.4 | 2.4 |
| 1.2 | 2.4 | 16.4 | 3.5 |
| 1.5 | 3.0 | 54.6 | 5.9 |
| 2.0 | 4.0 | 403 | 14.4 |
| 2.5 | 5.0 | 2981 | 35.0 |

Read the two things this table says. A delta at 0.8× floor still returns `E > 1`: **`E > 1` is not
"clears"**, the floor and the e-value are separate instruments and step 3 still binds. And a
family of 30 at α = 0.05 needs `E >= 600` for a lone rejection (§5) — which is `2.1×` the floor at
`c = 1`, or `4.1×` at `c = 1.5`. A 1.2× crossing is weak evidence, and this construction says so
in a number.

**The hole, stated plainly.** `sd` comes from five reseeds. `sd/sigma ~ sqrt(chi2_4 / 4)`, so there is a
~16% chance the five seeds understate `sigma` by 40%, which inflates the exponent by 2.8× and breaks
`E[E] <= 1`. The martingale argument needs `s` fixed with respect to the data being scored. Two legitimate
ways out:

1. **Take `s` from a prior, separate reseed study of the same family** — a different seed set, run
   at an earlier checkpoint. Then `s` is genuinely fixed in advance, `c = 1` is defensible, and
   the assumption is only that the family's refit noise has not moved.
2. **Inflate and say so.** `c = 1.5` costs most of the power in the table above, and validity is
   then *conditional on* `sigma <= s`. State the condition in the leaf doc rather than letting the
   number read as unconditional.

If neither is comfortable, spend the refits and use Construction B.

---

## 4. Construction B — five paired deltas, unknown scale, exact  *(the default)*

Run the real arm and the shuffled arm at **the same five seeds** as the floor study. That is 10
refits where step 4 currently spends 2, and it is the recommended default because it removes the
plug-in-scale hole entirely: the safe t-test e-value is exact for *any* unknown `sigma`.

With `d_1..d_n` the paired information deltas (`n = 5`), `d_bar` their mean, `s_d` their sample sd
(`ddof=1`), and `t = sqrt(n) * d_bar / s_d`, pre-register `g > 0` and compute

```
E = (1 + n*g)^(-1/2) * [ (1 + t^2/(n-1)) / (1 + t^2/((1 + n*g)*(n-1))) ]^(n/2)
```

This is the one-sample Bayes factor under a right-Haar prior on `sigma` and a `N(0, g)` prior on the
effect size `mu/sigma`. Because the right-Haar prior makes it a likelihood ratio for the *t-statistic*,
whose null distribution does not depend on `sigma`, its expectation under H₀ is exactly 1 for every
`sigma > 0` — the safe t-test of Grünwald, de Heide & Koolen. `g` moves power only, never validity:
it is the squared effect size you are betting on, and `g = 1` (a one-sd effect) is a fine default
if you have no better number.

**Worked example.** Five paired CRPS information deltas, in target units:

```
d = [0.0121, 0.0088, 0.0154, 0.0067, 0.0110]
d_bar = 0.01080   s_d = 0.003305   t = sqrt(5) * 0.01080 / 0.003305 = 7.31
g = 1, n = 5:
  (1 + 5)^(-1/2)                        = 0.40825
  1 + t^2/4                             = 14.345
  1 + t^2/24                            = 3.2242
  (14.345 / 3.2242)^2.5                 = 41.75
  E = 0.40825 * 41.75                   = 17.0
```

`t = 7.3` on four df looks overwhelming and returns `E = 17`, which **does not clear e-BH in a
family of 30** (§5). That gap is the price of arbitrary dependence and optional stopping, and it
is the honest calibration of what a single strong-looking arm is worth in this campaign. Do not
read it as a bug in the construction.

**Verify before you trust it.** Simulate 100k draws of five i.i.d. `N(0, sigma)` deltas at a few `sigma`,
push them through your implementation, and confirm the mean of `E` is 1.00 to Monte Carlo error at
every `sigma`. A construction whose null mean is not 1 is not an e-value, and this check costs a
minute.

---

## 5. Construction C — beat the shuffles  *(assumption-free, capped)*

If you can afford `K` independent row-shuffles of the new columns at a fixed seed, H₀ makes the
real arm exchangeable with all `K` of them, and

```
E = (K + 1) / k   if the real arm ranks in the top k of the K+1 statistics, else 0
```

is an e-value on exchangeability alone — no scale, no tail assumption, no Gaussianity. Pre-register
`k` (`k = 1` is the sharpest). The ceiling is `K + 1`, so 19 shuffles buy at most `E = 20`; reaching
the `n/alpha` thresholds of §5 this way is expensive. Use it when the tail behaviour of the score is
genuinely unknown and you would rather spend refits than assumptions.

---

## 6. What the campaign does with them: e-BH

Collect the declared e-values `E_1..E_n` across arms — one per declared hypothesis, whenever they
were run, however dependent. Sort descending, `E_[1] >= ... >= E_[n]`, and

```
k* = max { k : E_[k] >= n / (alpha * k) }        reject the k* largest; if no k qualifies, reject nothing
```

FDR `<= alpha` under arbitrary dependence, and at any stopping time. Equivalently: run ordinary BH on
the pseudo p-values `p_i = 1/E_i`.

At `alpha = 0.05`, a lone rejection needs `E >= 20n`: `E >= 200` in a family of 10, `E >= 600` in a family
of 30. Several arms clearing together is much cheaper than one clearing alone — which is the
correct incentive, and the opposite of what a fixed per-test floor rewards.

`n` is the number of **declared** hypotheses, including the ones that returned `E < 1`. Declaring an
arm and then omitting it because it failed re-introduces exactly the selection problem this whole
instrument exists to remove.

---

## 7. The pre-registration block

Copy into the leaf doc, fill in every field, commit it, then run the arm. No field may be decided
after the delta is known.

```
### E-value pre-registration — <item id>

H0                : the <named> columns carry no information (real vs row-shuffled, per gates.md step 4)
Statistic         : <score>, cv_final_fold, train 2018-2023, eval 2024
Delta orientation : delta = score(shuffled) - score(real); positive = improvement
Construction      : A (single-delta betting) | B (paired safe-t) | C (shuffle rank)
Seeds             : <the five seeds, matching the floor study>
Parameters        : A: c = <>, s = <> (source of s: prior study | inflation), lambda = <>
                    B: n = <>, g = <>
                    C: K = <>, k = <>
Formula           : <the one line, with the numbers that are known before the run substituted in>
Declared alt      : <delta*, the smallest effect worth shipping, and why>
Hypothesis count  : this adds <m> hypotheses to the campaign family
Reported          : E, whatever its value, including E < 1
```

---

## 8. What this does not fix

- **The 22 checkpoints already run.** They have no declared construction and cannot acquire one
  retrospectively. [`../work/04-campaign-audit.md`](../work/04-campaign-audit.md) `04c` is a
  descriptive audit for that reason, and the e-BH family starts empty from the first arm that
  declares.
- **Hyperparameter search.** Optuna selection is a selection problem, not a testing problem; e-BH
  does not address it. `04a` already lists those events separately and that stands.
- **Choosing the score.** An e-value is valid for the null it declared, on the statistic it named.
  Swapping CRPS for p90 pinball after the fact is a new hypothesis, not the same one re-read.
