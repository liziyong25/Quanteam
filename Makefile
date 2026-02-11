.PHONY: init-env doctor up down logs test lint fmt shell

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
