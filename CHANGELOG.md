# Changelog

## [0.2.0](https://github.com/JustinClarke/off-the-pace/compare/v0.1.0...v0.2.0) (2026-07-11)


### Features

* add ingestion monitoring script for long-running backfills ([26ff998](https://github.com/JustinClarke/off-the-pace/commit/26ff9987393b4ee9673692f0db24c165338b2b08))
* add Jolpica client for standings and pit stops (ingestion-v0.2 step 9) ([b999a0d](https://github.com/JustinClarke/off-the-pace/commit/b999a0d10e69d5f087b3d3e68ae31bf08016442d))
* **app:** add app shell, state management, and UI primitives ([ec3d781](https://github.com/JustinClarke/off-the-pace/commit/ec3d781069209cfa30194e8ce61a62b5c5feae66))
* **app:** implement feature pages and client-side routing ([0d20a77](https://github.com/JustinClarke/off-the-pace/commit/0d20a770dc089b7df658b4112b95ed65ffeace29))
* **app:** scaffold Vite React application and Tailwind config ([a01d9fa](https://github.com/JustinClarke/off-the-pace/commit/a01d9fa448be1fcd5d49da34dea9fd191e45efca))
* **app:** wire DuckDB-WASM data layer and ONNX inference client ([1ae8a2f](https://github.com/JustinClarke/off-the-pace/commit/1ae8a2fba71bba49c5bb374519d5aeec74b299b3))
* enhance documentation structure ([dcd0218](https://github.com/JustinClarke/off-the-pace/commit/dcd021886aec3d67be0b4f8cff15617f26dde6ad))
* expand analytics suite with new performance features, model marts, and comprehensive documentation updates ([b90c487](https://github.com/JustinClarke/off-the-pace/commit/b90c487d416349ba2bc9f1057b35b0cd2a675324))
* implement infrastructure as code, enhance app observability, and expand documentation across the application, transformation, and ML pipelines. ([adf8acc](https://github.com/JustinClarke/off-the-pace/commit/adf8acc6046a1d84d339e8bbdab405a75acd6c7c))
* **ingestion:** add FastF1/OpenF1 api client and environment config ([1404c74](https://github.com/JustinClarke/off-the-pace/commit/1404c74a1b9eda259575be45dcf620ef03239602))
* **ingestion:** define JSON schemas and ingestion config ([b3010c0](https://github.com/JustinClarke/off-the-pace/commit/b3010c053b194cc4c6b6ee6eb9ed28f295cc6744))
* **ingestion:** implement ingest CLI, replay simulator, and offline tests ([794439b](https://github.com/JustinClarke/off-the-pace/commit/794439b797a9006bec0e64506f9ea7023b5f43ff))
* **ml:** add Optuna hyperparameter tuning and trial inspection ([b352230](https://github.com/JustinClarke/off-the-pace/commit/b35223022497e9620940288484545b5b6a1a2c59))
* **ml:** add prediction, ONNX export with parity tests, and evaluation ([59719e3](https://github.com/JustinClarke/off-the-pace/commit/59719e30b6315174eda6257e2d5f430ec18af7d0))
* **ml:** implement XGBoost quantile + classifier training ([22031ff](https://github.com/JustinClarke/off-the-pace/commit/22031ff8260b8ed76d0f804c11104488c9914dff))
* **ml:** setup environment and feature engineering pipeline ([4c9f050](https://github.com/JustinClarke/off-the-pace/commit/4c9f0507504466a46dc5c514323f07073300f82d))
* redesign home page and hide unshipped features ([3999a2a](https://github.com/JustinClarke/off-the-pace/commit/3999a2abedeb524e730f521152e60f2ccd7bf64f))
* **transform:** add prediction-feature marts and data tests ([03d3436](https://github.com/JustinClarke/off-the-pace/commit/03d34362d1df011b87c9e1d9725abafdfb8a45b4))
* **transform:** add static seeds and source definitions ([507c95a](https://github.com/JustinClarke/off-the-pace/commit/507c95a6fad0fbb08bc917c10cf53879d35eea47))
* **transform:** build seven-term lap-residual and stint marts ([61f8395](https://github.com/JustinClarke/off-the-pace/commit/61f8395866cee8a565cf3f4e86232d29b6ea5812))
* **transform:** build staging models for laps, weather, pits, telemetry ([b8a2cad](https://github.com/JustinClarke/off-the-pace/commit/b8a2cad7663ff0b6f269b5a1dae6add5220f1e98))
* **transform:** implement intermediate transformations and bayesian macros ([ee4190a](https://github.com/JustinClarke/off-the-pace/commit/ee4190a020b32920374fa51a3088d2bfa77defac))
* upgrade to v4 tyre degradation models with updated ONNX inference and CI scanner integration ([c571f91](https://github.com/JustinClarke/off-the-pace/commit/c571f91029b3c095df52a2a8363485ffe3ee4fb2))


### Refactors

* resolve join ambiguities, fix workspace build configuration, and add app roadmap documentation ([1d64d22](https://github.com/JustinClarke/off-the-pace/commit/1d64d22f730d89bb0db2a123d0ac9bb1ad9dd56f))


### Documentation

* add narrative content and generated reference pages ([104ea50](https://github.com/JustinClarke/off-the-pace/commit/104ea504c503e936ae66a84a67a447df6258f296))
* add reference-generation and app-data export scripts ([ff1f031](https://github.com/JustinClarke/off-the-pace/commit/ff1f031c1cd3527716981c13f8e80a2385142b56))
* add repository tour, top-level README, and Makefile entry points ([80e1bef](https://github.com/JustinClarke/off-the-pace/commit/80e1bef2db80fec1fffd48834ce81567140be6ba))
* initialize Docusaurus site and theme ([e5a340f](https://github.com/JustinClarke/off-the-pace/commit/e5a340f73ea58a984df4f272127c301d14ebef32))
* project documentation structure and expand public data assets while refining transformation macros and validation scripts ([2a1feb1](https://github.com/JustinClarke/off-the-pace/commit/2a1feb188ac65914db952bb3f8cde7b6210caca6))


### Build & CI

* add GitHub Actions workflows for automated testing and deployment ([3f6f766](https://github.com/JustinClarke/off-the-pace/commit/3f6f766f7499f1a1f0873369e252ee4de6c9407c))
