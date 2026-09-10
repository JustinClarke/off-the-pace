#!/usr/bin/env python3
"""
Apply Benjamini–Hochberg (BH) and Benjamini–Yekutieli (BY) correction
to campaign-level CLEARS verdicts.

CLEARS ratios are floor_ratio × units, where the floor_ratio is
Δ / (2*sqrt(2)*sd) estimated from 5 reseeds.

This is a DESCRIPTIVE audit: the family was assembled adaptively,
and pre-registration cannot be applied backwards. These numbers show
calibration, not FDR-controlled inference.
"""

import json
import math
from scipy import stats

# The 8 CLEARS claims from ml_execution_plan.md
# Format: (checkpoint, model, metric, ratio, description)
claims = [
    ("P8 add-ablation", "degradation_regressor_p50", "pinball", 1.54, "add-ablation total"),
    ("P8 add-ablation", "cliff_classifier", "macro-F1", 2.17, "add-ablation total"),
    ("P8 permutation", "cliff_classifier", "macro-F1 decomp", 2.28, "permutation-null decomposition"),
    ("P9 add-ablation", "cliff_classifier", "macro-F1", 1.21, "add-ablation total"),
    ("P9 add-ablation", "stint_life_regressor", "C-index", 1.30, "add-ablation total"),
    ("P9 permutation", "stint_life_regressor", "C-index decomp", 1.62, "permutation-null decomposition"),
    ("P10 add-ablation", "degradation_regressor_p50", "pinball (worse)", 2.03, "add-ablation total, harmful"),
    ("P10 permutation", "degradation_regressor_p50", "pinball decomp", 2.02, "permutation-null decomposition"),
]

# CLEARS ratio to p-value conversion:
# The ratio is Δ / (2*sqrt(2)*sd), estimated from 5 reseeds.
# Under normality, this is a t-like quantity. But the spec says
# to use BY as the honest default under arbitrary dependence.
#
# Since we have ratios (not p-values), we need a conversion.
# The ratio threshold of 1.0 corresponds to a 2-sigma (95% coverage) floor.
# Ratios > 1.0 beat the floor by that factor.
#
# For a conservative p-value conversion: treat the ratio as a z-score
# and convert to p-value assuming a standard normal.
# If ratio is the number of std errors above the floor, then
# p = 1 - Φ(ratio) under a one-tailed test.

def ratio_to_pvalue_twotailed(ratio):
    """
    Convert a CLEARS ratio to a two-tailed p-value.

    The ratio is Δ / (2*sqrt(2)*sd), where sd is estimated from n=5 reseeds.
    With df = n - 1 = 4 (Bessel correction), and if the true effect is 0,
    the test statistic under the null follows a t(df=4) distribution.
    """
    # df = 4 from the 5 reseeds
    # Two-tailed p-value: P(|t| >= ratio) where t ~ t(df=4)
    df = 4
    pval = 2 * (1 - stats.t.cdf(abs(ratio), df))
    return pval

# Convert ratios to p-values
pvalues = [ratio_to_pvalue_twotailed(ratio) for _, _, _, ratio, _ in claims]

print("=" * 80)
print("CAMPAIGN AUDIT 04c: Multiple Comparison Correction")
print("=" * 80)
print()
print("⚠ DESCRIPTIVE AUDIT — not FDR-controlled statement")
print("  The 22 checkpoints were run without a declared construction.")
print("  The family was assembled adaptively: each checkpoint's arms")
print("  were selected knowing the previous checkpoint's results.")
print("  Pre-registration cannot be applied backwards.")
print("  This report shows calibration of the campaign's own confidence,")
print("  not a forward-valid FDR guarantee.")
print()
print("-" * 80)
print()

# Display the claims and converted p-values
print("CLEARS verdicts (8 claims, including duplicates):")
print()
print("Checkpoint | Model | Metric | Ratio | p-value")
print("-" * 60)
for i, (checkpoint, model, metric, ratio, desc) in enumerate(claims):
    pval = pvalues[i]
    print(f"{i+1:2d}. {checkpoint:12s} | {model:25s} | {ratio:4.2f}× | p={pval:.4f}")
print()

# Sort by p-value for BH/BY ranking
ranked = sorted(zip(pvalues, claims), key=lambda x: x[0])

print("Ranked by p-value (ascending):")
print()
print("Rank | p-value | Checkpoint | Model | CLEARS Ratio | Description")
print("-" * 80)
for rank, (pval, (checkpoint, model, metric, ratio, desc)) in enumerate(ranked, 1):
    print(f"{rank:2d}. p={pval:.4f} | {checkpoint:12s} | {model:25s} | {ratio:4.2f}× | {desc}")
print()

# Apply Benjamini–Hochberg (BH) — assumes independence or PRDS
print("=" * 80)
print("BENJAMINI–HOCHBERG (BH) Correction")
print("Assumes independence or Positive Regression Dependency on Subset (PRDS)")
print("=" * 80)
print()

m = len(pvalues)
alpha = 0.05

# BH: sort p-values, find largest k such that p(k) <= (k/m) * alpha
ranked_pvals = sorted(pvalues)
bh_threshold = None
bh_rank = None

for k in range(m, 0, -1):
    if ranked_pvals[k-1] <= (k / m) * alpha:
        bh_threshold = (k / m) * alpha
        bh_rank = k
        break

print(f"α = {alpha}")
print(f"m = {m} tests")
print()

if bh_rank is None:
    print(f"No tests satisfy BH threshold. All {m} tests would be rejected.")
    bh_survivors = []
else:
    print(f"Largest k where p(k) ≤ (k/m)×α:")
    print(f"  k = {bh_rank}, threshold = ({bh_rank}/{m}) × {alpha} = {bh_threshold:.4f}")
    print(f"  p({bh_rank}) = {ranked_pvals[bh_rank-1]:.4f}")
    print()
    print(f"Expected rejections (BH FWER control): ≤ {alpha}")

    bh_survivors = [pval for pval in pvalues if pval <= bh_threshold]
    print(f"Surviving tests: {len(bh_survivors)} / {m}")
print()

# Apply Benjamini–Yekutieli (BY) — works under arbitrary dependence
print("=" * 80)
print("BENJAMINI–YEKUTIELI (BY) Correction")
print("Works under arbitrary dependence (log(m) factor more conservative)")
print("=" * 80)
print()

# BY threshold: (k/m) × α / c(m), where c(m) = sum(1/i) for i=1..m
c_m = sum(1/i for i in range(1, m+1))
print(f"Harmonic factor: c({m}) = Σ(1/i for i=1..{m}) = {c_m:.4f}")
print(f"BY correction factor: 1 / c(m) = {1/c_m:.4f}")
print()

by_threshold = None
by_rank = None

for k in range(m, 0, -1):
    threshold_k = (k / m) * (alpha / c_m)
    if ranked_pvals[k-1] <= threshold_k:
        by_threshold = threshold_k
        by_rank = k
        break

if by_rank is None:
    print(f"No tests satisfy BY threshold. All {m} tests would be rejected.")
    by_survivors = []
else:
    print(f"Largest k where p(k) ≤ (k/m)×α/c(m):")
    print(f"  k = {by_rank}, threshold = ({by_rank}/{m}) × {alpha} / {c_m:.4f} = {by_threshold:.4f}")
    print(f"  p({by_rank}) = {ranked_pvals[by_rank-1]:.4f}")
    print()
    print(f"Expected rejections (BY FWER control): ≤ {alpha}")

    by_survivors = [pval for pval in pvalues if pval <= by_threshold]
    print(f"Surviving tests: {len(by_survivors)} / {m}")
print()

# Comparison table
print("=" * 80)
print("SUMMARY: Which CLEARS survive?")
print("=" * 80)
print()

print("Claim | Ratio | p-value | BH survive? | BY survive? | Implication")
print("-" * 100)

for i, (checkpoint, model, metric, ratio, desc) in enumerate(claims):
    pval = pvalues[i]
    bh_survives = "✓ YES" if bh_threshold is not None and pval <= bh_threshold else "✗ no"
    by_survives = "✓ YES" if by_threshold is not None and pval <= by_threshold else "✗ no"

    print(f"{i+1}. {ratio:4.2f}× | p={pval:.4f} | {bh_survives:11s} | {by_survives:11s}")

print()
print("=" * 80)
print()
print("RECOMMENDATION: Use BY (Benjamini–Yekutieli)")
print()
print("  Rationale:")
print("    • The add-ablation totals and their permutation-null decompositions")
print("      are arithmetically linked (not independent).")
print("    • The campaign's 22 checkpoints were run without a declared")
print("      construction, and the family was assembled adaptively.")
print("    • BY controls FWER under arbitrary dependence and is the")
print("      honest default when independence cannot be assumed.")
print()
print("=" * 80)
