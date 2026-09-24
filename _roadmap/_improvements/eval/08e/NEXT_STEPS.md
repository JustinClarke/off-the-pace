# Handoff: 08e Landing — Decision & Bookkeeping

## Current State
- **08e is GATED and definition-of-done complete**
- All measurements are done; all gates pass
- No warehouse changes, artefacts, or build-log edits are pending
- Ready for human decision on landing

## The Decision: Split D3 or Keep Bundled?

### D3 as Written
"Land 08e + 08f? Their deltas were measured against the target 08m superseded and must be re-read first."

### Current Landscape
- **08e:** Re-read is done (2026-09-17). Family T clears on v12 on all five targets. ✅
- **08f:** No re-read. Moreover, `cliff_candidate_flag` (family C ablation target) was pruned by 08j. The 2026-09-09 family C measurement is no longer runnable on the current contract.

### Option A: Land 08e Now (Recommended)
**Rationale:** See the thermal contribution in isolation; de-risk 08f decision.

**What this means:**
1. Mark 08e LANDED in build-log.json
2. Model outputs update to include the rebuilt thermal family (four columns)
3. 08f stays GATED and open; its D3 half becomes "what do we do now that family C is gone?"

**08f Path Forward:**
- Measure 08f-1 (survival-weight season-lag) without family C ablation, OR
- Explicitly close 08f with a note that its ablation target vanished, OR
- Re-scope to only measure the survival weight and skip the interaction family

### Option B: Keep D3 Bundled
**Rationale:** Wait for both to be "clean" before any land.

**What this means:**
- Hold 08e at GATED
- Re-read or re-scope 08f to handle the missing family C
- Land both together

**Consequence:** Delays getting thermal contribution into the live contract.

---

## If You Choose Option A (Land 08e Now)

### Step 1: Update build-log.json

In the 08e entry:
1. Change `"stage": "GATED"` → `"stage": "LANDED"`
2. Append to the note field the re-read section (optional but recommended for auditability):
   ```
   RE-READ ON V12/08M SUBSTRATE 2026-09-17: ... [full re-read findings]
   ```
3. Correct D3's context in the final summary, since "their deltas were measured..." is now half-true

### Step 2: Update Pointer
```json
"pointer": "08f"
```

### Step 3: Run Consistency Checks
```bash
python3 _improvements/status/board.py --check
python3 _improvements/status/board.py --write-order
```

### Step 4: Update Model Card & Exports
Standard post-gate steps when landing a GATED item:
- Update `ml/model_card.yml` to reflect the rebuilt thermal family
- Export models to the live contract version
- Update docs snippets that quote family T numbers (use v12 re-read values, not 2026-09-09 values)

### Step 5: Address Stint-Life Caveat
In the history entry for this session, note:
> `stint_life_regressor` arm was fitted with current params; re-read after 10d/10e, like all stint-life numbers in the tree.

---

## If You Choose Option B (Keep Bundled)

Skip steps 1–5 above. Instead:

1. Create/update an 08f re-scope task (probably a new sub-item):
   - Decide: measure 08f-1 only? Close 08f? Measure differently?
   - If measuring, design the gate arms without family C
   - Run gates on the new design
   
2. Once 08f is similarly re-read, land both together

---

## Files Ready in `_improvements/eval/`

- **README.md** — executive summary with status, problem, fix, all work completed
- **MEASUREMENTS.md** — all tables (materiality, gates, re-read) for reference
- **NEXT_STEPS.md** — this file
- **08e_thermal_family_arms.json** — artefact with all fits and e-values
- **08e_thermal_family_arms.log** — generation log

## Reference in Next Chat
Start with: "I'm continuing 08e from `_improvements/eval/`. Here's the state: [copy README]"

Then: "Decision to make: land 08e now (separating from D3), or wait for 08f re-read?"

The tables in MEASUREMENTS.md are all you need to justify either call.

---

## Command Summary for Landing (Option A)

```bash
# Check consistency
python3 _improvements/status/board.py --check

# Edit build-log.json
# - Change 08e stage to LANDED
# - Advance pointer to 08f
# - (Optional) append re-read findings to 08e note

# Regenerate ordered task list
python3 _improvements/status/board.py --write-order

# Check consistency again
python3 _improvements/status/board.py --check

# User commits when ready
git add build-log.json _improvements/status/BUILD-ORDER.md
git commit -m "Land 08e (thermal proxy rebuild passes v12 gates on all targets)"
```
