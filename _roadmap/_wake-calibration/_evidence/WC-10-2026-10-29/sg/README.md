# WC-10e SG1-SG7: PRE-FIX partial results. Do NOT rely on these. They must be re-run.

**Status: stopped by owner decision on 2026-10-30.** These numbers come from code that has a known flaw and from flawed synthetic outcomes. They are kept only as a record. Amendment B2 (draft) will drop rows with NaN `tyre_life` from step 1. After the fix, SG1-SG7 must be re-run from scratch, twice, on the fixed code.

## The flaw

- The real 2022-23 structure has 958 free passes with NaN `tyre_life`.
- In the real run, those rows enter step 1 with NaN tyre-trend regressors. Step 1 then fails to converge in races 2022_7 and 2022_11, in both design A and the lap arm.
- The SG harness hid this. In `sg_checks.plant`, the term `g = th1*t + th2*t^2` (and the SG2/SG3 drift terms) turn NaN `t` into NaN `y`. `design_a.free_set` drops a non-finite `y` as a null outcome, so SG1, SG2, SG3, SG6 and SG7 never put those rows into step 1.
- In SG5, the synthetic lap times were built with `groupby().sum()`, which skips NaN.
- The lap-arm structural check (`SG5_lap_arm_convergence_structural.csv`) did catch the non-convergence in 2022_7 and 2022_11.

## Fix needed in `transform/tasks/wake_calibration/sg_checks.py` (for the next session)

- **`plant()`:** a NaN `tyre_life` must not turn into a NaN outcome. Compute the tyre terms on `np.nan_to_num(t)`, or zero them where `t` is NaN, so `y` stays finite and the NaN-`t` rows reach the estimator exactly as real rows would. Keep `keys["t"]` itself NaN. Do the same for the SG2 slope/curvature and the SG3 drift `term` (and the SG3 cell mean).
- **`sg5_timing()`:** build the lap times with `groupby(...).sum(min_count=1)`, or propagate NaN explicitly, rather than silently skipping.
- **Tests:** add a test that a NaN-`t` free pass gives a finite synthetic `y`.

## What ran (pre-fix)

- **Code:** estimator at HEAD `1a9ef80`, unmodified. Harness `sg_checks.py` sha256 `655bd30a…f8d55c`. Tests `test_sg_checks.py` sha256 `991a574e…155541` (9 passed, 1 skipped).
- **Run 1 command:** `cd transform && ../.venv/bin/python -m tasks.wake_calibration.sg_checks --out ../_roadmap/_wake-calibration/_evidence/WC-10-2026-10-29/sg/run1 --sims 200 --draws 200 --workers 6`
- **Run 2:** the same command with `--out .../sg/run2 --workers 5`. It was killed before any simulation set finished.
- **Seeds:** simulations `SeedSequence([20261030, sg, sim])`; bootstrap draws 1-200 of the registered plan (seed 20261029). BLAS threads pinned to 1.
- **SG4:** run once, via `--sets ""`, into scratch, then copied here.
- **Determinism:** not shown. Run 2 never finished a set. The SG5 structural CSV is byte-identical across runs 1 and 2.

## Pre-fix numbers (invalid)

| Check | Result | Key numbers |
|---|---|---|
| SG1 | pass | Minimum per-bin coverage 0.925 in bins 0.3-3.0 s. Near-band bias +0.4 / +0.4 / +0.3 % (fast / medium / slow). |
| SG2 | pass | Minimum coverage 0.91. Bias −1.5 / −1.4 / −0.6 %. |
| SG7 | pass | Medium and slow both AGREE in 95.5 % of sims. DISAGREE 0 %. Medium or slow INCONCLUSIVE in 4.5 %. Fast INCONCLUSIVE 100 % (n_brk 383 < 500). |
| SG4 | pass | Reweighted vs literal refit (circuit copy + duplicate race) max difference 5e-15; 0 label mismatches. All mechanics items pass. |
| SG5 | recorded | Design A fit 18 s, one draw 0.08 s. Lap arm fails to converge (2022_7, 2022_11). |
| SG3, SG6 | not finished | — |

## Other open findings

- `design_a.RULED_CHOICES["duplicate_race_in_copy"]` is `"separate_copy"`, but B1 §D(2) says `"copy"`.
- B1's SHA-256 (`c9566233…`) is not yet recorded on DD-WC20.
- `run_wc10` real mode does not check the SG results, the B-ii evidence or B1 before RUN START.

## Files (sha256)

```
76e4c845d1a0512ac4519ef0952b48be42614b4abf9edac6802bc9a69f757a89  partial_run1/SG1_bias.csv
3441ba94f55d4cd448a6e032135fd20ca55123b0a5646148ea13aeeb001f5f46  partial_run1/SG1_coverage.csv
e4308986f577bb1c8e944a26ecf7d15b5be048021715697817cface3ea9b7269  partial_run1/SG2_bias.csv
ea0713bd9c70a31592c44c56144bca43d3793c5538367d48e1038ad460898fe1  partial_run1/SG2_coverage.csv
062aa8339f9cb40211705fa136c4f8845123bf241bc43706d33a1adb5b3669c2  partial_run1/SG4_labels_reweight_vs_literal_refit.csv
d3623dd4d0db0baf27e856885bf2391292ec257c217700eebc51c2d4354e9d01  partial_run1/SG4_mechanics.csv
4ca355622621319be9b4f140ac0977fb0e983b554021c10924010b57b5ee0abc  partial_run1/SG4_reweight_vs_literal_refit.csv
567c43d5498160b8d2ed31494f293f76a892b82fc6819f78a816687760eb6743  partial_run1/SG5_lap_arm_convergence_structural.csv
f5b85db49221e18cc86a64ca4afeea676a1b94be9bcac1f0c1aa49179519d290  partial_run1/SG7_s2_rates.csv
4390b98dc4484f07b8609233d9aa0605f69f92cd81a888ff5cff3a635d50a690  partial_run1/timing_SG5.csv
d734c6e83fa89d1efe623d28197e20a0b9d0b886d5f90b8ff6496558cb63675b  partial_run1/verdicts_PRE_FIX.json
22f3d29d22ca1f31ab9508cba97140ac8e96b6c111d72758eaae9f6ea8f496fc  run1/SG1_sims.csv
a3e8ced0aefe43c01ce8b37a01054d98eab11ee5b5a302b3a4ed5bf0d6366ed6  run1/SG2_sims.csv
567c43d5498160b8d2ed31494f293f76a892b82fc6819f78a816687760eb6743  run1/SG5_lap_arm_convergence_structural.csv
4390b98dc4484f07b8609233d9aa0605f69f92cd81a888ff5cff3a635d50a690  run1/timing_SG5.csv
567c43d5498160b8d2ed31494f293f76a892b82fc6819f78a816687760eb6743  run2/SG5_lap_arm_convergence_structural.csv
769b14d1456ba2e50ffc0d1fc0cdecb2d53c479fc1a827fcc6f86f8efb5bca1b  run2/timing_SG5.csv
```
