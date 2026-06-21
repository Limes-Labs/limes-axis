.PHONY: install lint test typecheck build-web openapi openapi-check test-api test-worker test-web test-integration dev-stack-up dev-stack-down

install:
	pnpm install
	cd services/api && uv sync
	cd services/worker && uv sync

lint:
	pnpm lint
	cd services/api && uv run ruff check .
	cd services/worker && uv run ruff check .

typecheck:
	pnpm typecheck

test: test-api test-worker test-web

test-api:
	cd services/api && uv run pytest

test-worker:
	cd services/worker && uv run pytest

test-web:
	pnpm --filter @limes-axis/web test

test-integration:
	cd services/api && AXIS_RUN_INTEGRATION=1 uv run pytest tests/integration
	cd services/worker && AXIS_RUN_INTEGRATION=1 uv run pytest tests/integration

build-web:
	pnpm --filter @limes-axis/web build

openapi:
	cd services/api && uv run python scripts/export_openapi.py ../../docs/openapi.json

openapi-check:
	cd services/api && uv run python scripts/export_openapi.py /tmp/limes-axis-openapi.json
	diff -u docs/openapi.json /tmp/limes-axis-openapi.json

dev-stack-up:
	docker compose -f infra/docker/docker-compose.yml up -d

dev-stack-down:
	docker compose -f infra/docker/docker-compose.yml down
