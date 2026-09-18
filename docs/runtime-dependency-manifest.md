# Runtime dependency manifest: what each capability needs from the network

[#869](https://github.com/Limes-Labs/limes-axis/issues/869) (parent #473) is
delivered here as one module:
[`services/api/src/axis_api/runtime_dependency_manifest.py`](../services/api/src/axis_api/runtime_dependency_manifest.py),
with the generated human-readable matrix at
[`docs/runtime-dependency-matrix.md`](runtime-dependency-matrix.md). It is a
versioned machine-readable inventory plus configuration validation — one
manifest-and-validation PR, explicitly **not** a deployment accreditation
claim and **not** runtime isolation evidence.

## What an operator gets

For every shipped capability's network dependency, one entry names:

- the **component** (api, web, worker, identity, object_storage,
  model_inference, telemetry, static_assets, network_baseline, diagnostics)
  and its **capability owner** (one accountable layer);
- the **configuration key** — never a value — and whether the dependency is
  `required`, `optional` or `conditional`;
- **direction/protocol/port** and, where one exists, the **logical local
  service reference** and a **supported local replacement**;
- the **failure behavior** (what stops working when it is unavailable) and
  an **evidence/test reference**.

Build/install/upgrade dependencies (language package registries, container
base images) are separate entries with `phase="build_install_upgrade"`:
runtime of already-built images is unaffected by their unavailability, and
offline bundle production remains #474.

## How completeness is kept honest

- The settings inventory is **scanned from the existing registry**
  (`axis_api.config.Settings`) — this module is not a second settings
  registry. A new endpoint-shaped setting (`AXIS_…_URL/ENDPOINT/ADDRESS/
  DSN/HOST/ISSUER/…`) makes `build_runtime_dependency_manifest` and
  `validate_runtime_dependency_manifest` fail with
  `unclassified_endpoint_setting` until it is reviewed into an entry or
  into the closed `REVIEWED_NON_ENDPOINT_KEYS` map (each key with its
  review reason; a reviewed key that disappears is caught as
  `reviewed_non_endpoint_key_drift`).
- **Static checks flag; they do not prove absence.** The docstring and the
  generated matrix state plainly that hidden network calls are not excluded
  by this inventory. A future live network rehearsal (#870) is a separate
  evidence kind: `live_rehearsal_reference` stays explicitly `None` until
  one exists, and inventory evidence (tests), configuration validation
  (this module) and rehearsal are recorded separately.
- **No secrets, no customer hosts**: entries carry keys and protocol facts
  only; validation rejects secret-looking material
  (`password=`, `sk-…`, `AKIA…`, PEM blocks) and the matrix carries no
  customer-specific hosts.

## Profiles: reasoned omissions, not a sovereign flag

`ManifestProfile` lists per-component omissions, each with an explicit
reason of at least 8 characters; validation refuses omissions of components
the manifest does not declare. The documented
`local-only-sample` profile omits model inference, telemetry and external
diagnostics links with their reasons — optional features, disabled
explicitly, no boolean "sovereign" anywhere in the schema.

## Deterministic matrix

`render_dependency_matrix` produces the Markdown matrix sorted by
component/entry with fixed columns and LF endings — byte-identical across
runs, so [`docs/runtime-dependency-matrix.md`](runtime-dependency-matrix.md)
is regenerable and its staleness is test-detectable
(`test_generated_matrix_doc_is_deterministic_and_current`). Edit the curated
inventory in the module, never the generated file.

## What this PR does not claim

No broad network probing, no fleet management, no license redesign, no new
cloud service, and no statement about what the network *will* do at
runtime — posture separation and enforcement belong to #870/#871/#872.
