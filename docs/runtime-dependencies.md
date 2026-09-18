# Runtime dependency inventory

Generated from `runtime-dependencies.json`; do not edit this matrix by hand.

Inventory source revision: `d09efeceb898d5eb3791eb827a6a0d27f7f7699e`.

This is a static inventory, not deployment accreditation, an egress policy,
a runnable deployment profile or proof that hidden network calls are absent.

The checker reads source declarations without importing the API or reading `.env`.
Topology changes require explicit inventory review; their digests are not refreshed
by `--write`. File references identify evidence to inspect, not tests run by this checker.
See [scope and verification](runtime-dependencies-guide.md) for the exact boundaries.

## Packaged components

| Component | Owner | Packaging source |
| --- | --- | --- |
| api | Control API | `infra/helm/limes-axis/templates/api-deployment.yaml` |
| keycloak | Identity infrastructure | `infra/docker/docker-compose.yml` |
| minio | Object storage | `infra/docker/docker-compose.yml` |
| postgres | Operational persistence | `infra/docker/docker-compose.yml` |
| temporal | Workflow infrastructure | `infra/docker/docker-compose.yml` |
| temporal-ui | Workflow operations | `infra/docker/docker-compose.yml` |
| typedb | Ontology runtime | `infra/docker/docker-compose.yml` |
| valkey | Rate-limit infrastructure | `infra/docker/docker-compose.yml` |
| web | Governance console | `infra/helm/limes-axis/templates/web-deployment.yaml` |
| worker | Workflow runtime | `infra/docker/docker-compose.yml`, `infra/helm/limes-axis/templates/worker-deployment.yaml` |

## Dependencies

### artifact-object-store

Store source envelopes and export artifacts behind the existing object-store adapter.

Owner: **Canonical payload and artifact storage**. Components: api, minio, worker.

Phase: runtime. Requirement: **conditional**. S3 artifact adapter selected; local filesystem does not require this network connection.

Configuration references: `AXIS_CONNECTOR_EXPORT_S3_ENDPOINT`.

Local option (supported): Use local MinIO for shared S3-compatible storage. Local filesystem mode is a distinct single-host option, not WORM or multi-node parity.

Failure behavior: Object-store-dependent extraction or export cannot complete if payload writes/reads fail. Durable acceptance remains with existing ingestion owners.

- outbound, https, ports 443, 9000: A configured S3-compatible artifact endpoint; not the input source endpoint.

Evidence references: source `services/api/src/axis_api/object_storage.py`; source `services/api/src/axis_api/settings/persistence.py`; test `services/api/tests/test_object_storage.py`.

### clock

Maintain time used for tokens, leases, certificate validity and workflow scheduling.

Owner: **Host operations**. Components: api, keycloak, temporal, worker.

Phase: runtime. Requirement: **required**.

Configuration references: none; platform or packaged dependency.

Local option (conditional): Use a trusted local time source or controlled offline clock procedure. Axis has no separate time configuration authority.

Failure behavior: Clock drift can invalidate identity, lease and scheduling assumptions. No automatic public-time dependency is asserted from source inventory alone.

- host, ntp, ports 123: Host-owned time source, not an Axis-created client. A trusted offline clock is also an operator option.

Evidence references: documentation `docs/development.md`; source `services/api/src/axis_api/connector_credential_leases.py`; source `services/api/src/axis_api/identity.py`.

### console-origin

Public console origin and permitted browser origins constrain login navigation and cross-origin requests. These are not autonomous API dial targets. The host cookie prefix is cookie-scope metadata; AXIS_CSRF_HOST_COOKIE_NAME is a web source constant naming the API-issued readable CSRF cookie, not an environment setting or remote host.

Owner: **Browser session boundary**. Components: api, web.

Phase: runtime. Requirement: **required**.

Configuration references: `AXIS_CORS_ORIGINS`, `AXIS_CSRF_HOST_COOKIE_NAME`, `AXIS_OIDC_SESSION_COOKIE_HOST_PREFIX`, `AXIS_PUBLIC_BASE_URL`.

Local option (supported): Host the console within the boundary and use matching public origins and identity callbacks.

Failure behavior: A wrong origin can prevent cross-origin or browser authentication flows; no alternate origin is admitted by this inventory.

- browser, https, ports 443: Browser navigation to the same locally hosted console; development uses port 3000.

Evidence references: test `apps/web/lib/session-csrf.test.ts`; source `apps/web/lib/session-csrf.ts`; documentation `docs/development.md`; source `services/api/src/axis_api/oidc_code_flow.py`; source `services/api/src/axis_api/settings/runtime.py`.

### control-api

The console reads and mutates through the same tenant-bound control API, including liveness and readiness probes.

Owner: **Console/API transport**. Components: api, web.

Phase: runtime. Requirement: **required**.

Configuration references: `AXIS_API_BASE_URL`, `NEXT_PUBLIC_AXIS_API_BASE_URL`.

Local option (supported): Serve the control API inside the deployment. The public web build embeds its API origin; changing only the container environment does not retarget that build.

Failure behavior: The console reports an unavailable or degraded API; a successful liveness probe alone is not readiness.

- browser, https, ports 443: Browser-reachable API origin; local development uses port 8000.

Evidence references: source `apps/web/lib/api-status.ts`; source `apps/web/lib/axis-api.ts`; documentation `docs/development.md`.

### distributed-rate-limit

Share rate-limit admission across API processes through a Redis-compatible service.

Owner: **Policy admission**. Components: api, valkey.

Phase: runtime. Requirement: **conditional**. Required for production; optional only where the existing configuration permits an in-memory development backend.

Configuration references: `AXIS_REDIS_URL`.

Local option (supported): Use local Redis or the packaged Valkey service. Production validation requires the Redis backend and closed failure mode.

Failure behavior: With the required production closed failure mode, unavailable admission storage rejects requests rather than falling back to an uncoordinated counter.

- outbound, redis, ports 6379: TLS and service port follow the selected Redis-compatible deployment.

Evidence references: source `infra/docker/docker-compose.yml`; source `services/api/src/axis_api/config.py`; source `services/api/src/axis_api/settings/policy.py`; test `services/api/tests/test_rate_limit.py`.

### dns

Resolve approved logical services inside the deployment.

Owner: **Deployment network**. Components: api, keycloak, minio, postgres, temporal, temporal-ui, typedb, valkey, web, worker.

Phase: runtime. Requirement: **required**.

Configuration references: none; platform or packaged dependency.

Local option (conditional): Provide local service discovery and review resolver forwarding. Network policy enforcement belongs to the later zero-egress slice.

Failure behavior: Name-based connections may fail or resolve incorrectly when service discovery is unavailable. Inventory checks never resolve names.

- host, dns, ports 53: Local resolver over UDP and TCP; external forwarding must be explicitly reviewed.

Evidence references: source `infra/docker/docker-compose.yml`; source `infra/helm/limes-axis/templates/networkpolicy.yaml`.

### external-database-source

Read the selected external PostgreSQL source through the existing lease and runtime egress boundary.

Owner: **Governed database connector**. Components: api, worker.

Phase: runtime. Requirement: **conditional**. Live discovery or extraction enabled with an approved source and execution context.

Configuration references: `AXIS_EXTERNAL_DB_LIVE_QUERY_DSN`, `AXIS_EXTERNAL_DB_LIVE_QUERY_ENDPOINT_TARGET_SHA256`, `AXIS_EXTERNAL_DB_LIVE_QUERY_PRIVATE_ENDPOINT_REF`.

Local option (conditional): Use an approved local read-only source and existing supported material resolver. An unsupported secret provider is not silently replaced.

Failure behavior: Denied or unavailable source access cannot be treated as successful ingestion. Checkpoint and retry authority remain in the ingestion host.

- outbound, postgresql, ports 5432: DSN identifies the source; endpoint reference and digest are evidence, not credentials or new targets.

Evidence references: source `services/api/src/axis_api/connector_source_extraction.py`; source `services/api/src/axis_api/settings/connectors.py`; test `services/api/tests/test_connector_source_extraction.py`.

### identity-browser-navigation

Record identity redirects separately from API-to-provider network calls.

Owner: **OIDC browser flow**. Components: api, keycloak, web.

Phase: runtime. Requirement: **conditional**. Browser authentication and provider logout paths are configured.

Configuration references: `AXIS_OIDC_AUTHORIZATION_URL`, `AXIS_OIDC_END_SESSION_URL`, `AXIS_OIDC_POST_LOGOUT_REDIRECT_URI`, `AXIS_OIDC_REDIRECT_URI`.

Local option (conditional): Use local provider, API callback and console logout origins; keep the existing exact callback and cookie controls.

Failure behavior: A remote or unavailable navigation target interrupts browser login/logout even when the API is locally hosted.

- browser, https, ports 443: Authorization, callback and logout navigation must all remain browser-reachable inside the boundary.

Evidence references: documentation `docs/development.md`; source `services/api/src/axis_api/oidc_code_flow.py`; source `services/api/src/axis_api/settings/identity.py`.

### identity-token-exchange

Exchange authorization codes and refresh tokens through the configured identity token endpoint.

Owner: **OIDC authorization-code and refresh flow**. Components: api, keycloak.

Phase: runtime. Requirement: **conditional**. Browser login or refresh flow is enabled.

Configuration references: `AXIS_OIDC_TOKEN_URL`.

Local option (conditional): Provide a local token endpoint. Moving only JWKS locally does not make login and refresh independent of the provider.

Failure behavior: Login or refresh fails when token exchange cannot complete. The inventory grants no cached-authentication bypass.

- outbound, https, ports 443: Back-channel token exchange; client credentials remain in existing secret handling.

Evidence references: source `services/api/src/axis_api/identity_session.py`; source `services/api/src/axis_api/oidc_code_flow.py`; test `services/api/tests/test_oidc_session_lifecycle.py`.

### identity-validation

Validate the configured issuer and obtain signing keys from the configured or derived JWKS endpoint.

Owner: **Identity and token validation**. Components: api, keycloak.

Phase: runtime. Requirement: **required**.

Configuration references: `AXIS_OIDC_ISSUER`, `AXIS_OIDC_JWKS_URL`.

Local option (conditional): Use a local supported OIDC provider and its local JWKS endpoint. Cached keys do not remove future key refresh dependencies.

Failure behavior: Unknown or unverifiable signing keys cannot establish identity. Key cache lifetime and provider failure behavior need runtime acceptance tests.

- outbound, https, ports 443: Issuer/JWKS service inside the deployment; the development Keycloak uses port 8080.

Evidence references: source `services/api/src/axis_api/identity.py`; source `services/api/src/axis_api/settings/identity.py`; test `services/api/tests/test_identity.py`.

### model-artifacts

Acquire compatible inference weights and provider dependencies before starting a local model service.

Owner: **Model deployment owner**. Components: api.

Phase: build, install, upgrade. Requirement: **conditional**. A local model provider is part of the selected capability profile.

Configuration references: none; platform or packaged dependency.

Local option (unsupported): Preload reviewed model artifacts in the inference deployment. Axis does not ship a verified universal model bundle.

Failure behavior: A provider missing required weights cannot serve inference; inventory alone cannot mark it ready.

- outbound, https, ports 443: Only build/install/upgrade acquisition; no runtime model download is authorized.

Evidence references: documentation `docs/architecture.md`; source `services/api/src/axis_api/model_providers.py`.

### model-inference

Execute model requests using the registered endpoint and configured allowlist, not arbitrary URLs from prompts.

Owner: **Governed model routing**. Components: api.

Phase: runtime. Requirement: **conditional**. Model routing execution is enabled and a compatible endpoint is registered.

Configuration references: `AXIS_MODEL_INVOCATION_ALLOWED_BASE_URLS`.

Local option (conditional): Serve a compatible model inside the boundary and preload weights before runtime. A local URL by itself is not provider conformance evidence.

Failure behavior: Disabled, denied, unsupported or unavailable providers cannot produce a verified model result. No automatic public-provider fallback is introduced.

- outbound, https, ports deployment-selected: Port is selected by the approved local model deployment. The allowlist is not the endpoint registry.

Evidence references: source `services/api/src/axis_api/model_endpoints.py`; source `services/api/src/axis_api/model_providers.py`; source `services/api/src/axis_api/settings/models.py`.

### ontology-store

Back separately enabled TypeDB ontology queries and mutations.

Owner: **Ontology ports**. Components: api, typedb.

Phase: runtime. Requirement: **conditional**. Enabled ontology query or mutation runtime; omit only with both capabilities disabled.

Configuration references: `AXIS_TYPEDB_ADDRESS`.

Local option (conditional): Use local TypeDB for live graph operations. The Postgres reference graph is a limited reference path, not feature parity.

Failure behavior: Live TypeDB-dependent operations cannot complete when unavailable. Disabling those features is an explicit capability omission.

- outbound, grpc, ports 1729: The packaged service also exposes a separate HTTP interface on container port 8000.

Evidence references: documentation `docs/architecture.md`; source `infra/docker/docker-compose.yml`; source `services/api/src/axis_api/settings/persistence.py`.

### operational-database

Persist tenant-owned operational state and audit evidence. The packaged Temporal service also uses PostgreSQL.

Owner: **Operational persistence**. Components: api, postgres, temporal, worker.

Phase: runtime. Requirement: **required**.

Configuration references: `AXIS_POSTGRES_DSN`.

Local option (supported): Use an operator-managed local PostgreSQL deployment. SQLite fixtures are not a production PostgreSQL substitute.

Failure behavior: Database-dependent requests, writes and workflow persistence cannot be assumed available. Backup and restore procedures remain separate evidence.

- outbound, postgresql, ports 5432: Control-plane database and separately configured Temporal database schemas.

Evidence references: source `infra/docker/docker-compose.yml`; source `services/api/src/axis_api/db.py`; source `services/api/src/axis_api/settings/persistence.py`.

### operator-diagnostics

Keep operator runbooks, status links and infrastructure consoles distinct from automatic support uploads.

Owner: **Operational support**. Components: api, keycloak, minio, temporal-ui, web.

Phase: runtime. Requirement: **optional**.

Configuration references: `AXIS_SUPPORT_CUSTOMER_RUNBOOK_URL`, `AXIS_SUPPORT_STATUS_PAGE_URL`.

Local option (supported): Publish local runbooks/status pages and restrict infrastructure consoles. No remote support upload is implied by a configured link.

Failure behavior: Unavailable links or consoles remove diagnostic visibility; they do not establish or revoke application authority.

- browser, https, ports 443, 8080, 8088, 9001: Operator navigation; development consoles use the listed non-production ports.

Evidence references: source `infra/docker/docker-compose.yml`; source `services/api/src/axis_api/settings/runtime.py`.

### pki

Supply certificate trust and renewal material for local TLS endpoints.

Owner: **Deployment trust material**. Components: api, keycloak, web, worker.

Phase: runtime. Requirement: **required**.

Configuration references: none; platform or packaged dependency.

Local option (conditional): Distribute a local CA trust bundle and offline or local renewal procedure. The shipped development Keycloak is not a production TLS profile.

Failure behavior: Missing or expired trust material can prevent TLS communication. Disabling certificate verification is not a local replacement.

- host, tls, ports 443: Any certificate issuance, renewal or revocation traffic is deployment-owned and must be reviewed separately.

Evidence references: documentation `docs/development.md`; source `infra/docker/docker-compose.yml`; source `infra/helm/limes-axis/templates/ingress.yaml`.

### s3-input

Read an approved input bucket through deployment-owned profiles and lease-scoped credentials.

Owner: **S3 source ingestion**. Components: api, worker.

Phase: runtime. Requirement: **conditional**. S3 source ingestion explicitly enabled with approved source profiles.

Configuration references: `AXIS_S3_SOURCE_PROFILES`, `model:S3SourceProfile.credential_secret_ref`, `model:S3SourceProfile.endpoint`, `model:S3SourceProfile.private_endpoint_ref`.

Local option (conditional): Use a local approved S3-compatible source. Only explicitly allowed loopback fixtures permit insecure HTTP; real profiles retain TLS.

Failure behavior: Unavailable or denied sources do not authorize checkpoint advancement. Lease, egress and ingestion dispatch gates remain authoritative.

- outbound, https, ports 443, 9000: Actual profile endpoint; private endpoint and credential fields are references, not extra dial permission.

Evidence references: source `services/api/src/axis_api/connector_s3_ingestion.py`; source `services/api/src/axis_api/s3_source_profile.py`; test `services/api/tests/test_connector_s3_source.py`.

### software-distribution

Acquire locked packages, container images and tooling before runtime.

Owner: **Release engineering**. Components: api, keycloak, minio, postgres, temporal, temporal-ui, typedb, valkey, web, worker.

Phase: build, install, upgrade. Requirement: **required**.

Configuration references: none; platform or packaged dependency.

Local option (conditional): Prepare and verify artifacts before disconnecting. Production of the complete offline bundle belongs to issue 474.

Failure behavior: A disconnected installation or upgrade fails if an artifact is missing; successful runtime inventory does not prove installability.

- outbound, oci, ports 443: Container registry or preloaded release artifacts, not normal application traffic.
- outbound, package-registry, ports 443: Package registry or reviewed mirror during build/install/upgrade.

Evidence references: documentation `docs/development.md`; source `infra/docker/docker-compose.yml`; source `services/api/pyproject.toml`.

### static-assets

Serve application assets and package-supplied Geist fonts from the built console.

Owner: **Governance console build**. Components: web.

Phase: runtime. Requirement: **required**.

Configuration references: none; platform or packaged dependency.

Local option (supported): Include static assets and font files in the web artifact. The inspected layout imports package fonts, not a remote font stylesheet.

Failure behavior: Missing build assets break rendering or typography. Layout inspection alone does not certify every browser request.

Evidence references: source `apps/web/app/layout.tsx`; documentation `docs/development.md`.

### telemetry-export

Export optional OTLP HTTP traces and metrics.

Owner: **Observability runtime**. Components: api, worker.

Phase: runtime. Requirement: **optional**.

Configuration references: `AXIS_OTEL_EXPORTER_OTLP_ENDPOINT`.

Local option (supported): Disable export or use an operator-provided local collector. The Compose collector block is commented, not an active packaged service.

Failure behavior: Telemetry delivery can be lost or delayed when the collector is unavailable; application availability is not proof that export succeeded.

- outbound, http, ports 4318: Collector endpoint inside the deployment; downstream collector exporters require their own local configuration.

Evidence references: source `infra/docker/docker-compose.yml`; source `services/api/src/axis_api/settings/observability.py`; source `services/api/src/axis_api/telemetry.py`; source `services/worker/src/axis_worker/telemetry.py`.

### workflow-engine

Execute workflows, register schedules and deliver governed workflow signals.

Owner: **Temporal adapter**. Components: api, temporal, temporal-ui, worker.

Phase: runtime. Requirement: **required**.

Configuration references: `AXIS_TEMPORAL_ADDRESS`.

Local option (supported): Run Temporal locally. The worker connects even when maintenance schedules are paused.

Failure behavior: The worker cannot poll or register schedules without Temporal. Signal/outbox behavior follows the existing adapter and retry ownership.

- outbound, grpc, ports 7233: API and worker connect through their existing Temporal ports.

Evidence references: source `infra/docker/docker-compose.yml`; source `services/api/src/axis_api/workflow_runtime.py`; source `services/worker/src/axis_worker/runtime.py`.

## Local-only planning profile

Logical local-only capability plan. This is not a runnable environment, validated configuration, offline bundle, or proof of network isolation.

| Dependency | State | Logical service | Reason |
| --- | --- | --- | --- |
| artifact-object-store | local | object-store | Provide the logical service inside the deployment and verify its declared limitations. |
| clock | local | local-time | Provide the logical service inside the deployment and verify its declared limitations. |
| console-origin | local | axis-web | Provide the logical service inside the deployment and verify its declared limitations. |
| control-api | local | axis-api | Provide the logical service inside the deployment and verify its declared limitations. |
| distributed-rate-limit | local | valkey | Provide the logical service inside the deployment and verify its declared limitations. |
| dns | local | local-dns | Provide the logical service inside the deployment and verify its declared limitations. |
| external-database-source | omitted | — | Leave external database discovery and live extraction disabled. |
| identity-browser-navigation | local | identity | Provide the logical service inside the deployment and verify its declared limitations. |
| identity-token-exchange | local | identity | Provide the logical service inside the deployment and verify its declared limitations. |
| identity-validation | local | identity | Provide the logical service inside the deployment and verify its declared limitations. |
| model-artifacts | omitted | — | Inference is omitted; this inventory does not supply or download weights. |
| model-inference | omitted | — | Leave model execution disabled until a compatible local provider is qualified. |
| ontology-store | omitted | — | Disable live TypeDB queries and mutations; the limited reference graph is not equivalent. |
| operational-database | local | postgres | Provide the logical service inside the deployment and verify its declared limitations. |
| operator-diagnostics | omitted | — | Do not configure operator links; supply local operating procedures separately. |
| pki | local | local-pki | Provide the logical service inside the deployment and verify its declared limitations. |
| s3-input | omitted | — | Leave the S3 source adapter disabled with no source profiles. |
| software-distribution | preloaded | — | Acquire and verify locked packages and images before disconnecting; bundle production remains separate. |
| static-assets | bundled | — | Serve packaged assets and fonts from the local web artifact. |
| telemetry-export | omitted | — | Leave telemetry export disabled; adding a collector requires reviewing its downstream destinations. |
| workflow-engine | local | temporal | Provide the logical service inside the deployment and verify its declared limitations. |

## Topology review baseline

Git blob digests bind the review baseline to packaging, not live traffic.

| Source | Git blob digest |
| --- | --- |
| `infra/docker/docker-compose.yml` | `066d34e76411c3f0dc0c9dc13249521b51dcc2bd` |
| `infra/helm/limes-axis/Chart.yaml` | `6450c0e7c5695c4f378083e892134b58effa4585` |
| `infra/helm/limes-axis/templates/_helpers.tpl` | `fd9afc2734bdefd3e9b67abde18309510e901688` |
| `infra/helm/limes-axis/templates/api-deployment.yaml` | `3385ce302e45d7fc3f3368b9a1bbf17cea4e9fe7` |
| `infra/helm/limes-axis/templates/api-service.yaml` | `70c5fb300f8b1489c51afb96e56c8cdb9dd9e0b3` |
| `infra/helm/limes-axis/templates/configmap.yaml` | `d5b470b74e26685090b1fb87acb5af9d3f80518c` |
| `infra/helm/limes-axis/templates/externalsecret.yaml` | `09c60ad1cbd9fcc0afdfcac4912d0bcd90cb5136` |
| `infra/helm/limes-axis/templates/hpa.yaml` | `3ffd02e33cbc0111d592d37075ddf117972dd4a2` |
| `infra/helm/limes-axis/templates/ingress.yaml` | `e032e6ad4103f39e3ca09ef42d19472159168953` |
| `infra/helm/limes-axis/templates/networkpolicy.yaml` | `4d338d938e998acbedae86cbca9b5db465952298` |
| `infra/helm/limes-axis/templates/poddisruptionbudget.yaml` | `a95f7a191beb2bc4f23295cda2f46b6ecd343ae9` |
| `infra/helm/limes-axis/templates/secret-example.yaml` | `3f7ef22a4797f4e7131d94f0102c9ef61c34d362` |
| `infra/helm/limes-axis/templates/serviceaccount.yaml` | `840c07358a3cb37e981fd04322329da1546eab4a` |
| `infra/helm/limes-axis/templates/tests/smoke-test.yaml` | `ee10754d59d3a63fe7364eaeb9210bf9f878abb2` |
| `infra/helm/limes-axis/templates/web-deployment.yaml` | `aa3a536df5be2557cf6fe5114ab91091c85a9056` |
| `infra/helm/limes-axis/templates/web-service.yaml` | `d39e38f066e8621189e4e8478ee6ae73d09c2f79` |
| `infra/helm/limes-axis/templates/worker-deployment.yaml` | `1fa78dff7fe2176d2485ed77d22dda4c828a386f` |
