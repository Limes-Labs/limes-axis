# Dependency inventory: scope and verification

The [generated inventory](runtime-dependencies.md) supports issue #869, the first
inventory slice of the zero-egress workstream. It separates configuration and
packaging evidence from deployment enforcement and live network evidence.
The [decision record](adr/runtime-dependency-inventory.md) explains the boundary.

## One source of configuration truth

`axis_api.config.Settings` and its capability models remain the configuration
owners. The worker reuses that facade. The manifest references setting names;
it does not redefine their types, defaults, environment loading or validation.
It is not imported by the API, worker, SDK or web application.

The offline checker reads Python syntax trees, not imported application models.
It does not read `.env`, resolve a hostname, connect to a database, obtain a
credential, start a service or evaluate a template. JSON Schema validation uses
only the bundled schema and local references. No new runtime dependency is
introduced. The checker uses the API's existing `jsonschema` development dependency.

## What is inventoried

The manifest identifies ten packaged components and 21 logical dependencies.
It distinguishes actual outbound connections, browser navigation, host-managed
services, optional features and build/install/upgrade artifact retrieval.
Configuration references include endpoint-related policy metadata: a cookie host
prefix, cookie-name constant, endpoint digest, private endpoint reference or allowlist
is not itself an additional network connection. `AXIS_CSRF_HOST_COOKIE_NAME` names
the API-issued readable CSRF cookie in the console; it is not an environment setting.
The conservative web scanner includes this source constant because its name contains
`HOST`, so it is explicitly classified under the browser session boundary.

An entry records its owner, purpose, requirement and condition, phases,
protocol/port/direction, logical local replacement, failure behavior and evidence
references. Ports are deployment hints, not firewall rules. A test file reference
means that related evidence exists there, not that the checker runs that test.

The local-only sample is deliberately a logical capability plan, not a deployable
Helm profile. It contains service identifiers and explicit omission reasons,
not endpoint values or secrets. Every dependency must have exactly one disposition.
A required service cannot disappear through an omission; a network service cannot
be reclassified as a bundled asset. A preloaded artifact is not a running service.

The sample keeps identity, PostgreSQL, rate limiting, workflow execution and
artifact storage local. Live TypeDB operations, source connectors, model inference,
telemetry export and optional operator links are explicitly omitted. These
omissions describe a proposed profile; this file does not change any runtime flag.

## Detection boundaries

The checker detects:

- Endpoint-shaped `Field` aliases, annotated fields and URI-bearing field values
  in the capability settings directory and the flat facade; explicit nested
  endpoint/reference fields in `S3SourceProfile`.
- Literal endpoint-related environment keys in API/worker Python sources, plus
   conservative endpoint-shaped Axis identifiers in the web app, lib, components
   and providers directories, including source constants that resemble environment
   keys. Test-only web files are excluded.
- New, removed or changed primary Compose and Helm topology sources. This gate
  compares Git blob digests; it does not parse YAML or render Go templates.
- Duplicate owners, stale classifications, incomplete profiles, missing source
  roots or evidence files, invalid JSON/schema and a stale generated matrix.

The topology baseline covers `infra/docker/docker-compose*.yml` and `.yaml`,
Helm `Chart.yaml`, and Helm templates ending in `.yaml`, `.yml` or `.tpl`.
The baseline digests identify retrieved source objects. They are not signatures,
proof of semantic review of every template or evidence of a running cluster.

This deliberately does not establish completeness for dynamically constructed
keys, arbitrary nested configuration types, code-generated targets, dependency
internals, third-party environment variables consumed outside Axis source,
provider-managed endpoints, every Next configuration entry point, Helm values
or customer overrides. New configuration mechanisms must extend the discovery
contract and tests, not be marked covered by a guessed default.

Nor does this prove that DNS forwarding, time services, PKI renewal, telemetry
collector exporters, model downloads, identity federation or operator browsers
stay local. Their deployment configuration and traffic require separate review.
The commented collector in the development Compose file is not an active service.
Development Keycloak and plaintext development ports are not production TLS guidance.

## Run in the complete checkout

Use the repository's locked development environment:

```sh
make install
cd services/api
uv run python ../../scripts/check_runtime_dependencies.py
uv run pytest tests/test_runtime_dependencies.py -q
cd ../..
make docs-check
```

The full-checkout test is part of the normal API test suite. No extra CI job,
workflow permission or runtime endpoint is introduced. The checker is covered by
`make lint` and the existing CI Python job's Ruff step, using the explicit API
configuration. It is not added to the pre-install `docs-check` step: `jsonschema`
must be available first.

Regenerate the human-readable matrix only after classification and source checks
pass:

```sh
cd services/api
uv run python ../../scripts/check_runtime_dependencies.py --write
```

`--write` changes only the matrix. It cannot bless a topology change by refreshing
its hash. For a topology failure, inspect the changed packaging, update component
and dependency entries where needed, then record the new Git blob digest after
review. Digest refresh is an explicit source edit. Even a formatting-only change
requires review of that diff; this conservative gate trades some reviewer effort
for not maintaining a fragile partial YAML/Helm parser.

`unclassified_endpoint_setting` means a detected reference has no dependency
owner. `stale_endpoint_classification` means a manifest key is no longer detected;
check removals and discovery changes before deleting it. Missing files or source
roots are failures, not permission to treat an incomplete checkout as a pass.

Before merging the candidate, run the complete-checkout gate and repository
verification, reconcile every discovered setting, review packaging references,
and check CI on the actual PR head. Synthetic checker fixtures cannot substitute
for this step.

## Evidence levels

**Inventory:** JSON/schema consistency, source references, declaration discovery,
topology-baseline drift checks and generated-document parity.

**Configuration validation:** the existing Settings validators and deployment
render checks applied to the selected real deployment. This checker does not
perform that validation or create a second settings facade.

**Live isolation and failure rehearsal:** traffic observation, identity refresh,
provider/collector behavior, unavailable dependencies and network policy tests.
These belong to subsequent work. Offline bundle production remains issue #474.
No result from this checker should be described as air-gap accreditation.
