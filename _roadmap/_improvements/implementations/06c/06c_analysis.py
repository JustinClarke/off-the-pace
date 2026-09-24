#!/usr/bin/env python3
"""
SUPERSEDED 2026-09-20 -- PRE-FIX. DO NOT RE-QUOTE ITS OUTPUT.

This script was written before 00d corrected the braking sign in
int_corner_skill_residuals.sql. Everything it "confirms" below is either
inverted or false against the rebuilt mart:
  - NOR does not lead 2024 (4th at -1.69; GAS leads at -3.76)
  - VER's braking is -0.0745, not +0.076, and it means braking LATER
  - there is no anomaly to confirm
Kept for provenance only. The current numbers are in 06c_stats.json and
06c_findings_summary.md, and the queries behind them are recorded there.

---- original docstring ----
Load and analyze mart_corner_skill_driver for 2024 season.
Focus on:
1. Confirm NOR's leadership (index ~ -3.22)
2. Confirm VER's anomaly (braking +0.076, mid-corner -0.078)
3. Extract cell counts and standard errors
4. Check team baseline comparisons
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Load 2024 data
parquet_path = Path('/Users/justin/github/off-the-pace/app/public/data/marts/mart_corner_skill_driver/2024.parquet')
df = pd.read_parquet(parquet_path)

print("=" * 80)
print("MART_CORNER_SKILL_DRIVER 2024 ANALYSIS")
print("=" * 80)

print(f"\nTotal rows (driver-seasons): {len(df)}")
print(f"\nColumns: {sorted(df.columns.tolist())}")

# Show data types
print(f"\nData types:\n{df.dtypes}")

# Check for null values in key columns
print(f"\nNull value counts in key columns:")
key_cols = ['driver_id', 'braking_skill_s', 'mid_corner_skill_s', 'exit_skill_s',
            'corner_skill_index', 'braking_cells_n', 'mid_cells_n', 'exit_cells_n']
for col in key_cols:
    if col in df.columns:
        print(f"  {col}: {df[col].isna().sum()}")

# Full sample of data
print("\nFull 2024 dataset:")
display_cols = ['driver_id', 'constructor_id', 'braking_skill_s', 'mid_corner_skill_s',
                'exit_skill_s', 'braking_skill_se_s', 'mid_corner_skill_se_s',
                'exit_skill_se_s', 'corner_skill_index', 'braking_cells_n',
                'mid_cells_n', 'exit_cells_n']
print(df[display_cols].to_string())

print("\n" + "=" * 80)
print("LEADER ANALYSIS")
print("=" * 80)

# Sort by corner_skill_index (lower = better/faster)
df_sorted = df.sort_values('corner_skill_index')

print("\nTop 10 drivers by corner skill (index, lower = faster):")
top_10 = df_sorted[['driver_id', 'corner_skill_index', 'braking_skill_s',
                     'mid_corner_skill_s', 'exit_skill_s',
                     'braking_cells_n', 'mid_cells_n', 'exit_cells_n']].head(10)
print(top_10.to_string(index=False))

# Focus on NOR
nor_row = df[df['driver_id'] == 'NOR']
if not nor_row.empty:
    print("\n" + "=" * 80)
    print("NORRIS (NOR) - 2024 CORNER SKILL")
    print("=" * 80)
    nor = nor_row.iloc[0]
    print(f"Driver: {nor['driver_id']}")
    print(f"Team: {nor['constructor_id']}")
    print(f"\nCorner Skill Index: {nor['corner_skill_index']:.4f}")
    print(f"\nPhase Breakdown (in seconds, negative = faster):")
    print(f"  Braking:     {nor['braking_skill_s']:7.4f} s (SE: {nor['braking_skill_se_s']:.4f}, n_cells={nor['braking_cells_n']:.0f})")
    print(f"  Mid-corner:  {nor['mid_corner_skill_s']:7.4f} s (SE: {nor['mid_corner_skill_se_s']:.4f}, n_cells={nor['mid_cells_n']:.0f})")
    print(f"  Exit:        {nor['exit_skill_s']:7.4f} s (SE: {nor['exit_skill_se_s']:.4f}, n_cells={nor['exit_cells_n']:.0f})")

# Focus on VER
ver_row = df[df['driver_id'] == 'VER']
if not ver_row.empty:
    print("\n" + "=" * 80)
    print("VERSTAPPEN (VER) - 2024 CORNER SKILL")
    print("=" * 80)
    ver = ver_row.iloc[0]
    print(f"Driver: {ver['driver_id']}")
    print(f"Team: {ver['constructor_id']}")
    print(f"\nCorner Skill Index: {ver['corner_skill_index']:.4f}")
    print(f"\nPhase Breakdown (in seconds, negative = faster):")
    print(f"  Braking:     {ver['braking_skill_s']:7.4f} s (SE: {ver['braking_skill_se_s']:.4f}, n_cells={ver['braking_cells_n']:.0f})")
    print(f"  Mid-corner:  {ver['mid_corner_skill_s']:7.4f} s (SE: {ver['mid_corner_skill_se_s']:.4f}, n_cells={ver['mid_cells_n']:.0f})")
    print(f"  Exit:        {ver['exit_skill_s']:7.4f} s (SE: {ver['exit_skill_se_s']:.4f}, n_cells={ver['exit_cells_n']:.0f})")

    # Compare to NOR
    if not nor_row.empty:
        print(f"\nVERSTAPPEN vs NORRIS delta:")
        print(f"  Braking:     {ver['braking_skill_s'] - nor['braking_skill_s']:+.4f} s")
        print(f"  Mid-corner:  {ver['mid_corner_skill_s'] - nor['mid_corner_skill_s']:+.4f} s")
        print(f"  Exit:        {ver['exit_skill_s'] - nor['exit_skill_s']:+.4f} s")
        print(f"  Index:       {ver['corner_skill_index'] - nor['corner_skill_index']:+.4f}")

# Check cell counts distribution
print("\n" + "=" * 80)
print("CELL COUNT DISTRIBUTION")
print("=" * 80)
print(f"\nBraking cells (n={len(df)}):")
print(f"  Mean: {df['braking_cells_n'].mean():.1f}")
print(f"  Min: {df['braking_cells_n'].min():.0f}")
print(f"  Max: {df['braking_cells_n'].max():.0f}")

print(f"\nMid-corner cells (n={len(df)}):")
print(f"  Mean: {df['mid_cells_n'].mean():.1f}")
print(f"  Min: {df['mid_cells_n'].min():.0f}")
print(f"  Max: {df['mid_cells_n'].max():.0f}")

print(f"\nExit cells (n={len(df)}):")
print(f"  Mean: {df['exit_cells_n'].mean():.1f}")
print(f"  Min: {df['exit_cells_n'].min():.0f}")
print(f"  Max: {df['exit_cells_n'].max():.0f}")

# Check how many have index (all 3 phases >= 30)
rows_with_index = df['corner_skill_index'].notna().sum()
print(f"\nRows with corner_skill_index (all phases >= 30 cells): {rows_with_index} / {len(df)}")

# Check standard errors
print("\n" + "=" * 80)
print("STANDARD ERROR DISTRIBUTION")
print("=" * 80)
for phase, col in [('Braking', 'braking_skill_se_s'),
                   ('Mid-corner', 'mid_corner_skill_se_s'),
                   ('Exit', 'exit_skill_se_s')]:
    se_vals = df[col].dropna()
    print(f"\n{phase} skill SE (n={len(se_vals)}):")
    print(f"  Mean: {se_vals.mean():.4f} s")
    print(f"  Median: {se_vals.median():.4f} s")
    print(f"  Std: {se_vals.std():.4f} s")
    print(f"  Min: {se_vals.min():.4f} s")
    print(f"  Max: {se_vals.max():.4f} s")

# Export key stats to JSON for use in post
import json
stats = {
    "total_driver_seasons": len(df),
    "driver_seasons_with_index": int(rows_with_index),
    "nor": {
        "driver_id": "NOR",
        "corner_skill_index": float(nor['corner_skill_index']),
        "braking_skill_s": float(nor['braking_skill_s']),
        "braking_skill_se_s": float(nor['braking_skill_se_s']),
        "braking_cells_n": int(nor['braking_cells_n']),
        "mid_corner_skill_s": float(nor['mid_corner_skill_s']),
        "mid_corner_skill_se_s": float(nor['mid_corner_skill_se_s']),
        "mid_cells_n": int(nor['mid_cells_n']),
        "exit_skill_s": float(nor['exit_skill_s']),
        "exit_skill_se_s": float(nor['exit_skill_se_s']),
        "exit_cells_n": int(nor['exit_cells_n']),
    },
    "ver": {
        "driver_id": "VER",
        "corner_skill_index": float(ver['corner_skill_index']),
        "braking_skill_s": float(ver['braking_skill_s']),
        "braking_skill_se_s": float(ver['braking_skill_se_s']),
        "braking_cells_n": int(ver['braking_cells_n']),
        "mid_corner_skill_s": float(ver['mid_corner_skill_s']),
        "mid_corner_skill_se_s": float(ver['mid_corner_skill_se_s']),
        "mid_cells_n": int(ver['mid_cells_n']),
        "exit_skill_s": float(ver['exit_skill_s']),
        "exit_skill_se_s": float(ver['exit_skill_se_s']),
        "exit_cells_n": int(ver['exit_cells_n']),
    },
    "phase_se_means": {
        "braking": float(df['braking_skill_se_s'].mean()),
        "mid_corner": float(df['mid_corner_skill_se_s'].mean()),
        "exit": float(df['exit_skill_se_s'].mean()),
    }
}

output_path = Path('/private/tmp/claude-501/-Users-justin-github-off-the-pace/747de893-7d95-4054-83b7-5d43716c3ec5/scratchpad/06c_stats.json')
with open(output_path, 'w') as f:
    json.dump(stats, f, indent=2)

print(f"\nStats exported to {output_path}")
