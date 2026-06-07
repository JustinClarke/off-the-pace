.PHONY: setup dbt-dev dbt-dev-full dbt-prod dbt-test dbt-docs ingest ingest-all simulate streamlit test query \
        coefficients-check coefficients-fit coefficients-promote coefficients-status \
        test-all test-fast lint lint-fix \
        docs-reference docs-site docs-audit docs-facts app-data app-data-check app-data-wave0 app-models app-parity app-build \
        ml-setup ml-features ml-train ml-tune ml-predict ml-onnx ml-evaluate ml-card ml-reference ml-all ml-test ml-clean \
        clean-logs clean-ds

## ─── Setup ──────────────────────────────────────────────────────────────────────
## make setup        Build Python venv and install all dependencies (requirements.txt)
setup:
	./.venv/bin/pip install -r requirements.txt
	mkdir -p data/bronze data/silver data/gold data/cache
	touch data/bronze/.gitkeep data/silver/.gitkeep data/gold/.gitkeep data/cache/.gitkeep

## ─── dbt: Transform Layer ────────────────────────────────────────────────────────
## make dbt-dev          Run all 46 dbt models against the local dev DuckDB
## make dbt-dev-full     Freshness check → dbt run (checks seed staleness first)
## make dbt-test         Run all 339 dbt tests (includes assert_additive_identity)
## make dbt-docs         Generate and serve the dbt docs site on port 8080

## ─── Coefficients (seed fitting) ────────────────────────────────────────────────
## make coefficients-fit      Fit cliff + weight-penalty params → seeds/_pending/
## make coefficients-promote  Promote _pending/ → live seeds (archives previous)
## make coefficients-status   Show current seed state
# Run freshness check before dbt exits 1 (warning only) if seeds are stale.
coefficients-check:
	cd transform && ../.venv/bin/python -m tasks.coefficients.check_freshness || true

# Fit all coefficient seeds (writes to seeds/_pending/ does NOT promote).
coefficients-fit:
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_compound_cliff
	cd transform && ../.venv/bin/python -m tasks.coefficients.fit_weight_penalty
	@echo ""
	@echo "Pending seeds written to transform/seeds/_pending/"
	@echo "Review, then run: make coefficients-promote"

# Promote pending seeds to live (archives previous versions).
coefficients-promote:
	cd transform && ../.venv/bin/python -m tasks.coefficients.seed_writer promote --all --confirm

# Show current seed state.
coefficients-status:
	cd transform && ../.venv/bin/python -m tasks.coefficients.seed_writer status

# Full dev build: freshness check → dbt run.
dbt-dev-full: coefficients-check
	cd transform && dbt run --profiles-dir profiles --target dev

dbt-dev:
	cd transform && dbt run --profiles-dir profiles --target dev

dbt-prod:
	# Fabric target is deferred runs against dev until a fabric profile is wired up
	cd transform && dbt run --profiles-dir profiles --target dev

dbt-test:
	cd transform && dbt test --profiles-dir profiles

dbt-docs:
	cd transform && dbt docs generate --profiles-dir profiles && dbt docs serve

## ─── Ingestion ───────────────────────────────────────────────────────────────────
## make ingest-all     Pull all 168 races (2018–2024) to Bronze Parquet (~2 GB, 30–45 min)
## make ingest-recent  Pull 2023–2024 seasons only
## make test           Run offline ingestion tests (no network, <5 s)
ingest:
	./.venv/bin/python ingestion/src/api_client.py

ingest-all:
	./.venv/bin/python ingestion/src/ingest.py --start-season 2018 --end-season 2024 --sessions both

ingest-recent:
	./.venv/bin/python ingestion/src/ingest.py --start-season 2023 --end-season 2024 --sessions both

ingest-fix-2024:
	./.venv/bin/python ingestion/src/ingest.py -s 2024 --sessions R --force

simulate:
	./.venv/bin/python ingestion/src/replay_simulator.py --parquet_path data/bronze/2021_bahrain_laps.parquet --race_id 2021_01 --speed 10

streamlit:
	./.venv/bin/streamlit run app/app.py

test:
	pytest ingestion/tests/test_ingestion.py

query:
	./.venv/bin/harlequin data/dev.duckdb

## ─── Docs ────────────────────────────────────────────────────────────────────────
## make docs-reference  Regenerate all docs/docs/reference/**/*.mdx from source
## make docs-audit      README-presence + tour-footer + file-header checks (CI gate)
## make docs-facts      Headline-count reconciliation across README + docs/intro.md
## make docs-site       Start Docusaurus dev server at http://localhost:3000
## make app-data        Export warehouse → app/public/data/ parquet + _manifest.json
## make app-data-check  CI drift gate: regenerate and diff manifest (no write)
## make app-data-wave0  Export Wave-0 / canary tables only (fast)
## make app-models      Copy ONNX models + manifest/encoders → app/public/models/
## make app-parity      Prove in-browser ONNX inference == booster ground truth (F3 acceptance)
## make app-build       Type-check + build the React app to app/dist/ (local only)
docs-reference:
	./.venv/bin/python scripts/build_reference.py

docs-audit:
	./.venv/bin/python scripts/docs_audit.py --headers

docs-facts:
	./.venv/bin/python scripts/docs_facts.py

docs-site:
	cd docs && yarn start

app-data:
	./.venv/bin/python scripts/export_app_data.py

app-data-check:
	./.venv/bin/python scripts/export_app_data.py --check

app-data-wave0:
	./.venv/bin/python scripts/export_app_data.py --wave 0

app-models:
	@mkdir -p app/public/models
	@if [ -d ml/models ]; then \
	  cp ml/models/*_v1.onnx app/public/models/ 2>/dev/null || true; \
	  cp ml/models/manifest.json app/public/models/ 2>/dev/null || true; \
	  cp ml/models/encoders.json app/public/models/ 2>/dev/null || true; \
	  cp ml/models/model_card.json app/public/models/ 2>/dev/null || true; \
	  echo "  ✅  ONNX models copied to app/public/models/"; \
	  ls -lh app/public/models/; \
	else \
	  echo "  ⚠️   ml/models/ not found run: make ml-onnx"; \
	fi

app-build:
	cd app && pnpm build

app-parity:
	PYTHONPATH=. ./.venv/bin/python scripts/dump_parity_rows.py
	cd app && RUN_PARITY=1 ./node_modules/.bin/vitest run src/ml/parity.node.test.ts --environment node

## ─── Test & Lint ─────────────────────────────────────────────────────────────────
## make test-all   Full dbt build + coefficient tests (CI-equivalent)
## make lint       SQLFluff lint on all models
## make lint-fix   SQLFluff auto-fix
# Open-source contributor helpers
test-all:
	cd transform && dbt build --profiles-dir profiles --target ci
	PYTHONPATH=transform ./.venv/bin/pytest transform/tasks/coefficients/tests/

test-fast:
	cd transform && dbt build --profiles-dir profiles --target ci --selector fast_build
	cd transform && dbt test --profiles-dir profiles --target ci

lint:
	cd transform && sqlfluff lint models/ --dialect duckdb --disable-progress-bar

lint-fix:
	cd transform && sqlfluff fix models/ --dialect duckdb --disable-progress-bar

clean-logs:
	rm -rf transform/logs/*.log transform/logs/*.log.* ingestion/_archive/*.log ingestion/_archive/*.txt logs/*.log

clean-ds:
	find . -name ".DS_Store" -depth -exec rm {} \;

# ─── Machine Layer (XGBoost degradation models) ──────────────────────
# One venv (./.venv). Reads the warehouse read-only; never writes to app/.
ml-setup:
	./.venv/bin/pip install -r ml/requirements.txt

ml-features:
	./.venv/bin/python -m ml.src.features --check

ml-train:
	./.venv/bin/python -m ml.src.train --all

ml-tune:
	./.venv/bin/python -m ml.src.tune --target all --trials 50   # chains v1 refit

ml-predict:
	./.venv/bin/python -m ml.src.predict --out data/marts/mart_degradation_predictions.parquet

ml-onnx:
	./.venv/bin/python -m ml.src.export_onnx --all   # parity + writes ml/models/manifest.json; NO copy to app/

ml-evaluate:
	./.venv/bin/python -m ml.src.evaluate --all

ml-card:
	./.venv/bin/python -m ml.src.card --write

ml-reference:
	./.venv/bin/python scripts/gen_ml_reference.py

ml-test:
	./.venv/bin/python -m pytest ml/tests -q

ml-all: ml-features ml-tune ml-train ml-evaluate ml-predict ml-onnx ml-card ml-reference

ml-clean:
	rm -rf ml/models/*.bst ml/models/*.onnx ml/artefacts/* data/marts/mart_degradation_predictions.parquet
