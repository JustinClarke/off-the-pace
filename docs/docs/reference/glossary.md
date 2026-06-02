---
id: glossary
slug: /reference/glossary
sidebar_position: 10
title: Glossary
---

# Glossary

Unified definitions for domain (F1), data engineering, and statistical concepts used throughout the project.

---

## Formula 1 Domain

- **Stint:** A single period on track using one set of tyres. Ended by a pit stop or race finish.
- **Compound:** The chemical makeup of the tyre (SOFT, MEDIUM, HARD, INTERMEDIATE, WET).
- **Tyre Life:** The number of laps completed on the current set of tyres.
- **Delta:** The time difference between two laps or two drivers.
- **DRS (Drag Reduction System):** A movable rear wing element activated when a driver is within 1 second of the car ahead, reducing drag.
- **Undercut:** A pit strategy where a driver pits earlier than a rival to gain track position via fresher tyre pace.
- **Overcut:** The inverse-staying out longer than a rival to gain position through track evolution or their slower pit-stop exit.
- **Tyre Cliff:** The point at which tyre degradation accelerates sharply and lap times deteriorate rapidly. Modelled via Kaplan-Meier survival analysis in this project.
- **Dirty Air:** Aerodynamically disturbed airflow behind a leading car. Reduces the following car's downforce and increases tyre thermal load.
- **Safety Car Delta:** The mandated maximum pace during Safety Car periods. Drivers must not drive faster than the delta board shows.
- **Lap-Time Decomposition:** The process of isolating contributing factors (fuel weight, tyre degradation, dirty air, track evolution, driver skill) from the raw lap time. The core operation of this project.
- **Push Lap:** A qualifying-style lap driven at maximum effort, typically at low fuel and with fresh tyres.

---

## Data Engineering

- **Medallion Architecture:** A data design pattern (Bronze/Silver/Gold) for incremental data improvement. Bronze = raw, Silver = cleaned, Gold = feature-ready.
- **Lakehouse:** A hybrid architecture combining the flexibility of a data lake with the management of a data warehouse.
- **Parquet:** A columnar binary file format optimised for analytical queries. Used as the storage format for all Bronze and Silver layers.
- **DuckDB:** An in-process analytical OLAP database. Used as the local compute engine for all dbt models.
- **dbt (data build tool):** A SQL-based transformation framework that applies software engineering practices (testing, documentation, version control) to data pipelines.
- **Medallion Layer (Bronze):** Raw ingested data from FastF1 / OpenF1, partitioned by season and race, stored as Snappy-compressed Parquet.
- **Medallion Layer (Silver):** Cleaned and standardised staging models (`stg_*`), cast and deduplicated.
- **Medallion Layer (Gold):** Feature marts (`fct_*`, `dim_*`) ready for ML training or dashboard queries.
- **FastF1:** The open-source Python library used to fetch historical F1 telemetry, lap timing, and weather data from the Ergast and F1 APIs.
- **KQL (Kusto Query Language):** A query language for large-scale time-series telemetry data. Used in Microsoft Fabric Eventhouse.
- **SCD2 (Slowly Changing Dimension Type 2):** A method for tracking historical changes in dimension data by keeping prior rows.

---

## Statistics & ML

- **Tyre Degradation:** The rate at which lap times increase as tyres wear out (seconds per lap). Modelled as a linear coefficient per compound.
- **Causal Isolation:** The process of removing confounding variables to find the true effect of a single factor (e.g., driver skill net of car, fuel, and tyres).
- **Additive Identity:** The mathematical invariant `raw_lap_time = Σ(decomposed components)`. Enforced by `assert_lap_7term_identity` in dbt tests.
- **Kaplan-Meier Estimator:** A non-parametric survival analysis method. Used here to estimate tyre cliff onset probabilities by compound and circuit.
- **Cox Proportional Hazard:** A semi-parametric regression model for survival data. Used to fit cliff hazard rates as a function of tyre load and temperature covariates.
- **Bayesian Shrinkage:** A method of blending a driver's observed performance toward a population prior when sample size is small. Prevents extreme ratings for drivers with few laps.
- **OLS (Ordinary Least Squares):** A regression method used to estimate coefficients (e.g., fuel weight penalty, compound degradation rates).
- **MAE (Mean Absolute Error):** A metric for measuring the accuracy of a predictive model. Primary evaluation metric for degradation rate predictions.
- **TimeSeriesSplit:** A cross-validation strategy that respects temporal order-training on earlier seasons, validating on later ones. Used to prevent future data leakage in ML evaluation.
- **Feature Leakage:** When information from the future contaminates training data. Guarded against by `assert_no_future_leakage.sql`.
