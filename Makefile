.PHONY: install lint test typecheck build-web openapi openapi-check security-check deployment-check deployment-rollout-rehearsal-plan deployment-rollout-rehearsal deployment-backup-rehearsal-plan deployment-backup-rehearsal deployment-restore-rehearsal-plan deployment-restore-rehearsal deployment-typedb-recovery-rehearsal-plan deployment-typedb-recovery-rehearsal deployment-object-storage-recovery-rehearsal-plan deployment-object-storage-recovery-rehearsal container-check container-release-check container-security-check vulnerability-management-check container-build-api container-build-web container-build container-scan-local test-api test-worker test-web test-integration dev-stack-up dev-stack-down demo-stack-up demo-stack-down demo-db-upgrade demo-api demo-web demo-check demo-check-live demo-verify demo-backup-plan demo-backup-local demo-restore-local

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

security-check:
	cd services/api && uv run python scripts/check_security_posture.py

deployment-check:
	cd services/api && uv run python scripts/check_deployment_package.py

deployment-rollout-rehearsal-plan:
	cd services/api && uv run python scripts/rehearse_deployment_rollout.py --repo-root ../.. --plan

deployment-rollout-rehearsal:
	@test -n "$(AXIS_KUBE_CONTEXT)" || (echo "Set AXIS_KUBE_CONTEXT to the Kubernetes context to rehearse against"; exit 2)
	cd services/api && uv run python scripts/rehearse_deployment_rollout.py --repo-root ../.. --execute --context "$(AXIS_KUBE_CONTEXT)" $(AXIS_DEPLOYMENT_ROLLOUT_ARGS)

deployment-backup-rehearsal-plan:
	cd services/api && uv run python scripts/rehearse_production_backup.py --repo-root ../.. --plan

deployment-backup-rehearsal:
	@test -n "$(AXIS_KUBE_CONTEXT)" || (echo "Set AXIS_KUBE_CONTEXT to the Kubernetes context to rehearse against"; exit 2)
	cd services/api && uv run python scripts/rehearse_production_backup.py --repo-root ../.. --execute --context "$(AXIS_KUBE_CONTEXT)" $(AXIS_PRODUCTION_BACKUP_ARGS)

deployment-restore-rehearsal-plan:
	cd services/api && uv run python scripts/rehearse_production_restore.py --repo-root ../.. --plan

deployment-restore-rehearsal:
	@test -n "$(AXIS_KUBE_CONTEXT)" || (echo "Set AXIS_KUBE_CONTEXT to the Kubernetes context to rehearse against"; exit 2)
	cd services/api && uv run python scripts/rehearse_production_restore.py --repo-root ../.. --execute --context "$(AXIS_KUBE_CONTEXT)" $(AXIS_PRODUCTION_RESTORE_ARGS)

deployment-typedb-recovery-rehearsal-plan:
	cd services/api && uv run python scripts/rehearse_typedb_recovery.py --repo-root ../.. --plan

deployment-typedb-recovery-rehearsal:
	@test -n "$(AXIS_KUBE_CONTEXT)" || (echo "Set AXIS_KUBE_CONTEXT to the Kubernetes context to rehearse against"; exit 2)
	@test -n "$(AXIS_TYPEDB_RECOVERY_IMAGE)" || (echo "Set AXIS_TYPEDB_RECOVERY_IMAGE to a container image that includes TypeDB Console"; exit 2)
	cd services/api && uv run python scripts/rehearse_typedb_recovery.py --repo-root ../.. --execute --context "$(AXIS_KUBE_CONTEXT)" --image "$(AXIS_TYPEDB_RECOVERY_IMAGE)" $(AXIS_TYPEDB_RECOVERY_ARGS)

deployment-object-storage-recovery-rehearsal-plan:
	cd services/api && uv run python scripts/rehearse_object_storage_recovery.py --repo-root ../.. --plan

deployment-object-storage-recovery-rehearsal:
	@test -n "$(AXIS_KUBE_CONTEXT)" || (echo "Set AXIS_KUBE_CONTEXT to the Kubernetes context to rehearse against"; exit 2)
	@test -n "$(AXIS_OBJECT_STORAGE_RECOVERY_IMAGE)" || (echo "Set AXIS_OBJECT_STORAGE_RECOVERY_IMAGE to a container image that includes MinIO Client"; exit 2)
	cd services/api && uv run python scripts/rehearse_object_storage_recovery.py --repo-root ../.. --execute --context "$(AXIS_KUBE_CONTEXT)" --image "$(AXIS_OBJECT_STORAGE_RECOVERY_IMAGE)" $(AXIS_OBJECT_STORAGE_RECOVERY_ARGS)

container-check:
	cd services/api && uv run python scripts/check_container_images.py

container-release-check:
	cd services/api && uv run python scripts/check_container_release.py

container-security-check:
	cd services/api && uv run python scripts/check_container_security_scan.py

vulnerability-management-check:
	cd services/api && uv run python scripts/check_vulnerability_management.py

container-build-api:
	docker build -f services/api/Dockerfile -t limes-axis-api:local .

container-build-web:
	docker build -f apps/web/Dockerfile -t limes-axis-web:local .

container-build: container-build-api container-build-web

container-scan-local: container-build
	mkdir -p .axis/trivy-cache .axis/trivy-reports
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$$(pwd)/.axis/trivy-cache:/root/.cache/" -v "$$(pwd)/.axis/trivy-reports:/reports" aquasec/trivy:0.71.2 image --scanners vuln --pkg-types os,library --severity CRITICAL --ignore-unfixed --exit-code 1 --format json --output /reports/api-critical.json --timeout 10m limes-axis-api:local
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$$(pwd)/.axis/trivy-cache:/root/.cache/" -v "$$(pwd)/.axis/trivy-reports:/reports" aquasec/trivy:0.71.2 image --scanners vuln --pkg-types os,library --severity CRITICAL --ignore-unfixed --exit-code 1 --format json --output /reports/web-critical.json --timeout 10m limes-axis-web:local
	@echo "Trivy reports saved under .axis/trivy-reports/"

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

demo-backup-plan:
	cd services/api && uv run python scripts/demo_backup_restore.py --repo-root ../.. plan

demo-backup-local:
	cd services/api && uv run python scripts/demo_backup_restore.py --repo-root ../.. backup

demo-restore-local:
	@test -n "$(AXIS_BACKUP_DIR)" || (echo "Set AXIS_BACKUP_DIR=.axis/backups/<backup-id>"; exit 2)
	cd services/api && uv run python scripts/demo_backup_restore.py --repo-root ../.. restore --backup-dir "$(AXIS_BACKUP_DIR)" --confirm-restore
