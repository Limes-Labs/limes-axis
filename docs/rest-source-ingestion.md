# REST collection ingestion through the existing outbox

[#861](https://github.com/Limes-Labs/limes-axis/issues/861) (parent #336) adopts
the [REST source profile](rest-source-profiles.md) and its
[bounded page reader](../services/api/src/axis_api/connector_rest_reader.py)
into the **existing** source-ingestion owners:

- [`connector_rest_ingestion.py`](../services/api/src/axis_api/connector_rest_ingestion.py)
  maps one declared collection to one fenced outbox attempt.
- [`rest_source_profile.py`](../services/api/src/axis_api/rest_source_profile.py)
  is the deployment-owned binding: origin, lease-scoped credential reference,
  typed path/query values, declared protocol range and the capability set.
- [`connector_source_ingestion.py`](../services/api/src/axis_api/connector_source_ingestion.py)
  keeps sole ownership of claims, retries, attempt history, dead letters and the
  terminal transition.

There is no second outbox, scheduler, checkpoint database, secret store or
CDC/change-feed claim. Nothing here writes to the provider.

## Enablement

Default-off at two levels:

| Setting | Default | Effect |
| --- | --- | --- |
| `AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED` | `false` | Shared live-source execution gate |
| `AXIS_SOURCE_INGESTION_DISPATCH_ENABLED` | `false` | Outbox dispatch |
| `AXIS_SOURCE_INGESTION_EXTRACTION_ENABLED` | `false` | Real extraction stage |
| `AXIS_REST_SOURCE_INGESTION_ENABLED` | `false` | This adapter |
| `AXIS_REST_SOURCE_PROFILES` | `[]` | Declared tenant-scoped bindings |

A REST request submitted while the gate is off never dials: the runtime refuses
the profile lookup and the request dead-letters with
`unsupported_capability`. CSV, Postgres and S3 routing is unchanged because the
dispatcher only adds one branch; the existing suites remain green.

## What one attempt does

1. **Prepare under SQL** (`prepare_selection`): re-read the active binding
   (optionally `FOR UPDATE`), the profile, the tenant-scoped declared
   observation, the credential lease and the egress policy; validate the schema
   fingerprint, lease expiry/status, approved-private-endpoint mode, endpoint
   target digest and the current live manifest. The credential is resolved only
   through the existing lease-scoped resolver.
2. **Negotiate the protocol** before any client or transport is constructed.
3. **Read one page without a transaction.** The #860 reader enforces origin
   pinning, no-follow redirects, same-origin continuations and bounded
   wire/decoded/deadline limits. `ReadBatch` is validated against the request
   before acceptance.
4. **Store the bounded envelope** in the canonical object store under a
   deterministic key derived from `(tenant, connector, request, binding,
   generation)`. Object storage and SQL are not one transaction.
5. **Commit atomically inside the outbox transaction**: the claim-fenced
   terminal transition, the batch metadata row, its audit event and the
   compare-and-swap checkpoint advance. A stale claim or a changed binding
   revision commits nothing.

A page that the reader reports as `truncated` dropped unread source records; it
is a terminal failure and never advances the cursor. A candidate continuation
that repeats any cursor already seen in the current traversal is a terminal
protocol error (`no_progress`). The traversal ceiling (`limits.max_pages`)
terminates the traversal honestly instead of looping.

## Recovery semantics

| Interruption | Result on replay |
| --- | --- |
| Before upload | Nothing committed; the retry reads again |
| After upload, before SQL commit | Orphan object at a deterministic key; the retry overwrites it, then commits |
| After commit, before acknowledgement | The request is already `completed`; a new claim is required and the page is not re-read |
| Expired/foreign cursor | Terminal `invalid_checkpoint`, never a silent restart at page one |
| Repeated cursor | Terminal `no_progress` |
| 429 / eligible transient | Durable retry state with a bounded `Retry-After` floor; the worker schedules, it never sleeps |
| Exhausted attempts | Existing dead-letter evidence |

A dead-lettered request may leave an orphan payload object. Operators reconcile
by listing the tenant-scoped key prefix against recorded batches. This is
documented behaviour, not atomicity.

## Evidence and containment

Progress evidence is fixed metadata: resolver/lease/policy identifiers, page
counts, wire/decoded bytes, completion and traversal state. Provider payloads
appear only as raw rows inside the object-store envelope; audit payloads, batch
rows and retry errors carry counts, digests and public-safe codes only. The
bearer token never reaches SQL, audit or logs, and cross-tenant binding or
cursor substitution is rejected before any request is dialed.

## Verification and honest boundaries

`make test-api PYTEST_ARGS='tests/test_connector_rest_ingestion.py -q'` covers
the six acceptance groups of #861 with the real outbox, the real #860 reader and
an injected transport.

- **Ran here**: SQLite owners, scripted HTTP responses, fenced-claim and
  compare-and-swap races within one process, deterministic-key replay, retry
  scheduling, containment assertions over the persisted database bytes.
- **NOT RUN here**: a live provider (no credentials, contract or fixture
  exists), real PostgreSQL row-lock concurrency for two processes, and a real
  object store. Those need deployment evidence; they are not claimed by these
  tests.
- End-to-end REST conformance against a real provider belongs to
  [#862](https://github.com/Limes-Labs/limes-axis/issues/862). OAuth flows,
  REST writeback, scheduling and UI stay outside this slice.
