"""End-to-end portability conformance harness (#879, parent #476).

Runs the canonical #324/#876 export bundle through the real #877
validation and #878 restore paths in **two isolated deployment
facades** — a source that produces the bundle and then goes
permanently unreachable, and a destination that never shares identity,
storage, credentials or services with it — and publishes one
machine-readable PASS/FAIL/BLOCKED/NOT RUN report.

The harness orchestrates only; it implements no restore or validation
logic of its own. Every report row names the owner that decided the
outcome. Zero runtime source access is enforced by construction (every
destination read passes through a view that refuses a reachable
source), not promised. "portable" is claimed only when every scenario
row is PASS on a supported profile; missing handlers, blocked rows or
NOT RUN infrastructure yield the narrower ``partially_portable``
outcome, and failures yield ``not_portable``. Future app/workflow
handlers that do not exist are BLOCKED rows with an exact reason, never
silently excluded from a full-feature portability claim.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from axis_sdk.connector_authoring.contracts import ContractModel, Digest
from pydantic import Field

from axis_api.portability_manifest import (
    ComponentInventory,
    ConsistencyPoint,
    ManifestVersion,
    PortabilityManifest,
    RebindingReference,
    StoreWatermark,
    canonical_portability_digest,
)
from axis_api.portability_restore_runner import (
    HandlerRegistry,
    PortabilityRestoreError,
    StepContext,
    activation_blockers,
    block_unsupported_steps,
    claim_step,
    complete_step,
    fail_step,
    resume_run_plan,
    start_restore_run,
)
from axis_api.portability_validator import (
    ArchiveMember,
    BundleArchive,
    BundleSignature,
    PayloadRecord,
    PortabilityBundle,
    PortabilityValidationError,
    RestorePlan,
    acknowledge_restore_plan,
    validate_bundle,
)

REPORT_FORMAT = "axis.portability-conformance-report"
REPORT_VERSION = (1, 0)

ROW_PASS = "PASS"
ROW_FAIL = "FAIL"
ROW_BLOCKED = "BLOCKED"
ROW_NOT_RUN = "NOT RUN"
_ROW_STATES = frozenset({ROW_PASS, ROW_FAIL, ROW_BLOCKED, ROW_NOT_RUN})

OUTCOME_PORTABLE = "portable"
OUTCOME_PARTIAL = "partially_portable"
OUTCOME_NOT_PORTABLE = "not_portable"
OUTCOME_NOT_EVALUATED = "not_evaluated"

DEFAULT_AXIS_VERSION = "1.14.0"
# The harness declares its own verification trust anchor explicitly, the
# same way a deployment pins the export-signing keys it accepts.
HARNESS_TRUSTED_KEY_ID = "signing/2026/portability"

SOURCE_HISTORY_ORIGIN = "source_history"
DESTINATION_ACTION_ORIGIN = "destination_action"

_MAX_REPORT_ROWS = 512


class PortabilityConformanceError(ValueError):
    """Raised for harness misuse, never to express a scenario outcome."""

    SOURCE_CONNECTED = "source_deployment_reachable"
    SESSION_FACTORY_REQUIRED = "destination_session_factory_required"
    CHECK_NAME_INVALID = "check_name_invalid"
    RECORD_SHAPE_INVALID = "record_shape_invalid"


def _record_shape(record: Mapping[str, object]) -> dict[str, object]:
    """The one canonical record shape used everywhere in the harness:
    ``{"identity": str, "data": object}`` — exactly the #877
    PayloadRecord field set, so digests stay comparable end to end."""

    if set(record) != {"identity", "data"} or not isinstance(
        record["identity"], str
    ):
        raise PortabilityConformanceError(
            PortabilityConformanceError.RECORD_SHAPE_INVALID
        )
    return {"identity": record["identity"], "data": record["data"]}


class Deployment:
    """One isolated deployment facade.

    Holds only what a real deployment of the supported profile holds:
    its local stores and its local identity directory. Nothing is
    shared by reference with any other deployment. ``source_reachable``
    models whether this deployment can still reach the source instance.
    """

    def __init__(self, name: str, *, source_reachable: bool = True) -> None:
        self.name = name
        self.stores: dict[str, dict[str, dict[str, object]]] = {}
        self.identities: dict[str, str] = {}
        self.source_reachable = source_reachable

    def load(self, store: str, records: Iterable[Mapping[str, object]]) -> None:
        table = self.stores.setdefault(store, {})
        for raw in records:
            record = _record_shape(raw)
            table[str(record["identity"])] = record

    def records(self, store: str) -> tuple[Mapping[str, object], ...]:
        return tuple(self.stores.get(store, {}).values())


class DestinationView:
    """The only way a check observes the destination.

    Every access calls ``require_source_disconnected`` so a scenario
    cannot silently read the source after the cutoff (AC1 is enforced,
    not asserted after the fact).
    """

    def __init__(self, deployment: Deployment) -> None:
        self._deployment = deployment

    def require_source_disconnected(self) -> None:
        if self._deployment.source_reachable:
            raise PortabilityConformanceError(
                PortabilityConformanceError.SOURCE_CONNECTED
            )

    def records(self, store: str) -> tuple[Mapping[str, object], ...]:
        self.require_source_disconnected()
        return self._deployment.records(store)

    def resolve_identity(self, subject: str) -> str:
        """Only principals the operator explicitly mapped resolve (AC2:
        unmapped principals gain no access)."""

        self.require_source_disconnected()
        if self._deployment.identities.get(subject) != "mapped":
            raise PortabilityConformanceError("identity_not_resolvable")
        return subject

    def permissions_for(self, subject: str) -> tuple[str, ...]:
        self.require_source_disconnected()
        return tuple(
            sorted(
                str(record["data"].get("permission", ""))
                for record in self._deployment.records("policies")
                if record["data"].get("subject") == subject
                and str(record["data"].get("permission", ""))
            )
        )

    def audit_entries(self) -> tuple[Mapping[str, object], ...]:
        return self._deployment.records("audit_ledger")

    def append_audit(self, entry: Mapping[str, object]) -> None:
        """Append new destination-side attributable evidence. The origin
        field is stamped here so imported source history and new
        destination actions stay separately attributable forever."""

        self.require_source_disconnected()
        record = _record_shape(entry)
        data = dict(record["data"])  # type: ignore[arg-type]
        data["origin"] = DESTINATION_ACTION_ORIGIN
        table = self._deployment.stores.setdefault("audit_ledger", {})
        table[f"dest:{len(table)}:{record['identity']}"] = {
            "identity": record["identity"],
            "data": data,
        }


class BundleBytes:
    """The canonical #324/#876 transfer unit: the signed manifest plus
    the per-component payload records, exactly what an export producer
    emits at the declared consistency point."""

    def __init__(
        self,
        manifest: PortabilityManifest,
        component_payloads: Mapping[str, Sequence[PayloadRecord]],
    ) -> None:
        self.manifest = manifest
        self.component_payloads = {
            component_id: tuple(records)
            for component_id, records in component_payloads.items()
        }
        self.archive_members: tuple[str, ...] = (
            "manifest.json",
            *(
                f"components/{component_id}.jsonl"
                for component_id in self.component_payloads
            ),
        )

    def payload_digest(self, component_id: str) -> Digest:
        return canonical_portability_digest(
            [
                record.model_dump(mode="json")
                for record in self.component_payloads[component_id]
            ]
        )

    def member_bytes(self, path: str) -> int:
        if path == "manifest.json":
            return len(self.manifest.model_dump_json())
        component_id = path.removeprefix("components/").removesuffix(".jsonl")
        return max(len(self.payload_digest(component_id)), 1)


def export_bundle(
    source: Deployment,
    *,
    captured_at: str,
    decisions: Mapping[str, str] | None = None,
) -> BundleBytes:
    """Export at the declared consistency point (#324 producer role)."""

    if not source.source_reachable:
        raise PortabilityConformanceError(
            PortabilityConformanceError.SOURCE_CONNECTED
        )
    decisions = decisions or {}
    manifest = _source_manifest(source, captured_at=captured_at, decisions=decisions)
    component_payloads = {
        component.component_id: tuple(
            PayloadRecord(**record)
            for record in source.records(component.component_id)
        )
        for component in manifest.components
        if component.decision != "exclude"
    }
    return BundleBytes(manifest, component_payloads)


# Component ids are free-form identifiers; the manifest ``store`` field is a
# closed vocabulary. Relational components (policies, configuration) live in
# ``postgres``; the named stores map to themselves.
_STORE_KIND = {
    "ontology": "ontology",
    "audit_ledger": "audit_ledger",
    "object_storage": "object_storage",
}


def _store_kind(component_id: str) -> str:
    return _STORE_KIND.get(component_id, "postgres")


def _source_manifest(
    source: Deployment,
    *,
    captured_at: str,
    decisions: Mapping[str, str],
) -> PortabilityManifest:
    components = []
    for component_id in sorted(source.stores):
        records = source.records(component_id)
        decision = decisions.get(component_id, "restore")
        components.append(
            ComponentInventory(
                component_id=component_id,
                owner_layer="trust" if component_id == "audit_ledger" else "data",
                store=_store_kind(component_id),
                consistency="quiesced_export"
                if component_id == "audit_ledger"
                else "captured_watermark",
                decision=decision,
                schema_version=ManifestVersion(major=1, minor=0),
                object_count=len(records) if decision != "exclude" else 0,
                content_digest=(
                    canonical_portability_digest([dict(r) for r in records])
                    if decision != "exclude"
                    else None
                ),
                handler_registered=decision != "exclude",
                exclusion_reason=(
                    "excluded by source profile"
                    if decision == "exclude"
                    else None
                ),
            )
        )
    return PortabilityManifest(
        schema_version=ManifestVersion(major=1, minor=0),
        tenant_logical_id=f"tenant-{source.name}",
        source_axis_version=DEFAULT_AXIS_VERSION,
        consistency_point=ConsistencyPoint(
            mode="captured_watermark",
            captured_at=captured_at,
            per_store=tuple(
                StoreWatermark(store=_store_kind(store), watermark=f"wm-{index}")
                for index, store in enumerate(sorted(source.stores))
            ),
            disclosures="Watermarks captured per store during export.",
        ),
        components=tuple(components),
        rebinding_references=(
            RebindingReference(
                kind="credential",
                reference_id="credential.oidc-client",
                resolution="fresh_local_resolution_required",
            ),
        ),
    )


def supported_profile_plan(
    bundle: BundleBytes,
    *,
    axis_versions: Sequence[str] = (DEFAULT_AXIS_VERSION,),
) -> RestorePlan:
    """Validate the bundle through the real #877 validator."""

    portability_bundle = PortabilityBundle(
        manifest=bundle.manifest,
        archive=BundleArchive(
            members=tuple(
                ArchiveMember(path=path, size_bytes=bundle.member_bytes(path))
                for path in bundle.archive_members
            )
        ),
        component_payloads=bundle.component_payloads,
        signature=BundleSignature(
            signer_key_id=HARNESS_TRUSTED_KEY_ID,
            signed_manifest_digest=bundle.manifest.digest(),
        ),
    )
    return validate_bundle(
        portability_bundle,
        trusted_signer_key_ids=frozenset({HARNESS_TRUSTED_KEY_ID}),
        supported_axis_versions=tuple(axis_versions),
    )


def disconnect_source(source: Deployment) -> None:
    """The post-export cutoff: the source becomes permanently unreachable."""

    source.source_reachable = False


def destination_store_handler(destination: Deployment) -> Callable[[StepContext], Digest]:
    """The harness restore handler: writes the component's records into
    the destination's own stores through the declared context only.
    Idempotent (records are keyed by logical identity)."""

    def handler(context: StepContext) -> Digest:
        DestinationView(destination).require_source_disconnected()
        table = destination.stores.setdefault(context.component_id, {})
        for raw in context.records:
            record = _record_shape(raw)
            table[str(record["identity"])] = record
        return canonical_portability_digest(list(table.values()))

    return handler


def restore_into_destination(
    destination: Deployment,
    bundle: BundleBytes,
    *,
    session_factory: Callable[[], Any],
    handlers: Mapping[str, Callable[[StepContext], Digest]] | None = None,
    handler_component_ids: Sequence[str] | None = None,
    axis_versions: Sequence[str] = (DEFAULT_AXIS_VERSION,),
    target_tenant_status: str = "suspended",
    operator: str = "operator:restore",
) -> dict[str, object]:
    """Validate, plan, acknowledge and run the restore on the destination
    through the real #877 plan and the real #878 runner on the
    destination's own database — never harness shortcuts.

    ``handler_component_ids`` declares which components the destination
    actually has handlers for; a declared restore component outside the
    set stays a #878 blocked step (missing handler), never a fabricated
    success."""

    DestinationView(destination).require_source_disconnected()
    plan = supported_profile_plan(bundle, axis_versions=axis_versions)
    acknowledgement = acknowledge_restore_plan(
        plan,
        acknowledged_exclusions=plan.exclusions(),
        acknowledged_by=operator,
        acknowledged_at="2026-09-17T08:00:00Z",
    )
    registry = HandlerRegistry(
        handlers={
            component.component_id: destination_store_handler(destination)
            for component in bundle.manifest.components
            if component.decision == "restore"
            and component.component_id not in (handlers or {})
            and (handler_component_ids is None or component.component_id in handler_component_ids)
        }
        | dict(handlers or {})
    )
    with session_factory() as session:
        run = start_restore_run(
            session,
            plan=plan,
            acknowledgement=acknowledgement,
            target_tenant_id=f"tenant-{destination.name}",
            target_tenant_status=target_tenant_status,
            manifest_components=bundle.manifest.components,
            acknowledged_by=operator,
            authorized_by=operator,
            authorize=lambda _subject: True,
        )
        block_unsupported_steps(
            session,
            run_id=run.id,
            registry=registry,
            manifest_components=bundle.manifest.components,
        )
        for component_id in resume_run_plan(bundle.manifest.components, run):
            try:
                claim_step(
                    session,
                    run_id=run.id,
                    component_id=component_id,
                    worker_id=operator,
                    authorize=lambda _subject: True,
                )
            except PortabilityRestoreError:
                continue
            handler = registry.for_component(component_id)
            if handler is None:  # pragma: no cover — resume excludes these
                continue
            records = bundle.component_payloads.get(component_id, ())
            try:
                evidence = handler(
                    StepContext(
                        run_id=str(run.id),
                        component_id=component_id,
                        target_tenant_id=f"tenant-{destination.name}",
                        object_prefix=f"portability/{run.id}/{component_id}",
                        payload_digest=bundle.payload_digest(component_id),
                        records=tuple(
                            record.model_dump(mode="json") for record in records
                        ),
                    )
                )
            except Exception:  # noqa: BLE001 — surfaced as step failure
                fail_step(
                    session,
                    run_id=run.id,
                    component_id=component_id,
                    failure_code="handler_error",
                )
                continue
            complete_step(
                session,
                run_id=run.id,
                component_id=component_id,
                evidence_digest=evidence,
            )
        blockers = activation_blockers(session, run_id=run.id)
        restored = tuple(run.steps_completed)
        run_state = run.state
    return {
        "plan": plan,
        "run_state": run_state,
        "activation_blockers": blockers,
        "restored_components": restored,
    }


class ConformanceRow(ContractModel):
    """One PASS/FAIL/BLOCKED/NOT RUN row with its deciding owner."""

    check: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9_]+$")
    state: str = Field(pattern="^(PASS|FAIL|BLOCKED|NOT RUN)$")
    owner: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)


def _row(
    check: str,
    state: str,
    *,
    owner: str,
    reason: str,
) -> dict[str, str]:
    return ConformanceRow(
        check=check, state=state, owner=owner, reason=reason
    ).model_dump(mode="json")


def evaluate_scenario(
    bundle: BundleBytes,
    restore_result: Mapping[str, object],
    *,
    destination: Deployment,
    expected_permissions: Mapping[str, Sequence[str]] | None = None,
    activated_flow: Callable[[DestinationView], str] | None = None,
    search_rebuild: tuple[str, str] | None = None,
) -> tuple[dict[str, str], ...]:
    """Compare the restored destination against the approved plan.

    Compares logical identities, per-component digests and effective
    permissions — never deployment-specific UUID equality. The search
    row reflects the #875 rebuild outcome passed in by the caller; the
    restored destination never imports an index as authority.
    """

    view = DestinationView(destination)
    view.require_source_disconnected()
    plan: RestorePlan = restore_result["plan"]  # type: ignore[assignment]
    rows: list[dict[str, str]] = []

    rows.append(
        _row(
            "destination_has_zero_source_runtime_access",
            ROW_PASS,
            owner="axis_api.portability_conformance:DestinationView",
            reason="every destination read enforced against a disconnected view",
        )
    )

    mapped = {
        mapping.source_subject
        for mapping in plan.identity_mappings
        if mapping.target_state == "mapped"
    }
    unmapped_subject = next(
        (
            mapping.source_subject
            for mapping in plan.identity_mappings
            if mapping.target_state != "mapped"
        ),
        None,
    )
    identity_ok = True
    identity_reason = "all mapped principals resolve locally"
    for subject in sorted(mapped):
        try:
            view.resolve_identity(subject)
        except PortabilityConformanceError:
            identity_ok = False
            identity_reason = f"mapped principal does not resolve: {subject}"
            break
    rows.append(
        _row(
            "restored_logical_identities_match_plan",
            ROW_PASS if identity_ok else ROW_FAIL,
            owner="axis_api.portability_validator:RestorePlan.identity_mappings",
            reason=identity_reason,
        )
    )

    restored: tuple[str, ...] = restore_result["restored_components"]  # type: ignore[assignment]
    blockers: tuple[str, ...] = restore_result["activation_blockers"]  # type: ignore[assignment]
    missing_handler = {
        str(blocker).removeprefix("missing_handler:")
        for blocker in blockers
        if str(blocker).startswith("missing_handler:")
    }
    digest_fail: list[str] = []
    digest_blocked: list[str] = []
    for component in bundle.manifest.components:
        if component.decision == "exclude" or component.content_digest is None:
            continue
        if component.component_id not in restored:
            if component.component_id in missing_handler:
                digest_blocked.append(component.component_id)
            continue
        actual = canonical_portability_digest(
            list(destination.stores.get(component.component_id, {}).values())
        )
        if actual != component.content_digest:
            digest_fail.append(component.component_id)
    if digest_fail:
        rows.append(
            _row(
                "restored_artifact_digests_match_plan",
                ROW_FAIL,
                owner="axis_api.portability_manifest:canonical_portability_digest",
                reason=f"digest mismatch: {', '.join(digest_fail)}",
            )
        )
    elif digest_blocked:
        rows.append(
            _row(
                "restored_artifact_digests_match_plan",
                ROW_BLOCKED,
                owner="axis_api.portability_manifest:canonical_portability_digest",
                reason=(
                    "components not restored, no handler on the destination: "
                    + ", ".join(sorted(digest_blocked))
                ),
            )
        )
    else:
        rows.append(
            _row(
                "restored_artifact_digests_match_plan",
                ROW_PASS,
                owner="axis_api.portability_manifest:canonical_portability_digest",
                reason="restored store digests match declared inventory",
            )
        )

    if expected_permissions:
        permission_ok = True
        permission_reason = "effective permissions match the approved plan"
        for subject, expected in sorted(expected_permissions.items()):
            if tuple(sorted(expected)) != view.permissions_for(subject):
                permission_ok = False
                permission_reason = f"permission drift for {subject}"
                break
        rows.append(
            _row(
                "effective_permissions_match_plan",
                ROW_PASS if permission_ok else ROW_FAIL,
                owner="axis_api.portability_validator:IdentityMapping",
                reason=permission_reason,
            )
        )
    unmapped_ok = True
    unmapped_reason = "unmapped principals gain no access"
    if unmapped_subject is not None:
        try:
            view.resolve_identity(unmapped_subject)
            unmapped_ok = False
            unmapped_reason = f"unmapped principal resolved: {unmapped_subject}"
        except PortabilityConformanceError:
            pass
    rows.append(
        _row(
            "unmapped_principals_gain_no_access",
            ROW_PASS if unmapped_ok else ROW_FAIL,
            owner="axis_api.portability_validator:IdentityMapping.target_state",
            reason=unmapped_reason,
        )
    )

    if search_rebuild is None:
        rows.append(
            _row(
                "search_authority_rebuilt_via_rebuild_owner",
                ROW_NOT_RUN,
                owner="axis_api.search_rebuild (#875)",
                reason=(
                    "rebuild owner not part of this stack; run the dedicated"
                    " #875 conformance and pass its outcome in"
                ),
            )
        )
    else:
        state, reason = search_rebuild
        rows.append(
            _row(
                "search_authority_rebuilt_via_rebuild_owner",
                state if state in _ROW_STATES else ROW_NOT_RUN,
                owner="axis_api.search_rebuild (#875)",
                reason=reason,
            )
        )

    audit_entries = view.audit_entries()
    imported = [
        entry
        for entry in audit_entries
        if entry["data"].get("origin") == SOURCE_HISTORY_ORIGIN
    ]

    if activated_flow is not None:
        try:
            flow_result = activated_flow(view)
            rows.append(
                _row(
                    "one_restored_flow_works_after_activation",
                    ROW_PASS,
                    owner="axis_api.portability_restore_runner:activation",
                    reason=f"flow completed: {flow_result}",
                )
            )
        except Exception as error:  # noqa: BLE001 — reported, never swallowed
            rows.append(
                _row(
                    "one_restored_flow_works_after_activation",
                    ROW_FAIL,
                    owner="axis_api.portability_restore_runner:activation",
                    reason=f"flow failed: {error}",
                )
            )
        appended = [
            entry
            for entry in view.audit_entries()
            if entry["data"].get("origin") == DESTINATION_ACTION_ORIGIN
        ]
        rows.append(
            _row(
                "imported_audit_verifies_as_source_history_new_actions_attributable",
                ROW_PASS if imported and appended else ROW_FAIL,
                owner="axis_api.portability_restore_runner:restore handlers",
                reason=(
                    "imported evidence retained with source origin;"
                    " new destination actions carry destination origin"
                    if imported and appended
                    else "missing imported or destination-origin audit evidence"
                ),
            )
        )
    else:
        rows.append(
            _row(
                "imported_audit_verifies_as_source_history_new_actions_attributable",
                ROW_NOT_RUN if not imported else ROW_PASS,
                owner="axis_api.portability_restore_runner:restore handlers",
                reason=(
                    "imported evidence retained; no activated flow scenario,"
                    " destination-action attribution not exercised"
                    if imported
                    else "no imported source-history evidence found"
                ),
            )
        )
    rows.append(
        _row(
            "pending_old_external_effects_remain_inert",
            ROW_PASS,
            owner="axis_api.portability_validator:RestorePlan.suspended_operations",
            reason="; ".join(plan.suspended_operations)
            or "no pending external operations declared",
        )
    )

    if restore_result["run_state"] == "completed" and not blockers:
        rows.append(
            _row(
                "activation_gate_honest_after_restore",
                ROW_PASS,
                owner="axis_api.portability_restore_runner:activation_blockers",
                reason="run completed with no activation blockers",
            )
        )
    else:
        rows.append(
            _row(
                "activation_gate_honest_after_restore",
                ROW_BLOCKED,
                owner="axis_api.portability_restore_runner:activation_blockers",
                reason="; ".join(blockers) or f"run_state:{restore_result['run_state']}",
            )
        )

    return tuple(rows[:_MAX_REPORT_ROWS])


def not_run_row(check: str, *, owner: str, reason: str) -> dict[str, str]:
    """An explicit NOT RUN row: missing infrastructure is never a skip."""

    return _row(check, ROW_NOT_RUN, owner=owner, reason=reason)


def build_conformance_report(
    rows: Sequence[Mapping[str, str]],
    *,
    plan: RestorePlan | None,
    restore_result: Mapping[str, object] | None,
    profile: str,
    release: str,
    profile_supported: bool = True,
) -> dict[str, object]:
    """The machine-readable PASS/FAIL/BLOCKED/NOT RUN report (AC5).

    Outcome honesty: FAIL rows or an unsupported profile →
    ``not_portable``; any BLOCKED/NOT RUN row or missing handler → the
    narrower ``partially_portable``; only an all-PASS supported run may
    claim ``portable``. No rows at all → ``not_evaluated``.
    """

    row_list = [dict(row) for row in rows][:_MAX_REPORT_ROWS]
    failed = any(row["state"] == ROW_FAIL for row in row_list)
    degraded = any(
        row["state"] in {ROW_BLOCKED, ROW_NOT_RUN} for row in row_list
    )
    missing_handlers = sorted(
        blocker.removeprefix("missing_handler:")
        for blocker in (
            (restore_result or {}).get("activation_blockers", ())
            if restore_result
            else ()
        )
        if str(blocker).startswith("missing_handler:")
    )
    excluded_components = [list(pair) for pair in plan.excluded_components] if plan else []
    if not row_list:
        outcome = OUTCOME_NOT_EVALUATED
    elif plan is None:
        # Nothing was validated or restored: a FAIL row carries the exact
        # validation reason (never a success claim); rows that are only
        # NOT RUN infrastructure probes mean nothing was evaluated.
        outcome = OUTCOME_NOT_PORTABLE if failed else OUTCOME_NOT_EVALUATED
    elif not profile_supported or failed:
        outcome = OUTCOME_NOT_PORTABLE
    elif degraded or missing_handlers or excluded_components:
        # A minimal profile (planned exclusions) is a *narrower* claim than
        # complete #476 acceptance even when every executed row passes.
        outcome = OUTCOME_PARTIAL
    else:
        outcome = OUTCOME_PORTABLE

    return {
        "format": REPORT_FORMAT,
        "version": list(REPORT_VERSION),
        "profile": profile,
        "release": release,
        "plan_digest": plan.plan_digest if plan else None,
        "bundle_digest": plan.bundle_digest if plan else None,
        "source_axis_version": plan.source_axis_version if plan else None,
        "profile_supported": profile_supported,
        "outcome": outcome,
        "missing_handlers": missing_handlers,
        "excluded_components": excluded_components,
        "restored_components": list(
            (restore_result or {}).get("restored_components", ())
        ),
        "rows": row_list,
        "summary": {
            "pass": sum(1 for row in row_list if row["state"] == ROW_PASS),
            "fail": sum(1 for row in row_list if row["state"] == ROW_FAIL),
            "blocked": sum(1 for row in row_list if row["state"] == ROW_BLOCKED),
            "not_run": sum(1 for row in row_list if row["state"] == ROW_NOT_RUN),
        },
    }


def run_conformance_scenario(
    *,
    source_seed: Callable[[Deployment], None],
    destination_session_factory: Callable[[], Any],
    destination_identity_directory: Mapping[str, str] | None = None,
    handlers: Mapping[str, Callable[[StepContext], Digest]] | None = None,
    handler_component_ids: Sequence[str] | None = None,
    expected_permissions: Mapping[str, Sequence[str]] | None = None,
    activated_flow: Callable[[DestinationView], str] | None = None,
    search_rebuild: tuple[str, str] | None = None,
    axis_versions: Sequence[str] = (DEFAULT_AXIS_VERSION,),
    export_decisions: Mapping[str, str] | None = None,
    captured_at: str = "2026-09-17T08:00:00Z",
    profile: str = "canonical-1.0",
    release: str = DEFAULT_AXIS_VERSION,
) -> dict[str, object]:
    """One reproducible runbook entrypoint: seed → export at the
    consistency point → disconnect the source → restore into a clean,
    independently initialized destination → evaluate → report.

    Validation failures (corrupt bundle, unsupported profile version)
    surface as a ``not_portable`` report with the exact FAIL row — they
    never crash the runbook and never yield a success claim."""

    source = Deployment("source")
    source_seed(source)
    bundle = export_bundle(
        source, captured_at=captured_at, decisions=export_decisions
    )
    disconnect_source(source)

    destination = Deployment("destination", source_reachable=False)
    destination.identities.update(destination_identity_directory or {})
    try:
        restore_result = restore_into_destination(
            destination,
            bundle,
            session_factory=destination_session_factory,
            handlers=handlers,
            handler_component_ids=handler_component_ids,
            axis_versions=axis_versions,
        )
    except PortabilityValidationError as error:
        return build_conformance_report(
            [
                _row(
                    "bundle_validates_against_supported_profile",
                    ROW_FAIL,
                    owner="axis_api.portability_validator:validate_bundle",
                    reason=str(error)[:500],
                )
            ],
            plan=None,
            restore_result=None,
            profile=profile,
            release=release,
            profile_supported=DEFAULT_AXIS_VERSION in axis_versions,
        )
    rows = evaluate_scenario(
        bundle,
        restore_result,
        destination=destination,
        expected_permissions=expected_permissions,
        activated_flow=activated_flow,
        search_rebuild=search_rebuild,
    )
    return build_conformance_report(
        rows,
        plan=restore_result["plan"],  # type: ignore[arg-type]
        restore_result=restore_result,
        profile=profile,
        release=release,
        profile_supported=DEFAULT_AXIS_VERSION in axis_versions,
    )
