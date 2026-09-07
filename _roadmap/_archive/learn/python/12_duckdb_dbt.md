# Module 12 — DuckDB, SQL & the dbt Bridge

> **Goal:** Query data with DuckDB from Python, understand how the dbt transform layer works, and bridge SQL ↔ Python workflows.

---

## 1. Concept: DuckDB — an in-process analytical database

DuckDB is like SQLite but designed for analytics. It runs inside your Python process (no server).

```python
import duckdb

# Connect and query
con = duckdb.connect("data/dev.duckdb", read_only=True)
result = con.execute("SELECT COUNT(*) FROM fct_lap_residuals").fetchone()
print(f"Total rows: {result[0]:,}")
con.close()

# Or use the shorthand (temporary in-memory DB)
df = duckdb.sql("SELECT 1 AS x, 'hello' AS y").df()
```

### Codebase connection

The ML feature loader reads from DuckDB:

```python
# ml/src/features.py (lines 99-106)
con = duckdb.connect(duckdb_path, read_only=True)
df = con.execute(f"SELECT * FROM {S.MART} ORDER BY race_year, race_id, stint_id, lap_in_stint").df()
con.close()
```

---

## 2. Concept: DuckDB reads Parquet directly

DuckDB can query Parquet files without loading them into a table first:

```python
# Read a single Parquet file
df = duckdb.sql("SELECT * FROM read_parquet('data/bronze/laps/season=2024/race=bahrain/*.parquet')").df()

# Read all Parquet files with Hive partitioning
df = duckdb.sql("""
    SELECT * FROM read_parquet('data/bronze/laps/**/*.parquet', hive_partitioning=true)
    WHERE season = 2024
""").df()
```

This is powerful because you can query the Bronze layer directly without importing into a database.

---

## 3. Concept: DuckDB → Pandas and back

```python
import pandas as pd
import duckdb

# DuckDB result → Pandas DataFrame
con = duckdb.connect("data/dev.duckdb", read_only=True)
df = con.execute("SELECT driver_id, AVG(pace_delta_s) AS avg_delta FROM fct_lap_residuals GROUP BY 1").df()
con.close()

# Pandas DataFrame → DuckDB query (no import needed!)
laps = pd.DataFrame({"driver": ["VER", "HAM"], "time": [91.2, 92.5]})
result = duckdb.sql("SELECT * FROM laps WHERE time < 92").df()  # references the Python variable!
```

DuckDB automatically finds Pandas DataFrames in the local scope and treats them as tables. This is the bridge between SQL and Python.

---

## 4. Concept: Writing SQL in Python (multi-line strings)

```python
query = """
    SELECT
        driver_id,
        compound,
        race_year,
        AVG(pace_delta_s) AS avg_pace_delta,
        COUNT(*) AS n_laps
    FROM fct_lap_residuals
    WHERE race_year BETWEEN 2022 AND 2024
      AND pace_delta_s IS NOT NULL
    GROUP BY 1, 2, 3
    ORDER BY avg_pace_delta
"""

con = duckdb.connect("data/dev.duckdb", read_only=True)
df = con.execute(query).df()
con.close()
```

### Codebase connection

The validation gate script uses complex SQL queries:

```python
# scripts/validate_gate.py (lines 52-89)
def step_4_1(con):
    pairs = con.execute(f"""
        WITH tm AS (
            SELECT t.race_year, t.race_id, t.ego_driver_id, t.teammate_driver_id,
                   t.constructor_id, t.driver_skill_proxy_s, t.pair_quality_weight,
                   g.age_in_stint
            FROM int_synthetic_teammate t
            JOIN int_stint_geometry g
              ON g.race_year = t.race_year AND g.race_id = t.race_id
             AND g.driver_id = t.ego_driver_id AND g.lap_number = t.lap_number
            WHERE t.teammate_available_flag
              AND NOT t.strategic_divergence_flag
        )
        SELECT race_year, race_id, ego_driver_id, teammate_driver_id,
               REGR_SLOPE(driver_skill_proxy_s, age_in_stint) AS gap_slope
        FROM tm
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(*) >= {MIN_PAIR_LAPS}
    """).fetchdf()
```

Notice the f-string for `MIN_PAIR_LAPS` — this is safe because it's a Python constant (integer), not user input. For user input, use parameterized queries.

---

## 5. Concept: Parameterized queries (safe from SQL injection)

```python
# DANGEROUS — SQL injection risk with user input
driver = input("Enter driver: ")  # user types: VER'; DROP TABLE laps; --
query = f"SELECT * FROM laps WHERE driver_id = '{driver}'"  # BAD!

# SAFE — parameterized query
con.execute("SELECT * FROM laps WHERE driver_id = ?", [driver])
```

The repo doesn't use parameterized queries because all query inputs are internal constants, not user-supplied strings.

---

## 6. Concept: How dbt fits in

dbt (data build tool) is a SQL-first transformation framework:

```
Bronze (Parquet)  →  dbt models (SQL)  →  DuckDB warehouse
```

The Python relationship:
- **Python writes** Bronze Parquet files (ingestion layer)
- **dbt transforms** them into a warehouse (SQL models in `transform/models/`)
- **Python reads** the warehouse (ML layer, validation scripts)

dbt runs via the command line:

```bash
cd transform && ../.venv/bin/dbt run --target dev     # build all models
cd transform && ../.venv/bin/dbt test                   # run data tests
cd transform && ../.venv/bin/dbt docs generate && dbt docs serve  # browse schema
```

### Codebase connection

The Makefile wraps dbt:

```makefile
# Makefile (lines 144-148)
dbt-dev:
    cd transform && ../.venv/bin/dbt run --target dev --select +fct_lap_residuals

dbt-test:
    cd transform && ../.venv/bin/dbt test
```

---

## 7. Concept: COPY TO — exporting from DuckDB

```python
# Export a query result to Parquet
con.execute("""
    COPY (
        SELECT driver_id, compound, AVG(pace_delta_s) AS avg_delta
        FROM fct_lap_residuals
        GROUP BY 1, 2
    )
    TO 'output/summary.parquet'
    (FORMAT PARQUET, COMPRESSION ZSTD)
""")
```

### Codebase connection

```python
# scripts/export_app_data.py (lines 172-178)
con.execute(f"""
    COPY (
        SELECT * FROM {table_name}
        {where_clause}
    )
    TO '{target_path}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
""")
```

---

## 8. Guided exercises

### Exercise 1: Query the warehouse

```python
import duckdb

con = duckdb.connect("data/dev.duckdb", read_only=True)

# List all tables
tables = con.execute("SHOW TABLES").df()
print("Tables in the warehouse:")
print(tables.to_string())

# Count rows in the main fact table
count = con.execute("SELECT COUNT(*) FROM fct_lap_residuals").fetchone()[0]
print(f"\nfct_lap_residuals: {count:,} rows")

# What seasons are available?
seasons = con.execute("SELECT DISTINCT race_year FROM fct_lap_residuals ORDER BY 1").df()
print(f"\nSeasons: {seasons['race_year'].tolist()}")

con.close()
```

### Exercise 2: Bridge SQL and Pandas

```python
import duckdb
import pandas as pd

con = duckdb.connect("data/dev.duckdb", read_only=True)

# Pull data with SQL
drivers = con.execute("""
    SELECT driver_id, 
           COUNT(*) as total_laps,
           AVG(pace_delta_s) as avg_pace
    FROM fct_lap_residuals 
    WHERE race_year = 2024
    GROUP BY 1
    HAVING COUNT(*) > 100
    ORDER BY avg_pace
""").df()

# Continue analysis in Pandas
drivers["rank"] = range(1, len(drivers) + 1)
drivers["tier"] = pd.cut(drivers["avg_pace"], bins=3, labels=["Fast", "Mid", "Slow"])
print(drivers.head(10))

con.close()
```

### Exercise 3: Read Bronze Parquet directly

```python
import duckdb

# Read the Bronze laps directly (no warehouse needed)
df = duckdb.sql("""
    SELECT *
    FROM read_parquet('data/bronze/laps/**/*.parquet', hive_partitioning=true)
    WHERE season = 2024
    LIMIT 100
""").df()

print(f"Columns: {list(df.columns)}")
print(f"Rows: {len(df)}")
print(df.head())
```

---

## 9. Interview drills

**Q1:** What's the advantage of DuckDB over SQLite for analytics?

> **A:** DuckDB uses **columnar storage** — it reads only the columns a query needs. SQLite uses row storage — it reads entire rows. For analytical queries like "average pace_delta_s across 500,000 laps" (reading 1 column out of 42), DuckDB is 10–100× faster. DuckDB also supports complex analytics: window functions, REGR_SLOPE, and reading Parquet natively.

**Q2:** Why does the ML layer read from DuckDB instead of directly from Parquet?

> **A:** The feature mart (`fct_stint_features`) is computed by dbt from 20+ source tables with complex joins, window functions, and quality filters. Reading raw Parquet would require reimplementing all that logic in Python. The ML layer reads the finished mart — one clean table with all features pre-computed.

**Q3:** What does `hive_partitioning=true` do in `read_parquet`?

> **A:** It tells DuckDB to treat directory names like `season=2024/race=bahrain/` as columns. The values `2024` and `bahrain` become the `season` and `race` columns. This lets you `WHERE season = 2024` and DuckDB skips reading files in other season directories.

**Q4:** How do Python and dbt interact in this repo?

> **A:** They're loosely coupled through the DuckDB database. Python writes Bronze Parquet → dbt reads Parquet and writes to DuckDB → Python reads from DuckDB. They share no code. The contract is the table schemas. If dbt renames a column, the Python ML layer breaks — which is why the schema is tested.

---

## 10. Checkpoint

You should now be able to:

- [ ] Connect to DuckDB and run queries
- [ ] Read Parquet files directly with DuckDB
- [ ] Convert between DuckDB results and Pandas DataFrames
- [ ] Use `COPY TO` for Parquet export
- [ ] Explain the Bronze → dbt → DuckDB → ML data flow
- [ ] Understand Hive partitioning in `read_parquet`
- [ ] Write multi-line SQL queries in Python strings
