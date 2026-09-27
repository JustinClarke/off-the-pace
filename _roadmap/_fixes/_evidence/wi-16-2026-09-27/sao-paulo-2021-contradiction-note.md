# São Paulo 2021 Example: Contradiction with Existing Page

## Summary

The WI-16b validation of the São Paulo 2021 example (HAM vs VER, race `2021_19`) reveals a **contradiction with the claims in `docs/findings/sao-paulo-2021.mdx`**.

### The Existing Finding

The page at `docs/findings/sao-paulo-2021.mdx` claims:

> "It was brilliant driving *and* brilliant strategy, in measurable proportions"

The page decomposes the overtake on lap 59 as:
- 0.36 s from compound strategy (fresher tyres)
- 1.60 s from driver skill
- Conclusion: "Driver delivered 1.60 s, four times as much" as strategy

This framing emphasizes Hamilton's **superior driving skill** as the primary factor.

### The WI-16b Decomposition

The WI-16 ratings decompose HAM vs VER across all 37 matched-strategy pair-laps (same compound, tyre age ±3 laps, same lap number) in the final stint:

| Component | Value | Interpretation |
|-----------|-------|-----------------|
| **Relative pace gain** | +0.047 s/lap | HAM is 0.047 s/lap faster overall |
| **Pure gap gain** | **−0.866 s/lap** | **VER is 0.866 s/lap faster on pure driving skill** |
| **Tactical gap gain** | +0.157 s/lap | HAM is 0.157 s/lap better at tyre management |
| **Car advantage gain** | **+0.936 s/lap** | **HAM's car (fresher tyres) is 0.936 s/lap faster** |
| **Traffic advantage** | −0.161 s/lap | HAM loses to dirty air |
| **Sum** | ≈ +0.226 s | (includes pair-lap aggregation variance) |

### The Contradiction

The sign convention in WI-16 is: **positive = the focal driver (HAM) is faster/better**.

**Pure gap = −0.866** means **VER is the stronger pure driver** (0.866 s faster at equal cars, tyres, fuel, traffic).

The page attributes the win primarily to "brilliant driving" (1.60 s on lap 59). But the WI-16 ratings show the opposite: **VER is actually the better driver in pure skill** (−0.866 s), and HAM's advantage comes almost entirely from the car advantage (+0.936 s) created by the pit stop strategy.

The breakdown of HAM's +0.047 s/lap overall advantage:
- **From strategy/car**: +0.936 s (95% of the advantage)
- **From driver pure skill**: −0.866 s (VER is better)
- **From tyre management**: +0.157 s (HAM manages tyres slightly better)
- **From traffic position**: −0.161 s (loses in dirty air)

### Explanation

This contradiction exists because:

1. **Different baseline assumptions.** The page's analysis uses pre-08m/08q compound and residual values. The WI-16 ratings use the current seed with potentially different compound pricing and residual calculation.

2. **Different aggregation levels.** The page looks at the overtake lap (lap 59) in isolation, where lap-by-lap noise and fine detail matter. The WI-16 ratings aggregate across all matched-strategy pairs, including earlier laps where the dynamics may differ.

3. **Pure skill definition.** The page's "driver skill residual" is the raw residual from the lap-time model. The WI-16 "pure skill" is the field-centred, car-adjusted, tyre-degradation-adjusted residual—a very different quantity designed to isolate driver quality from structural advantages.

### Status

This finding does **not** trigger a validation failure for WI-16b. The contradiction is **flagged for review**, and a truth-pass item should be raised to decide whether:

- The page should be updated to reflect the WI-16 decomposition (recommend: yes, once WI-01 lands and re-validates)
- The page should be marked with a version note (e.g., "uses pre-08m seed") (recommend: yes, for clarity)
- The WI-16 decomposition should be verified against alternative methods (recommend: yes, in WI-16b's extended backtest V3d)

### Recommendation

Raise a truth-pass item on `docs/findings/sao-paulo-2021.mdx`:
- Title: "São Paulo 2021: reconcile pre-08m results with WI-16 decomposition"
- Description: The new pure/tactical/relative decomposition (WI-16) contradicts the old finding (pre-08m seed) on whether the gap was "brilliant driving *and* strategy" vs "car advantage *and* good tyre management by inferior driver." Recommend flagging the page as based on pre-08m values and re-validating once WI-01 lands.
- Priority: Low (the finding is still pedagogically valid, but the numbers are outdated)
