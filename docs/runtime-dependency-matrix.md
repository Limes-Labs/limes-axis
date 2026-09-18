# Runtime dependency matrix

Release: 1.14.0 · manifest axis.runtime-dependency-manifest v1.0

Generated from `axis_api/runtime_dependency_manifest.py`; edit the
curated inventory there, never this file. Static inventory only —
not runtime isolation evidence and not a deployment accreditation.

| Entry | Component | Owner | Purpose | Configuration key | Phase | Status | Direction | Protocol/Port | Local replacement | Failure behavior |
|---|---|---|---|---|---|---|---|---|---|---|
| api-external-db-live-query | api | data | Connector live query against an approved external database | `AXIS_EXTERNAL_DB_LIVE_QUERY_DSN` | normal_runtime | conditional | outbound | postgresql/tcp/5432 | customer-provided database reachable over the approved network path | Live query stays disabled; no implicit fallback. |
| api-postgres | api | operational-model | Primary relational store | `AXIS_POSTGRES_DSN` | normal_runtime | required | outbound | postgresql/tcp/5432 | postgres primary service (compose/helm profile) | Startup blocked; readiness reports the store not ready. |
| api-redis | api | trust | Distributed rate limiting backend | `AXIS_REDIS_URL` | normal_runtime | conditional | outbound | redis/tcp/6379 | redis local service | Production requires redis (fail-closed); development falls back. |
| api-temporal | api | workflow | Workflow engine connectivity | `AXIS_TEMPORAL_ADDRESS` | normal_runtime | conditional | outbound | grpc/tcp/7233 | Temporal local service | Workflow signals unavailable; governed domain flows degrade per feature flags. |
| api-typedb | api | operational-model | Ontology graph store | `AXIS_TYPEDB_ADDRESS` | normal_runtime | required | outbound | typedb/tcp/1729 | TypeDB local service | Ontology queries fail; readiness reports the store not ready. |
| build-language-packages | api | deployment | Language package registries at image build time | `none (build tooling)` | build_install_upgrade | required | outbound | https/443 | — | Build fails; runtime of already-built images unaffected. |
| diagnostics-runbook | diagnostics | trust | Operator-facing runbook link | `AXIS_SUPPORT_CUSTOMER_RUNBOOK_URL` | normal_runtime | optional | outbound (browser-side) | https/443 | — | Link unreachable; no functional impact on the platform. |
| diagnostics-status-page | diagnostics | trust | Operator-facing status page link | `AXIS_SUPPORT_STATUS_PAGE_URL` | normal_runtime | optional | outbound (browser-side) | https/443 | — | Link unreachable; no functional impact on the platform. |
| identity-authorization-endpoint | identity | trust | Browser authorization redirect | `AXIS_OIDC_AUTHORIZATION_URL` | normal_runtime | conditional | outbound | https/443 | self-hosted OIDC provider | Login cannot start; API reachable for already-authenticated sessions. |
| identity-end-session | identity | trust | Logout (end-session) redirect | `AXIS_OIDC_END_SESSION_URL` | normal_runtime | optional | outbound | https/443 | self-hosted OIDC provider | Logout stays local-only; provider-side termination skipped. |
| identity-issuer | identity | trust | OIDC issuer discovery fallback | `AXIS_OIDC_ISSUER` | normal_runtime | conditional | outbound | https/443 | self-hosted OIDC provider | Discovery fallback unavailable; explicit endpoint configuration still works. |
| identity-jwks | identity | trust | OIDC token signature validation (JWKS) | `AXIS_OIDC_JWKS_URL` | normal_runtime | conditional | outbound | https/443 | self-hosted OIDC provider with API-side JWKS caching | Token validation fails closed when keys cannot be refreshed. |
| identity-token-endpoint | identity | trust | OIDC code exchange | `AXIS_OIDC_TOKEN_URL` | normal_runtime | conditional | outbound | https/443 | self-hosted OIDC provider | Login cannot complete new sessions; existing sessions unaffected until expiry. |
| model-inference-routing | model_inference | intelligence | Model routing to allowlisted inference base URLs | `AXIS_MODEL_INVOCATION_ALLOWED_BASE_URLS` | normal_runtime | optional | outbound | https/— | self-hosted inference endpoint inside the allowlist | Model features stay disabled; no implicit fallback route. |
| network-dns | network_baseline | deployment | Name resolution for every outbound dependency | `none (resolver configuration)` | normal_runtime | required | outbound | dns udp/tcp/53 | — | Name resolution failure blocks hostname-based dependencies; IP-pinned local services keep working. |
| network-ntp | network_baseline | deployment | Clock discipline for token and lease validity | `none (host time sync)` | normal_runtime | required | outbound | ntp/udp/123 | — | Clock skew invalidates tokens and fenced leases; local RTC bounds drift. |
| network-pki | network_baseline | deployment | TLS trust anchors for outbound https | `none (host trust store)` | normal_runtime | required | outbound | x509/https/— | — | Untrusted chain fails closed; no bypass. |
| object-storage-export | object_storage | data | Canonical object store for connector export envelopes | `AXIS_CONNECTOR_EXPORT_S3_ENDPOINT` | normal_runtime | conditional | outbound | http/https/9000 | S3-compatible local object store (e.g. MinIO fixture) | Connector export disabled; readiness reports the store not ready when required. |
| static-assets-fonts | static_assets | experience | Browser font and static asset delivery | `none (self-hosted build output)` | normal_runtime | optional | inbound (browser) | https/— | self-hosted assets served by the web deployment | Self-hosted via the build output; a remote font CDN is an unsupported state, not a hidden dependency. |
| telemetry-otlp | telemetry | deployment | OTLP telemetry export | `AXIS_OTEL_EXPORTER_OTLP_ENDPOINT` | normal_runtime | optional | outbound | otlp/grpc+http/4317 | self-hosted collector | Telemetry dropped locally; service unaffected. |
| build-container-base-images | web | deployment | Container base image retrieval at build time | `none (build tooling)` | build_install_upgrade | required | outbound | https/443 | — | Build fails; runtime of already-built images unaffected. |
| web-api-base-url | web | experience | Browser calls from the web console to the API | `AXIS_API_BASE_URL` | normal_runtime | required | inbound (to api) | http/https/— | — | Console cannot reach the API; API itself unaffected. |
| web-public-base-url | web | experience | Advertised public URL of the web console | `AXIS_PUBLIC_BASE_URL` | normal_runtime | required | inbound (advertised) | http/https/— | — | Redirects and absolute links break until reconfigured. |
| worker-temporal | worker | workflow | Worker dispatch connectivity to the workflow engine | `AXIS_TEMPORAL_ADDRESS` | normal_runtime | required | outbound | grpc/tcp/7233 | Temporal local service | Worker cannot claim activities; queued work waits, no data loss. |

## Endpoint settings accounted for

- `AXIS_API_BASE_URL`
- `AXIS_CONNECTOR_EXPORT_S3_ENDPOINT`
- `AXIS_EXTERNAL_DB_LIVE_QUERY_DSN`
- `AXIS_EXTERNAL_DB_LIVE_QUERY_ENDPOINT_TARGET_SHA256`
- `AXIS_EXTERNAL_DB_LIVE_QUERY_PRIVATE_ENDPOINT_REF`
- `AXIS_MODEL_INVOCATION_ALLOWED_BASE_URLS`
- `AXIS_OIDC_AUTHORIZATION_URL`
- `AXIS_OIDC_END_SESSION_URL`
- `AXIS_OIDC_ISSUER`
- `AXIS_OIDC_JWKS_URL`
- `AXIS_OIDC_SESSION_COOKIE_HOST_PREFIX`
- `AXIS_OIDC_TOKEN_URL`
- `AXIS_OTEL_EXPORTER_OTLP_ENDPOINT`
- `AXIS_POSTGRES_DSN`
- `AXIS_PUBLIC_BASE_URL`
- `AXIS_REDIS_URL`
- `AXIS_SUPPORT_CUSTOMER_RUNBOOK_URL`
- `AXIS_SUPPORT_STATUS_PAGE_URL`
- `AXIS_TEMPORAL_ADDRESS`
- `AXIS_TYPEDB_ADDRESS`

## Reviewed non-endpoint keys

- `AXIS_EXTERNAL_DB_LIVE_QUERY_ENDPOINT_TARGET_SHA256`
- `AXIS_EXTERNAL_DB_LIVE_QUERY_PRIVATE_ENDPOINT_REF`
- `AXIS_OIDC_SESSION_COOKIE_HOST_PREFIX`

## Local-only sample profile (`local-only-sample`)

Optional external features are omitted with explicit reasons; everything
else is unchanged. Omissions are per-component and reasoned — there is no
boolean "sovereign" flag.

| Component | Reason |
|---|---|
| model_inference | sample profile runs without external model routing; the feature stays disabled |
| telemetry | sample profile exports no telemetry; a local collector may be attached without code changes |
| diagnostics | sample profile carries no external status-page/runbook links |

Build/install/upgrade dependencies are listed in the matrix with their
own phase; offline bundle production stays #474. Inventory evidence lives
in `services/api/tests/test_runtime_dependency_manifest.py`; configuration
validation is `validate_runtime_dependency_manifest`; no live network
rehearsal has been performed — that is #870 and will be recorded
separately when it exists.
