from uuid import uuid4

import pytest

from axis_worker.workflows.approval_workflow import (
    ApprovalDecisionSignalError,
    ApprovalWorkflow,
    normalize_approval_decision_signal,
)


def decision_payload(*, decision: str = "approve", event_id: str | None = None) -> dict:
    return {
        "schema_version": "axis.approval-decision.v1",
        "decision_event_id": event_id or str(uuid4()),
        "tenant_id": "tenant_demo",
        "workflow_id": "wf_supplier_delay",
        "approval_id": "appr_expedite",
        "decision": decision,
        "approved": decision == "approve",
        "actor_id": "plant-operations-owner-role",
        "note": "Reviewed against current evidence.",
        "decided_at": "2026-07-18T14:00:00+00:00",
    }


@pytest.mark.parametrize(
    ("legacy_value", "expected_decision"),
    [(True, "approve"), (False, "reject")],
)
def test_normalize_approval_decision_signal_keeps_legacy_boolean_compatibility(
    legacy_value: bool,
    expected_decision: str,
) -> None:
    normalized = normalize_approval_decision_signal(legacy_value)

    assert normalized["schema_version"] == "legacy-boolean.v0"
    assert normalized["decision"] == expected_decision
    assert normalized["approved"] is legacy_value


def test_normalize_approval_decision_signal_preserves_request_changes() -> None:
    normalized = normalize_approval_decision_signal(decision_payload(decision="request_changes"))

    assert normalized["decision"] == "request_changes"
    assert normalized["approved"] is False


def test_normalize_approval_decision_signal_rejects_inconsistent_boolean_projection() -> None:
    payload = decision_payload(decision="reject")
    payload["approved"] = True

    with pytest.raises(ApprovalDecisionSignalError, match="does not match"):
        normalize_approval_decision_signal(payload)


def test_normalize_approval_decision_signal_rejects_oversized_note() -> None:
    payload = decision_payload()
    payload["note"] = "x" * 601

    with pytest.raises(ApprovalDecisionSignalError, match="up to 600"):
        normalize_approval_decision_signal(payload)


@pytest.mark.asyncio
async def test_duplicate_identical_decision_event_is_a_noop() -> None:
    workflow = ApprovalWorkflow()
    payload = decision_payload()

    await workflow.approve(payload)
    await workflow.approve(dict(payload))

    assert workflow._decision == payload
    assert workflow._duplicate_delivery_count == 1
    assert workflow._conflicting_delivery_count == 0


@pytest.mark.asyncio
async def test_mutated_payload_for_same_event_id_does_not_overwrite_terminal_decision() -> None:
    workflow = ApprovalWorkflow()
    accepted = decision_payload(decision="approve")
    conflicting = decision_payload(
        decision="reject",
        event_id=accepted["decision_event_id"],
    )

    await workflow.approve(accepted)
    await workflow.approve(conflicting)

    assert workflow._decision == accepted
    assert workflow._duplicate_delivery_count == 0
    assert workflow._conflicting_delivery_count == 1


@pytest.mark.asyncio
async def test_different_terminal_event_does_not_overwrite_first_decision() -> None:
    workflow = ApprovalWorkflow()
    accepted = decision_payload(decision="request_changes")

    await workflow.approve(accepted)
    await workflow.approve(decision_payload(decision="approve"))

    assert workflow._decision == accepted
    assert workflow._decision["decision"] == "request_changes"
    assert workflow._conflicting_delivery_count == 1
