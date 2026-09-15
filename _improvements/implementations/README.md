# Implementations — Session Artifacts

Analysis scripts, diagnostics, and intermediate data for completed work items. Organized by item ID.

Each folder contains:
- **Scripts:** Python analysis notebooks (throwaway, not part of the shipped codebase)
- **Data:** Intermediate panels and diagnostic JSON (built locally, referenced in work docs)
- **Deliverables:** Final output (post drafts, findings summaries, etc.)

Scripts here reuse the production paths (`ml/src/{train,features,evaluate,attribution,intervals}.py`) rather than reimplementing fit/score logic.

## Folders

- **04c/** — Campaign-level test family audit
- **06b/** — Dirty-air per-season coefficient analysis and diagnostics
- **06c/** — Corner-phase skill decomposition and Verstappen anomaly analysis
- **07b/** — Causal pit-timing analysis (causality identification checks)

Not committed to git. These folders document the work and allow re-running diagnostic checks without rebuilding from scratch.
