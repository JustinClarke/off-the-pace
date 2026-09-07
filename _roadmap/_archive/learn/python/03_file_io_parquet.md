# Module 03 — File I/O & Parquet

> **Goal:** Read and write files like a data engineer — Parquet format, Hive partitioning, compression, and hash-based integrity checks.

---

## 1. Concept: Why Parquet?

CSV stores data row-by-row as text. Parquet stores data **column-by-column** in binary. This matters:

| Feature | CSV | Parquet |
|---------|-----|---------|
| Read "just the lap_time column" | Must read every row | Reads only that column |
| File size (1M rows) | ~80 MB | ~5 MB |
| Data types preserved? | No (everything is text) | Yes (int32, float64, timestamps) |
| Schema embedded? | No | Yes |
| Compression | None built-in | Snappy, ZSTD, gzip |

```python
import pandas as pd

# Write Parquet
df = pd.DataFrame({"driver": ["VER", "HAM"], "time": [91.2, 92.5]})
df.to_parquet("laps.parquet", index=False, compression="snappy")

# Read Parquet
df2 = pd.read_parquet("laps.parquet")
print(df2.dtypes)  # types preserved!

# Read only specific columns (huge performance win on large files)
times = pd.read_parquet("laps.parquet", columns=["time"])
```

### Codebase connection

Every data file in the repo is Parquet. The ingestion layer writes Snappy-compressed Parquet:

```python
# ingestion/src/ingest.py (line 437)
laps_df.to_parquet(target, index=False, compression="snappy")
```

The app export uses ZSTD for smaller CDN payloads:

```python
# scripts/export_app_data.py uses ZSTD for tighter compression
df.to_parquet(path, index=False, compression="zstd")
```

**Snappy** = fast read/write, moderate compression. **ZSTD** = slower write, tighter compression. The repo uses Snappy for intermediate files (speed matters during ingestion) and ZSTD for files served over the network (size matters for CDN costs).

---

## 2. Concept: Hive partitioning

Hive partitioning organizes files into directories named `column=value`. Instead of one huge file, you get a tree:

```
data/bronze/laps/
├── season=2018/
│   └── race=bahrain/
│       └── 2018_bahrain_laps.parquet
├── season=2019/
│   └── race=bahrain/
│       └── 2019_bahrain_laps.parquet
└── season=2024/
    ├── race=bahrain/
    │   └── 2024_bahrain_laps.parquet
    └── race=saudi_arabian/
        └── 2024_saudi_arabian_laps.parquet
```

**Why?**
- Query only 2024: read 24 files instead of 7×24 = 168
- Re-ingest one race: overwrite one file, not rebuild everything
- DuckDB and Spark can read `season=*` and auto-infer the partition column

```python
import os
from pathlib import Path

# Write a Hive-partitioned file
def write_partitioned(df, base_dir, year, slug):
    out_dir = Path(base_dir) / f"season={year}" / f"race={slug}"
    os.makedirs(out_dir, exist_ok=True)
    path = out_dir / f"{year}_{slug}_laps.parquet"
    df.to_parquet(path, index=False, compression="snappy")
    return path
```

### Codebase connection

This is the exact pattern from `ingest.py`:

```python
# ingestion/src/ingest.py (lines 143-148)
def _laps_path_race(year: int, slug: str) -> Path:
    return LAPS_DIR / f"season={year}" / f"race={slug}" / f"{year}_{slug}_laps.parquet"

def _laps_path_quali(year: int, slug: str) -> Path:
    return LAPS_DIR / f"season={year}" / f"race={slug}" / "session=Q" / f"{year}_{slug}_quali_laps.parquet"
```

---

## 3. Concept: Reading & writing text files (JSON, YAML)

```python
import json
from pathlib import Path

# JSON write
data = {"seasons": [2018, 2019, 2020], "status": "ok"}
Path("config.json").write_text(json.dumps(data, indent=2))

# JSON read
loaded = json.loads(Path("config.json").read_text())
print(loaded["seasons"])  # [2018, 2019, 2020]

# YAML (used for model cards, dbt config)
import yaml

config = yaml.safe_load(Path("dbt_project.yml").read_text())
```

### Codebase connection

The ML layer writes training logs as JSON:

```python
# ml/src/train.py (line 144)
(LOGS_DIR / f"{target}_{version}_{ts}.json").write_text(json.dumps(log, indent=2))
```

And reads best parameters from JSON:

```python
# ml/src/tune.py (line 89)
best_path.write_text(json.dumps(study.best_params, indent=2, sort_keys=True))
```

---

## 4. Concept: Hashing for integrity & reproducibility

A hash is a fixed-length fingerprint of data. Same input → same hash, always. Any change → totally different hash.

```python
import hashlib

# Hash a string
text = "hello world"
sha1 = hashlib.sha1(text.encode()).hexdigest()
print(sha1)  # 2aae6c35c94fcfb415dbe95f408b9ce91ee846ed

# Hash a file
def file_sha256(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()
```

### Codebase connection

The repo uses hashing in three ways:

**1. Schema fingerprint** — detect when FastF1 changes its column layout:

```python
# ingestion/src/ingest.py (lines 67-70)
def _schema_fingerprint(df: pd.DataFrame) -> str:
    col_sig = ",".join(sorted(df.columns))
    return hashlib.sha1(col_sig.encode()).hexdigest()[:12]
```

**2. Dataset fingerprint** — prove the exact same training data was used:

```python
# ml/src/features.py (lines 85-93)
def _fingerprint(X, training_seasons, feature_cols):
    ordered = X.reindex(columns=feature_cols).to_numpy(dtype=np.float32)
    ordered = ordered[np.lexsort(ordered.T[::-1])]  # canonical row order
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(ordered).tobytes())
    h.update(json.dumps({"seasons": training_seasons, "features": feature_cols}).encode())
    return h.hexdigest()
```

**3. ONNX model hash** — verify the exported model is bit-identical:

```python
# ml/src/export_onnx.py (lines 125-128)
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()
```

---

## 5. Concept: `os.makedirs` with `exist_ok`

```python
import os

# Create nested directories — won't error if they already exist
os.makedirs("data/bronze/laps/season=2024/race=bahrain", exist_ok=True)

# Without exist_ok=True, a second call would raise FileExistsError
```

This appears on **every write path** in the repo. It's the defensive pattern for idempotent writes — you can re-run the ingestion safely.

---

## 6. Guided exercises

### Exercise 1: Write and read Hive-partitioned Parquet

```python
import pandas as pd
import os
from pathlib import Path

# Simulated lap data for two races
data = [
    {"season": 2024, "race": "bahrain", "driver": "VER", "lap": 1, "time_s": 91.2},
    {"season": 2024, "race": "bahrain", "driver": "HAM", "lap": 1, "time_s": 92.5},
    {"season": 2024, "race": "jeddah",  "driver": "VER", "lap": 1, "time_s": 89.8},
    {"season": 2024, "race": "jeddah",  "driver": "HAM", "lap": 1, "time_s": 90.3},
    {"season": 2023, "race": "bahrain", "driver": "VER", "lap": 1, "time_s": 93.1},
]

df = pd.DataFrame(data)

# Write Hive-partitioned files
base = Path("exercise_data/laps")
for (season, race), group in df.groupby(["season", "race"]):
    out_dir = base / f"season={season}" / f"race={race}"
    os.makedirs(out_dir, exist_ok=True)
    group.drop(columns=["season", "race"]).to_parquet(
        out_dir / "laps.parquet", index=False, compression="snappy"
    )

# List what we created
for p in sorted(base.rglob("*.parquet")):
    print(f"  {p.relative_to(base)}")

# Read back just 2024
import duckdb
result = duckdb.sql(f"SELECT * FROM read_parquet('{base}/**/*.parquet', hive_partitioning=true) WHERE season = 2024")
print(result.df())
```

### Exercise 2: Build a file integrity checker

```python
import hashlib
from pathlib import Path

def integrity_report(directory: str) -> dict:
    """
    Walk a directory of Parquet files and return:
    - file_count: number of .parquet files
    - total_bytes: combined size
    - checksums: dict of filename -> SHA256 hex digest (first 12 chars)
    """
    root = Path(directory)
    files = sorted(root.rglob("*.parquet"))
    checksums = {}
    total = 0
    for f in files:
        data = f.read_bytes()
        total += len(data)
        checksums[str(f.relative_to(root))] = hashlib.sha256(data).hexdigest()[:12]
    
    return {
        "file_count": len(files),
        "total_bytes": total,
        "checksums": checksums,
    }

# Test it (if you ran Exercise 1)
report = integrity_report("exercise_data/laps")
print(f"Files: {report['file_count']}")
print(f"Total: {report['total_bytes']:,} bytes")
for name, sha in report["checksums"].items():
    print(f"  {sha}  {name}")
```

### Exercise 3: Explore the real Bronze layer

```bash
# In the repo root
find data/bronze/laps -name "*.parquet" | head -10
find data/bronze/laps -name "*.parquet" | wc -l
du -sh data/bronze/
```

```python
from pathlib import Path

bronze = Path("data/bronze")
for category in sorted(bronze.iterdir()):
    if category.is_dir() and not category.name.startswith("."):
        count = len(list(category.rglob("*.parquet")))
        print(f"{category.name:25s} {count:4d} files")
```

---

## 7. Interview drills

**Q1:** Why does this project use Parquet instead of CSV?

> **A:** Three reasons: (1) **Columnar storage** — DuckDB reads only the columns it needs, making queries on a 42-feature mart much faster. (2) **Type preservation** — timestamps, integers, and floats survive the round-trip without parsing. (3) **Compression** — Snappy-compressed Parquet is 10–15× smaller than CSV, critical when serving data over a CDN.

**Q2:** What is Hive partitioning and why does the Bronze layer use it?

> **A:** Hive partitioning splits data into directories named `column=value`. The Bronze layer partitions by `season` and `race`, so re-ingesting one race overwrites one file without touching others. DuckDB reads partition columns from directory names, enabling predicate pushdown (`WHERE season = 2024` skips all other directories).

**Q3:** What's the difference between Snappy and ZSTD compression?

> **A:** Snappy is faster to compress/decompress but produces larger files. ZSTD is slower but achieves tighter compression. The repo uses Snappy for intermediate bronze files (write speed matters during multi-hour ingestion) and ZSTD for CDN-served app exports (download size matters for users).

**Q4:** Why hash the training data in the ML pipeline?

> **A:** The dataset fingerprint (`features.py`) is a SHA-256 of the feature matrix, season split, and column list. It's logged alongside every model. If two models produce different predictions, you can check whether they trained on identical data. It also enables a "twice-run determinism proof" — run training twice, compare fingerprints, confirm identical.

**Q5:** What does `exist_ok=True` do in `os.makedirs()`?

> **A:** Without it, creating a directory that already exists raises `FileExistsError`. With `exist_ok=True`, it silently succeeds. This makes writes idempotent — you can re-run ingestion without deleting directories first. Every write path in the repo uses this pattern.

---

## 8. Checkpoint

You should now be able to:

- [ ] Explain columnar vs row-based storage
- [ ] Write Parquet files with compression
- [ ] Implement Hive-partitioned file layouts
- [ ] Read/write JSON configuration files
- [ ] Compute SHA-256 hashes of files and data
- [ ] Use `os.makedirs(exist_ok=True)` for idempotent writes
