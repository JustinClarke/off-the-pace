#!/usr/bin/env python3
"""
Check coverage of compound_code in int_stint_geometry by season.
Filed under 08p.
"""

import duckdb
import json
from pathlib import Path

# Connect to dev warehouse (read-only)
warehouse_path = Path(__file__).parent.parent / "data" / "dev.duckdb"
con = duckdb.connect(str(warehouse_path), read_only=True)

# Check coverage by season
coverage_query = """
SELECT
    race_year,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN compound_code IS NOT NULL THEN 1 END) as rows_with_code,
    ROUND(100.0 * COUNT(CASE WHEN compound_code IS NOT NULL THEN 1 END) / COUNT(*), 2) as coverage_pct,
    COUNT(DISTINCT compound_code) as distinct_codes,
    STRING_AGG(DISTINCT compound_code, ', ' ORDER BY compound_code) as codes_present
FROM int_stint_geometry
GROUP BY race_year
ORDER BY race_year
"""

result = con.execute(coverage_query).df()
print("\n=== compound_code Coverage by Season ===\n")
print(result.to_string(index=False))

# Check for 2018 violations (should be 0)
violation_query = """
SELECT COUNT(*) as violations_found
FROM int_stint_geometry
WHERE race_year = 2018 AND compound_code IS NOT NULL
"""

violations = con.execute(violation_query).fetchall()[0][0]
print(f"\n2018 NULL rule violations: {violations} (should be 0)")

# Check for any compound_label values that don't join
unmapped_query = """
SELECT
    race_year,
    compound AS compound_label,
    COUNT(*) as count
FROM int_stint_geometry
WHERE compound_code IS NULL
  AND race_year >= 2019  -- Should have coverage in 2019+
GROUP BY race_year, compound
ORDER BY race_year, compound
"""

unmapped_result = con.execute(unmapped_query).df()
if len(unmapped_result) > 0:
    print("\n=== Unmapped compound labels (2019+, should be empty) ===\n")
    print(unmapped_result.to_string(index=False))
else:
    print("\n=== Unmapped compound labels (2019+): None (good!) ===")

con.close()
