# PL-300 — 15-day module plan

Environment note: Power BI Desktop is Windows-only. Run it via a Windows VM (Parallels/VMware Fusion) or a cloud PC (Windows 365 / AVD). The browser Service alone doesn't cover Model view, full Power Query, or Performance Analyzer, which several days below need.

Where a day's DIY says "your own data," pull a small extract from the Off The Pace dbt gold layer (`docs/data/`) — Power BI Desktop reads Parquet natively (Get Data → File → Parquet). Ask Claude to prep the specific extract; do the actual Power BI clicking yourself.

## Daily format
1. **Recap** (2 min) — one-line reminder of last session
2. **Learn** (5–8 min) — one concept, plain language
3. **DIY** (10–15 min) — hands-on in Power BI Desktop
4. **Test** (5 min) — 3–5 exam-style questions, answers included
5. **Win** — what's crossed off + one-line preview of next day

To generate a day, say: *"Generate day N module: [title]"*

## The 15 days

| Day | Title | Focus | Status |
|---|---|---|---|
| 1 | Data sources | Connect & load | ✅ done |
| 2 | Data profiling | Quality checks | |
| 3 | Clean & shape | Power Query basics | |
| 4 | Advanced query | Merge, append, unpivot | |
| 5 | Dataflows | Reusable prep | |
| 6 | Star schema | Modeling & relationships | |
| 7 | DAX foundations | Columns vs measures | |
| 8 | Advanced DAX | CALCULATE & filter context | |
| 9 | Core visuals | Charts, matrix, slicers | |
| 10 | UX polish | Drillthrough, bookmarks | |
| 11 | AI visuals | Key influencers, decomp tree | |
| 12 | Workspaces | Publish & distribute | |
| 13 | Row-level security | RLS roles | |
| 14 | Refresh & governance | Incremental refresh, sensitivity labels | |
| 15 | Mock exam | Full review | |

## Domain weighting (for reference)
- Prepare the data — 25–30% (days 1–5)
- Model the data — 25–30% (days 6–8)
- Visualize and analyze — 25–30% (days 9–11)
- Deploy and maintain / manage & secure — 15–20% (days 12–14)