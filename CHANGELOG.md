# Changelog

This file records notable changes to Limes Axis. It describes shipped or
release-bound behavior, not the complete commit history.

## [Unreleased]

### Added

- Versioned Document Studio contract for durable documents and reusable
  templates: section/block schema with stable IDs, typed template parameters
  and fixed/editable/required regions, digest-bound template provenance that
  survives template deletion, published-revision immutability, bounded
  design tokens, and accessibility outline as contract data. Contract slice
  only; no storage, editor runtime, rendering or embed resolution
  ([#829](https://github.com/Limes-Labs/limes-axis/issues/829)).

- Versioned Workbook Studio contract separating workbook structure, source
  bindings and cell provenance: stable identities disjoint from source
  storage IDs, opaque resource-prefix bindings without credentials or rows,
  explicit local-only value labeling, frozen bind-time mapping whose schema
  drift surfaces as compatibility state instead of silent column remap, and
  shareable definitions that strip viewer-local values. Contract slice
  only; no grid UI, source access, formula evaluation or writeback
  ([#848](https://github.com/Limes-Labs/limes-axis/issues/848)).

- Versioned clean-room agreement contract modeling multi-party collaboration
  as a time-bounded agreement: typed purpose/input/output classes as
  enforcement inputs, bounded isolation profiles, provably independent
  per-party approvals, material amendments that invalidate prior approvals,
  authoritative suspension/expiry execution gates, and party removal that
  preserves historical digests while pruning its inputs. Contract slice
  only; no dataset binding, query engine or compute
  ([#855](https://github.com/Limes-Labs/limes-axis/issues/855)).

- Versioned public dataset release manifest contract: sealed immutable release
  revisions with opaque public IDs, closed frozen-source modes (no live query),
  deterministic digests with tamper-checked withdrawal evidence, private
  internal-lineage ledger kept structurally out of public manifests, and a
  deterministic readiness classifier over disclosure/license review evidence.
  Contract slice only; no distribution, API or storage is enabled
  ([#838](https://github.com/Limes-Labs/limes-axis/issues/838)).

- Index generation rebuild conformance (#875): a bounded-maintenance rebuild
  coordinator over the #873 projection — watermark-bound corpus reprojection
  onto a fresh `index_generation`, a watermark fence that refuses to
  overwrite rows changed after the snapshot, one rebuild per tenant at a
  time under an advisory lock, an atomic validated generation
  switch, a fail-closed validator (identity/revision/digest/revoked-sentinel),
  rollback-safe recovery with durable failure evidence, old-generation cursor
  rejection, and metadata-only rebuild evidence
  (ready/rebuilding/unavailable) through the audit boundary.
- Authorized full-text search over the #873 index projection: one bounded query
  service and `GET /operations/search` that re-evaluate current authorization
  before any representation, omit denied and non-evaluable records entirely,
  paginate by keyset with re-authorized cursors that never count hidden
  candidates and are bound to the principal, query, policy revision and
  index generation, and report authorized-subset counts/facets plus explicit
  index freshness. Python SDK
  `search.query(...)` and a public `search-result-page` JSON Schema contract
  are included
  ([#874](https://github.com/Limes-Labs/limes-axis/issues/874)).

- An optional authenticated public institutional context reader (GovCore),
  absent unless `create_app(public_context=...)` opts in, with current
  tenant/scope and separate fixed-origin policy checks before and after the
  remote read. No ontology ingestion, tenant writes or execution authority.
  See [ADR 0020](docs/adr/0020-public-institutional-context.md); production
  installation remains unverified
  ([#930](https://github.com/Limes-Labs/limes-axis/issues/930)).

- End-to-end portability conformance harness: two isolated deployment facades
  run the canonical #324/#876 export bundle through the real #877 validation
  and #878 restore paths with the source permanently disconnected before the
  destination is touched; zero runtime source access is enforced by the
  destination view, logical identities/digests/effective permissions are
  compared against the approved plan, imported audit evidence stays
  source-origin while new destination actions append separate attributable
  evidence, and one machine-readable PASS/FAIL/BLOCKED/NOT RUN report carries
  the exact reason, release and profile per row. `portable` is claimed only
  on an all-PASS supported profile; missing handlers, planned exclusions,
  blocked rows or NOT RUN infrastructure yield the narrower
  `partially_portable`, and corrupt bundles or incompatible versions yield
  `not_portable` with the exact validator reason
  ([#879](https://github.com/Limes-Labs/limes-axis/issues/879)).

- Resumable restore runner for portability: persisted run/step state machine
  over versioned component restore ports, dependency-ordered sequencing with
  per-step digest evidence, worker fencing and idempotent retries, quarantine
  and resume of interrupted runs (only identical bundle/plan digests are
  resumed), targets gated on the persisted suspended tenant row (never a
  tenant with lifecycle history) and bound to one bundle, steps settled only
  by their fencing worker, unsupported plans refused, fail-closed operator
  authorization, missing handlers recorded as
  blocked instead of fabricated completion, and activation blockers surfaced
  for the later verification slice
  ([#878](https://github.com/Limes-Labs/limes-axis/issues/878)).

- Offline portability bundle validator and dry-run restore plan: bounded
  archive-safety checks without opening members, Ed25519 manifest signature
  verification against operator-supplied public keys, per-component payload
  digest verification, deterministic
  identity mapping with explicit consent (two-to-one merges refused, unknown
  principals disabled without default roles), suspension of operational
  schedules, and exclusion acknowledgment gating the later write runner.
  Zero network, admission, credential or destination-write behavior
  ([#877](https://github.com/Limes-Labs/limes-axis/issues/877)).

- Versioned assurance pack manifest contract: audience/engagement-bound
  selection of exact answer, posture and evidence revisions, structured
  support states that keep gaps and limitations visible, freshness
  re-verification against observed facts (expired certificates, wrong
  release/profile, superseded answers cannot pass as current), preflight
  gating (required entries without positive support block issuance unless
  the partial pack lists them), entry disclosure bound to the pack's
  disclosure class, and a fixed scope note for #871/#879 report citations. Contract
  slice only; no artifact packaging or signing
  ([#883](https://github.com/Limes-Labs/limes-axis/issues/883)).
- Deterministic assurance pack assembly: released-only packaging of a
  preflight-ready manifest into a bounded, stored (uncompressed) archive
  (canonical manifest JSON, sanitized local Markdown index, permitted
  attachments) with caller-owned release authorization and final-output
  secret scanning; revocation, revision changes, digest mismatches or
  unsupported scan formats abort generation instead of reusing a privileged
  cached package. No signing, issuance or download delivery
  ([#884](https://github.com/Limes-Labs/limes-axis/issues/884)).
- Immutable signed assurance pack issuance and bounded offline verification:
  final approval binds to the exact assembled package and manifest digests
  after a sign-time preflight and support re-check; frozen issuance records
  carry the approver, Ed25519 signing profile and the #729 lifecycle facts
  (capture time, valid-through, supersession by record digest) as separate
  fields. The verifier reads the manifest and attachments from the package
  itself under member/size bounds, needs only a separately trusted public
  key, rejects unknown record fields and unsupported algorithms, and lets
  stale or missing revocation data or an uncertain clock only qualify the
  result; the wording states that a signature proves integrity and
  provenance, not certification
  ([#885](https://github.com/Limes-Labs/limes-axis/issues/885)).

- A provider-neutral writeback contract that maps an existing typed action onto
  one registered external mutation: adapter capability/readiness and conformance
  declarations, a schema-bound REST operation mapping with allowlisted methods,
  protected host-derived headers and bounded response projection, remote
  identifier/version/precondition fields, honest idempotency metadata and
  normalized outcome states that keep remote request, acknowledgement, business
  result and later source verification apart. A tenant-bound registry keeps
  append-only target versions with explicit enable/disable, and resolution
  rechecks tenant, approval payload digest, credential handle and lease,
  resolved egress target, readiness and request bounds before any I/O
  ([#510](https://github.com/Limes-Labs/limes-axis/issues/510)).

- A reproducible REST connector conformance scenario (one documented command,
  `make rest-conformance`) that drives a declared synthetic collection through
  the real host boundaries over a loopback service: pagination completion with a
  bounded payload digest, durable 429 retry, repeated-cursor and malformed-JSON
  terminals, schema-change blocking before any request, interrupted acceptance
  replay and zero source I/O behind disabled gates. Support evidence projects
  the shared health model from existing durable records and labels its own
  verification scope (`contract_only`, `local_wire_level`, `provider_verified`),
  so a local run never claims provider support and a past green run never
  certifies current availability
  ([#862](https://github.com/Limes-Labs/limes-axis/issues/862)).

- REST collection ingestion through the existing source-ingestion outbox: one
  governed page per fenced attempt, protocol negotiation before any client,
  per-attempt revalidation of the active binding, declared observation, lease
  and egress policy, deterministic payload keys with a compare-and-swap
  checkpoint commit, bounded `Retry-After` scheduling instead of in-worker
  sleeps, and terminal handling of repeated cursors, truncated pages and
  completed traversals. Default-off behind `AXIS_REST_SOURCE_INGESTION_ENABLED`
  with profiles in `AXIS_REST_SOURCE_PROFILES`; no second outbox, scheduler,
  checkpoint database or secret store
  ([#861](https://github.com/Limes-Labs/limes-axis/issues/861)).

- Bounded host-owned REST page reads over the approved source profiles: GET-only
  transport pinned to the egress-approved origin, no-follow redirects with
  same-origin pagination validation, streaming wire/decoded-byte caps and
  deadlines, fixed safe error codes with bounded retry hints, honest truncated
  results and metadata-only progress evidence. The host still owns leases,
  secret resolution, retries and durable checkpoint commits
  ([#860](https://github.com/Limes-Labs/limes-axis/issues/860)).

- Bounded Google Drive discovery adapter over Drive API v3: one explicitly
  configured My Drive root or shared drive is enumerated with pinned origin,
  drive-scoped queries and token-only pagination, normalizing user/group/domain/link
  permission evidence into the document observation contract with fixed safe setup
  states, shortcut pointers that are never fetched, and no content download
  ([#866](https://github.com/Limes-Labs/limes-axis/issues/866)).

- Additive `offline_readiness` section in the deployment readiness report that
  keeps declared configuration, observed rehearsal evidence and external
  accreditation distinct: an offline profile with no rehearsal is reported as
  configured but unverified, and missing, malformed, tampered, stale or
  mismatched evidence is never observed. A consistent rehearsal reference is
  reported as an operator declaration, not as verified isolation. It adds no
  production-required check and establishes no accreditation
  ([#871](https://github.com/Limes-Labs/limes-axis/issues/871)).

- Opt-in `local_only` Helm egress profile with scoped DNS, an explicit local
  service graph derived from the runtime dependency inventory and fail-closed
  validation of missing or unbounded bindings. Rendering a NetworkPolicy is a
  policy check, not proof of isolation: CNI enforcement, additive policies and
  upstream resolver forwarding remain deployment prerequisites
  ([#870](https://github.com/Limes-Labs/limes-axis/issues/870)).

- Versioned static dependency inventory with local options, reasoned capability
  omissions, configuration-reference checks and a generated operator matrix.
  This does not enable adapters, enforce zero egress or certify an offline bundle
  ([#869](https://github.com/Limes-Labs/limes-axis/issues/869)).

- Offline GET-only REST source profiles with typed selectors/parameters, declared
  limits and context-bound SDK checkpoints. Endpoint revisions and selection
  changes invalidate resume; no HTTP transport or source execution is enabled
  ([#859](https://github.com/Limes-Labs/limes-axis/issues/859)).

- Tenant-scoped full-text search index projection (#873): bounded approved text
  from committed ontology promotions and normalized document observations,
  monotonic revision fencing with durable tombstones, row-locked concurrent
  writer serialization, metadata-only audit evidence and a disposable,
  rebuildable index table. No query surface or retrieval authorization in this
  slice.
- Restore-capable tenant portability manifest contract
  ([#876](https://github.com/Limes-Labs/limes-axis/issues/876)): versioned
  component inventory with owner/consistency/restore decisions, typed rebinding
  references that keep secrets non-portable, watermark-vs-quiesced consistency
  disclosure, default-suspended restore safety policy and deterministic
  portability review for the later #877 dry run.

- Microsoft 365 library discovery (#864): bounded Graph v1.0 enumeration of one
  explicitly selected drive, permission evidence normalized into #863
  observations, distinct safe setup states per permission mode, and an
  endpoint-by-permission-mode support table
  (`docs/m365-discovery-permissions.md`). No content reads, no auto-escalation;
  production support is unclaimed until a real authorized tenant is tested.

- Approval queue search and risk/domain filters, compact counts, and a dedicated
  mobile review with focus restoration. Explicit approval links remain reviewable
  outside filters; decision context and required controls are easier to inspect
  ([#436](https://github.com/Limes-Labs/limes-axis/issues/436)).

- Reproducible ingestion strategy benchmarks for REST, database, object and
  document fixtures, with peak memory, queue delay, bounded admission, tenant
  turn scheduling and checkpoint/replay checks. The experiments evaluate
  candidates locally; production scheduling and connector contracts retain
  their existing behavior ([#365](https://github.com/Limes-Labs/limes-axis/issues/365)).

- Opt-in S3/MinIO prefix ingestion through the existing governed source outbox:
  conditional bounded reads, cross-request hash checkpoints, absence observations,
  fenced atomic metadata commits and source-neutral discovery aliases. Migration
  0066 adds binding checkpoint state; API/worker runtime dependencies now include
  the repository Python SDK ([#335](https://github.com/Limes-Labs/limes-axis/issues/335)).

- Versioned SME/enterprise performance workloads, local load/soak and Python
  stack-profiling harnesses, query/pool/resource baseline evidence and a
  noise-aware regression policy. Real deployment SLOs and unimplemented search
  remain separate evidence ([#361](https://github.com/Limes-Labs/limes-axis/issues/361)).

- Seven-layer architecture contract with component/issue ownership, public port
  and backend adoption decisions, plus an offline guard against new core-to-vertical
  imports. Existing reference coupling remains explicitly inventoried
  ([#352](https://github.com/Limes-Labs/limes-axis/issues/352)).

- Opt-in connector event protocol 1.1 with scoped replay/ordering decisions,
  bounded signed webhook validation and a tested offline reference. Kafka/MQTT
  mappings define future host adoption; no event transport is enabled
  ([#340](https://github.com/Limes-Labs/limes-axis/issues/340)).

- Local files-only OSS candidate preparation with exact committed allowlists,
  capability/licence/content checks, reproducible provenance manifests and an
  explicit human release gate. Candidates remain private and publication-blocked
  ([#321](https://github.com/Limes-Labs/limes-axis/issues/321)).

- Hosted prospect sandbox specification: dedicated evaluation environments,
  authenticated time-limited access, generation replacement, synthetic workflow
  installation and retention-aware cleanup gates. This is a design contract;
  hosted invitations and reset are not enabled
  ([#322](https://github.com/Limes-Labs/limes-axis/issues/322)).

- MCP 2026-07-28 gateway design: audience-bound authorization, governed capability
  mappings, transport/resource budgets and a defensive threat model. This defines
  implementation gates without enabling an endpoint, tool or task runtime
  ([#367](https://github.com/Limes-Labs/limes-axis/issues/367)).

- Legacy API usage counters and deprecation/Sunset notices with a planned
  2027-01-01 removal subject to observed migration and maintainer review.
  `/demo/bootstrap` shares the existing governed demo handler; console and CI
  use the new path while all 103 legacy operations remain supported
  ([#357](https://github.com/Limes-Labs/limes-axis/issues/357)).

- Reusable connector conformance checks and reference fault fixtures in the
  authoring SDK, plus a metadata-only freshness/lag/checkpoint/error/retry health
  model. Preview/supported release criteria require adapter-specific and host
  evidence; no source is automatically certified or enabled
  ([#342](https://github.com/Limes-Labs/limes-axis/issues/342)).

- Connector authoring protocol 1.0 in the Python SDK: typed source, discovery,
  read, checkpoint, health and optional writeback contracts, explicit version
  negotiation and a bounded offline reference. The author guide maps adoption
  to existing host gates without enabling new sources
  ([#334](https://github.com/Limes-Labs/limes-axis/issues/334)).

- Shared document-source contracts for scoped identities, immutable revisions,
  ACL freshness and explicit deletion/access-loss observations. Pure replay and
  predecessor checks reject stale updates without adding a store or granting
  read access; provider adapters remain unimplemented
  ([#863](https://github.com/Limes-Labs/limes-axis/issues/863)).

- A repository-topology ADR makes the private repository the commercial source
  of truth and defines the fail-closed, fresh-history boundary for any future
  OSS edition ([#319](https://github.com/Limes-Labs/limes-axis/issues/319)).
- A machine-checked capability matrix assigns current and planned product scope
  to OSS, shared SDK, Hosted or Enterprise/private-cloud editions and blocks
  export on undecided entries
  ([#320](https://github.com/Limes-Labs/limes-axis/issues/320)).
- A compliance-readiness matrix records deployment-specific applicability,
  roles, control/evidence ownership and unresolved ISO/IEC 27001, GDPR, EU AI
  Act and NIS2 review boundaries
  ([#372](https://github.com/Limes-Labs/limes-axis/issues/372)).
- Repository governance baseline with code ownership, support and conduct
  policies, architecture decision records, bounded dependency updates and an
  automated documentation-path check ([#323](https://github.com/Limes-Labs/limes-axis/issues/323)).

### Changed

- Closing ontology entity details returns keyboard focus to the opening graph
  node or list control, with the explorer heading as a fallback for direct links,
  removed nodes or responsive hidden controls. Peer navigation, browser history,
  view selection, zoom and tenant-bound reads are preserved
  ([#431](https://github.com/Limes-Labs/limes-axis/issues/431)).

- The connector console loads a bounded, principal-scoped summary and selected
  details on demand. A local 60-connector browser fixture drops from seven
  initial requests/161,020 bytes to two requests/9,587 bytes; pagination, audit
  and identity invalidation retain explicit contracts. Existing registries and
  aliases remain supported
  ([#364](https://github.com/Limes-Labs/limes-axis/issues/364)).

- Model endpoint and invocation persistence now has an aggregate owner behind
  the existing repository methods, preserving caller-owned transactions and
  SQL behavior. Shared facade/aggregate contracts also run against PostgreSQL
  in CI ([#356](https://github.com/Limes-Labs/limes-axis/issues/356)).

- Model HTTP handlers now live in a domain router, with the existing application
  dependencies, authorization, tenant binding and audit behavior preserved.
  A generated route ownership map tracks the remaining composition-root work
  ([#355](https://github.com/Limes-Labs/limes-axis/issues/355)).

- The connector capability audit records the existing source families, runtime
  gates and gaps. Bounded Postgres extraction now uses its profile's statement
  timeout and returns a null watermark for tables without a single-column
  primary key, fixing two read-loop errors found by the audit
  ([#333](https://github.com/Limes-Labs/limes-axis/issues/333)).

- API settings are grouped into seven capabilities behind the existing flat
  environment facade, with a generated operator reference. Production startup
  now rejects non-positive rate limits and inconsistent enabled source-ingestion
  retry and extraction claim windows. Existing aliases, defaults and development
  behavior are preserved ([#358](https://github.com/Limes-Labs/limes-axis/issues/358)).

- Governed model invocations commit the requested record before calling the
  provider, so a provider timeout no longer occupies a database connection and
  the idempotency key survives an interrupted process. At most one provider
  call is now issued per tenant and idempotency key, including under concurrent
  duplicate delivery; a replay whose outcome is not yet recorded returns status
  `requested` with an explanatory note and is never re-invoked automatically
  ([#362](https://github.com/Limes-Labs/limes-axis/issues/362)).
- Container build, signing-provenance and SARIF upload actions use reviewed
  dependency updates; static contract checks retain the exact expected versions.

- Data-asset lineage batches promotion history reads while retaining tenant
  isolation, chronological output and the latest-50 limit per proposal.
- CSV preview detects duplicate headers in one pass with unchanged validation
  messages and ordering.
- Local development targets load the repository-root environment file; setup
  uses committed lockfiles and verification includes the public schema package.
- The data asset catalog read is bounded to the assets it returns instead of
  materializing every current stewardship row and grouping every observation
  row for the tenant. A new `(tenant_id, asset_id)` index on
  `data_asset_resource_observations` keeps the scoped count proportional to the
  requesting tenant's rows; without it the planner combined two single-column
  indexes and scanned index entries belonging to every other tenant. Responses
  are unchanged ([#363](https://github.com/Limes-Labs/limes-axis/issues/363)).
- The architecture overview now describes current runtime truth while delivery
  history lives in a separate changelog ([#359](https://github.com/Limes-Labs/limes-axis/issues/359)).
- The API compatibility suite is warning-clean and fails on new warnings
  ([#377](https://github.com/Limes-Labs/limes-axis/issues/377)).

## Changelog Policy

Every pull request that changes user-visible behavior, public schemas, security
posture, data migrations, deployment requirements or supported dependencies must
add an entry under `Unreleased`.

Pure tests, internal refactors and documentation corrections may omit an entry
when they do not change those contracts. The pull request must state why the
change is exempt. Architecture changes additionally require an ADR or an entry in
`docs/architecture-changelog.md`.

At release time, maintainers move the relevant `Unreleased` entries into a
versioned section with an ISO date. Entries describe outcomes and compatibility
impact; commit-by-commit chronology stays in Git history.
