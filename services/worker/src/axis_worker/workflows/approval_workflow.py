from typing import Any
from uuid import UUID

from temporalio import workflow

APPROVAL_DECISION_SCHEMA_VERSION = "axis.approval-decision.v1"
_DECISIONS = frozenset({"approve", "reject", "request_changes"})


class ApprovalDecisionSignalError(ValueError):
    pass


def normalize_approval_decision_signal(signal: bool | dict[str, Any]) -> dict[str, Any]:
    """Normalize both the legacy boolean and governed v1 signal contracts."""
    if isinstance(signal, bool):
        decision = "approve" if signal else "reject"
        return {
            "schema_version": "legacy-boolean.v0",
            "decision_event_id": f"legacy:{decision}",
            "tenant_id": None,
            "workflow_id": None,
            "approval_id": None,
            "decision": decision,
            "approved": signal,
            "actor_id": None,
            "note": None,
            "decided_at": None,
        }
    if not isinstance(signal, dict):
        raise ApprovalDecisionSignalError("approval decision signal must be a boolean or object")
    if signal.get("schema_version") != APPROVAL_DECISION_SCHEMA_VERSION:
        raise ApprovalDecisionSignalError("unsupported approval decision schema version")

    required_strings = (
        "decision_event_id",
        "tenant_id",
        "workflow_id",
        "approval_id",
        "decision",
    )
    for field_name in required_strings:
        if not isinstance(signal.get(field_name), str) or not signal[field_name]:
            raise ApprovalDecisionSignalError(f"{field_name} must be a non-empty string")
    try:
        UUID(signal["decision_event_id"])
    except ValueError as exc:
        raise ApprovalDecisionSignalError("decision_event_id must be a UUID") from exc

    decision = signal["decision"]
    if decision not in _DECISIONS:
        raise ApprovalDecisionSignalError("unsupported approval decision")
    approved = signal.get("approved")
    if not isinstance(approved, bool) or approved != (decision == "approve"):
        raise ApprovalDecisionSignalError("approved flag does not match decision")
    actor_id = signal.get("actor_id")
    note = signal.get("note")
    decided_at = signal.get("decided_at")
    if actor_id is not None and (not isinstance(actor_id, str) or not actor_id):
        raise ApprovalDecisionSignalError("actor_id must be null or a non-empty string")
    if note is not None and (not isinstance(note, str) or len(note) > 600):
        raise ApprovalDecisionSignalError("note must be null or a string up to 600 characters")
    if decided_at is not None and (not isinstance(decided_at, str) or not decided_at):
        raise ApprovalDecisionSignalError("decided_at must be null or a non-empty string")

    return {
        "schema_version": APPROVAL_DECISION_SCHEMA_VERSION,
        "decision_event_id": signal["decision_event_id"],
        "tenant_id": signal["tenant_id"],
        "workflow_id": signal["workflow_id"],
        "approval_id": signal["approval_id"],
        "decision": decision,
        "approved": approved,
        "actor_id": actor_id,
        "note": note,
        "decided_at": decided_at,
    }


@workflow.defn
class ApprovalWorkflow:
    def __init__(self) -> None:
        self._decision: dict[str, Any] | None = None
        self._legacy_delivery = False
        self._duplicate_delivery_count = 0
        self._conflicting_delivery_count = 0
        self._invalid_delivery_count = 0

    @workflow.run
    async def run(self, payload: dict) -> dict:
        await workflow.wait_condition(lambda: self._decision is not None)
        assert self._decision is not None
        status = {
            "approve": "approved",
            "reject": "rejected",
            "request_changes": "changes_requested",
        }[self._decision["decision"]]
        # Preserve the result shape consumed by workflows started before the
        # governed payload rollout. New senders receive the richer evidence.
        if self._legacy_delivery:
            return {"status": status, "payload": payload}
        return {
            "status": status,
            "payload": payload,
            "decision": self._decision,
            "delivery": {
                "duplicate_count": self._duplicate_delivery_count,
                "conflict_count": self._conflicting_delivery_count,
                "invalid_count": self._invalid_delivery_count,
            },
        }

    @workflow.signal
    async def approve(self, signal: bool | dict[str, Any]) -> None:
        await self._accept_decision(signal)

    @workflow.signal(name="approval_decided_v1")
    async def approval_decided_v1(self, signal: dict[str, Any]) -> None:
        await self._accept_decision(signal)

    async def _accept_decision(self, signal: bool | dict[str, Any]) -> None:
        try:
            decision = normalize_approval_decision_signal(signal)
        except ApprovalDecisionSignalError:
            self._invalid_delivery_count += 1
            return
        if self._decision is None:
            self._decision = decision
            self._legacy_delivery = isinstance(signal, bool)
            return
        if (
            decision["decision_event_id"] == self._decision["decision_event_id"]
            and decision == self._decision
        ):
            self._duplicate_delivery_count += 1
            return
        # Terminal decisions are first-write-wins. A different event id or a
        # mutated payload for the same id is evidence of conflicting delivery,
        # never authority to overwrite the accepted decision.
        self._conflicting_delivery_count += 1
