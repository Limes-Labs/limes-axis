# Portability validator: offline bundle verification and dry-run plan

[#877](https://github.com/Limes-Labs/limes-axis/issues/877) (Portability 2/4,
parent #476) is delivered as an offline validator stacked on the #876
manifest contract:
[`services/api/src/axis_api/portability_validator.py`](../services/api/src/axis_api/portability_validator.py).
No network calls, no tenant admission, no credential resolution, no source
connections, no destination writes. Possessing an export cannot create a
tenant or grant privileges; the plan it produces is descriptive and requires
separately authorized execution (#878).

## Bundle verification before anything is opened

- `BundleArchive` validates members **by name and size only**: bounded member
  counts and declared total size, absolute paths, backslashes, `..`
  traversal, drive letters/schemes (`:`), empty or `.` segments, control and
  format characters, duplicate paths and executable serialization formats (`.py`,
  `.pkl`, `.so`, `.jar`, `.wasm`, …) are rejected without inspecting
  contents. The archive description is the producer's declaration; a later
  reader that extracts real members must enforce the same limits on the
  actual bytes it reads.
- The bundle carries an Ed25519 signature over the canonical manifest digest
  (domain-separated as `axis.tenant-portability-bundle:manifest:<digest>`).
  It is verified against **operator-supplied** raw public keys
  (`trusted_signer_keys`, key id → 32-byte public key); the key id only
  selects the key. A key id or public key carried by an untrusted bundle is
  never its own trust anchor. An unknown key id, a signature by any other
  key, or a signature over any other digest fails
  (`bundle_signer_not_trusted`). Producers sign with
  `sign_portability_manifest`; key custody stays with #324/#329.
- Every `restore` component's payload must exist; every carried payload
  (including `rebuild` components) must match the declared object count,
  digest to the manifest's signed `content_digest`, and carry unique
  identities. Payloads for undeclared or excluded components are refused
  (`undeclared_component_payload`), so no unsigned record reaches the plan.
  Missing required payloads, digest mismatches, duplicate identities and
  unsupported source versions fail before any plan exists.

## Deterministic restore plan

`validate_bundle` derives the plan from the manifest plus an operator-supplied
identity map:

- **Explicit mapping only**: two source principals mapping to one target is
  an ambiguous merge and is refused; principals are never matched by email
  or display name.
- Malformed operator mappings (unknown kind, invalid subject) fail with
  `invalid_identity_mapping`.
- **Unknown principals stay `unmapped_disabled`** with no target subject and
  no default roles.
- Rebinding references become concrete actions: credentials/signing keys
  resolve fresh locally, endpoints and stores rebind, `unsupported`
  references become `unsupported_blocked` and appear in `blocked_by` — a
  plan with blocked rebinding is `supported=False` while remaining fully
  inspected.
- Excluded components carry their reasons for explicit acknowledgment;
  `rebuild` components are listed for the writer; operational schedules stay
  suspended per the manifest safety policy (auto-replay is structurally
  impossible there).
- The plan digest is deterministic: the same bundle and mapping always
  produce the same `plan_digest`.

## Explicit acknowledgment before execution

`acknowledge_restore_plan` requires the operator to name **exactly** the
plan's excluded components — nothing missed, nothing extra
(`unacknowledged_exclusion`). The resulting `PlanAcknowledgement` binds the
plan digest and is the handoff artifact the write runner (#878) must
require; it is not an approval token by itself. The runner additionally
refuses plans that are not `supported`.

## Offline, provably

The module imports no HTTP client, no socket, no database driver, no
`subprocess` (enforced by test); serialization is canonical JSON only and
signature verification uses local `cryptography` primitives.
Malformed input degrades to the fixed safe codes of the #876 contract —
bundle details are never echoed back.
