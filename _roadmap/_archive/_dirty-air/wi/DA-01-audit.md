# DA-01 - Phase 0 audit

**Question.** Can the position data support a gap-based measure at all?

**Method (from the design note, section 6, phase 0).**
- Sample spacing per season (one race measured so far; the rest UNVERIFIED).
- Share of green samples with a known car ahead, and the share with `distance_to_ahead_m` NULL (about 5% on the first measurement).
- Agreement between the gap computed from crossing times and the gap the timing feed reports, by gap band.
- Whether `DriverAhead` includes lapped cars.
- Whether DRS code 8 is reliable, including 2018.
- Whether marshal-sector data exists for 2018-2020 (needs DD3).

**Gate to continue.** At least 90% of green samples valid. Median gap disagreement under 0.1 s for gaps under 2 s.

**Stop if.** The gap is unreliable under 1 s, or the sample spacing differs by season in a way that cannot be corrected.

**Dependency.** Numbers are provisional until CO-17 rebuilds dev (watch W1).

**Definition of done.** A short evidence note under `_evidence/DA-01-<date>/` with PROVENANCE.txt, the queries, and a pass/stop verdict per gate.
