# Offline readiness: configured posture versus observed isolation evidence

[#871](https://github.com/Limes-Labs/limes-axis/issues/871) (parent #473, builds
on [#869](https://github.com/Limes-Labs/limes-axis/issues/869) and
[#870](https://github.com/Limes-Labs/limes-axis/issues/870)) adds an **additive
`offline_readiness` section** to the deployment readiness report
(`GET /deployment/readiness`). It exists because readiness previously had to
answer a question it was not shaped to answer: whether a zero-egress deployment
is *verified*, rather than merely *declared*.

The implementation is
[`services/api/src/axis_api/offline_readiness.py`](../services/api/src/axis_api/offline_readiness.py).

## Three distinct concepts, never conflated

| Concept | What it means | Where it appears |
| --- | --- | --- |
| **Configured** | The operator declared an offline egress profile and its approved local bindings, and configuration validation accepted them. | `offline_readiness.configuration` |
| **Observed in a rehearsal** | A bounded local rehearsal-artifact reference matches the live profile digest, release identity and freshness window. | `offline_readiness.observed_evidence` |
| **Externally accredited** | An independent party has attested to isolation. | **Not established here, ever.** |

Nothing in this section probes the network, mutates firewall or DNS state, or
trusts a caller-supplied `verified` flag. It reads declared configuration,
computes a digest over public-safe material facts and validates a declared
rehearsal-artifact reference. This feature establishes no accreditation and adds
no production-required check: `production_blockers` and every existing response
field keep their previous meaning, so existing clients and non-offline
deployments are unaffected.

## Section states

| `offline_readiness.state` | Meaning |
| --- | --- |
| `not_declared` | The deployment does not declare an offline egress profile (`AXIS_DEPLOYMENT_NETWORK_EGRESS_MODE` is neither `offline` nor `local_only`). Nothing is evaluated. |
| `action_required` | The profile is declared but configuration validation found blockers. |
| `configured_unverified` | The profile is declared and configuration validation passed, but isolation is unverified: evidence is missing, incomplete, malformed, tampered, stale or mismatched. |
| `verified_in_rehearsal` | Configuration passed and a rehearsal-artifact reference matched. Observed in a rehearsal, never accredited. |

`observed_evidence.state` is one of `not_run`, `incomplete`, `malformed`,
`tampered`, `mismatched`, `stale` or `matched`. Only `matched` can produce
`verified_in_rehearsal`.

## Configuration

```bash
# Declare the offline profile (rendered by the chart's local-only profile).
AXIS_DEPLOYMENT_NETWORK_EGRESS_MODE=local_only
# Bind the reviewed dependency-inventory revision this profile was validated against.
AXIS_DEPENDENCY_MANIFEST_REVISION=<40-hex commit of docs/runtime-dependencies.json>
# Declare the release the profile is part of (defaults to the application build identity).
AXIS_DEPLOYMENT_RELEASE_IDENTITY=<release identity>
# Approve the local binding for each active dependency: id=opaque-reference
AXIS_DEPLOYMENT_OFFLINE_LOCAL_BINDINGS='["operational-database=private-endpoint://local/ops-postgres","workflow-engine=private-endpoint://local/temporal"]'
# Declare the rehearsal-artifact reference (see below); leave empty until a rehearsal exists.
AXIS_OFFLINE_REHEARSAL_EVIDENCE='{"ref":"...","release":"...","profile_digest":"...","captured_at":"...","scope":"...","result_digest":"..."}'
```

Endpoint locality is resolved **only** through these approved bindings, never
through address text: the API does not treat an RFC1918-looking or `.internal`
host as local. A binding reference must be an opaque reference
(`scheme://path`, at most 200 characters) and must not be an `http`, `https`,
`file` or `ftp` URL, contain credentials, or carry a query string. Approved
references and reached endpoints never appear in the readiness response.

### Dependency validation

Every active dependency must be locally bound. A dependency that is not active
is reported as an omitted capability **with the configuration that disables
it**, so a weaker fallback is never silently activated:

| Requirement | Dependencies |
| --- | --- |
| Required | `artifact-object-store`, `identity-validation`, `operational-database`, `workflow-engine` |
| Optional | `distributed-rate-limit`, `external-database-source`, `model-inference`, `ontology-store`, `s3-input`, `telemetry-export` |

Blockers are machine-readable codes such as
`required_dependency_not_locally_bound:<id>`,
`optional_dependency_not_locally_bound:<id>`,
`dependency_manifest_revision_not_declared`,
`dependency_manifest_revision_not_a_git_revision`,
`invalid_binding_reference:<id>`, `unknown_binding_dependency:<id>`,
`duplicate_binding_dependency:<id>` and `malformed_local_binding:<index>`.
A blocker code never echoes a binding reference, endpoint or secret.

## Declaring a rehearsal-artifact reference

1. Deploy with the offline profile and no evidence configured.
2. Read `offline_readiness.profile_digest` from `/deployment/readiness`. The
   digest is SHA-256 over canonical JSON of public-safe material facts: schema
   id, egress mode, release identity, dependency-manifest revision, the sorted
   `dependency id → opaque binding reference` map, and the required/optional
   dependency lists. No endpoint, DSN, issuer or credential value enters it.
3. Run the isolated rehearsal and record its header:

   | Field | Content |
   | --- | --- |
   | `ref` | Opaque rehearsal-artifact reference |
   | `release` | Tested release identity |
   | `profile_digest` | The digest read in step 2 |
   | `captured_at` | Timezone-aware ISO-8601 capture time |
   | `scope` | Environment and CNI scope the rehearsal covered |
   | `result_digest` | `sha256` of the canonical JSON of the five fields above |

4. Set `AXIS_OFFLINE_REHEARSAL_EVIDENCE` to that JSON object and redeploy.

Canonical JSON means `json.dumps(payload, sort_keys=True, separators=(",", ":"),
ensure_ascii=True)` encoded as UTF-8, and a digest is its lowercase `sha256` hex
digest. The profile digest in step 2 uses the same canonicalization over the
material-facts object, so an operator can reproduce both digests outside Axis
and compare them with the reported values.

`result_digest` is a **consistency binding**, not a signature: it detects an
edited, partially copied or inconsistent reference and establishes no provenance
or accreditation. The freshness window is 90 days
(`OFFLINE_REHEARSAL_MAX_AGE_SECONDS`), and a capture time more than five minutes
in the future is rejected as malformed.

## Which checks are static, configuration-based or runtime-observed

| Check | Kind | Status in this slice |
| --- | --- | --- |
| Chart render assertions (no unrestricted DNS, no port-only rule, no all-address CIDR, declared local graph) | **Static** (manifest rendering) | Runs in CI (`deployment-profile-render-check`) |
| Dependency manifest consistency and configuration-reference coverage | **Static** (inventory and configuration) | Runs in CI |
| Required/optional dependency bindings, omitted capabilities, manifest revision, binding shape | **Configuration-based** | Evaluated on every readiness request |
| Profile digest, release identity, evidence freshness, scope and result digest | **Configuration-based** | Evaluated on every readiness request |
| Local connectivity from the Axis workloads to each bound dependency | **Runtime-observed** | **NOT RUN** — supplied by the #872 disconnected rehearsal |
| External denial from the Axis workloads | **Runtime-observed** | **NOT RUN** — supplied by the #872 disconnected rehearsal |
| CNI enforcement, additive-policy absence, upstream resolver behaviour, node-local DNS support | **Runtime-observed** | **NOT RUN** — deployment prerequisites documented in [zero-egress-local-only-profile.md](zero-egress-local-only-profile.md) |
| Independent attestation of isolation | **External** | **NOT RUN** — no accreditation is established by this feature |

A green readiness response therefore means *declared and, at most, observed in a
bounded rehearsal*. It is not evidence that no packet can leave the environment.

## Reproducible checks

```bash
cd services/api
uv run pytest tests/test_offline_readiness.py -q
uv run pytest tests/test_deployment_readiness.py -q
```

## Scope and follow-ups

This slice delivers the readiness contract, the configuration validation and the
evidence-matching rules, with tests for each acceptance criterion. It does not
run a rehearsal and reports no runtime observation:
[#872](https://github.com/Limes-Labs/limes-axis/issues/872) supplies the real
disconnected rehearsal evidence. Offline bundle production remains
[#474](https://github.com/Limes-Labs/limes-axis/issues/474) and the deployment
posture gates remain [#879](https://github.com/Limes-Labs/limes-axis/issues/879).
