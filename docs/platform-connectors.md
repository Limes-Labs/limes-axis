# Platform Connector Foundation

The connector foundation introduces a public-safe contract for bringing
external data sources into Axis without enabling live production mutation.

This slice defines connector manifests, runtime policy boundaries, schema
mapping metadata and a first preview-only file/CSV connector for the
manufacturing reference demo. It also adds the first tenant-scoped connector
configuration records and metadata-only connector run records, while keeping
connector execution and live sync disabled.
It also introduces metadata-only credential handles and rotation history for
future connector execution, without storing raw credential material in Axis.

## Current Scope

```text
GET /demo/manufacturing/connectors
GET /demo/manufacturing/connectors/configurations
POST /demo/manufacturing/connectors/configurations
GET /demo/manufacturing/connectors/credential-handles
POST /demo/manufacturing/connectors/credential-handles
POST /demo/manufacturing/connectors/credential-handles/{handle_id}/rotations
GET /demo/manufacturing/connectors/runs
POST /demo/manufacturing/connectors/runs
POST /demo/manufacturing/connectors/file-csv/preview
```

The registry endpoint returns:

- connector id, type, version and display name;
- supported sync modes;
- runtime sandbox boundary;
- required permissions;
- credential storage posture;
- schema fields and ontology mapping targets;
- allowed and blocked runtime operations;
- preview sample metadata.

The CSV preview endpoint accepts a demo CSV payload and returns:

- validation status;
- accepted and rejected record counts;
- ontology entity proposals;
- redacted audit event preview;
- public-safe preview notes.

The endpoint does not persist raw file content, store credentials, call external
systems or write ontology graph records.

The configuration endpoints store and query tenant-scoped preview connector
configuration records. A configuration includes:

- tenant id;
- connector id;
- display name;
- preview sync mode;
- runtime boundary;
- creator role/system id;
- public-safe configuration payload;
- credential reference ids;
- configuration notes.

Configuration payloads reject raw credential fields such as passwords, API keys
and credential values. The current configuration status is
`configured_preview_only`; scheduled sync and connector execution remain future
Platform work.

The credential handle endpoints store and query tenant-scoped metadata for
external secret references. A handle includes:

- tenant id;
- connector id;
- handle id;
- display name;
- external secret provider;
- external secret reference;
- purpose;
- rotation interval;
- last and next rotation timestamps;
- labels and notes;
- latest rotation evidence.

The create endpoint accepts references such as `vault://...`,
`external-secret://...`, `kms://...` or environment-backed development refs. It
rejects inline values that do not look like external references. Rotation
records update handle metadata and append rotation history. Axis does not
retrieve, store or return raw credential values.

The connector run endpoints store and query tenant-scoped run evidence. A run
record includes:

- tenant id;
- connector id;
- run id;
- preview/manual-import-record execution mode;
- runtime boundary;
- requester role/system id;
- credential handle ids;
- redacted input and result summaries;
- linked audit event id and type;
- run notes.

Creating a run record writes an append-only `connector.run.recorded` audit event
with the same redacted metadata. The endpoint rejects raw payload fields such as
`csv_content`, raw file content, passwords, API keys, tokens and secret refs.
Run records do not execute connector sync, call external systems or mutate the
ontology graph.

## Manufacturing CSV Manifest

The first connector is `file_csv_manufacturing_assets`.

It maps these source columns to manufacturing asset proposals:

- `asset_id`;
- `asset_name`;
- `domain`;
- `station`;
- `risk_level`.

Required columns are validated before proposals are generated. Unsupported
connector ids are blocked. The response includes ontology proposals only; the
raw `csv_content` field is not returned.

## Console Behavior

The `/connectors` page loads the connector registry and preview result from the
API when available. It also loads tenant-scoped connector configurations from
`/demo/manufacturing/connectors/configurations` and metadata-only credential
handles from `/demo/manufacturing/connectors/credential-handles`, plus run
records from `/demo/manufacturing/connectors/runs`. If the API is unavailable,
it uses the same public-safe fallback seed so the page remains useful in
frontend-only development.

The console displays:

- connector manifest and runtime boundary;
- preview-only sync posture;
- required permissions;
- blocked operations;
- tenant-scoped preview configuration;
- credential handle references and rotation posture;
- audit-backed connector run records;
- public-safe configuration payload fields;
- schema mapping;
- redacted ontology proposals and audit event preview.

The page is read-only for operators. It does not upload files to storage,
execute connector runs, capture credentials or trigger live sync.

## Governance Boundary

Connectors are designed as extractable from day one. The current manifest
contract keeps these boundaries visible:

- connector runtime sandbox;
- typed permission requirements;
- credential handles instead of raw credential values;
- rotation metadata before production vault integration;
- no external egress by default;
- redacted preview payloads;
- audit event preview before future connector execution;
- tenant-scoped run records before future connector execution;
- ontology proposal generation before future graph mutation.

Future Platform work should add:

- persisted connector manifest management beyond the demo seed;
- production vault/KMS integration and secret lease automation;
- scheduled sync lifecycle;
- Postgres or external database demo connector;
- connector-backed action invocation behind policy and approval gates.

Future extraction to `limes-axis-connectors` becomes mandatory when the
connector surface gains independent release cadence, customer-specific
integrations, separate ownership or substantial runtime/deployment concerns.

## Verification

The slice is covered by:

- API unit tests for manifest shape, public-safety checks and CSV mapping;
- API unit tests for tenant-scoped connector configuration persistence and raw
  credential field rejection;
- API unit tests for credential handle metadata, secret reference guardrails
  and rotation history;
- API unit tests for connector run records, audit writes and raw payload
  rejection;
- API unit tests for required-column and unsupported-connector guardrails;
- API endpoint and OpenAPI exposure tests;
- web unit tests for fallback registry, configuration, credential handle, run
  record and preview contracts;
- Playwright smoke tests for `/connectors` rendering.
