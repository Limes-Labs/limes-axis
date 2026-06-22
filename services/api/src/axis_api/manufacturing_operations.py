from datetime import UTC

from pydantic import BaseModel, Field

from axis_api.demo import OverviewMetric, OverviewStatus
from axis_api.models import ManufacturingOperationRecord
from axis_api.persistence import AxisPersistenceRepository


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
