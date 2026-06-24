from datetime import UTC
from hashlib import sha256
from uuid import UUID

from pydantic import BaseModel, Field

from axis_api.audit import AuditEventCreate
from axis_api.demo import OverviewMetric, OverviewStatus
from axis_api.models import (
    ManufacturingDailyBrief,
    ManufacturingOperationRecord,
    ManufacturingRiskScenario,
)
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import (
    AxisPersistenceRepository,
    ManufacturingDailyBriefCreate,
    ManufacturingRiskScenarioCreate,
)

DAILY_BRIEF_REQUIRED_SCOPES = ["briefs:generate", "audit:read", "workflows:read"]
QUALITY_RISK_REQUIRED_SCOPES = ["quality:read", "workflows:read", "audit:read"]


class DailyPlantBriefPermissionDenied(PermissionError):
    def __init__(self, decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


class DailyPlantBriefValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class DailyPlantBriefIdempotencyConflict(ValueError):
    def __init__(self, brief_id: str) -> None:
        super().__init__("Idempotency key already exists with a different request")
        self.brief_id = brief_id


class QualityRiskScenarioPermissionDenied(PermissionError):
    def __init__(self, decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


class QualityRiskScenarioValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class QualityRiskScenarioIdempotencyConflict(ValueError):
    def __init__(self, scenario_id: str) -> None:
        super().__init__("Idempotency key already exists with a different request")
        self.scenario_id = scenario_id


class ManufacturingOperationRecordView(BaseModel):
    record_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    record_type: str = Field(min_length=1)
    source_system: str = Field(min_length=1)
    status: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    related_asset: str | None = None
    workflow_id: str | None = None
    risk_level: str | None = None


class ManufacturingOperationsDataset(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    metrics: list[OverviewMetric]
    domains: list[str]
    source_systems: list[str]
    records: list[ManufacturingOperationRecordView]
    notes: list[str] = Field(default_factory=list)


class ManufacturingOperationQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    domain: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    record_type: str | None = Field(default=None, min_length=1)
    source_system: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


class DailyPlantBriefRequest(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    brief_date: str = Field(min_length=1, max_length=40)
    requested_by: str = Field(default="agent_daily_brief", min_length=1)
    actor_scopes: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=220)
    source_record_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=200)


class QualityRiskScenarioRequest(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    requested_by: str = Field(default="agent_quality_risk", min_length=1)
    actor_scopes: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=220)
    source_record_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=200)


class DailyPlantBriefRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    brief_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    brief_date: str = Field(min_length=1)
    status: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    required_scopes: list[str]
    source_record_ids: list[str]
    summary_payload: dict
    permission_decision: PermissionDecision
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    idempotent_replay: bool = False


class QualityRiskScenarioRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    status: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    workflow_ids: list[str]
    source_record_ids: list[str]
    scenario_payload: dict
    permission_decision: PermissionDecision
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    idempotent_replay: bool = False


def _isoformat_utc(value) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _operation_record_to_public(
    record: ManufacturingOperationRecord,
) -> ManufacturingOperationRecordView:
    return ManufacturingOperationRecordView(
        record_id=record.record_id,
        domain=record.domain,
        record_type=record.record_type,
        source_system=record.source_system,
        status=record.status,
        owner_role=record.owner_role,
        related_asset=record.related_asset,
        workflow_id=record.workflow_id,
        risk_level=record.risk_level,
        occurred_at=_isoformat_utc(record.occurred_at),
        payload=record.payload,
        evidence_refs=record.evidence_refs,
    )


def _brief_record_to_public(
    brief: ManufacturingDailyBrief,
    *,
    idempotent_replay: bool,
) -> DailyPlantBriefRecord:
    return DailyPlantBriefRecord(
        tenant_id=brief.tenant_id,
        brief_id=brief.brief_id,
        idempotency_key=brief.idempotency_key,
        brief_date=brief.brief_date,
        status=brief.status,
        requested_by=brief.requested_by,
        required_scopes=brief.required_scopes,
        source_record_ids=brief.source_record_ids,
        summary_payload=brief.summary_payload,
        permission_decision=PermissionDecision.model_validate(brief.permission_decision),
        audit_event_id=brief.audit_event_id,
        audit_event_type=brief.audit_event_type,
        idempotent_replay=idempotent_replay,
    )


def _risk_scenario_to_public(
    scenario: ManufacturingRiskScenario,
    *,
    idempotent_replay: bool,
) -> QualityRiskScenarioRecord:
    return QualityRiskScenarioRecord(
        tenant_id=scenario.tenant_id,
        scenario_id=scenario.scenario_id,
        idempotency_key=scenario.idempotency_key,
        domain=scenario.domain,
        status=scenario.status,
        risk_level=scenario.risk_level,
        requested_by=scenario.requested_by,
        owner_role=scenario.owner_role,
        workflow_ids=scenario.workflow_ids,
        source_record_ids=scenario.source_record_ids,
        scenario_payload=scenario.scenario_payload,
        permission_decision=PermissionDecision.model_validate(scenario.permission_decision),
        audit_event_id=scenario.audit_event_id,
        audit_event_type=scenario.audit_event_type,
        idempotent_replay=idempotent_replay,
    )


def _metric_status(records: list[ManufacturingOperationRecordView]) -> OverviewStatus:
    if any(record.status == "action_required" for record in records):
        return OverviewStatus.ACTION_REQUIRED
    if any(record.status == "watch" for record in records):
        return OverviewStatus.WATCH
    return OverviewStatus.READY


def _metrics(records: list[ManufacturingOperationRecordView]) -> list[OverviewMetric]:
    action_required = sum(1 for record in records if record.status == "action_required")
    watch = sum(1 for record in records if record.status == "watch")
    domains = sorted({record.domain for record in records})
    source_systems = sorted({record.source_system for record in records})
    return [
        OverviewMetric(
            label="Operational Records",
            value=str(len(records)),
            detail="Tenant-scoped manufacturing records read from Postgres",
            status=OverviewStatus.READY if records else OverviewStatus.WATCH,
        ),
        OverviewMetric(
            label="Action Required",
            value=str(action_required),
            detail="Records currently blocking or escalating an operating decision",
            status=(
                OverviewStatus.ACTION_REQUIRED
                if action_required
                else OverviewStatus.READY
            ),
        ),
        OverviewMetric(
            label="Watch",
            value=str(watch),
            detail="Records that require owner monitoring before mutation",
            status=OverviewStatus.WATCH if watch else OverviewStatus.READY,
        ),
        OverviewMetric(
            label="Coverage",
            value=f"{len(domains)} domains",
            detail=f"{len(source_systems)} source systems represented",
            status=_metric_status(records),
        ),
    ]


def query_manufacturing_operations_dataset(
    repository: AxisPersistenceRepository,
    query: ManufacturingOperationQuery,
) -> ManufacturingOperationsDataset:
    records = [
        _operation_record_to_public(record)
        for record in repository.list_manufacturing_operation_records(
            tenant_id=query.tenant_id,
            domain=query.domain,
            status=query.status,
            record_type=query.record_type,
            source_system=query.source_system,
            limit=query.limit,
        )
    ]
    as_of = records[0].occurred_at if records else "2026-06-22T00:00:00+00:00"
    return ManufacturingOperationsDataset(
        tenant_id=query.tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of=as_of,
        metrics=_metrics(records),
        domains=sorted({record.domain for record in records}),
        source_systems=sorted({record.source_system for record in records}),
        records=records,
        notes=[
            "This view is backed by tenant-scoped manufacturing operation records.",
            "Records are public-safe operational references, not browser fallbacks.",
            "Source payloads are redacted to business metadata before API exposure.",
        ],
    )


def _daily_brief_idempotency_key(request: DailyPlantBriefRequest) -> str:
    if request.idempotency_key is not None:
        return request.idempotency_key
    return f"{request.tenant_id}:daily-plant-brief:{request.brief_date}:{request.requested_by}"


def _daily_brief_request_fingerprint(request: DailyPlantBriefRequest) -> dict:
    return {
        "brief_date": request.brief_date,
        "requested_by": request.requested_by,
        "source_record_ids": sorted(request.source_record_ids),
        "limit": request.limit,
    }


def _evaluate_daily_brief_permission(
    request: DailyPlantBriefRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            actor_scopes=request.actor_scopes,
            required_scopes=DAILY_BRIEF_REQUIRED_SCOPES,
            relationship_scopes=[],
            attributes={
                "brief_date": request.brief_date,
                "source_record_ids": request.source_record_ids,
                "operation": "manufacturing.daily_plant_brief.generate",
            },
        )
    )
    if not decision.allowed:
        raise DailyPlantBriefPermissionDenied(decision)
    return decision


def _select_daily_brief_records(
    repository: AxisPersistenceRepository,
    request: DailyPlantBriefRequest,
) -> list[ManufacturingOperationRecordView]:
    records = [
        _operation_record_to_public(record)
        for record in repository.list_manufacturing_operation_records(
            tenant_id=request.tenant_id,
            limit=request.limit,
        )
    ]
    if request.source_record_ids:
        requested = set(request.source_record_ids)
        records = [record for record in records if record.record_id in requested]
        found = {record.record_id for record in records}
        missing = sorted(requested - found)
        if missing:
            raise DailyPlantBriefValidationError(
                "Daily plant brief source records were not found.",
                f"missing_source_records:{','.join(missing)}",
            )

    if not records:
        raise DailyPlantBriefValidationError(
            "Daily plant brief requires at least one persisted operation record.",
            "no_operation_records",
        )

    return records


def _daily_brief_summary_payload(
    *,
    request: DailyPlantBriefRequest,
    records: list[ManufacturingOperationRecordView],
) -> dict:
    action_required = [record for record in records if record.status == "action_required"]
    watch = [record for record in records if record.status == "watch"]
    domains = sorted({record.domain for record in records})
    source_systems = sorted({record.source_system for record in records})
    top_actions = [
        {
            "record_id": record.record_id,
            "domain": record.domain,
            "status": record.status,
            "owner_role": record.owner_role,
            "related_asset": record.related_asset,
            "workflow_id": record.workflow_id,
            "risk_level": record.risk_level,
        }
        for record in [*action_required, *watch][:5]
    ]
    return {
        "request": _daily_brief_request_fingerprint(request),
        "headline": (
            f"Ravenna Works has {len(action_required)} action-required and "
            f"{len(watch)} watch records across {len(domains)} operational domains."
        ),
        "summary": {
            "record_count": len(records),
            "action_required_count": len(action_required),
            "watch_count": len(watch),
            "domains": domains,
            "source_systems": source_systems,
        },
        "top_actions": top_actions,
        "cited_evidence": sorted({ref for record in records for ref in record.evidence_refs}),
        "source_records": [
            {
                "record_id": record.record_id,
                "domain": record.domain,
                "record_type": record.record_type,
                "source_system": record.source_system,
                "status": record.status,
                "occurred_at": record.occurred_at,
            }
            for record in records
        ],
        "generation_boundary": "deterministic_persisted_records",
        "notes": [
            "Generated from persisted tenant-scoped manufacturing operation records.",
            "No external model provider or source-system mutation is invoked.",
        ],
    }


def _daily_brief_id(request: DailyPlantBriefRequest, source_record_ids: list[str]) -> str:
    digest = sha256(
        "|".join([request.tenant_id, request.brief_date, *sorted(source_record_ids)]).encode()
    ).hexdigest()[:12]
    return f"brief_{request.brief_date.replace('-', '')}_{digest}"


def generate_daily_plant_brief(
    repository: AxisPersistenceRepository,
    request: DailyPlantBriefRequest,
) -> DailyPlantBriefRecord:
    idempotency_key = _daily_brief_idempotency_key(request)
    decision = _evaluate_daily_brief_permission(request)
    existing = repository.get_manufacturing_daily_brief_by_idempotency_key(
        request.tenant_id,
        idempotency_key,
    )
    if existing is not None:
        if existing.summary_payload.get("request") != _daily_brief_request_fingerprint(request):
            raise DailyPlantBriefIdempotencyConflict(existing.brief_id)
        return _brief_record_to_public(existing, idempotent_replay=True)

    records = _select_daily_brief_records(repository, request)
    source_record_ids = [record.record_id for record in records]
    summary_payload = _daily_brief_summary_payload(request=request, records=records)
    brief_id = _daily_brief_id(request, source_record_ids)
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            event_type="manufacturing.daily_brief.generated",
            payload={
                "brief_id": brief_id,
                "brief_date": request.brief_date,
                "source_record_ids": source_record_ids,
                "required_scopes": DAILY_BRIEF_REQUIRED_SCOPES,
                "permission_decision": decision.model_dump(),
            },
        )
    )
    brief = repository.create_manufacturing_daily_brief(
        ManufacturingDailyBriefCreate(
            tenant_id=request.tenant_id,
            brief_id=brief_id,
            idempotency_key=idempotency_key,
            brief_date=request.brief_date,
            requested_by=request.requested_by,
            required_scopes=DAILY_BRIEF_REQUIRED_SCOPES,
            source_record_ids=source_record_ids,
            summary_payload=summary_payload,
            permission_decision=decision.model_dump(),
            audit_event_id=audit_event.id,
        )
    )
    return _brief_record_to_public(brief, idempotent_replay=False)


def _quality_risk_idempotency_key(request: QualityRiskScenarioRequest) -> str:
    if request.idempotency_key is not None:
        return request.idempotency_key
    return f"{request.tenant_id}:quality-risk-scenario:{request.requested_by}"


def _quality_risk_request_fingerprint(request: QualityRiskScenarioRequest) -> dict:
    return {
        "requested_by": request.requested_by,
        "source_record_ids": sorted(request.source_record_ids),
        "limit": request.limit,
    }


def _evaluate_quality_risk_permission(
    request: QualityRiskScenarioRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            actor_scopes=request.actor_scopes,
            required_scopes=QUALITY_RISK_REQUIRED_SCOPES,
            relationship_scopes=[],
            attributes={
                "domain": "Quality",
                "source_record_ids": request.source_record_ids,
                "operation": "manufacturing.quality_risk_scenario.generate",
            },
        )
    )
    if not decision.allowed:
        raise QualityRiskScenarioPermissionDenied(decision)
    return decision


def _select_quality_risk_records(
    repository: AxisPersistenceRepository,
    request: QualityRiskScenarioRequest,
) -> list[ManufacturingOperationRecordView]:
    records = [
        _operation_record_to_public(record)
        for record in repository.list_manufacturing_operation_records(
            tenant_id=request.tenant_id,
            domain="Quality",
            limit=request.limit,
        )
    ]
    if request.source_record_ids:
        requested = set(request.source_record_ids)
        records = [record for record in records if record.record_id in requested]
        found = {record.record_id for record in records}
        missing = sorted(requested - found)
        if missing:
            raise QualityRiskScenarioValidationError(
                "Quality risk scenario source records were not found.",
                f"missing_source_records:{','.join(missing)}",
            )

    if not records:
        raise QualityRiskScenarioValidationError(
            "Quality risk scenario requires at least one persisted quality operation record.",
            "no_quality_operation_records",
        )
    return records


def _quality_risk_level(records: list[ManufacturingOperationRecordView]) -> str:
    risk_levels = {record.risk_level for record in records}
    if "critical" in risk_levels:
        return "critical"
    if "high" in risk_levels:
        return "high"
    if any(record.status == "action_required" for record in records):
        return "high"
    if "medium" in risk_levels or any(record.status == "watch" for record in records):
        return "medium"
    return "low"


def _quality_risk_payload(
    *,
    request: QualityRiskScenarioRequest,
    records: list[ManufacturingOperationRecordView],
    risk_level: str,
) -> dict:
    workflow_ids = sorted({record.workflow_id for record in records if record.workflow_id})
    evidence_refs = sorted({ref for record in records for ref in record.evidence_refs})
    assets = sorted({record.related_asset for record in records if record.related_asset})
    owner_roles = sorted({record.owner_role for record in records})
    return {
        "request": _quality_risk_request_fingerprint(request),
        "headline": (
            f"Quality risk scenario is {risk_level} across {len(records)} "
            "persisted quality records."
        ),
        "domain": "Quality",
        "risk_level": risk_level,
        "owner_roles": owner_roles,
        "related_assets": assets,
        "workflow_ids": workflow_ids,
        "recommended_controls": [
            "Keep quality owner review before any hold or release decision.",
            "Cite QMS and batch genealogy evidence before workflow mutation.",
            "Maintain no-external-egress policy for quality-risk analysis.",
        ],
        "cited_evidence": evidence_refs,
        "source_records": [
            {
                "record_id": record.record_id,
                "record_type": record.record_type,
                "status": record.status,
                "risk_level": record.risk_level,
                "owner_role": record.owner_role,
                "related_asset": record.related_asset,
                "workflow_id": record.workflow_id,
                "source_system": record.source_system,
                "occurred_at": record.occurred_at,
            }
            for record in records
        ],
        "generation_boundary": "deterministic_persisted_quality_records",
        "notes": [
            "Generated from persisted tenant-scoped quality operation records.",
            "No QMS mutation, model provider call or approval decision is performed.",
        ],
    }


def _quality_scenario_id(
    request: QualityRiskScenarioRequest,
    source_record_ids: list[str],
) -> str:
    digest = sha256(
        "|".join([request.tenant_id, "quality", *sorted(source_record_ids)]).encode()
    ).hexdigest()[:12]
    return f"quality_risk_{digest}"


def generate_quality_risk_scenario(
    repository: AxisPersistenceRepository,
    request: QualityRiskScenarioRequest,
) -> QualityRiskScenarioRecord:
    idempotency_key = _quality_risk_idempotency_key(request)
    decision = _evaluate_quality_risk_permission(request)
    existing = repository.get_manufacturing_risk_scenario_by_idempotency_key(
        request.tenant_id,
        idempotency_key,
    )
    if existing is not None:
        if existing.scenario_payload.get("request") != _quality_risk_request_fingerprint(
            request
        ):
            raise QualityRiskScenarioIdempotencyConflict(existing.scenario_id)
        return _risk_scenario_to_public(existing, idempotent_replay=True)

    records = _select_quality_risk_records(repository, request)
    source_record_ids = [record.record_id for record in records]
    risk_level = _quality_risk_level(records)
    scenario_id = _quality_scenario_id(request, source_record_ids)
    scenario_payload = _quality_risk_payload(
        request=request,
        records=records,
        risk_level=risk_level,
    )
    workflow_ids = sorted({record.workflow_id for record in records if record.workflow_id})
    owner_roles = sorted({record.owner_role for record in records})
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            event_type="manufacturing.risk_scenario.generated",
            payload={
                "scenario_id": scenario_id,
                "domain": "Quality",
                "risk_level": risk_level,
                "source_record_ids": source_record_ids,
                "workflow_ids": workflow_ids,
                "required_scopes": QUALITY_RISK_REQUIRED_SCOPES,
                "permission_decision": decision.model_dump(),
            },
        )
    )
    scenario = repository.create_manufacturing_risk_scenario(
        ManufacturingRiskScenarioCreate(
            tenant_id=request.tenant_id,
            scenario_id=scenario_id,
            idempotency_key=idempotency_key,
            domain="Quality",
            risk_level=risk_level,
            requested_by=request.requested_by,
            owner_role=owner_roles[0] if owner_roles else "quality-owner",
            workflow_ids=workflow_ids,
            source_record_ids=source_record_ids,
            scenario_payload=scenario_payload,
            permission_decision=decision.model_dump(),
            audit_event_id=audit_event.id,
        )
    )
    return _risk_scenario_to_public(scenario, idempotent_replay=False)
