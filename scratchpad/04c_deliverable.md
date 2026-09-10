# 04c Deliverable: Campaign-Level Multiple Comparison Audit

**Item:** 04c — Apply BH (or BY) at campaign level; report which CLEARS survive  
**Status:** SPEC → MEASURED  
**Method chosen:** Benjamini–Yekutieli (BY), not Benjamini–Hochberg (BH)  
**Date completed:** 2026-09-10

---

## Executive Summary

**⚠ This is a DESCRIPTIVE AUDIT, not an FDR-controlled statement.**

The 22 checkpoints were run without a declared construction. The family was assembled **adaptively**: each checkpoint's arms were selected knowing the previous checkpoint's results. **Pre-registration cannot be applied backwards.** This report shows the campaign's own calibration of confidence, not a forward-valid FDR guarantee.

### Key Finding

**Zero CLEARS verdicts survive campaign-level multiple comparison correction at α=0.05** under either method.

The two tightest performers—cliff_classifier macro-F1 at **2.28×** and **2.17×** CLEARS ratios—have p-values of **0.0848** and **0.0958**, respectively. Both fall short of the BY threshold (0.0091) and would not survive under BH either (which would reject all 8 at α=0.05).

This finding calibrates the campaign's claims: the CLEARS verdicts, while impressive in isolation, do not constitute a family-level confirmation when correction is applied.

---

## Method: Why BY instead of BH

**Benjamini–Hochberg (BH)** assumes independence or PRDS (positive regression dependency on a subset).

**Benjamini–Yekutieli (BY)** controls FWER under arbitrary dependence, with a log(m) correction factor.

### The dependence problem in this family

The 8 CLEARS claims include:
- **Add-ablation totals** (the full effect + breakdown on add vs. remove)
- **Permutation-null decompositions** (the same experiments analyzed under permutation-null)

These pairs are **arithmetically linked**: if add-ablation decomposes into two components, the permutation-null decomposition is a direct re-analysis of the same data under a different null distribution. They are not independent; they are highly correlated.

Additionally, the 22 checkpoints were not pre-registered as a fixed family. Instead:
- Each checkpoint was designed knowing results from prior checkpoints.
- Arms were selected adaptively within each checkpoint.
- The family was assembled retrospectively from 22 checkpoints chosen for stopping and publication.

### Decision: BY is the honest default

BH's assumption cannot be satisfied. BY makes no independence assumption and is the principled choice here. Its log(m) = log(8) ≈ 2.04 factor means thresholds are roughly 2× tighter:

- **BH threshold (largest k):** none found (all 8 p-values exceed (k/8) × 0.05)
- **BY threshold (largest k):** none found (all 8 p-values exceed (k/8) × 0.05 / 2.7179)

---

## Results: Which CLEARS Survive?

| Claim | Model | Ratio | p-value | BH survive? | BY survive? |
|:---|:---|---:|---:|:---:|:---:|
| 1. cliff_classifier (permutation) | macro-F1 decomp | 2.28× | 0.0848 | ✗ | ✗ |
| 2. cliff_classifier (add-ablation) | macro-F1 | 2.17× | 0.0958 | ✗ | ✗ |
| 3. degradation_regressor_p50 (add, harmful) | pinball | 2.03× | 0.1122 | ✗ | ✗ |
| 4. degradation_regressor_p50 (permutation) | pinball decomp | 2.02× | 0.1135 | ✗ | ✗ |
| 5. stint_life_regressor (permutation) | C-index decomp | 1.62× | 0.1805 | ✗ | ✗ |
| 6. degradation_regressor_p50 (add) | pinball | 1.54× | 0.1984 | ✗ | ✗ |
| 7. stint_life_regressor (add) | C-index | 1.30× | 0.2635 | ✗ | ✗ |
| 8. cliff_classifier (add, worst) | macro-F1 | 1.21× | 0.2929 | ✗ | ✗ |

**Summary:** 0 of 8 survive under BH, 0 of 8 survive under BY.

---

## Implications for Shipped Decisions

The campaign shipped claims based on CLEARS verdicts. None of those verdicts survive family-level correction:

1. **cliff_classifier improvements (P8)** — Shipped as evidence for the model's discriminative value. Under campaign-level correction, the signal dissolves. **The decision to ship this model was exploratory, not confirmatory.**

2. **stint_life_regressor repairs (P9)** — Shipped with claims of improved predictive power. Under correction, all associated CLEARS ratios fall below threshold. **The decision to ship was exploratory.**

3. **degradation_regressor_p50 tests (P10, including harmful signal)** — Some ratios are high (2.03× and 2.02×), yet still fail correction. The pair's arithmetic linkage means both components (add and permutation) fall short together. **The decision to ship was exploratory; the harmful signal (2.03×) should be treated with greater skepticism than its isolated ratio suggests.**

**What this means:** The campaign's claims are consistent with exploration. They are not FDR-controlled. The measured effects could easily be chance findings when viewed as confirmatory statements.

---

## Forward-Valid Safeguard

The forward-valid instrument **exists as of 09b** ([`gates.md`](../foundations/gates.md) step 7 and [`e_value_construction.md`](../reference/e_value_construction.md)):

- The e-BH family **starts empty** at the first arm that declares under e-value correction.
- **No checkpoint audited here joins the e-value family.** No claim from these 22 checkpoints is retrofitted as an e-value.
- Future arms will be evaluated under pre-registered e-value correction with `09b`'s machinery.

This audit is about where the campaign came from. Forward validity is a different task.

---

## Definition of Done ✓

- [x] Enumerated the 8 distinct CLEARS claims and their ratios (04a)
- [x] Chosen a correction method (BY, justified by arbitrary dependence)
- [x] Applied both BH and BY, reported which survive (none under either)
- [x] Stated the method, reasoning, and dependence structure
- [x] Reported implications for each shipped decision
- [x] Included the descriptive disclaimer on all output
- [x] Pointed to forward-valid safeguard (09b, e-values)

---

## Caveats and Disclaimers

1. **Not an FDR-controlled statement.** The family was assembled adaptively. Pre-registration cannot be applied backwards.

2. **Describes the campaign's confidence, not ground truth.** The CLEARS ratios are real measurements, but when viewed as a family, they do not constitute a corrected inference.

3. **The p-value conversion is conservative.** Each CLEARS ratio Δ / (2√2 σ) is modeled as a t-statistic with df=4 (from 5 reseeds). This is conservative compared to knowing the true σ.

4. **Hyperparameter search and selection-among-arms are out of scope.** BH/BY does not address nested CV or selective inference, as stated in 04a. Those are separate correction problems.

5. **Forward-valid claims require e-values.** This audit is descriptive. For confirmatory statements going forward, use the machinery in 09b.
