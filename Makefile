.PHONY: install lint test typecheck build-web test-api test-worker test-web dev-stack-up dev-stack-down

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

build-web:
	pnpm --filter @limes-axis/web build

dev-stack-up:
	docker compose -f infra/docker/docker-compose.yml up -d

dev-stack-down:
	docker compose -f infra/docker/docker-compose.yml down
