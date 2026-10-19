# REST source profile contract

This is the offline contract slice of [#336](https://github.com/Limes-Labs/limes-axis/issues/336),
implemented for [#859](https://github.com/Limes-Labs/limes-axis/issues/859).
It does not register a connector, open a connection or enable ingestion.

[`connector_rest_profiles.py`](../services/api/src/axis_api/connector_rest_profiles.py)
uses the existing [connector authoring protocol](connector-authoring.md).
Profile version `1.0` is distinct from SDK protocol `1.0`; the latter is unchanged.
The existing [capability matrix](connector-capabilities.md) remains authoritative
for executable source support.

## Profile and selection

A profile declares an opaque registered endpoint-profile ID **and its exact
revision digest**, collection ID, GET path template, typed query declarations,
record-member path, declared schema fingerprint, pagination mode and hard limits.
It contains neither a URL to dial nor credentials, headers or executable selectors.
The host must look up that endpoint reference and revalidate its current revision,
lease, policy and resource binding before any future I/O.

Path templates contain literal segments or whole named segments such as
`/v1/accounts/{account}/orders`. Supplied path values are bounded literal segments;
slashes, percent encoding, dot traversal and URL/query fragments are unsupported.
Query values support exact string, signed 64-bit integer and boolean types. No
implicit coercion is performed; undeclared names and caller-supplied pagination
parameters are rejected. Record and continuation selectors are finite member-name
tuples such as `("data", "orders")`, not JSONPath or code.

Supported pagination declarations are `opaque_cursor` and `next_link`. Next links
are restricted to the same registered endpoint; the transport must validate the
actual destination before using them, and the bounded reader below enforces
this. A declaration alone is not enforcement.
Only `mutable_traversal` consistency is supported. A schema fingerprint or a
recorded source revision does not imply snapshot isolation or CDC. The declared
fingerprint must resolve to the host's approved schema before records are accepted.

## Checkpoints and evidence

`profile.checkpoint(context, resource, SecretStr(token), path_values=..., query_values=...)`
returns the existing SDK `Checkpoint`. The host still owns persistence and commits
progress only after durable batch acceptance. Its protected cursor envelope binds
the full profile digest and selected path/query values in addition to the SDK's
tenant, connector, protocol, collection, schema and source-revision bindings.
Changing the endpoint revision, filters, profile or selection therefore invalidates
resume, while a new operation ID can resume committed progress under fresh authority.

`profile.resume_cursor(request, path_values=..., query_values=...)` validates those
bindings before returning a `SecretStr`, or `None` for an initial request. Tokens
are opaque; invalid/expired provider tokens require explicit recovery by the host.
Neither hashes nor checkpoint possession constitute an authorization grant.

Only `Checkpoint.storage_record()` deliberately exposes the envelope for the
existing protected checkpoint store. Ordinary repr/JSON masks it. Use
`ReadBatch.evidence()` for metadata-only evidence, never serialize a batch into
audit. SDK `more`, `complete` and `truncated` semantics remain unchanged.

Use `parse_rest_source_profile()` at an untrusted configuration boundary. It maps
validation failures to a fixed error code, including unknown field names. Do not
return or log raw Pydantic `.errors()`, chained exception context, profile query
values or storage records. `hide_input_in_errors` alone does not sanitize those
structured errors. Treat validation errors from direct model construction as
internal only.

Limits are declarations for the reader/host: SDK row/record-byte and elapsed
budgets, page-count, wire-byte and decoded-body bounds. The bounded reader
enforces them per page; the host must additionally bound total work across a
traversal and its retries. This module does not run timers, count network bytes
or enforce job admission.

## Bounded transport (implemented for #860)

[`connector_rest_reader.py`](../services/api/src/axis_api/connector_rest_reader.py)
implements one governed page read per `RestPageSource.read()` call. Trust and
durability stay with existing owners: the host constructs the source from a
fail-closed lease/policy evidence pair (`RestSourceAuthority`) plus
already-resolved lease-scoped bearer material; the module performs no lease,
secret-resolution or policy lookups and adds no secret store.

The egress policy is enforced on the actual connection: the transport is pinned
to the approved origin, redirects are never followed, and pagination
continuations must resolve to the same origin before any request. A 3xx is a
fixed safe failure. GET-only transport applies explicit connect/read timeouts
and hard wire/decoded-byte caps, streaming the body under a shared deadline so
a slow or endless source cannot exceed the configured bounds. A page that
exceeds its declared record/byte bounds is an honest `truncated` result without
a checkpoint, never a silently skipping `more`.

Failure codes stay on the protocol 1.0 SDK surface: a 401 maps to
`SOURCE_UNAVAILABLE` (as in the SDK credential fixture) with `auth_failure`
evidence marking the lease terminal for reauthorization; 429 and eligible 5xx
report a bounded `Retry-After` hint without ever sleeping or retrying inside
the adapter. Provider payloads appear only as raw records in the returned
`ReadBatch`; progress evidence is fixed metadata with no authorization headers,
tokens, cursors or row values.

The transport performs no live authorization by itself and records no audit
events: constructing evidence, resolving material, committing checkpoints and
admitting page counts across a traversal remain host responsibilities.
[#861](https://github.com/Limes-Labs/limes-axis/issues/861) owns fenced durable
host adoption; [#862](https://github.com/Limes-Labs/limes-axis/issues/862) owns
end-to-end conformance. OAuth, external writes, source discovery execution,
schedules and UI remain outside this contract.

## Verification

From a complete locked checkout, run:

```sh
make test-api PYTEST_ARGS='tests/test_connector_rest_profiles.py tests/test_connector_rest_reader.py -q'
make docs-check
```

The profile tests exercise both pagination modes, strict validation,
revision/filter binding, safe errors and cursor storage round-trips without any
I/O. The reader tests drive the transport against a local HTTP fixture server:
bounded pages and candidate checkpoints, zero transport calls on gate failures,
redirect/continuation containment, compressed/oversized/endless payloads, MIME
and JSON-shape failures, fixed status codes with bounded retry hints, honest
truncation and secret-leak assertions. They require no provider, database or
network access beyond loopback.
