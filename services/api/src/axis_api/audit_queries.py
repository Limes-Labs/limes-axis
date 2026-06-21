from datetime import UTC
from typing import Any

from pydantic import BaseModel, Field

from axis_api.demo import (
    AuditFilterOptions,
    AuditLedgerEvent,
    ManufacturingAuditExplorer,
    OverviewMetric,
    OverviewStatus,
)
from axis_api.models import AuditEvent
from axis_api.persistence import AxisPersistenceRepository


class AuditEventQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    event_type: str | None = Field(default=None, min_length=1)
    actor_id: str | None = Field(default=None, min_length=1)
    scope: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


def _string_value(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return ",".join(_string_value(item) for item in value[:4])
    if isinstance(value, dict):
        return ",".join(sorted(value.keys())[:4]) or "object"
    return str(value)


def _first_payload_value(payload: dict, keys: list[str], default: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return _string_value(value)
    return default


def _actor_type(actor_id: str) -> str:
    if actor_id.startswith("agent_") or actor_id.endswith("-agent"):
        return "agent"
    if "role" in actor_id:
        return "role"
    return "service"


def _category(event_type: str, payload: dict) -> str:
    category = payload.get("category")
    if isinstance(category, str) and category:
        return category
    return event_type.split(".", maxsplit=1)[0]


def _scope(event: AuditEvent) -> str:
    return _first_payload_value(
        event.payload,
        ["scope", "workflow_id", "approval_id", "action_id", "idempotency_key"],
        event.event_type,
    )


def _result(payload: dict) -> str:
    return _first_payload_value(
        payload,
        ["status", "decision", "result", "workflow_signal_status"],
        "recorded",
    )


def _severity(payload: dict, result: str) -> OverviewStatus:
    if payload.get("approval_required") is True:
        return OverviewStatus.ACTION_REQUIRED
    if result in {
        "approval_required",
        "pending",
        "runtime_signal_unavailable",
        "waiting_for_approval",
    }:
        return OverviewStatus.ACTION_REQUIRED
    if "unavailable" in result or "failed" in result or "request_changes" in result:
        return OverviewStatus.WATCH
    return OverviewStatus.READY


def _summary(event: AuditEvent, scope: str, result: str) -> str:
    return f"Persisted {event.event_type} for {scope} with result {result}."


def _evidence_refs(payload: dict, fallback: str) -> list[str]:
    refs = []
    for key in [
        "workflow_id",
        "approval_id",
        "action_id",
        "action_run_id",
        "idempotency_key",
        "required_permission",
    ]:
        value = payload.get(key)
        if value:
            refs.append(_string_value(value))
    return refs or [fallback]


def _payload_preview(payload: dict) -> dict[str, str]:
    preview_keys = [
        "action_id",
        "approval_id",
        "workflow_id",
        "decision",
        "status",
        "execution_mode",
        "idempotency_key",
        "workflow_signal_status",
        "permission_decision",
        "payload_field_names",
    ]
    preview = {
        key: _string_value(payload[key])
        for key in preview_keys
        if key in payload and payload[key] is not None
    }
    if not preview:
        preview = {"payload_keys": ",".join(sorted(payload.keys())[:6]) or "none"}
    return preview


def _audit_event_to_ledger_event(event: AuditEvent) -> AuditLedgerEvent:
    scope = _scope(event)
    result = _result(event.payload)
    occurred_at = event.created_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    return AuditLedgerEvent(
        audit_event_id=str(event.id),
        occurred_at=occurred_at.astimezone(UTC).isoformat(),
        tenant_id=event.tenant_id,
        actor_id=event.actor_id,
        actor_type=_actor_type(event.actor_id),
        event_type=event.event_type,
        category=_category(event.event_type, event.payload),
        domain=_first_payload_value(event.payload, ["domain", "risk_level"], "Operations"),
        scope=scope,
        result=result,
        severity=_severity(event.payload, result),
        source=_first_payload_value(event.payload, ["source"], "Axis API"),
        summary=_summary(event, scope, result),
        permission_scope=_first_payload_value(
            event.payload,
            ["required_permission", "permission_scope"],
            "audit:read",
        ),
        data_classification="public-demo",
        related_workflow_id=event.payload.get("workflow_id"),
        related_approval_id=event.payload.get("approval_id"),
        related_agent_id=event.payload.get("agent_id"),
        evidence_refs=_evidence_refs(event.payload, event.event_type),
        payload_preview=_payload_preview(event.payload),
    )


def _filter_options(events: list[AuditLedgerEvent], tenant_id: str) -> AuditFilterOptions:
    return AuditFilterOptions(
        tenants=sorted({event.tenant_id for event in events}) or [tenant_id],
        event_types=sorted({event.event_type for event in events}),
        scopes=sorted({event.scope for event in events}),
        actors=sorted({event.actor_id for event in events}),
        categories=sorted({event.category for event in events}),
    )


def _metrics(events: list[AuditLedgerEvent]) -> list[OverviewMetric]:
    action_required_count = sum(
        event.severity == OverviewStatus.ACTION_REQUIRED for event in events
    )
    return [
        OverviewMetric(
            label="Persisted Events",
            value=str(len(events)),
            detail="Append-only audit events read from Postgres",
            status=OverviewStatus.READY if events else OverviewStatus.WATCH,
        ),
        OverviewMetric(
            label="Action Required",
            value=str(action_required_count),
            detail="Persisted events currently marked as requiring attention",
            status=(
                OverviewStatus.ACTION_REQUIRED
                if action_required_count
                else OverviewStatus.READY
            ),
        ),
        OverviewMetric(
            label="Query Source",
            value="Postgres",
            detail="Tenant-scoped query over audit_events",
            status=OverviewStatus.READY,
        ),
        OverviewMetric(
            label="Replay",
            value="Pending",
            detail="Events are queryable, but replay is not implemented yet",
            status=OverviewStatus.WATCH,
        ),
    ]


def query_persisted_audit_events(
    repository: AxisPersistenceRepository,
    query: AuditEventQuery,
) -> ManufacturingAuditExplorer:
    records = repository.list_audit_events(
        tenant_id=query.tenant_id,
        event_type=query.event_type,
        actor_id=query.actor_id,
        limit=query.limit,
    )
    events = [_audit_event_to_ledger_event(record) for record in records]
    if query.scope is not None:
        events = [event for event in events if event.scope == query.scope]

    return ManufacturingAuditExplorer(
        tenant_id=query.tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of=events[0].occurred_at if events else "2026-06-21T16:30:00+02:00",
        ledger_status=OverviewStatus.READY if events else OverviewStatus.WATCH,
        metrics=_metrics(events),
        filter_options=_filter_options(events, query.tenant_id),
        events=events,
        retention_notes=[
            "This view is backed by persisted append-only audit events.",
            "Payload previews expose governed field summaries, not raw sensitive payloads.",
            "Queries are tenant-scoped before optional event, actor and scope filters.",
            "Export, retention policy enforcement and replay remain Platform work.",
        ],
    )
