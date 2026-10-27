# DA-03 follow-up: slow-corner loss under a blocking control

**DRAFT, not registered.** Not committed, no hash recorded, nothing run. Drafted 2026-10-27. Owner choices C1-C4 settled 2026-10-27.

**Label: EXPLORATORY-CONFIRMATORY FOLLOW-UP.** This hypothesis was suggested by the failed DA-03 run. DA-03 failed on its registered spec (P2 and P3 failed in every sample; P3 found slow corners losing more than fast ones). This is a new test with its own pre-registration. It does not rescue, amend or reinterpret DA-03. DA-03 stays failed whatever this test finds.

**What was seen beforehand.** The hypothesis came from the failed DA-03 run and the exploratory look that followed it. It was not stated before DA-03 was run. DA-03 stays FAILED on its registered spec, and nothing in this test changes that.

**What the drafter has seen (disclosure).** The full DA-03 output, and the exploratory per-season and per-circuit tables (descriptive, not confirmatory). Those tables showed slow-corner losses of about 130-160 ms per micro-sector, against about 50-60 ms overall, and flagged blocking and the mix of street circuits as the main artefact risks. The brief fixed the kind of blocking proxy before drafting began. The cut below comes from the definition of `y_s`, not from any output. Partial per-circuit numbers were visible while race counts were being gathered. The race counts, the venue list and the kept-row counts in section 3 come from count queries. The power figures in section 7 were produced before registration.

## 1. Hypothesis

When the car ahead is not itself slow, a following car within 1 s still loses more time in slow corners than in fast corners.

- **Support (PASS):** the per-sample result is S in the pooled sample, in 2018-21 and in 2022-25 (section 5).
- **Refutation (REFUTED):** the per-sample result is R in at least one sample (section 5). Either the slow-corner excess is gone there, or it is too small to matter by the size logic of the DA-03 rulebook.
- **Inconclusive (INCONCLUSIVE):** no sample is R and at least one is N. This is reported as inconclusive, never as partial support. In plain words: the data cannot tell whether slow corners still lose more once slow cars ahead are removed. This is neither evidence for nor against, and it is not partial support.

## 2. Data

- The same warehouse as DA-03 (`int_microsector_proximity` joined to `int_microsector_corner_class` and `stg_laps`, 20 micro-sectors, seconds grain, 2018-2025, 171 races), rebuilt by the same dbt models at the commit where this file is registered.
- The same valid rows as DA-03: `invalid_reason IS NULL`, `y_s` present, `ahead_y_s` present, `tyre_life` present (the estimator drops rows with no tyre age). The lapped-car rule (DD5) is unchanged: rows with a lapped car ahead within 3 s are already invalid.
- The same corner classes as the registered P3: **low** apex under 120 km/h, **high** 200 to under 280 km/h. The thresholds, buffers and apex-speed definition are unchanged.
- The same model as the registered spec `p3`: the four gap bands interacted with corner class, a driver-lap FE, a driver-race by corner-class FE, `ahead_y_s`, tyre age by class, CRV1 by race, and t(races - 1) intervals. Only the sample changes (sections 3 and 4).

## 3. Blocking control (fixed)

- **Proxy:** `ahead_y_s`, the car ahead's own time in the same micro-sector minus the field median for that race, lap and micro-sector. It is built from the car ahead's crossings only and never reads the follower's `y_s`.
- **Cut:** keep a row only if `ahead_y_s <= 0`, meaning the car ahead was at or quicker than the field median in that micro-sector. The cut applies to every row, in every gap band (the >3 s reference band included) and every corner class, so all rows are selected the same way. There is no noise margin.
- **Why 0, no margin:** zero is the reference that `y_s` is built on, so the cut needs no estimate and no tuning. A margin would have to be picked from a noise figure, which adds a free choice that could drift toward a preferred result.
- **Kept rows:** 539,516 of 1,040,951 valid rows in the 59 races (51.8%).
- **Known limits, stated now.**
  - DA-01 crossing noise (0.053-0.061 s in 2018-21, 0.067-0.078 s in 2022-25, as quoted in the DA-03 registration) puts some slightly slow cars ahead on the kept side. This leaks some blocking back into the sample, so any residual slow-corner excess is an upper bound on the non-blocking part.
  - The cut does not catch a follower who gives up time on purpose to line up a pass.
  - A timing error at the ahead car's crossing k moves both the gap and `ahead_y_s`. That changes which rows are kept, but not the follower's `y_s`.
- **If the proxy is missing:** valid rows require `ahead_y_s`, so it cannot be missing. If any valid row lacks it at run time, the run stops (NOT RUN). The count goes to the owner, and nothing is imputed.

## 4. Venue restriction (fixed)

- **Rule:** the unit is the venue, not the event. A venue is kept only if it has a p3-sample race in every season from 2018 to 2025. All of a kept venue's p3-sample races are included, one-off events at that venue among them.
- **Why, without outcomes:** the rule keeps venues that appear in both eras every year, so venue mix differs little between eras. It also removes the street circuits (Monaco, Baku, Singapore, Jeddah, Las Vegas, Miami), which have the most blocking risk, by attendance alone.
- **Kept venues (7):** Abu Dhabi, Austria, Belgium, Britain, Hungary, Italy (Monza), Spain.
- **Races:** 59 in all, 31 in 2018-21 and 28 in 2022-25. The one-off races at kept venues (the 70th Anniversary GP at Britain, the Styrian GPs at Austria) are included.
- **Bahrain is excluded:** the 2020 Sakhir race used a different layout, so Bahrain does not have a race on the same layout in every season.
- Layout changes inside a kept venue (Abu Dhabi 2021, Barcelona 2023) are handled by the per-race corner map.

## 5. Primary quantity and verdict rule

- **Quantity (one number per sample):** `D = beta(lt1, low) - beta(lt1, high)` from spec `p3` on the sample after the blocking cut and the venue restriction. It is in seconds per micro-sector, with its race-clustered 95% interval (the same contrast code as `high_minus_low`, with the sign reversed).
- **Size line:** `T = |beta(lt1)| / 3`, with `beta(lt1)` fitted with spec `lt1` on the same restricted sample (the same sample as D).
- **Per-sample result (pooled, 2018-21, 2022-25 each):**
  - **S** if the lower 95% bound of D is above 0 and D >= T.
  - **R** if the upper 95% bound of D is below T.
  - **N** otherwise.
- **Overall verdict:**
  - **PASS** if all three samples are S.
  - **REFUTED** if at least one sample is R. Add "reversed" if, in a sample that is R, the upper 95% bound of D is below 0.
  - **INCONCLUSIVE** if no sample is R and at least one is N.
  - **NOT RUN** if the run crashes, the proxy is missing (section 3), or a sample has no slow or no fast rows. The counts go to the owner.
- S and R cannot both hold in one sample (D >= T puts the upper bound at or above T). So each of the 27 patterns of S, R and N across the three samples lands in exactly one of PASS, REFUTED and INCONCLUSIVE.
- **Where the one-third comes from:** it is the registered P1 and P2 size logic ("one third of `beta(lt1)`" as the line between too small to matter and material). It is applied here to the follow-up's own `beta(lt1)`. No DA-03 coefficient enters any threshold.

## 6. Not allowed

- Changing the proxy, the cut (0), the venue rule, the class thresholds or the one-third rule after any output is seen.
- Running other cuts, other venue sets, other class maps or other specs and reporting the best one. Any extra analysis is labelled exploratory and cannot change the verdict.
- Reusing DA-03 outputs as inputs, thresholds or evidence for the verdict.
- Running more than once. A crash before output may be re-run, and the crash is logged. A run that produced numbers is final.

## 7. Forking paths and power

- **Forking paths:** the motive comes from DA-03's own result, so a pass here is a replication under a control on a subset of the same data, not independent evidence. The same races appear in both tests. Read a pass as "the slow-corner excess survives this blocking proxy", not as a mechanism.
- **Precision (power run before registration):** standard errors of D are about 0.011 s pooled, 0.0165 s in 2018-21 and 0.012 s in 2022-25, with t(30) and t(27) inside the eras.
  - DA-01 crossing noise is already inside these standard errors. It adds attenuation, not bias, unless the noise differs by corner class.
- **Smallest detectable excess (80% power, 5%):** about 0.032 s pooled, 0.048 s in 2018-21 and 0.036 s in 2022-25.
- **False refutation:** when the true excess is zero, the chance of an R result is about 30% in the pooled sample alone. That is not unlikely, and a REFUTED verdict should be read with it in mind.
- **Other limits:** with 31 and 28 races per era from only 7 venues, race clustering may understate the uncertainty, because the same corners repeat across years.
- **Write-up sentence (use exactly):** "This test was run once on 59 races at 7 venues (31 in 2018-21, 28 in 2022-25). After the blocking cut it can reliably detect a slow-minus-fast excess of about 0.05 s per micro-sector in 2018-21, and about 0.035 s pooled and in 2022-25. It cannot reliably detect a smaller excess. It can rarely rule out an excess that is small but material. No more data can be added for these eras."
- **If the verdict is INCONCLUSIVE, say:** "The data cannot tell whether slow corners still lose more once slow cars ahead are removed. This is neither evidence for nor against, and it is not partial support."

## 8. Pre-run steps

1. The owner settles C5 and approves the text.
2. The code that applies sections 3-5 (a sample filter and a verdict function on the existing `p3` and `lt1` code, with its own pre-registration path and hash field) is written, tested on synthetic data only, and committed on its own.
3. This file, relabelled "registered", is committed alone. Its SHA-256 goes in the build log under a new follow-up item, never on DA-02P.
4. The test is run once, alone, on a scratch copy of the warehouse (own folder, copy named `dev.duckdb`), with that hash. The owner reads the verdict before anything else.

## Owner choices

Settled 2026-10-27:

- **C1.** Cut at `ahead_y_s <= 0` in every band and corner class, no margin (section 3).
- **C2.** Group by venue, kept only with a p3-sample race in every season 2018-2025; all of a kept venue's p3 races included. Seven venues, 59 races (section 4).
- **C3.** Run now, accepting the power limit in section 7.
- **C4.** The verdict rule in section 5: size line T = |beta(lt1)|/3 on the restricted sample, per-sample S/R/N, overall PASS / REFUTED / INCONCLUSIVE / NOT RUN.

Still open before registration:

- **C5.** The name of the new build-log item and its hash field.
