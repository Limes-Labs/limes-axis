"""Quickstart for the Limes Axis Python SDK against a local Axis API."""

import os
import uuid

from axis_sdk import AxisClient, AxisError, PolicyViolationError

BASE_URL = os.environ.get("AXIS_BASE_URL", "http://127.0.0.1:8000")
BEARER_TOKEN = os.environ.get("AXIS_BEARER_TOKEN")
TENANT_ID = os.environ.get("AXIS_TENANT_ID", "tenant_demo_manufacturing")


def main() -> None:
    with AxisClient(BASE_URL, token=BEARER_TOKEN, tenant_id=TENANT_ID) as client:
        health = client.system.health()
        ready = client.system.ready()
        print(f"API: {health.service} status={health.status} readiness={ready.status}")

        inbox = client.approvals.list()
        print(f"\nApproval inbox ({len(inbox.approvals)} pending):")
        for approval in inbox.approvals:
            print(f"  - {approval.approval_id}: {approval.action} [{approval.risk_level}]")

        catalog = client.actions.catalog()
        print(f"\nAction catalog ({len(catalog.actions)} actions):")
        for entry in catalog.actions:
            definition = entry.definition
            print(
                f"  - {definition.action_id}: {definition.display_name} "
                f"(risk={definition.risk_level}, approval={definition.approval_mode})"
            )

        idempotency_key = f"sdk-quickstart-{uuid.uuid4().hex[:12]}"
        run = client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            idempotency_key=idempotency_key,
            payload={
                "supplier_batch_id": "asset_motors_batch",
                "target_arrival": "2026-06-22T08:00:00+02:00",
                "reason": "Line 2 packaging risk",
                "cost_ceiling_eur": "1200",
            },
        )
        print(
            f"\nAction run {run.action_run_id}: status={run.status} "
            f"approval_required={run.approval_required} key={run.idempotency_key}"
        )

        try:
            client.actions.create_run(
                "request_supplier_expedite",
                actor_id="agent_supply_risk",
                actor_scopes=["supply:read", "approvals:supply:request"],
                idempotency_key=idempotency_key,
                payload={
                    "supplier_batch_id": "asset_motors_batch",
                    "target_arrival": "2026-06-23T08:00:00+02:00",
                    "reason": "Different payload with the same key",
                    "cost_ceiling_eur": "1500",
                },
            )
        except PolicyViolationError as error:
            print(
                "Idempotency conflict was rejected as expected: "
                f"code={error.code} request_id={error.request_id}"
            )

        runs = client.workflows.list_runs()
        print(f"\nPersisted workflow runs ({len(runs.workflow_runs)}):")
        for workflow_run in runs.workflow_runs:
            print(
                f"  - {workflow_run.workflow_id}: state={workflow_run.state} "
                f"timeline_events={len(workflow_run.timeline)}"
            )

        events = client.audit.query_events(limit=10)
        print(f"\nRecent audit events ({len(events.events)}):")
        for event in events.events:
            print(f"  - {event.event_type} by {event.actor_id} at {event.occurred_at}")


if __name__ == "__main__":
    try:
        main()
    except AxisError as error:
        raise SystemExit(f"Axis API request failed: {error}") from error
