.PHONY: install lint test typecheck build-web openapi openapi-check test-api test-worker test-web test-integration dev-stack-up dev-stack-down demo-stack-up demo-stack-down demo-db-upgrade demo-api demo-web demo-check demo-check-live demo-verify

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

demo-stack-up: dev-stack-up

demo-stack-down: dev-stack-down

demo-db-upgrade:
	cd services/api && uv run alembic upgrade head

demo-api:
	cd services/api && uv run uvicorn axis_api.main:create_app --factory --host 127.0.0.1 --port 8000

demo-web:
	NEXT_PUBLIC_AXIS_API_BASE_URL=http://127.0.0.1:8000 pnpm --filter @limes-axis/web dev

demo-check:
	cd services/api && uv run python scripts/check_demo_environment.py

demo-check-live:
	cd services/api && uv run python scripts/check_demo_environment.py --api-url http://127.0.0.1:8000 --web-url http://127.0.0.1:3000

demo-verify: openapi-check demo-check
