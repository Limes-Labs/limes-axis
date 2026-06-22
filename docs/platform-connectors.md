# Platform Connector Foundation

The connector foundation introduces a public-safe contract for bringing
external data sources into Axis without enabling live production mutation.

This slice defines connector manifests, runtime policy boundaries, schema
mapping metadata and a first preview-only file/CSV connector for the
manufacturing reference demo. It also adds the first tenant-scoped connector
configuration records, while keeping connector runs and live sync disabled.

## Current Scope

```text
GET /demo/manufacturing/connectors
GET /demo/manufacturing/connectors/configurations
POST /demo/manufacturing/connectors/configurations
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
`configured_preview_only`; scheduled sync, connector run records and audit
writes from connector runs remain future Platform work.

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
`/demo/manufacturing/connectors/configurations`. If the API is unavailable, it
uses the same public-safe fallback seed so the page remains useful in
frontend-only development.

The console displays:

- connector manifest and runtime boundary;
- preview-only sync posture;
- required permissions;
- blocked operations;
- tenant-scoped preview configuration;
- public-safe configuration payload fields;
- schema mapping;
- redacted ontology proposals and audit event preview.

The page is read-only for operators. It does not upload files to storage,
persist connector runs, capture credentials or trigger live sync.

## Governance Boundary

Connectors are designed as extractable from day one. The current manifest
contract keeps these boundaries visible:

- connector runtime sandbox;
- typed permission requirements;
- credential handles instead of raw credential values;
- no external egress by default;
- redacted preview payloads;
- audit event preview before future audit writes;
- tenant-scoped configuration before future connector run records;
- ontology proposal generation before future graph mutation.

Future Platform work should add:

- persisted connector manifest management beyond the demo seed;
- credential handle storage and rotation;
- connector run records and append-only audit writes;
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
- API unit tests for required-column and unsupported-connector guardrails;
- API endpoint and OpenAPI exposure tests;
- web unit tests for fallback registry, configuration and preview contracts;
- Playwright smoke tests for `/connectors` rendering.
