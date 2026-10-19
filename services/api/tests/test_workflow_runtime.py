import asyncio
import time
from uuid import UUID

import pytest

from axis_api.demo import ApprovalDecision
from axis_api.workflow_runtime import (
    DeferredWorkflowSignalRuntime,
    TemporalWorkflowSignalConfig,
    TemporalWorkflowSignalRuntime,
    WorkflowActionSignalRequest,
    WorkflowSignalError,
    WorkflowSignalRequest,
)


class RecordingHandle:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, object]] = []

    async def signal(self, name: str, payload: object, *, rpc_timeout: object) -> None:
        self.calls.append((name, payload, rpc_timeout))


class RecordingClient:
    def __init__(self, handle: RecordingHandle) -> None:
        self.handle = handle
        self.workflow_ids: list[str] = []

    def get_workflow_handle(self, workflow_id: str) -> RecordingHandle:
        self.workflow_ids.append(workflow_id)
        return self.handle


def approval_request(**updates: object) -> WorkflowSignalRequest:
    values: dict[str, object] = {
        "tenant_id": "tenant_demo",
        "workflow_id": "wf_supplier_delay",
        "approval_id": "appr_expedite",
        "decision": ApprovalDecision.REQUEST_CHANGES,
        "actor_id": "plant-operations-owner-role",
        "note": "Please attach updated supplier evidence.",
        "decided_at": None,
    }
    values.update(updates)
    return WorkflowSignalRequest.model_validate(values)


def test_approval_signal_request_generates_stable_event_id_and_full_payload() -> None:
    first = approval_request()
    second = approval_request()

    assert isinstance(first.decision_event_id, UUID)
    assert second.decision_event_id == first.decision_event_id
    assert first.runtime_payload == {
        "schema_version": "axis.approval-decision.v1",
        "decision_event_id": str(first.decision_event_id),
        "tenant_id": "tenant_demo",
        "workflow_id": "wf_supplier_delay",
        "approval_id": "appr_expedite",
        "decision": "request_changes",
        "approved": False,
        "actor_id": "plant-operations-owner-role",
        "note": "Please attach updated supplier evidence.",
        "decided_at": None,
    }


@pytest.mark.asyncio
async def test_temporal_runtime_sends_full_approval_decision_payload() -> None:
    handle = RecordingHandle()
    client = RecordingClient(handle)
    runtime = TemporalWorkflowSignalRuntime(TemporalWorkflowSignalConfig())
    runtime._client = client  # type: ignore[assignment]
    request = approval_request(decision=ApprovalDecision.REJECT)

    result = await runtime.signal_approval_decision(request)

    assert client.workflow_ids == ["wf_supplier_delay"]
    assert handle.calls[0][0] == "approval_decided_v1"
    assert handle.calls[0][1] == request.runtime_payload
    assert result.payload == request.audit_payload


@pytest.mark.asyncio
async def test_deferred_runtime_preserves_full_decision_evidence() -> None:
    request = approval_request()

    result = await DeferredWorkflowSignalRuntime().signal_approval_decision(request)

    assert result.status == "runtime_signal_deferred"
    assert result.payload == request.audit_payload


class HangingHandle:
    async def signal(self, name: str, payload: object, *, rpc_timeout: object) -> None:
        await asyncio.Event().wait()


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def action_request() -> WorkflowActionSignalRequest:
    return WorkflowActionSignalRequest(
        tenant_id="tenant_demo",
        workflow_id="wf_action",
        action_id="action_expedite",
        action_run_id=UUID("00000000-0000-4000-8000-000000000001"),
        idempotency_key="idem-1",
        execution_mode="demo",
    )


@pytest.mark.asyncio
async def test_temporal_connect_is_bounded_by_the_signal_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def blackholed_connect(*_args: object, **_kwargs: object) -> object:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr("axis_api.workflow_runtime.Client.connect", blackholed_connect)
    runtime = TemporalWorkflowSignalRuntime(
        TemporalWorkflowSignalConfig(address="192.0.2.1:7233", signal_timeout_seconds=0.05)
    )

    started = time.monotonic()
    with pytest.raises(WorkflowSignalError) as raised:
        await asyncio.wait_for(runtime.signal_approval_decision(approval_request()), 2.0)

    assert time.monotonic() - started < 1.0
    assert raised.value.reason == "TimeoutError"
    assert raised.value.may_be_closed is False


@pytest.mark.asyncio
async def test_temporal_signal_rpc_is_bounded_even_when_the_rpc_timeout_is_ignored() -> None:
    runtime = TemporalWorkflowSignalRuntime(
        TemporalWorkflowSignalConfig(signal_timeout_seconds=0.05)
    )
    runtime._client = RecordingClient(HangingHandle())  # type: ignore[assignment,arg-type]

    with pytest.raises(WorkflowSignalError) as raised:
        await asyncio.wait_for(runtime.signal_action_run(action_request()), 2.0)

    assert raised.value.reason == "TimeoutError"


@pytest.mark.asyncio
async def test_concurrent_requests_share_one_temporal_connect_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = RecordingHandle()
    released = asyncio.Event()
    connects: list[str] = []

    async def slow_connect(address: str, **_kwargs: object) -> RecordingClient:
        connects.append(address)
        await released.wait()
        return RecordingClient(handle)

    monkeypatch.setattr("axis_api.workflow_runtime.Client.connect", slow_connect)
    runtime = TemporalWorkflowSignalRuntime(TemporalWorkflowSignalConfig())

    pending = [
        asyncio.create_task(runtime.signal_approval_decision(approval_request()))
        for _ in range(10)
    ]
    await asyncio.sleep(0.01)
    released.set()
    results = await asyncio.wait_for(asyncio.gather(*pending), 2.0)

    assert connects == ["localhost:7233"]
    assert len(handle.calls) == 10
    assert {result.status for result in results} == {"approval_signaled"}


@pytest.mark.asyncio
async def test_failed_temporal_connect_is_negatively_cached_with_bounded_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[float] = []
    clock = FakeClock()

    async def refused_connect(*_args: object, **_kwargs: object) -> object:
        attempts.append(clock.now)
        raise RuntimeError("connection refused")

    monkeypatch.setattr("axis_api.workflow_runtime.Client.connect", refused_connect)
    runtime = TemporalWorkflowSignalRuntime(
        TemporalWorkflowSignalConfig(connect_backoff_max_seconds=4.0),
        clock=clock,
    )

    async def attempt() -> str:
        with pytest.raises(WorkflowSignalError) as raised:
            await runtime.signal_approval_decision(approval_request())
        return raised.value.reason

    assert await attempt() == "RuntimeError"
    # Requests inside the backoff window fail fast without another connect.
    for _ in range(20):
        assert await attempt() == "TemporalConnectBackoffError"
    assert len(attempts) == 1

    clock.now += 1.0
    assert await attempt() == "RuntimeError"
    assert len(attempts) == 2
    clock.now += 1.0
    assert await attempt() == "TemporalConnectBackoffError"
    clock.now += 1.0
    assert await attempt() == "RuntimeError"
    # The backoff doubles and is capped at the configured maximum.
    clock.now += 4.0
    assert await attempt() == "RuntimeError"
    clock.now += 4.0
    assert await attempt() == "RuntimeError"
    assert len(attempts) == 5


@pytest.mark.asyncio
async def test_successful_temporal_connect_clears_the_negative_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = RecordingHandle()
    clock = FakeClock()
    outcomes: list[object] = [RuntimeError("down"), RecordingClient(handle)]

    async def flaky_connect(*_args: object, **_kwargs: object) -> object:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr("axis_api.workflow_runtime.Client.connect", flaky_connect)
    runtime = TemporalWorkflowSignalRuntime(TemporalWorkflowSignalConfig(), clock=clock)

    with pytest.raises(WorkflowSignalError):
        await runtime.signal_approval_decision(approval_request())
    clock.now += 1.0
    result = await runtime.signal_approval_decision(approval_request())

    assert result.status == "approval_signaled"
    assert outcomes == []
    assert len(handle.calls) == 1
