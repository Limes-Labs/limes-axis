# Clean Rooms contract: multi-party agreement and workspace lifecycle

[#855](https://github.com/Limes-Labs/limes-axis/issues/855) (parent #854) is
delivered here as a contract slice:
[`services/api/src/axis_api/clean_room_contracts.py`](../services/api/src/axis_api/clean_room_contracts.py).
It is pure vocabulary — no dataset binding, no query engine, no compute. A
clean room is modeled as what the issue demands: a **time-bounded multi-party
agreement** whose purpose, participants and release rules are machine-visible
enforcement inputs, not free-text documentation.

## Versioned envelope

`axis.clean-room.agreement`, `schema_version` 1.0, `extra="forbid"`, strict
round-trips. Incompatible major versions get the dedicated
`incompatible_clean_room_contract_version` code; everything else degrades to
the single `invalid_clean_room_agreement` code — raw validation details are
never rendered.

## Parties, roles and separation of duties

- `Party` carries organization, domain, roles (contributor, analyst, result
  reviewer, administrator, auditor), accountable owner contact, and whether
  it contributes inputs. Administrators cannot simultaneously contribute raw
  inputs (construction-refused): configuring a workspace never grants raw
  participant data.
- The host must itself be a party; a clean room without contributing
  parties is not a clean room.

## Purpose and classes as enforcement inputs

- `PurposeScope` (intents + prohibited uses + statement), `InputClass`
  (data class + handling reference + named contributing parties) and
  `OutputClass` (shape, reviewer role, minimum reviewers) are typed and
  versioned. Input classes must name existing contributing parties; actual
  input bindings are absent from this contract — membership grants no
  dataset access.
- `IsolationProfile` bounds compute mode, egress mode, tenant boundary
  references and retention; contradictory profiles (confidential requirement
  on a non-confidential compute, zero-egress federated query) are
  construction-refused.

## Independent approvals, provable

- `PartyApproval` records one party's sign-off signed by **its own
  organization**, with an `authority_ref` that must cite the signing
  organization. Forging another party's approval, signing from an
  organization outside the agreement, and duplicate approvals are all
  construction failures (`approval_not_by_party_owner`,
  `unknown_clean_room_party`).
- `activate_agreement` requires every party's record; a lone signature can
  never activate anything. `agreement_readiness` exposes the exact blocking
  gaps (missing approvals by party, undeclared input classes, governance
  references, confidential-compute attestation) before approval.

## Material amendment invalidates approvals

`amend_agreement` refuses non-material changes and, for material ones
(participants, purpose, input/output classes, isolation, validity,
governance), produces a new revision with **empty approvals** and no
activation timestamp — nothing is silently carried forward. Prior revisions
stay untouched with their historical approval evidence.

## Lifecycle gate, authoritative

- `suspend_agreement` / `terminate_agreement` stamp when execution stopped;
  `authorizes_execution` returns true only for a current agreement inside
  its validity window — expiry and suspension block new computation at
  contract level regardless of session validity or cleanup-worker lag.
- `remove_party` amends the agreement (pruning that party's input classes)
  and returns the **historical digest** released-result and audit records
  must keep citing; the removed party's inputs become unusable in the new
  revision while historical evidence survives. A clean room never drops
  below two parties.

## Round-trips at untrusted boundaries

`parse_clean_room_agreement` accepts canonical JSON with the strict
error-code policy above; digests recomputed from the parsed model match the
producer's digest exactly.
