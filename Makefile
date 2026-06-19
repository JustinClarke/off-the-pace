# ══════════════════════════════════════════════════════════════════════════════
#  Off The Pace project Makefile
#
#  Targets are ordered by the data pipeline, top to bottom the same order you
#  run them in:
#
#     1. Setup   →  2. Ingest  →  3. Coefficients  →  4. Transform
#                                                          │
#                            6. App  ←  5. Machine Learning┘
#
#  Plus cross-cutting stages: 7. Docs and 8. Housekeeping.
#
#  New here? Just run `make` (or `make help`) for a grouped list of every target.
# ══════════════════════════════════════════════════════════════════════════════

.DEFAULT_GOAL := help

.PHONY: help \
        setup ml-setup app-install \
        ingest-all ingest-recent ingest-jolpica verify-bronze monitor-ingest manifest-report simulate test test-integration \
        coefficients-fit coefficients-promote coefficients-status coefficients-check car-fe-fit \
        dbt-dev dbt-dev-full dbt-prod dbt-test dbt-docs query lint lint-fix lint-oracle-snapshot lint-oracle-check test-all test-fast transform-check \
        ml-features ml-tune ml-train ml-evaluate ml-predict ml-onnx ml-card ml-reference ml-all ml-test ml-clean \
        app-data app-data-wave0 app-data-check app-models app-dev app-dev-local app-build app-parity app-publish app-publish-dry app-deploy \
        docs-reference project-graph watch-graph docs-audit docs-facts docs-site docs-install \
        clean-logs clean-ds

help:  ## Show this help, grouped by pipeline stage
	@awk 'BEGIN {FS = ":.*##"} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next} \
		/^[a-zA-Z0-9_.-]+:.*?##/ {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


##@ 1. Setup install once, in this order
setup:  ## Build venv + install all deps, scaffold data/ (run first)
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv .venv; \
	fi
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r requirements.txt
	mkdir -p data/bronze data/silver data/gold data/cache data/marts
	touch data/bronze/.gitkeep data/silver/.gitkeep data/gold/.gitkeep data/cache/.gitkeep data/marts/.gitkeep
	cd transform && ../.venv/bin/dbt deps

ml-setup:  ## Install ML deps (ml/requirements.txt) into the shared venv
	./.venv/bin/pip install -r ml/requirements.txt

app-install:  ## Install web-app deps (pnpm)
	cd app && pnpm install


##@ 2. Ingest pull raw F1 timing data into Bronze Parquet
ingest-all:  ## Pull all 2018–2024 races → Bronze (~2 GB, 30–45 min)
	./.venv/bin/python ingestion/src/ingest.py --start-season 2018 --end-season 2024 --session both

ingest-recent:  ## Pull 2023–2024 only → Bronze (~15 min, ~200 MB)
	./.venv/bin/python ingestion/src/ingest.py --start-season 2023 --end-season 2024 --session both

ingest-jolpica:  ## Pull standings + pit stops (2018–2024) via Jolpica API (~2–3 min)
	./.venv/bin/python ingestion/src/jolpica_client.py --start-season 2018 --end-season 2024

verify-bronze:  ## Verify Bronze integrity (counts, nulls, schema)
	./.venv/bin/python ingestion/verify_bronze.py

monitor-ingest:  ## Watch a running ingest log for failures/completion (LOG=path)
	@test -n "$(LOG)" || { echo "Usage: make monitor-ingest LOG=path/to/ingest.log"; exit 1; }
	./.venv/bin/python ingestion/scripts/monitor_ingest.py $(LOG)

simulate:  ## Replay a Bronze race lap-by-lap (demo of the data)
	./.venv/bin/python ingestion/src/replay_simulator.py --parquet_path data/bronze/laps/season=2024/race=bahrain_grand_prix/2024_bahrain_grand_prix_laps.parquet --race_id 2024_1 --speed 10

manifest-report:  ## Report ingestion run status + schema-drift from manifests
	./.venv/bin/python ingestion/manifest_report.py

test:  ## Offline ingestion unit tests (no network, <5 s)
	./.venv/bin/pytest ingestion/tests/test_ingestion.py ingestion/tests/test_jolpica.py

test-integration:  ## Live FastF1 ingestion test (needs network)
	./.venv/bin/pytest ingestion/tests/test_integration_fastf1.py -m integration


##@ 3. Coefficients fit physics seeds before transforming
coefficients-fit:  ## Fit cliff + weight-penalty seeds → seeds/_pending/ (no promote)
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_compound_cliff
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_weight_penalty
	@echo ""
	@echo "Pending seeds written to transform/seeds/_pending/"
	@echo "Review, then run: make coefficients-promote"

coefficients-promote:  ## Promote _pending/ seeds → live (archives previous)
	cd transform && ../.venv/bin/python -m tasks.coefficients.seed_writer promote --all --confirm

coefficients-status:  ## Show current seed state
	cd transform && ../.venv/bin/python -m tasks.coefficients.seed_writer status

coefficients-check:  ## Warn (non-fatal) if seeds are stale vs the data window
	cd transform && ../.venv/bin/python -m tasks.coefficients.check_freshness || true

car-fe-fit:  ## Fit de-biased constructor car FE → data/fits/constructor_car_fe.parquet
	cd transform && ../.venv/bin/dbt run --profiles-dir profiles --target dev \
	  --select +int_lap_fuel_state +int_field_pace_curve +int_event_corrections +int_track_evolution +stg_laps
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_constructor_car_fe

deg-iso-fit:  ## Fit isotonic tyre-deg curves + modulation coefs → data/fits/degradation_isotonic.parquet
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_degradation_isotonic


##@ 4. Transform Bronze → DuckDB warehouse (dbt)
dbt-dev:  ## Build all 53 dbt models → data/dev.duckdb
	cd transform && ../.venv/bin/dbt run --profiles-dir profiles --target dev

dbt-dev-full: coefficients-check car-fe-fit  ## Seed check → car-FE refit → full dbt run
	cd transform && ../.venv/bin/dbt run --profiles-dir profiles --target dev

dbt-prod:  ## Prod build (Fabric deferred runs against dev for now)
	cd transform && ../.venv/bin/dbt run --profiles-dir profiles --target dev

dbt-test:  ## Run all 336 dbt tests (schema + singular + assert_* invariants)
	cd transform && ../.venv/bin/dbt test --profiles-dir profiles

dbt-docs:  ## Generate + serve the dbt docs site (port 8080)
	cd transform && ../.venv/bin/dbt docs generate --profiles-dir profiles && ../.venv/bin/dbt docs serve

query:  ## Open the warehouse in the Harlequin SQL IDE
	./.venv/bin/harlequin data/dev.duckdb

lint:  ## SQLFluff lint all models
	cd transform && ../.venv/bin/sqlfluff lint models/ --dialect duckdb --disable-progress-bar

lint-fix:  ## SQLFluff auto-fix all models
	cd transform && ../.venv/bin/sqlfluff fix models/ --dialect duckdb --disable-progress-bar

lint-oracle-snapshot:  ## Record byte-stable baseline of all model outputs (run on a known-good ci.duckdb)
	cd transform && ../.venv/bin/python scripts/snapshot_model_hashes.py

lint-oracle-check:  ## Fail if any fct_* model output drifted vs the recorded baseline (gates lint fixes)
	cd transform && ../.venv/bin/python scripts/snapshot_model_hashes.py --check

test-all:  ## CI-equivalent: full dbt build on fixtures + coefficient tests
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target ci --vars '{"bronze_base": "../transform/tests/fixtures/bronze"}'
	PYTHONPATH=transform ./.venv/bin/pytest transform/tasks/coefficients/tests/

test-fast:  ## CI fast path: fast_build selector on fixtures
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target ci --selector fast_build --vars '{"bronze_base": "../transform/tests/fixtures/bronze"}'

transform-check:  ## Reproduce the CI transform gates in order (parse → lint → build → singular tests → pytest)
	cd transform && ../.venv/bin/dbt parse --profiles-dir profiles --target ci
	cd transform && ../.venv/bin/sqlfluff lint models/ --dialect duckdb --disable-progress-bar
	cd transform && ../.venv/bin/dbt build --profiles-dir profiles --target ci --vars '{"bronze_base": "../transform/tests/fixtures/bronze"}'
	cd transform && ../.venv/bin/dbt test --profiles-dir profiles --target ci --select test_type:singular --vars '{"bronze_base": "../transform/tests/fixtures/bronze"}'
	PYTHONPATH=transform ./.venv/bin/pytest transform/tasks/coefficients/tests/


##@ 5. Machine Learning warehouse → XGBoost / ONNX models
ml-features:  ## Validate the ML feature contract against the warehouse
	./.venv/bin/python -m ml.src.features --check

ml-tune:  ## Hyperparameter search (Optuna, 50 trials) → chains production-version refit
	./.venv/bin/python -m ml.src.tune --target all --trials 50

ml-train:  ## Train all XGBoost degradation models
	./.venv/bin/python -m ml.src.train --all

ml-evaluate:  ## Evaluate models (metrics + leakage checks)
	./.venv/bin/python -m ml.src.evaluate --all

ml-predict:  ## Score → data/marts/mart_degradation_predictions.parquet
	./.venv/bin/python -m ml.src.predict --out data/marts/mart_degradation_predictions.parquet

ml-onnx:  ## Export ONNX + parity + ml/models/manifest.json (no copy to app/)
	./.venv/bin/python -m ml.src.export_onnx --all

ml-card:  ## Write the model card (ml/models/model_card.json)
	./.venv/bin/python -m ml.src.card --write

ml-reference:  ## Regenerate the ML reference docs
	./.venv/bin/python scripts/gen_ml_reference.py

ml-all: ml-features ml-tune ml-train ml-evaluate ml-predict ml-onnx ml-card ml-reference  ## Full ML pipeline end-to-end

ml-test:  ## ML unit tests (leakage, parity, schema)
	./.venv/bin/python -m pytest ml/tests -q

ml-clean:  ## Remove built models + predictions
	rm -rf ml/models/*.bst ml/models/*.onnx ml/artefacts/* data/marts/mart_degradation_predictions.parquet


##@ 6. App warehouse + models → web app & CDN
app-data:  ## Export warehouse → app/public/data/ parquet + _manifest.json
	./.venv/bin/python scripts/export_app_data.py

app-data-wave0:  ## Export Wave-0 / canary tables only (fast)
	./.venv/bin/python scripts/export_app_data.py --wave 0

app-data-check:  ## CI drift gate: regenerate manifest and diff (no write)
	./.venv/bin/python scripts/export_app_data.py --check

app-models:  ## Copy ONNX models (version per manifest) + manifest/encoders → app/public/models/
	@mkdir -p app/public/models
	@if [ -d ml/models ]; then \
	  ver=$$(./.venv/bin/python -c "import json;print(json.load(open('ml/models/manifest.json'))['model_version'])"); \
	  rm -f app/public/models/*.onnx; \
	  cp ml/models/*_$$ver.onnx app/public/models/ 2>/dev/null || true; \
	  cp ml/models/manifest.json app/public/models/ 2>/dev/null || true; \
	  cp ml/models/encoders.json app/public/models/ 2>/dev/null || true; \
	  cp ml/models/model_card.json app/public/models/ 2>/dev/null || true; \
	  echo "  ✅  $$ver ONNX models copied to app/public/models/"; \
	  ls -lh app/public/models/; \
	else \
	  echo "  ⚠️   ml/models/ not found run: make ml-onnx"; \
	fi

app-dev:  ## Start Vite dev server (reads live CDN data)
	cd app && pnpm dev

app-dev-local:  ## Start Vite dev server using local app/public/data/ (offline)
	cd app && VITE_DATA_BASE="" pnpm dev

app-build:  ## Type-check + build the React app → app/dist/
	cd app && pnpm build

app-parity:  ## Prove in-browser ONNX == booster ground truth (F3 acceptance)
	PYTHONPATH=. ./.venv/bin/python scripts/dump_parity_rows.py
	cd app && RUN_PARITY=1 ./node_modules/.bin/vitest run src/ml/parity.node.test.ts --environment node

app-publish:  ## Sync app/public/data/ → live GCS CDN (no delete; manifest last)
	./scripts/publish_cdn.sh

app-publish-dry:  ## Preview the CDN sync without uploading
	./scripts/publish_cdn.sh --dry-run

app-deploy: app-data app-publish  ## Export warehouse then publish to the CDN

add-season:  ## Onboard a new season end-to-end (stops before publish): make add-season SEASON=YYYY
	@test -n "$(SEASON)" || { echo "Usage: make add-season SEASON=YYYY"; exit 1; }
	@echo "── 1/7  Ingest races for season $(SEASON) ──────────────────────────"
	./.venv/bin/python ingestion/src/ingest.py --season $(SEASON) --session both
	@echo "── 2/7  Ingest standings + pit stops for $(SEASON) ─────────────────"
	./.venv/bin/python ingestion/src/jolpica_client.py --start-season $(SEASON) --end-season $(SEASON)
	@echo "── 3/7  Verify Bronze integrity ────────────────────────────────────"
	./.venv/bin/python ingestion/verify_bronze.py
	@echo "── 4/7  Re-fit isotonic tyre-deg curves ────────────────────────────"
	$(MAKE) deg-iso-fit
	@echo "── 5/7  Full dbt build (car-FE refit + all models) ─────────────────"
	$(MAKE) dbt-dev-full
	@echo "── 6/7  dbt tests ──────────────────────────────────────────────────"
	$(MAKE) dbt-test
	@echo "── 7/7  Export warehouse → app/public/data/ ────────────────────────"
	$(MAKE) app-data
	@echo "── ✔    Smoke test ─────────────────────────────────────────────────"
	./.venv/bin/python scripts/smoke_test_season.py $(SEASON)
	@echo ""
	@echo "✔  Season $(SEASON) onboarded locally."
	@echo "   Review the simulator at: make app-dev-local"
	@echo "   When satisfied, publish: make app-publish"


##@ 7. Docs reference, project graph, site
##   Tip: for live editing run `make docs-site` and `make watch-graph` in two terminals  
##   the graph regenerates on source change and Mintlify hot-reloads it.
docs-reference:  ## Regenerate docs/reference/**/*.mdx from source
	./.venv/bin/python scripts/build_reference.py

project-graph:  ## Regenerate the interactive project dependency graph HTML
	./.venv/bin/python scripts/gen_project_graph.py -o docs/project-graph.html

watch-graph:  ## Watch source files and run project-graph on change
	./.venv/bin/python scripts/watch_project_graph.py

docs-audit:  ## CI gate: README-presence + tour-footer + file-header checks
	./.venv/bin/python scripts/docs_audit.py --headers

docs-facts:  ## CI gate: reconcile headline counts across README + docs
	./.venv/bin/python scripts/docs_facts.py

docs-site:  ## Start the Mintlify docs dev server (http://localhost:3000)
	cd docs && npx -y mintlify dev

docs-install:  ## (no-op) npx fetches Mintlify automatically
	@echo "No global install needed. npx will be used automatically."


##@ 8. Housekeeping
clean-logs:  ## Remove dbt + ingestion + root logs
	rm -rf transform/logs/*.log transform/logs/*.log.* ingestion/_archive/*.log ingestion/_archive/*.txt logs/*.log

clean-ds:  ## Remove stray .DS_Store files
	find . -name ".DS_Store" -depth -exec rm {} \;
