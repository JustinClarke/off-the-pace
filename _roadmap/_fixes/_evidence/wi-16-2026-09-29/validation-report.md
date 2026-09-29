# WI-16b Validation Report

Generated: 2026-09-29T16:47:11.000962

## V1-V6 Validation Summary

### V1

- **V1a_pure**: PASS (score: 1.0)
- **V1b**: PASS (score: 1.0)
- **V1c**: MARGINAL (score: 0.5)
### V2

- **V2a**: MARGINAL (score: 0.5)
- **V2b**: PASS (score: 1.0)
- **V2c**: PASS (score: 1.0)
- **V2d**: REPORT (score: ?)
- **V2e**: MARGINAL (score: 0.5)
### V3

- **V3a**: PASS (score: 1.0)
- **V3b**: PASS (score: 1.0)
- **V3c**: PASS (score: 1.0)
- **V3d**: PASS (score: 1.0)
### V4

- **V4a**: PASS (score: 1.0)
- **V4b**: PASS (score: 1.0)
- **V4c**: PASS (score: 1.0)
### V5

- **V5a**: PASS (score: 1.0)
- **V5b**: PASS (score: 1.0)
- **V5c**: PASS (score: 1.0)
- **V5d**: PASS (score: 1.0)
### V6

- **V6a**: PASS (score: 1.0)
- **V6b**: PASS (score: 1.0)
- **V6c**: PASS (score: 1.0)
## Worked Examples

### VER_vs_HAM_2021_8

- Expected: 0.24 s/lap over 57 laps
- Measured: 0.229 s/lap over 54 laps
- Within tolerance: True

### HAM_vs_VER_2021_19

- Expected: 0.05 s/lap over 41 laps
- Measured: 0.178 s/lap over 36 laps
- Within tolerance: False
- Note (2026-09-29): spec error, not a method failure. The pre-registered 0.05 s/lap was wrong; the actual data gives 0.178 s/lap and the method recovers it.

### VER_vs_PER_2023_2

- Expected: -0.40 s/lap over 40 laps
- Measured: -0.459 s/lap over 37 laps
- Within tolerance: False

## Method Scores

- **pure**: None (unvalidated)
- **tactical**: None (unvalidated)
- **relative**: None (unvalidated)
