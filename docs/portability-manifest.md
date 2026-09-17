# Tenant portability manifest contract

[#876](https://github.com/Limes-Labs/limes-axis/issues/876) defines the
restore-capable profile of the canonical #324 tenant export manifest:
[`portability_manifest.py`](../services/api/src/axis_api/portability_manifest.py)
is a pure contract module — no producer, no restore writes, no credential
resolution, no I/O. It extends the #324 canonical export format rather than
introducing a second portability archive.

## What the manifest declares

`PortabilityManifest` is a versioned envelope (`axis.tenant-portability-manifest`,
schema version 1.0) binding:

* the tenant logical identity and the source Axis version;
* a `ConsistencyPoint` that discloses either a quiesced export or a captured
  watermark. Independent per-store timestamps are never treated as one
  transactionally consistent snapshot; watermark-based exports carry an
  explicit acknowledgement in every review;
* one `ComponentInventory` per authoritative store (relational, object
  artifacts, ontology, audit ledger): owner layer, consistency rule, schema
  version, object count and content digest, dependency order, and an explicit
  restore decision — `restore`, `rebuild` (only for declared
  `rebuildable_projection` components such as indexes/caches) or `exclude`
  (only with a written exclusion reason and zero exported objects);
* typed `RebindingReference` entries for credential, signing-key,
  identity-provider, service-endpoint and object-store material. These are
  pointers, never portable data: credentials and signing keys resolve fresh at
  the destination (`fresh_local_resolution_required`) or block restore;
* a `RestoreSafetyPolicy` that defaults pending actions, pending deliveries,
  workflow schedules and credential leases to `suspended`, and structurally
  forbids auto-replaying external effects (`auto_replay_external_effects` is a
  literal `False` — the type system rejects `True`).

## Honesty invariants

The contract makes fabricated success unrepresentable:

* a `restore` decision requires a registered handler **and** a content digest —
  a subsystem without a restore handler cannot be declared restorable, and
  future subsystems are declared `unsupported`/excluded instead of
  empty-success placeholders;
* excluded components cannot claim exported objects;
* every inventoried store needs its watermark in the consistency point; each
  store is inventoried exactly once;
* a quiesced export cannot contain captured-watermark components;
* review (`review_portability_manifest`) never invents authority: unsupported
  rebinding references block portability outright; exclusions, required
  rebinding and watermark consistency become explicit
  `acknowledgements_required` entries operators must accept before any later
  execution (the #877 dry-run consumes this verdict).

## Versioning policy

Strict round-trips with deterministic canonical-JSON digests
(`canonical_portability_digest`). Unknown fields are rejected at the untrusted
boundary (`parse_portability_manifest` maps every validation failure to fixed
safe codes; raw Pydantic errors are never rendered):

* **Same major, same minor** — fully supported.
* **Same major, later minor** — envelope accepted for forward reading; new
  field names still fail strict parsing, so additive minors require updating
  this contract deliberately.
* **Different major** — rejected with `incompatible_manifest_version`. There is
  no implicit major fallback and no all-version compatibility promise.

## Secret exclusion

Secret material has no field to occupy: sessions, runtime credentials, signing
private keys and tokens cannot be attached to the manifest (extra fields are
rejected), and appear only as typed rebinding references with fixed
resolutions. Deployment-specific identifiers stay deployment-specific; logical
object/ontology identifiers are preserved for the destination to rebind.

## Handoff to #324

#324 (durable governed export workflow) remains the export **producer**. The
handoff contract is: a producer emits `PortabilityManifest` documents validated
by `parse_portability_manifest`, computes component digests with
`canonical_portability_digest`, and records the manifest digest alongside the
bundle. Runtime state (pending actions, deliveries, schedules, leases) must be
exported as suspended-by-policy — the manifest carries that posture; the
producer must not "improve" it. Search indexes and caches are
`rebuildable_projection` components. Producer-side partial failure semantics,
signing of the bundle and retention stay owned by #324/#329.

Verification: `make test-api
PYTEST_ARGS='tests/test_portability_manifest.py -q'` from a complete checkout —
33 tests cover round-trips, digest determinism, major-version rejection,
unknown-field rejection, store/consistency coherence, handler honesty, secret
exclusion, suspension defaults and deterministic review verdicts.
