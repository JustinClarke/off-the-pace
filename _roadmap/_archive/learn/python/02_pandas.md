# Module 02 — Data Wrangling with Pandas

> **Goal:** Fluently create, filter, transform, merge, and aggregate DataFrames — the core of every data pipeline in this repo.

---

## 1. Concept: DataFrames are tables

A DataFrame is a 2D table with named columns and an index. Think of it as a spreadsheet in memory.

```python
import pandas as pd

# Create from a dictionary
laps = pd.DataFrame({
    "driver":     ["VER", "HAM", "VER", "HAM", "VER", "HAM"],
    "lap_number": [1, 1, 2, 2, 3, 3],
    "lap_time_s": [92.3, 93.1, 91.8, 92.5, 91.5, 92.1],
    "compound":   ["SOFT", "SOFT", "SOFT", "MEDIUM", "SOFT", "MEDIUM"],
})

print(laps.shape)      # (6, 4) — 6 rows, 4 columns
print(laps.dtypes)     # column types
print(laps.head(3))    # first 3 rows
```

### Codebase connection

In `ingest.py`, every FastF1 session is immediately turned into a DataFrame:

```python
# ingestion/src/ingest.py (line 423)
laps_df = pd.DataFrame(session.laps)
laps_df["race_id"] = f"{year}_{round_num}"
laps_df["season"]  = year
```

Notice: new columns (`race_id`, `season`) are added by simple assignment. Pandas columns are just dict-like keys.

---

## 2. Concept: Selecting & filtering

```python
# Select columns
times = laps[["driver", "lap_time_s"]]

# Filter rows (boolean indexing)
fast_laps = laps[laps["lap_time_s"] < 92.0]

# Combine conditions (use & for AND, | for OR, ~ for NOT)
ver_fast = laps[(laps["driver"] == "VER") & (laps["lap_time_s"] < 92.0)]

# .loc for label-based, .iloc for position-based
first_row = laps.iloc[0]        # by position
named_row = laps.loc[0]         # by index label (same here, but different concept)
```

### Codebase connection

In `data_quality.py`, filtering is used to find duplicate lap keys:

```python
# ingestion/src/data_quality.py (lines 96-99)
dupe_mask = df.duplicated(subset=key_cols, keep=False)
dupe_count = int(dupe_mask.sum())
if dupe_count:
    sample = df[dupe_mask][key_cols].head(5).to_dict("records")
```

`df.duplicated()` returns a boolean Series. Using it as a mask (`df[dupe_mask]`) gives only the duplicate rows.

---

## 3. Concept: Data types matter

Pandas has specific types: `int64`, `float64`, `object` (strings), `datetime64`, `timedelta64`, `bool`, `category`.

```python
# Check types
print(laps.dtypes)

# Convert types
laps["lap_number"] = laps["lap_number"].astype("int32")
laps["compound"] = laps["compound"].astype("category")

# Handle missing values
laps["lap_time_s"] = pd.to_numeric(laps["lap_time_s"], errors="coerce")  # NaN for bad values

# Check for nulls
print(laps.isnull().sum())         # count NULLs per column
print(laps.isnull().mean())        # NULL rate per column (0.0 to 1.0)
```

### Codebase connection

In `data_quality.py`, null-rate checking is a core quality gate:

```python
# ingestion/src/data_quality.py (lines 59-63)
null_rates = df.isnull().mean().to_dict()
high = {k: v for k, v in null_rates.items() if v > threshold}
if high:
    logger.warning(f"Columns above {threshold*100:.0f}% null threshold: {high}")
```

The feature encoder in `features.py` explicitly handles type conversion:

```python
# ml/src/features.py (line 81)
out[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")
```

---

## 4. Concept: Renaming, mapping & transforming

```python
# Rename columns
df = laps.rename(columns={"lap_time_s": "time_seconds", "driver": "driver_id"})

# Map values (like a lookup table)
compound_to_grip = {"SOFT": 1.0, "MEDIUM": 0.85, "HARD": 0.70}
laps["grip_factor"] = laps["compound"].map(compound_to_grip)

# Apply a function to every value in a column
laps["fast_flag"] = laps["lap_time_s"].apply(lambda t: t < 92.0)

# Vectorized operations (much faster than .apply!)
laps["delta_to_best"] = laps["lap_time_s"] - laps["lap_time_s"].min()
```

### Codebase connection

The ingestion layer renames weather columns from FastF1's format to the project's snake_case:

```python
# ingestion/src/ingest.py (lines 52-60)
WEATHER_COL_MAP = {
    "AirTemp":       "ambient_temp_c",
    "TrackTemp":     "track_temp_c",
    "Humidity":      "humidity_pct",
    "Rainfall":      "rainfall_flag",
}
# Then: wx = wx.rename(columns=WEATHER_COL_MAP)
```

---

## 5. Concept: GroupBy & aggregation

GroupBy splits data into groups, applies a function to each, and combines results.

```python
# Mean lap time per driver
laps.groupby("driver")["lap_time_s"].mean()

# Multiple aggregations
laps.groupby("driver")["lap_time_s"].agg(["mean", "min", "max", "count"])

# GroupBy multiple columns
laps.groupby(["driver", "compound"])["lap_time_s"].mean()

# Named aggregations (cleaner output)
summary = laps.groupby("driver").agg(
    avg_time=("lap_time_s", "mean"),
    best_time=("lap_time_s", "min"),
    total_laps=("lap_number", "count"),
)
```

### Codebase connection

The evaluation module groups by cohort dimensions to build per-cohort baselines:

```python
# ml/src/evaluate.py (lines 151-152)
g = train_dims.groupby(["compound", "circuit_key", "age_bucket"], observed=True)[value_col]
return (g.quantile(agg) if isinstance(agg, float) else g.mean()).to_dict()
```

---

## 6. Concept: Merge & join

```python
# Two DataFrames to merge
drivers = pd.DataFrame({
    "driver": ["VER", "HAM"],
    "team":   ["Red Bull", "Mercedes"],
})

laps_with_team = laps.merge(drivers, on="driver", how="left")
# how="left"  — keep all rows from laps, NaN if no match in drivers
# how="inner" — only keep rows that match both sides
# how="outer" — keep all rows from both, NaN where missing
```

### Codebase connection

In `features.py`, stint length is joined to the main DataFrame:

```python
# ml/src/features.py (lines 133-137)
for d in (train_df, holdout_df):
    merged = d.merge(stint_len, on="stint_id", how="left")
    d["stint_length_laps"] = merged["stint_length_laps"].to_numpy()
    d[S.STINT_LIFE_TARGET] = np.clip(
        d["stint_length_laps"] - d["lap_in_stint"], 0, None)
```

This is a classic pattern: load two tables from DuckDB, merge them in Pandas, then derive a new column from the joined data.

---

## 7. Concept: Value counts, unique values & the `.str` accessor

```python
# How many laps per compound?
laps["compound"].value_counts()

# Unique values
laps["compound"].unique()          # array of unique values
laps["compound"].nunique()         # count of unique values

# String operations (the .str accessor)
names = pd.Series(["Australian Grand Prix", "Bahrain Grand Prix"])
slugs = names.str.lower().str.replace(" ", "_").str.replace("'", "")
```

### Codebase connection

The `_slug()` helper in `ingest.py` does exactly this string transform:

```python
# ingestion/src/ingest.py (line 140)
def _slug(event_name: str) -> str:
    return event_name.lower().replace(" ", "_").replace("'", "")
```

---

## 8. Guided exercises

### Exercise 1: Build a mini data quality checker

```python
import pandas as pd

def check_quality(df: pd.DataFrame, required_cols: list[str]) -> dict:
    """
    Return a quality report dict with:
    - row_count: number of rows
    - missing_columns: list of required cols not in df
    - null_rates: dict of column -> null rate (only columns above 5%)
    - duplicate_count: number of fully duplicated rows
    """
    missing = [c for c in required_cols if c not in df.columns]
    nulls = df.isnull().mean()
    high_null = {col: round(rate, 4) for col, rate in nulls.items() if rate > 0.05}
    
    return {
        "row_count": len(df),
        "missing_columns": missing,
        "null_rates": high_null,
        "duplicate_count": int(df.duplicated().sum()),
    }


# Test it
test_df = pd.DataFrame({
    "driver": ["VER", "HAM", "VER", None, "HAM", "HAM"],
    "lap":    [1, 1, 2, 2, 3, 3],
    "time":   [91.0, 92.0, 91.5, None, None, 92.1],
})

report = check_quality(test_df, ["driver", "lap", "time", "compound"])
print(report)
```

Expected output:

```python
{
    'row_count': 6,
    'missing_columns': ['compound'],
    'null_rates': {'driver': 0.1667, 'time': 0.3333},
    'duplicate_count': 0
}
```

### Exercise 2: GroupBy analysis on real data

Open a Python REPL in the repo venv:

```python
import duckdb

con = duckdb.connect("data/dev.duckdb", read_only=True)
laps = con.execute("""
    SELECT driver_id, compound, race_year, pace_delta_s
    FROM fct_lap_residuals
    WHERE race_year = 2024 AND pace_delta_s IS NOT NULL
    LIMIT 5000
""").df()
con.close()

# 1. Average pace delta per driver
print(laps.groupby("driver_id")["pace_delta_s"].mean().sort_values())

# 2. Lap count per compound
print(laps["compound"].value_counts())

# 3. Which driver-compound combination has the most laps?
combo = laps.groupby(["driver_id", "compound"]).size().reset_index(name="count")
print(combo.sort_values("count", ascending=False).head(10))
```

### Exercise 3: Merge practice

```python
import pandas as pd

# Create standings and team data
standings = pd.DataFrame({
    "driver_id": ["max_verstappen", "lewis_hamilton", "lando_norris"],
    "points": [575, 211, 374],
    "position": [1, 7, 2],
})

teams = pd.DataFrame({
    "driver_id": ["max_verstappen", "lewis_hamilton", "charles_leclerc"],
    "constructor": ["red_bull", "mercedes", "ferrari"],
})

# Inner join — only matching drivers
inner = standings.merge(teams, on="driver_id", how="inner")
print("Inner join:")
print(inner)  # 2 rows (Norris missing from teams, Leclerc from standings)

# Left join — keep all standings, NaN where no team match
left = standings.merge(teams, on="driver_id", how="left")
print("\nLeft join:")
print(left)  # 3 rows, Norris has NaN constructor
```

---

## 9. Interview drills

**Q1:** What's the difference between `.apply()` and vectorized operations?

> **A:** Vectorized operations (`df["col"] * 2`, `df["col"].str.lower()`) operate on the whole column in C, which is 10–100× faster. `.apply()` calls a Python function row-by-row, which has Python interpreter overhead. Always prefer vectorized operations. Use `.apply()` only when the logic is too complex for vectorized ops.

**Q2:** When would you use `how="left"` vs `how="inner"` in a merge?

> **A:** `left` keeps every row from the left DataFrame and fills NaN where there's no match on the right. `inner` keeps only rows that match both sides. In this repo, `features.py` uses `how="left"` to merge stint length — every lap should get a stint length, and a NaN indicates a data issue. An `inner` join would silently drop unmatched laps, hiding the problem.

**Q3:** How do you detect and handle duplicate rows?

> **A:** `df.duplicated(subset=key_cols)` returns a boolean mask of rows that are duplicates based on the specified columns. The repo's `DataQualityEngine.check_lap_key_duplicates()` uses `keep=False` to flag *all* copies (not just the second one), then reports the count and a sample for debugging. It checks `["race_id", "DriverNumber", "LapNumber"]` — the natural key for a lap.

**Q4:** What does `df.isnull().mean()` calculate?

> **A:** `isnull()` returns a DataFrame of `True/False`. `.mean()` treats `True` as 1 and `False` as 0, so it computes the fraction of null values per column (the null rate, between 0.0 and 1.0). A null rate of 0.05 means 5% of values are missing.

**Q5:** Why does the codebase use `.to_dict("records")` when logging?

> **A:** `.to_dict("records")` converts a DataFrame to a list of dictionaries (one per row), which is human-readable in logs and JSON-serializable. It's used in `data_quality.py` to show a sample of duplicate rows: `df[dupe_mask][key_cols].head(5).to_dict("records")`.

---

## 10. Checkpoint

You should now be able to:

- [ ] Create DataFrames from dicts, CSVs, and query results
- [ ] Filter rows with boolean indexing
- [ ] Rename columns and map values
- [ ] Use `groupby` to aggregate data
- [ ] Merge two DataFrames with the right join type
- [ ] Check null rates and detect duplicates
- [ ] Explain why vectorized ops beat `.apply()`
