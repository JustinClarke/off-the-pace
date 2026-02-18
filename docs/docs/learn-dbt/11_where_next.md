---
sidebar_position: 12
title: "Part 11: Next Steps"
---

# Part 11: Where next?

You have walked through the full transformation layer  from raw Bronze Parquet directories to verified gold marts, with tests validated at every compilation step. Depending on your analytical or development objectives, here is where to proceed next.

---

## Canonical Architecture and Methodology

*   [Goal & Approach](../understand/goal-and-approach.md): The system architecture: how ingestion, transform, and machine learning blocks interface.
*   [Methodology](../understand/methodology.md): The causal inference approach: why we decompose pace additively, what we isolate, and the limits of the physical estimators.

---

## Adjacent Components

*   [ingestion/README.md](https://github.com/justinclarke/off-the-pace/blob/main/ingestion/README.md): Where Bronze data is sourced. If you need to add a new session type or modify sensor variables, start here.
*   [transform/tasks/coefficients/](https://github.com/justinclarke/off-the-pace/tree/main/transform/tasks/coefficients/): The survival analysis coefficient fitter. Review this block before running `make coefficients-fit`.
*   [ml/](https://github.com/justinclarke/off-the-pace/tree/main/ml/): The downstream consumer of the gold feature marts (`fct_driver_skill_features` and `fct_cliff_prediction_features`).

---

## Interactive Exploration & Verification

To inspect model details, column schema types, and SQL lineage:

```bash
# Generate and open the interactive dbt docs lineage graph
make dbt-docs

# Open the SQL explorer interface (Harlequin) against the dev DB
make query
```

The dbt docs lineage graph is the best way to visualize how models connect. Select any node in the DAG to inspect its database schemas, validation constraints, and compiled SQL logic.

---

**Read the complete guide in a single page at [Complete Single-Page Guide](./master.md).**
