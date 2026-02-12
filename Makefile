.PHONY: init-env doctor up down logs test lint fmt shell qa-fetch-matrix qa-fetch-registry qa-fetch-probe-v3 qa-fetch-probe-v3-notebook

init-env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example; please edit paths/UID/GID")

doctor:
	@bash -lc 'set -euo pipefail; \
		set -a; [ -f ./.env ] && . ./.env || true; set +a; \
		echo "PWD=$$(pwd)"; \
		echo "EAM_REPO_HOST=$${EAM_REPO_HOST:-.}"; \
		echo "EAM_ARTIFACTS_HOST=$${EAM_ARTIFACTS_HOST:-./artifacts}"; \
		echo "EAM_DATA_HOST=$${EAM_DATA_HOST:-./data}"; \
		echo "EAM_UID/EAM_GID (Linux) should be: $$(id -u):$$(id -g)"; \
		mkdir -p "$${EAM_ARTIFACTS_HOST:-./artifacts}" "$${EAM_DATA_HOST:-./data}"; \
		test -w "$${EAM_ARTIFACTS_HOST:-./artifacts}" || (echo "ERROR: artifacts dir not writable" && exit 2); \
		test -w "$${EAM_DATA_HOST:-./data}" || (echo "ERROR: data dir not writable" && exit 2); \
		tmpf="$${EAM_ARTIFACTS_HOST:-./artifacts}/.doctor_write_test"; \
		echo "doctor ok $$(date -Is)" > "$$tmpf"; \
		rm -f "$$tmpf"; \
		echo "doctor: OK"'

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

test:
	docker compose run --rm api pytest -q tests

lint:
	docker compose run --rm api ruff check src tests

fmt:
	docker compose run --rm api ruff format src tests

shell:
	docker compose run --rm api bash

docs-check:
	python3 scripts/check_docs_tree.py

qa-fetch-matrix:
	python3 scripts/generate_qa_fetch_rename_matrix.py

qa-fetch-registry:
	python3 scripts/generate_qa_fetch_registry_json.py

qa-fetch-probe-v3:
	python3 scripts/run_qa_fetch_probe_v3.py

qa-fetch-probe-v3-notebook:
	docker compose run --rm api bash -lc 'python -m pip install --no-cache-dir jupyter nbconvert ipykernel && jupyter nbconvert --to notebook --execute notebooks/qa_fetch_probe_v3.ipynb --output qa_fetch_probe_v3.executed.ipynb --output-dir notebooks --ExecutePreprocessor.timeout=0'

subagent-check:
	@python3 scripts/check_subagent_packet.py --phase-id "$${PHASE_ID:?PHASE_ID is required}"
