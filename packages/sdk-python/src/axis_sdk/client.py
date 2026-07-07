"""Synchronous and asynchronous clients for the Limes Axis REST API.

Both clients share one request core (``_transport``) and one endpoint map
(``_endpoints``); only the I/O execution differs. The sync client is a thin
blocking executor rather than a wrapper around an event loop, so it works
in plain scripts, worker processes and notebooks without loop juggling.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from axis_sdk import _endpoints as endpoints
from axis_sdk import models
from axis_sdk._transport import (
    RequestSpec,
    backoff_delay,
    build_headers,
    handle_response,
    new_request_id,
    parse_model,
    resolve_params,
    response_retry_delay,
    should_retry_error,
    should_retry_response,
)
from axis_sdk._version import USER_AGENT
from axis_sdk.config import AxisClientConfig, RetryConfig, TokenProvider
from axis_sdk.exceptions import AxisConnectionError
from axis_sdk.models import ApprovalDecision

__all__ = ["AxisClient", "AsyncAxisClient"]


def _build_config(
    base_url: str,
    *,
    token: str | None,
    token_provider: TokenProvider | None,
    tenant_id: str | None,
    timeout_seconds: float,
    user_agent: str,
    retry: RetryConfig | None,
) -> AxisClientConfig:
    return AxisClientConfig(
        base_url=base_url,
        token=token,
        token_provider=token_provider,
        tenant_id=tenant_id,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
        retry=retry if retry is not None else RetryConfig(),
    )


class AxisClient:
    """Blocking client. Use as a context manager or call ``close()``."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        token_provider: TokenProvider | None = None,
        tenant_id: str | None = None,
        timeout_seconds: float = 30.0,
        user_agent: str = USER_AGENT,
        retry: RetryConfig | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = _build_config(
            base_url,
            token=token,
            token_provider=token_provider,
            tenant_id=tenant_id,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
            retry=retry,
        )
        self._http = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            transport=transport,
        )
        self.system = SystemResource(self)
        self.approvals = ApprovalsResource(self)
        self.actions = ActionsResource(self)
        self.workflows = WorkflowsResource(self)
        self.audit = AuditResource(self)
        self.ontology = OntologyResource(self)
        self.agents = AgentsResource(self)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> AxisClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _request(self, spec: RequestSpec) -> Any:
        retry = self.config.retry
        params = resolve_params(spec, self.config)
        # One request id per logical operation, reused across retry attempts
        # so server-side correlation sees retries as the same operation.
        request_id = new_request_id()
        attempt = 0
        while True:
            headers = build_headers(self.config, request_id)
            try:
                response = self._http.request(
                    spec.method,
                    spec.path,
                    params=params,
                    json=spec.json_body,
                    headers=headers,
                )
            except httpx.TransportError as exc:
                if should_retry_error(spec, retry, attempt):
                    time.sleep(backoff_delay(retry, attempt))
                    attempt += 1
                    continue
                raise AxisConnectionError(
                    f"Could not reach the Axis API: {exc}", request_id=request_id
                ) from exc
            if should_retry_response(spec, response, retry, attempt):
                time.sleep(response_retry_delay(retry, attempt, response))
                attempt += 1
                continue
            return handle_response(response, request_id)

    def _call(self, endpoint: endpoints.Endpoint) -> Any:
        spec, model_type = endpoint
        return parse_model(self._request(spec), model_type)


class AsyncAxisClient:
    """Asynchronous client. Use as an async context manager or await ``aclose()``."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        token_provider: TokenProvider | None = None,
        tenant_id: str | None = None,
        timeout_seconds: float = 30.0,
        user_agent: str = USER_AGENT,
        retry: RetryConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = _build_config(
            base_url,
            token=token,
            token_provider=token_provider,
            tenant_id=tenant_id,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
            retry=retry,
        )
        self._http = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            transport=transport,
        )
        self.system = AsyncSystemResource(self)
        self.approvals = AsyncApprovalsResource(self)
        self.actions = AsyncActionsResource(self)
        self.workflows = AsyncWorkflowsResource(self)
        self.audit = AsyncAuditResource(self)
        self.ontology = AsyncOntologyResource(self)
        self.agents = AsyncAgentsResource(self)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncAxisClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _request(self, spec: RequestSpec) -> Any:
        retry = self.config.retry
        params = resolve_params(spec, self.config)
        # One request id per logical operation, reused across retry attempts
        # so server-side correlation sees retries as the same operation.
        request_id = new_request_id()
        attempt = 0
        while True:
            headers = build_headers(self.config, request_id)
            try:
                response = await self._http.request(
                    spec.method,
                    spec.path,
                    params=params,
                    json=spec.json_body,
                    headers=headers,
                )
            except httpx.TransportError as exc:
                if should_retry_error(spec, retry, attempt):
                    await asyncio.sleep(backoff_delay(retry, attempt))
                    attempt += 1
                    continue
                raise AxisConnectionError(
                    f"Could not reach the Axis API: {exc}", request_id=request_id
                ) from exc
            if should_retry_response(spec, response, retry, attempt):
                await asyncio.sleep(response_retry_delay(retry, attempt, response))
                attempt += 1
                continue
            return handle_response(response, request_id)

    async def _call(self, endpoint: endpoints.Endpoint) -> Any:
        spec, model_type = endpoint
        return parse_model(await self._request(spec), model_type)


# ---------------------------------------------------------------------------
# Sync resources
# ---------------------------------------------------------------------------


class SystemResource:
    def __init__(self, client: AxisClient) -> None:
        self._client = client

    def health(self) -> models.HealthStatus:
        return self._client._call(endpoints.health())

    def ready(self) -> models.ReadinessStatus:
        return self._client._call(endpoints.ready())

    def deployment_readiness(self) -> models.DeploymentReadinessReport:
        return self._client._call(endpoints.deployment_readiness())


class ApprovalsResource:
    def __init__(self, client: AxisClient) -> None:
        self._client = client

    def list(self, tenant_id: str | None = None) -> models.ApprovalInbox:
        return self._client._call(endpoints.list_approvals(tenant_id))

    def get(self, approval_id: str, tenant_id: str | None = None) -> models.ApprovalInboxItem:
        """Return one approval from the inbox.

        The API does not expose a single-approval route, so this filters
        the tenant inbox client-side and raises ``LookupError`` on a miss.
        """
        inbox = self.list(tenant_id)
        for approval in inbox.approvals:
            if approval.approval_id == approval_id:
                return approval
        raise LookupError(f"Approval {approval_id!r} is not in the tenant approval inbox.")

    def decide(
        self,
        approval_id: str,
        *,
        decision: ApprovalDecision | str,
        actor_id: str,
        actor_scopes: list[str] | None = None,
        note: str | None = None,
    ) -> models.ApprovalDecisionResult:
        return self._client._call(
            endpoints.decide_approval(
                approval_id,
                decision=decision,
                actor_id=actor_id,
                actor_scopes=actor_scopes,
                note=note,
            )
        )


class ActionsResource:
    def __init__(self, client: AxisClient) -> None:
        self._client = client

    def catalog(self, tenant_id: str | None = None) -> models.ActionRegistry:
        return self._client._call(endpoints.action_catalog(tenant_id))

    def create_run(
        self,
        action_id: str,
        *,
        actor_id: str,
        payload: dict[str, Any],
        actor_scopes: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> models.ActionRunResult:
        return self._client._call(
            endpoints.create_action_run(
                action_id,
                actor_id=actor_id,
                payload=payload,
                actor_scopes=actor_scopes,
                idempotency_key=idempotency_key,
            )
        )

    def record_outcome(
        self,
        action_run_id: str,
        *,
        actor_id: str,
        status: str,
        result_summary: str,
        idempotency_key: str,
        evidence_refs: list[str],
        actor_scopes: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
        external_mutation_started: bool = False,
    ) -> models.ActionRunOutcomeResult:
        return self._client._call(
            endpoints.record_action_run_outcome(
                action_run_id,
                actor_id=actor_id,
                status=status,
                result_summary=result_summary,
                idempotency_key=idempotency_key,
                actor_scopes=actor_scopes,
                evidence_refs=evidence_refs,
                metrics=metrics,
                external_mutation_started=external_mutation_started,
            )
        )


class WorkflowsResource:
    def __init__(self, client: AxisClient) -> None:
        self._client = client

    def console(self, tenant_id: str | None = None) -> models.WorkflowConsole:
        return self._client._call(endpoints.workflow_console(tenant_id))

    def list_runs(
        self,
        tenant_id: str | None = None,
        *,
        state: str | None = None,
        limit: int | None = None,
    ) -> models.WorkflowConsole:
        return self._client._call(
            endpoints.list_workflow_runs(tenant_id, state=state, limit=limit)
        )

    def get_run(self, workflow_id: str, tenant_id: str | None = None) -> models.WorkflowRun:
        """Return one persisted workflow run including its timeline.

        The API does not expose a single-run route, so this filters the
        persisted runs client-side and raises ``LookupError`` on a miss.
        """
        console = self.list_runs(tenant_id)
        for run in console.workflow_runs:
            if run.workflow_id == workflow_id:
                return run
        raise LookupError(f"Workflow run {workflow_id!r} is not persisted for this tenant.")


class AuditResource:
    def __init__(self, client: AxisClient) -> None:
        self._client = client

    def explorer(self, tenant_id: str | None = None) -> models.AuditExplorer:
        return self._client._call(endpoints.audit_explorer(tenant_id))

    def query_events(
        self,
        tenant_id: str | None = None,
        *,
        event_type: str | None = None,
        actor_id: str | None = None,
        scope: str | None = None,
        limit: int | None = None,
    ) -> models.AuditExplorer:
        return self._client._call(
            endpoints.query_audit_events(
                tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                scope=scope,
                limit=limit,
            )
        )

    def export(
        self,
        tenant_id: str | None = None,
        *,
        event_type: str | None = None,
        actor_id: str | None = None,
        scope: str | None = None,
        limit: int | None = None,
        export_reason: str | None = None,
        retention_days: int | None = None,
        legal_hold: bool | None = None,
    ) -> models.AuditExportBundle:
        return self._client._call(
            endpoints.export_audit_events(
                tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                scope=scope,
                limit=limit,
                export_reason=export_reason,
                retention_days=retention_days,
                legal_hold=legal_hold,
            )
        )


class OntologyResource:
    def __init__(self, client: AxisClient) -> None:
        self._client = client

    def graph(
        self, tenant_id: str | None = None, *, limit: int | None = None
    ) -> models.OntologyGraph:
        return self._client._call(endpoints.ontology_graph(tenant_id, limit=limit))

    def entity(self, node_id: str, tenant_id: str | None = None) -> models.OntologyEntityDetail:
        return self._client._call(endpoints.ontology_entity(node_id, tenant_id))


class AgentsResource:
    def __init__(self, client: AxisClient) -> None:
        self._client = client

    def registry(self, tenant_id: str | None = None) -> models.AgentRegistry:
        return self._client._call(endpoints.agent_registry(tenant_id))


# ---------------------------------------------------------------------------
# Async resources
# ---------------------------------------------------------------------------


class AsyncSystemResource:
    def __init__(self, client: AsyncAxisClient) -> None:
        self._client = client

    async def health(self) -> models.HealthStatus:
        return await self._client._call(endpoints.health())

    async def ready(self) -> models.ReadinessStatus:
        return await self._client._call(endpoints.ready())

    async def deployment_readiness(self) -> models.DeploymentReadinessReport:
        return await self._client._call(endpoints.deployment_readiness())


class AsyncApprovalsResource:
    def __init__(self, client: AsyncAxisClient) -> None:
        self._client = client

    async def list(self, tenant_id: str | None = None) -> models.ApprovalInbox:
        return await self._client._call(endpoints.list_approvals(tenant_id))

    async def get(
        self, approval_id: str, tenant_id: str | None = None
    ) -> models.ApprovalInboxItem:
        """See :meth:`ApprovalsResource.get`."""
        inbox = await self.list(tenant_id)
        for approval in inbox.approvals:
            if approval.approval_id == approval_id:
                return approval
        raise LookupError(f"Approval {approval_id!r} is not in the tenant approval inbox.")

    async def decide(
        self,
        approval_id: str,
        *,
        decision: ApprovalDecision | str,
        actor_id: str,
        actor_scopes: list[str] | None = None,
        note: str | None = None,
    ) -> models.ApprovalDecisionResult:
        return await self._client._call(
            endpoints.decide_approval(
                approval_id,
                decision=decision,
                actor_id=actor_id,
                actor_scopes=actor_scopes,
                note=note,
            )
        )


class AsyncActionsResource:
    def __init__(self, client: AsyncAxisClient) -> None:
        self._client = client

    async def catalog(self, tenant_id: str | None = None) -> models.ActionRegistry:
        return await self._client._call(endpoints.action_catalog(tenant_id))

    async def create_run(
        self,
        action_id: str,
        *,
        actor_id: str,
        payload: dict[str, Any],
        actor_scopes: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> models.ActionRunResult:
        return await self._client._call(
            endpoints.create_action_run(
                action_id,
                actor_id=actor_id,
                payload=payload,
                actor_scopes=actor_scopes,
                idempotency_key=idempotency_key,
            )
        )

    async def record_outcome(
        self,
        action_run_id: str,
        *,
        actor_id: str,
        status: str,
        result_summary: str,
        idempotency_key: str,
        evidence_refs: list[str],
        actor_scopes: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
        external_mutation_started: bool = False,
    ) -> models.ActionRunOutcomeResult:
        return await self._client._call(
            endpoints.record_action_run_outcome(
                action_run_id,
                actor_id=actor_id,
                status=status,
                result_summary=result_summary,
                idempotency_key=idempotency_key,
                actor_scopes=actor_scopes,
                evidence_refs=evidence_refs,
                metrics=metrics,
                external_mutation_started=external_mutation_started,
            )
        )


class AsyncWorkflowsResource:
    def __init__(self, client: AsyncAxisClient) -> None:
        self._client = client

    async def console(self, tenant_id: str | None = None) -> models.WorkflowConsole:
        return await self._client._call(endpoints.workflow_console(tenant_id))

    async def list_runs(
        self,
        tenant_id: str | None = None,
        *,
        state: str | None = None,
        limit: int | None = None,
    ) -> models.WorkflowConsole:
        return await self._client._call(
            endpoints.list_workflow_runs(tenant_id, state=state, limit=limit)
        )

    async def get_run(
        self, workflow_id: str, tenant_id: str | None = None
    ) -> models.WorkflowRun:
        """See :meth:`WorkflowsResource.get_run`."""
        console = await self.list_runs(tenant_id)
        for run in console.workflow_runs:
            if run.workflow_id == workflow_id:
                return run
        raise LookupError(f"Workflow run {workflow_id!r} is not persisted for this tenant.")


class AsyncAuditResource:
    def __init__(self, client: AsyncAxisClient) -> None:
        self._client = client

    async def explorer(self, tenant_id: str | None = None) -> models.AuditExplorer:
        return await self._client._call(endpoints.audit_explorer(tenant_id))

    async def query_events(
        self,
        tenant_id: str | None = None,
        *,
        event_type: str | None = None,
        actor_id: str | None = None,
        scope: str | None = None,
        limit: int | None = None,
    ) -> models.AuditExplorer:
        return await self._client._call(
            endpoints.query_audit_events(
                tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                scope=scope,
                limit=limit,
            )
        )

    async def export(
        self,
        tenant_id: str | None = None,
        *,
        event_type: str | None = None,
        actor_id: str | None = None,
        scope: str | None = None,
        limit: int | None = None,
        export_reason: str | None = None,
        retention_days: int | None = None,
        legal_hold: bool | None = None,
    ) -> models.AuditExportBundle:
        return await self._client._call(
            endpoints.export_audit_events(
                tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                scope=scope,
                limit=limit,
                export_reason=export_reason,
                retention_days=retention_days,
                legal_hold=legal_hold,
            )
        )


class AsyncOntologyResource:
    def __init__(self, client: AsyncAxisClient) -> None:
        self._client = client

    async def graph(
        self, tenant_id: str | None = None, *, limit: int | None = None
    ) -> models.OntologyGraph:
        return await self._client._call(endpoints.ontology_graph(tenant_id, limit=limit))

    async def entity(
        self, node_id: str, tenant_id: str | None = None
    ) -> models.OntologyEntityDetail:
        return await self._client._call(endpoints.ontology_entity(node_id, tenant_id))


class AsyncAgentsResource:
    def __init__(self, client: AsyncAxisClient) -> None:
        self._client = client

    async def registry(self, tenant_id: str | None = None) -> models.AgentRegistry:
        return await self._client._call(endpoints.agent_registry(tenant_id))
