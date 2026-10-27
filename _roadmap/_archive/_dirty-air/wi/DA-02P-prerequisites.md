# DA-02P - Prerequisites before the fit

**Why this exists.** DA-03 cannot pass as written. The pre-registration names a P3 mechanism placebo (loss in high-speed corners, gain on straights from tow) but no micro-sector to corner-class map exists. DRS state is not in the panel at all. Both are needed before the fit.

**Scope.**
1. **Corner-class map (P3).** Build a micro-sector to corner-class table from `dim_corners` (corner positions, apex speed). Set the speed thresholds before any fit, and record them as an amendment to the pre-registration. Test: every circuit-year is covered.
2. **DRS state.** `stg_telemetry` maps codes 10, 12 and 14 to `drs_active` and drops code 8 (eligible). Add code 8 in staging, and carry DRS state at micro-sector entry into the panel. Use it as a separate registered spec that drops micro-sectors where DRS is open. Do not use it as a control, because being within 1 s is what opens DRS.
3. **Pre-registration amendment.** Add items 1 and 2 to `DA-03-preregistration.md`, remove the DRAFT marking, and commit that file on its own commit. Record the committed file's SHA-256 in the log before DA-03 runs.

**Done when.** The corner-class and DRS tests pass on a scratch copy, the amendment is committed, and the hash is recorded.

**Runs on.** Scratch copies only, under the scratch-copy convention. Never `data/dev.duckdb` directly.

**Owner decisions.** Approve the amendment text before it is committed (DA-03 depends on it).
