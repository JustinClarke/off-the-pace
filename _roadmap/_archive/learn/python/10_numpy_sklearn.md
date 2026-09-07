# Module 10 — NumPy & scikit-learn for ML

> **Goal:** Understand array operations, cross-validation, and evaluation metrics — the computational core of the ML pipeline.

---

## 1. Concept: NumPy arrays vs Python lists

NumPy arrays are fixed-type, contiguous memory blocks that enable vectorized math.

```python
import numpy as np

# Create arrays
a = np.array([1.0, 2.0, 3.0, 4.0])
b = np.arange(0, 10, 2)       # [0, 2, 4, 6, 8]
c = np.zeros((3, 4))          # 3×4 matrix of zeros
d = np.random.default_rng(42).standard_normal((5, 3))  # 5×3 random

# Vectorized operations (no loops!)
doubled = a * 2                # [2, 4, 6, 8]
squared = a ** 2               # [1, 4, 9, 16]
total = a.sum()                # 10.0
mean = a.mean()                # 2.5
```

**Why not Python lists?** A loop over 100,000 elements in Python takes ~10ms. The same operation as a NumPy vectorized op takes ~0.1ms (100× faster).

### Codebase connection

The training module uses NumPy throughout:

```python
# ml/src/train.py (lines 37-43)
def pinball_loss(y, pred, alpha: float) -> float:
    d = y - pred
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))

def rmse(y, pred) -> float:
    return float(np.sqrt(np.mean((y - pred) ** 2)))
```

---

## 2. Concept: Boolean masking & fancy indexing

```python
# Boolean mask
ages = np.array([5, 12, 3, 8, 15, 2])
mature = ages > 10
print(mature)          # [False, True, False, False, True, False]
print(ages[mature])    # [12, 15] — only elements where mask is True

# Fancy indexing
indices = np.array([0, 3, 5])
print(ages[indices])   # [5, 8, 2]

# np.where — conditional selection
result = np.where(ages > 10, "old", "new")
# ['new', 'old', 'new', 'new', 'old', 'new']

# np.isin — membership test
seasons = np.array([2018, 2019, 2020, 2021, 2022, 2023, 2024])
train_seasons = [2018, 2019, 2020, 2021]
mask = np.isin(seasons, train_seasons)
print(seasons[mask])  # [2018, 2019, 2020, 2021]
```

### Codebase connection

Season-based cross-validation splits use exactly this:

```python
# ml/src/train.py (lines 83-93)
def _season_folds(seasons, training_seasons, n_splits):
    uniq = np.asarray(sorted(training_seasons))
    for tr_seasons_idx, val_seasons_idx in TimeSeriesSplit(n_splits=n_splits).split(uniq):
        tr = np.isin(seasons, uniq[tr_seasons_idx])     # boolean mask
        val = np.isin(seasons, uniq[val_seasons_idx])
        yield np.where(tr)[0], np.where(val)[0]         # convert mask to indices
```

---

## 3. Concept: `np.clip`, `np.concatenate`, `np.lexsort`

```python
# Clip values to a range
raw = np.array([-5, 0, 3, 15, 50])
clipped = np.clip(raw, 0, None)    # [0, 0, 3, 15, 50] — clip negatives to 0
clipped2 = np.clip(raw, -10, 10)   # [-5, 0, 3, 10, 10]

# Concatenate arrays
a = np.array([1, 2, 3])
b = np.array([4, 5])
c = np.concatenate([a, b])  # [1, 2, 3, 4, 5]

# lexsort — sort by multiple keys (last key is primary)
names = np.array(["VER", "HAM", "VER", "HAM"])
laps = np.array([2, 1, 1, 2])
order = np.lexsort((laps, names))  # sort by name, then by lap
print(names[order])  # ['HAM', 'HAM', 'VER', 'VER']
```

### Codebase connection

`np.clip` is used to bound the stint-life target:

```python
# ml/src/features.py (lines 136-137)
d[S.STINT_LIFE_TARGET] = np.clip(d["stint_length_laps"] - d["lap_in_stint"], 0, None)
```

`np.lexsort` creates deterministic row ordering for the fingerprint:

```python
# ml/src/features.py (line 89)
ordered = ordered[np.lexsort(ordered.T[::-1])]  # canonical row order, NaN-stable
```

---

## 4. Concept: TimeSeriesSplit — why random splits are wrong for time data

**The problem:** In time-series data, the future depends on the past. If you randomly split laps into train/test, training data from 2024 could leak future information into predictions for 2020.

**TimeSeriesSplit** keeps time ordering: train on early data, validate on later data.

```python
from sklearn.model_selection import TimeSeriesSplit

seasons = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
tscv = TimeSeriesSplit(n_splits=5)

for i, (train_idx, val_idx) in enumerate(tscv.split(seasons)):
    print(f"Fold {i}: train={[seasons[j] for j in train_idx]}, val={[seasons[j] for j in val_idx]}")
```

Output:

```
Fold 0: train=[2018], val=[2019]
Fold 1: train=[2018, 2019], val=[2020]
Fold 2: train=[2018, 2019, 2020], val=[2021]
Fold 3: train=[2018, 2019, 2020, 2021], val=[2022]
Fold 4: train=[2018, 2019, 2020, 2021, 2022], val=[2023]
```

Notice: the training window **expands** each fold. The validation is always the **next unseen season**. This prevents temporal leakage.

### Codebase connection

The repo applies TimeSeriesSplit to **whole seasons**, not individual rows:

```python
# ml/src/train.py (lines 83-93)
def _season_folds(seasons, training_seasons, n_splits):
    uniq = np.asarray(sorted(training_seasons))
    n_splits = min(n_splits, len(uniq) - 1)
    for tr_seasons_idx, val_seasons_idx in TimeSeriesSplit(n_splits=n_splits).split(uniq):
        tr = np.isin(seasons, uniq[tr_seasons_idx])
        val = np.isin(seasons, uniq[val_seasons_idx])
        yield np.where(tr)[0], np.where(val)[0]
```

---

## 5. Concept: ML metrics

```python
from sklearn.metrics import f1_score, mean_squared_error
import numpy as np

# RMSE — root mean squared error (lower is better)
y_true = np.array([91.0, 92.0, 93.0])
y_pred = np.array([91.5, 91.8, 93.2])
rmse = np.sqrt(mean_squared_error(y_true, y_pred))  # 0.37

# Macro F1 — multi-class classification (higher is better)
y_true_cls = np.array([0, 1, 2, 0, 1, 2])
y_pred_cls = np.array([0, 1, 1, 0, 2, 2])
f1 = f1_score(y_true_cls, y_pred_cls, average="macro")

# Pinball loss — quantile regression (lower is better)
def pinball_loss(y, pred, alpha):
    d = y - pred
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))
```

### Codebase connection

```python
# ml/src/train.py (lines 46-51)
def _headline(spec, y, pred):
    if spec.kind == "quantile":
        return "pinball", pinball_loss(y, pred, spec.quantile_alpha)
    if spec.kind == "classification":
        return "macro_f1", float(f1_score(y, pred, average="macro"))
    return "rmse", rmse(y, pred)
```

---

## 6. Concept: Sample weights for class imbalance

When classes are imbalanced (most laps have no cliff), the model learns to always predict the majority class. Balanced class weights fix this.

```python
from sklearn.utils.class_weight import compute_class_weight

y = np.array([0, 0, 0, 0, 0, 1, 1, 2, 3, 3])  # class 0 is dominant
classes = np.unique(y)
weights = compute_class_weight("balanced", classes=classes, y=y)
print(dict(zip(classes, weights)))
# {0: 0.5, 1: 2.5, 2: 5.0, 3: 2.5}
```

### Codebase connection

```python
# ml/src/train.py (lines 66-78)
def _sample_weight(spec, y, meta=None):
    if spec.kind == "classification":
        classes = np.unique(y)
        w = compute_class_weight("balanced", classes=classes, y=y)
        lut = dict(zip(classes, w))
        return np.asarray([lut[v] for v in y], dtype=np.float32)
    return None
```

---

## 7. Guided exercises

### Exercise 1: Implement pinball loss

```python
import numpy as np

def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, alpha: float) -> float:
    """
    Quantile loss (pinball loss).
    
    When alpha=0.5, this is equivalent to MAE.
    When alpha=0.1, under-predictions are penalized less (we want a low estimate).
    When alpha=0.9, over-predictions are penalized less (we want a high estimate).
    """
    d = y_true - y_pred
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


# Test
y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
pred = np.array([1.5, 2.5, 2.5, 3.5, 5.5])

print(f"p10 loss: {pinball_loss(y, pred, 0.1):.4f}")
print(f"p50 loss: {pinball_loss(y, pred, 0.5):.4f}")
print(f"p90 loss: {pinball_loss(y, pred, 0.9):.4f}")
```

### Exercise 2: Build a season-based splitter

```python
import numpy as np

def season_split(seasons: np.ndarray, holdout_season: int):
    """
    Split data into training (all seasons < holdout) and holdout.
    Return (train_indices, holdout_indices).
    """
    train_mask = seasons < holdout_season
    holdout_mask = seasons == holdout_season
    return np.where(train_mask)[0], np.where(holdout_mask)[0]

# Test
seasons = np.array([2018]*10 + [2019]*10 + [2020]*10 + [2021]*10)
train_idx, holdout_idx = season_split(seasons, holdout_season=2021)
print(f"Train: {len(train_idx)} rows (seasons: {np.unique(seasons[train_idx])})")
print(f"Holdout: {len(holdout_idx)} rows (seasons: {np.unique(seasons[holdout_idx])})")
```

---

## 8. Interview drills

**Q1:** Why use `TimeSeriesSplit` instead of `KFold` for this project?

> **A:** F1 data is temporal — 2024 regulations, car designs, and tyre compounds don't exist in 2018 data. `KFold` would randomly mix future data into training, creating temporal leakage. `TimeSeriesSplit` trains on past seasons and validates on the next, mimicking how the model will actually be used (trained on history, scoring live data).

**Q2:** What is pinball loss and why use it for quantile regression?

> **A:** Pinball loss asymmetrically penalizes errors. For the p10 quantile (α=0.1), under-predictions are penalized at rate 0.1 but over-predictions at rate 0.9 — the model learns to predict low. For p90, it's reversed. The degradation trio uses p10/p50/p90 to give a calibrated interval: "next-lap degradation will be between X and Y with ~80% confidence."

**Q3:** What's the difference between micro, macro, and weighted F1?

> **A:** **Micro** pools all TP/FP/FN, biased toward the majority class. **Macro** averages F1 per class equally, treating each class as equally important (used in the repo). **Weighted** averages by class support. The cliff classifier uses macro because "0_to_2" (imminent cliff) is rare but critical — macro F1 ensures it matters even with few examples.

**Q4:** Why are class weights important for the cliff classifier?

> **A:** Most stints don't have a cliff, so `none_in_stint` dominates. Without balanced weights, the model predicts "no cliff" for everything and gets ~70% accuracy while being useless for the actual task (detecting cliffs). Balanced weights up-weight rare cliff classes so the model learns to detect them.

---

## 9. Checkpoint

You should now be able to:

- [ ] Use NumPy for vectorized math, boolean masking, and fancy indexing
- [ ] Explain why `TimeSeriesSplit` prevents temporal leakage
- [ ] Compute RMSE, pinball loss, and macro F1
- [ ] Use `compute_class_weight` for imbalanced classification
- [ ] Implement season-based train/holdout splits
- [ ] Use `np.clip`, `np.concatenate`, and `np.lexsort`
