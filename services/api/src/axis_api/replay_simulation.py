import hashlib
import json

from pydantic import BaseModel, Field

from axis_api.audit_queries import _audit_event_to_ledger_event
from axis_api.demo import AuditLedgerEvent, OverviewMetric, OverviewStatus, WorkflowTimelineEvent
from axis_api.models import AuditEvent, WorkflowRunRecord, WorkflowTimelineRecord
from axis_api.persistence import AxisPersistenceRepository
from axis_api.workflow_queries import _timeline_event_to_public


class ReplaySimulationQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    workflow_id: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=20, ge=1, le=100)


class PolicySimulationResult(BaseModel):
    policy_id: str = Field(min_length=1)
    policy_name: str = Field(min_length=1)
    baseline_decision: str = Field(min_length=1)
    simulated_decision: str = Field(min_length=1)
    changed_outcome: bool
    evidence_refs: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)


class PolicySetVersionDiff(BaseModel):
    diff_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    baseline_policy_set_id: str = Field(min_length=1)
    baseline_policy_set_version: str = Field(min_length=1)
    candidate_policy_set_id: str = Field(min_length=1)
    candidate_policy_set_version: str = Field(min_length=1)
    historical_event_count: int = Field(ge=0)
    changed_policy_ids: list[str] = Field(default_factory=list)
    baseline_decision: str = Field(min_length=1)
    candidate_decision: str = Field(min_length=1)
    changed_outcome: bool
    diff_status: str = Field(min_length=1)
    audit_event_type: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)


class ReplayArtifact(BaseModel):
    artifact_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    workflow_name: str = Field(min_length=1)
    audit_scope: str = Field(min_length=1)
    replay_mode: str = Field(min_length=1)
    replay_ready: bool
    determinism_status: str = Field(min_length=1)
    timeline_event_count: int = Field(ge=0)
    audit_event_count: int = Field(ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    timeline: list[WorkflowTimelineEvent] = Field(default_factory=list)
    audit_events: list[AuditLedgerEvent] = Field(default_factory=list)
    policy_results: list[PolicySimulationResult] = Field(default_factory=list)
    policy_set_diffs: list[PolicySetVersionDiff] = Field(default_factory=list)


class ManufacturingReplaySimulation(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    simulation_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(default_factory=list)
    artifacts: list[ReplayArtifact] = Field(default_factory=list)
    simulation_notes: list[str] = Field(default_factory=list)


def build_replay_simulation(
    repository: AxisPersistenceRepository,
    query: ReplaySimulationQuery,
) -> ManufacturingReplaySimulation:
    workflow_records = repository.list_workflow_runs(
        tenant_id=query.tenant_id,
        limit=query.limit,
    )
    if query.workflow_id is not None:
        workflow_records = [
            workflow for workflow in workflow_records if workflow.workflow_id == query.workflow_id
        ]

    audit_records = repository.list_audit_events(
        tenant_id=query.tenant_id,
        limit=200,
    )
    artifacts = [
        _build_artifact(
            workflow,
            repository.list_workflow_timeline_events(
                tenant_id=workflow.tenant_id,
                workflow_id=workflow.workflow_id,
                limit=100,
            ),
            _matching_audit_records(audit_records, workflow),
        )
        for workflow in workflow_records
    ]
    artifacts = [artifact for artifact in artifacts if artifact.timeline or artifact.audit_events]

    return ManufacturingReplaySimulation(
        tenant_id=query.tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of=_as_of(artifacts),
        simulation_status=OverviewStatus.READY if artifacts else OverviewStatus.WATCH,
        metrics=_metrics(artifacts),
        artifacts=artifacts,
        simulation_notes=[
            "Replay artifacts are derived from tenant-scoped workflow history and audit events.",
            "Policy simulation is deterministic preview logic, not live workflow replay.",
            "Policy-set version diffs compare governed connector policy sets over historical "
            "events without activating a new set.",
            "Raw action payloads are not exposed in replay artifacts.",
            "Temporal replay, persisted simulation outputs and retention enforcement remain "
            "Platform work.",
        ],
    )


def _matching_audit_records(
    audit_records: list[AuditEvent],
    workflow: WorkflowRunRecord,
) -> list[AuditEvent]:
    records = [
        event
        for event in audit_records
        if event.payload.get("workflow_id") == workflow.workflow_id
        or event.payload.get("scope") == workflow.audit_scope
    ]
    return sorted(records, key=lambda event: (event.created_at, str(event.id)))


def _build_artifact(
    workflow: WorkflowRunRecord,
    timeline_records: list[WorkflowTimelineRecord],
    audit_records: list[AuditEvent],
) -> ReplayArtifact:
    timeline = [_timeline_event_to_public(event) for event in timeline_records]
    audit_events = [_audit_event_to_ledger_event(event) for event in audit_records]
    evidence_refs = _evidence_refs(workflow, audit_events)

    policy_result = _human_approval_policy(workflow, audit_events, evidence_refs)
    return ReplayArtifact(
        artifact_id=_artifact_id(workflow, timeline, audit_events),
        workflow_id=workflow.workflow_id,
        workflow_name=workflow.name,
        audit_scope=workflow.audit_scope,
        replay_mode="governance-preview",
        replay_ready=workflow.replay_ready,
        determinism_status=_determinism_status(workflow, timeline, audit_events),
        timeline_event_count=len(timeline),
        audit_event_count=len(audit_events),
        evidence_refs=evidence_refs,
        timeline=timeline,
        audit_events=audit_events,
        policy_results=[policy_result],
        policy_set_diffs=[
            _connector_policy_set_diff(
                workflow=workflow,
                timeline=timeline,
                audit_events=audit_events,
                evidence_refs=evidence_refs,
            )
        ],
    )


def _artifact_id(
    workflow: WorkflowRunRecord,
    timeline: list[WorkflowTimelineEvent],
    audit_events: list[AuditLedgerEvent],
) -> str:
    payload = {
        "workflow_id": workflow.workflow_id,
        "timeline": [event.model_dump(mode="json") for event in timeline],
        "audit": [event.audit_event_id for event in audit_events],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"replay-{workflow.workflow_id}-{checksum}"


def _determinism_status(
    workflow: WorkflowRunRecord,
    timeline: list[WorkflowTimelineEvent],
    audit_events: list[AuditLedgerEvent],
) -> str:
    if workflow.replay_ready and timeline and audit_events:
        return "replay_ready"
    if timeline or audit_events:
        return "preview_only"
    return "insufficient_history"


def _evidence_refs(
    workflow: WorkflowRunRecord,
    audit_events: list[AuditLedgerEvent],
) -> list[str]:
    refs = {workflow.workflow_id, workflow.audit_scope, workflow.related_risk}
    refs.update(str(asset) for asset in workflow.related_assets)
    for signal in workflow.pending_signals:
        approval_id = signal.get("approval_id")
        if approval_id:
            refs.add(str(approval_id))
    for event in audit_events:
        refs.update(event.evidence_refs)
        if event.related_approval_id:
            refs.add(event.related_approval_id)
    return sorted(refs)


def _human_approval_policy(
    workflow: WorkflowRunRecord,
    audit_events: list[AuditLedgerEvent],
    evidence_refs: list[str],
) -> PolicySimulationResult:
    has_waiting_signal = any(
        signal.get("status") == "waiting" for signal in workflow.pending_signals
    )
    has_approval_required_event = any(
        event.severity == OverviewStatus.ACTION_REQUIRED for event in audit_events
    )
    simulated_decision = (
        "blocked_until_human_approval"
        if has_waiting_signal or has_approval_required_event
        else "no_block"
    )
    return PolicySimulationResult(
        policy_id="human-approval-required",
        policy_name="Human approval before external mutation",
        baseline_decision=workflow.state,
        simulated_decision=simulated_decision,
        changed_outcome=workflow.state != simulated_decision,
        evidence_refs=evidence_refs[:8],
        summary=(
            "Replay preview keeps the workflow blocked until the required owner signal "
            "is approved."
            if simulated_decision == "blocked_until_human_approval"
            else "Replay preview finds no pending human approval gate for this workflow."
        ),
    )


def _connector_policy_set_diff(
    workflow: WorkflowRunRecord,
    timeline: list[WorkflowTimelineEvent],
    audit_events: list[AuditLedgerEvent],
    evidence_refs: list[str],
) -> PolicySetVersionDiff:
    changed_policy_ids = ["connector.asset.required"]
    historical_event_count = len(timeline) + len(audit_events)
    return PolicySetVersionDiff(
        diff_id=_policy_set_diff_id(workflow, audit_events),
        connector_id="file_csv_manufacturing_assets",
        baseline_policy_set_id="policy_set_connector_asset_required_20260622_v2",
        baseline_policy_set_version="2026-06-22.2",
        candidate_policy_set_id="policy_set_connector_asset_required_20260622_rollback",
        candidate_policy_set_version="2026-06-22.3",
        historical_event_count=historical_event_count,
        changed_policy_ids=changed_policy_ids,
        baseline_decision="allow_after_manifest_validation",
        candidate_decision="block_until_required_asset_gate",
        changed_outcome=True,
        diff_status="changed_outcome_detected",
        audit_event_type="connector.promotion_policy_set.simulated_diff",
        evidence_refs=evidence_refs[:8],
        summary=(
            "Historical workflow and audit evidence would be re-gated by the rollback "
            "policy set before connector promotion."
        ),
    )


def _policy_set_diff_id(
    workflow: WorkflowRunRecord,
    audit_events: list[AuditLedgerEvent],
) -> str:
    payload = {
        "workflow_id": workflow.workflow_id,
        "baseline_policy_set_id": "policy_set_connector_asset_required_20260622_v2",
        "candidate_policy_set_id": "policy_set_connector_asset_required_20260622_rollback",
        "audit": [event.audit_event_id for event in audit_events],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"policy-set-diff-{workflow.workflow_id}-{checksum}"


def _as_of(artifacts: list[ReplayArtifact]) -> str:
    timestamps = [
        event.at
        for artifact in artifacts
        for event in artifact.timeline
    ] + [
        event.occurred_at
        for artifact in artifacts
        for event in artifact.audit_events
    ]
    if timestamps:
        return max(timestamps)
    return "2026-06-21T16:30:00+02:00"


def _metrics(artifacts: list[ReplayArtifact]) -> list[OverviewMetric]:
    history_events = sum(
        artifact.timeline_event_count + artifact.audit_event_count for artifact in artifacts
    )
    policy_results = sum(len(artifact.policy_results) for artifact in artifacts)
    policy_set_diffs = sum(len(artifact.policy_set_diffs) for artifact in artifacts)
    ready_artifacts = sum(
        artifact.determinism_status == "replay_ready" for artifact in artifacts
    )
    return [
        OverviewMetric(
            label="Replay Artifacts",
            value=str(len(artifacts)),
            detail="Workflow histories with matching audit evidence",
            status=OverviewStatus.READY if artifacts else OverviewStatus.WATCH,
        ),
        OverviewMetric(
            label="History Events",
            value=str(history_events),
            detail="Timeline and audit events included in replay previews",
            status=OverviewStatus.READY if history_events else OverviewStatus.WATCH,
        ),
        OverviewMetric(
            label="Policy Simulations",
            value=str(policy_results),
            detail="Deterministic policy previews evaluated against history",
            status=OverviewStatus.READY if policy_results else OverviewStatus.WATCH,
        ),
        OverviewMetric(
            label="Policy Set Diffs",
            value=str(policy_set_diffs),
            detail="Versioned connector policy-set comparisons over historical events",
            status=OverviewStatus.READY if policy_set_diffs else OverviewStatus.WATCH,
        ),
        OverviewMetric(
            label="Deterministic Replay",
            value=str(ready_artifacts),
            detail="Full Temporal replay remains behind a future runtime path",
            status=OverviewStatus.WATCH,
        ),
    ]
