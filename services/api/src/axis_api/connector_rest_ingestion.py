"""REST collection host mapping into the existing ingestion outbox owners.

This is the host-adoption slice of #336 for [#861](https://github.com/Limes-Labs/limes-axis/issues/861).
It adds **no** second outbox, scheduler, checkpoint database or secret store:

* Selection preparation re-reads the active binding, declared observation,
  credential lease and egress policy from the current tenant-scoped records
  (same posture gate as the S3/live-query boundaries) and resolves material
  only through the existing lease-scoped secret resolver.
* One page is read through the #860 ``RestPageSource`` and its declared schema
  fingerprint is re-validated before any row is accepted.
* The bounded envelope goes to the canonical object store, then the metadata
  row, the audit event and the compare-and-swap checkpoint advance commit in
  the outbox's existing transaction. Object storage and SQL are not atomic:
  deterministic per-generation keys make replay overwrite, and a dead-lettered
  request leaves reconcilable orphan objects rather than silent skips.
* 429/eligible transient failures map into the existing durable retry state
  with a bounded ``Retry-After`` hint and never block a worker by sleeping.
  Authentication, schema, cursor and protocol errors are terminal.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

from axis_sdk.connector_authoring.contracts import (
    Checkpoint,
    ConnectorError,
    ErrorCode,
    OperationContext,
    ReadBatch,
    ReadLimits,
    ReadRequest,
    ResourceSelection,
    SourceDescriptor,
    negotiate_protocol,
)
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from axis_api.connector_postgres_discovery import (
    ConnectorSourceVerificationExecution,
    _resolve_operation_evidence,
)
from axis_api.connector_rest_reader import RestPageSource, RestSourceAuthority
from axis_api.connector_secret_resolution import (
    EnvLeaseScopedSecretResolver,
    SecretResolutionError,
    SecretResolutionRequest,
)
from axis_api.connector_source_extraction import SourceExtractionOutcome
from axis_api.data_asset_discovery import (
    DRIFT_ADDED,
    DRIFT_CHANGED,
    DRIFT_UNCHANGED,
)
from axis_api.data_assets import data_asset_id_for_connector
from axis_api.persistence import (
    AuditEventCreate,
    AxisPersistenceRepository,
    ConnectorSourceExtractionBatchCreate,
    DataResourceObservationCreate,
)
from axis_api.rest_source_profile import (
    REST_DECLARED_OBSERVATION_KIND,
    REST_SOURCE_CONNECTOR_ID,
    RestHostProfile,
)

REST_ADAPTER = "axis-rest-page-source"

# Bounded cursor memory per traversal: a loop shorter than this window is
# detected, and the window itself is a fixed, honest ceiling.
_VISITED_CURSOR_WINDOW = 32
_STATE_KEYS = frozenset({"cursor", "pages_committed", "traversal", "visited"})
_TRAVERSAL_IN_PROGRESS = "in_progress"
_TRAVERSAL_COMPLETE = "complete"
_TRAVERSAL_PAGE_LIMIT = "page_limit_reached"
_TERMINAL_TRAVERSALS = frozenset({_TRAVERSAL_COMPLETE, _TRAVERSAL_PAGE_LIMIT})
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._:-]*$")


class RestSourceFailure(ConnectorError):
    """A fixed public-safe code plus bounded attempt facts.

    ``retry_after_seconds`` is a provider hint the dispatcher turns into durable
    retry state; it never sleeps here. ``source_dial_performed`` is true only
    when the failure came from an actual request attempt.
    """

    def __init__(
        self,
        code: ErrorCode,
        *,
        retry_after_seconds: int | None = None,
        source_dial_performed: bool = False,
    ) -> None:
        super().__init__(code)
        self.retry_after_seconds = retry_after_seconds
        self.source_dial_performed = source_dial_performed


class RestCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    bearer_token: SecretStr


@dataclass(frozen=True)
class PreparedRestExtraction:
    tenant_id: str
    request_id: str
    binding_id: str
    profile: RestHostProfile
    credential_lease_id: str
    egress_policy_id: str
    execution: ConnectorSourceVerificationExecution
    revision: int
    checkpoint_state: dict | None
    classification: str
    executed_by: str


@dataclass(frozen=True)
class CompletedRestExtraction:
    prepared: PreparedRestExtraction
    outcome: SourceExtractionOutcome
    checkpoint_state: dict

    @property
    def batch_key(self) -> str:
        # Deterministic per generation: an uncommitted attempt replays onto the
        # same object, while a committed predecessor advances the generation and
        # never collides with immutable recorded history.
        identity = (
            self.prepared.tenant_id,
            REST_SOURCE_CONNECTOR_ID,
            self.prepared.request_id,
            self.prepared.binding_id,
            self.prepared.revision + 1,
        )
        digest = hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()
        return f"rest:{digest}"


class RestCheckpointConflict(RuntimeError):
    """A different committed request advanced the binding; retry from current state."""


def _cursor_digest(checkpoint: Checkpoint) -> str:
    return hashlib.sha256(checkpoint.cursor.get_secret_value().encode()).hexdigest()


def record_rest_declared_observation(
    repository: AxisPersistenceRepository,
    profile: RestHostProfile,
    *,
    observed_by: str,
):
    """Record the profile's *declared* schema as the binding's observation evidence.

    No provider is contacted: the operator declared the fingerprint in the
    profile, and activation still has to pin exactly this evidence. The source
    kind says ``rest_declared_schema`` so no consumer mistakes it for discovery.
    """

    resource_name = profile.resource_name
    fingerprint = profile.source.schema_fingerprint
    repository.acquire_data_resource_observation_lock(
        tenant_id=profile.tenant_id,
        connector_id=REST_SOURCE_CONNECTOR_ID,
        resource_name=resource_name,
    )
    existing = repository.get_data_resource_observation(
        profile.tenant_id, REST_SOURCE_CONNECTOR_ID, resource_name
    )
    if existing is None:
        record = repository.create_data_resource_observation(
            DataResourceObservationCreate(
                tenant_id=profile.tenant_id,
                connector_id=REST_SOURCE_CONNECTOR_ID,
                asset_id=data_asset_id_for_connector(REST_SOURCE_CONNECTOR_ID),
                resource_name=resource_name,
                schema_fingerprint=fingerprint,
                drift_state=DRIFT_ADDED,
                observed_by=observed_by,
                source_kind=REST_DECLARED_OBSERVATION_KIND,
            )
        )
        drift_state = DRIFT_ADDED
    else:
        drift_state = (
            DRIFT_UNCHANGED if existing.schema_fingerprint == fingerprint else DRIFT_CHANGED
        )
        record = repository.record_repeat_data_resource_observation(
            existing,
            schema_fingerprint=fingerprint,
            drift_state=drift_state,
            observed_by=observed_by,
        )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id=profile.tenant_id,
            actor_id=observed_by,
            event_type="data.resource.observed",
            payload={
                "asset_id": record.asset_id,
                "connector_id": REST_SOURCE_CONNECTOR_ID,
                "resource_name": resource_name,
                "source_kind": REST_DECLARED_OBSERVATION_KIND,
                "drift_state": drift_state,
                "observation_count": record.observation_count,
            },
        )
    )
    return record, drift_state


class RestIngestionRuntime:
    """One governed REST page per attempt, committed through the shared outbox."""

    def __init__(
        self,
        settings,
        object_store=None,
        *,
        resolver=None,
        transport_factory=None,
        clock=time.monotonic,
    ) -> None:
        self.settings = settings
        self.object_store = object_store
        self.resolver = resolver or EnvLeaseScopedSecretResolver()
        # Injecting a transport is the only test seam; production uses the
        # reader's pinned-origin transport.
        self.transport_factory = transport_factory
        self.clock = clock
        identities = [(p.tenant_id, p.profile_id) for p in settings.rest_source_profiles]
        if len(set(identities)) != len(identities):
            raise ValueError("REST source profile identities must be unique per tenant")

    def profile(self, tenant_id: str, profile_id: str) -> RestHostProfile:
        if not (
            self.settings.connector_sync_execution_enabled
            and self.settings.rest_source_ingestion_enabled
        ):
            raise ConnectorError(ErrorCode.UNSUPPORTED_CAPABILITY)
        for profile in self.settings.rest_source_profiles:
            if (profile.tenant_id, profile.profile_id) == (tenant_id, profile_id):
                return profile
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)

    @staticmethod
    def negotiate(profile: RestHostProfile):
        """Select an implemented protocol before any client is constructed."""
        descriptor = SourceDescriptor(
            connector_id=REST_SOURCE_CONNECTOR_ID,
            protocol=profile.protocol,
            capabilities=profile.capabilities,
        )
        return negotiate_protocol(descriptor, required=frozenset({"read"}))

    @staticmethod
    def validate_execution_profile(
        profile: RestHostProfile, execution: ConnectorSourceVerificationExecution
    ) -> None:
        policy = execution.egress_policy_evidence
        if (
            execution.connector_id != REST_SOURCE_CONNECTOR_ID
            or execution.credential_secret_ref != profile.credential_secret_ref
            or policy.get("egress_policy_evidence_status") != "validated"
            or policy.get("egress_policy_mode") != "approved_private_endpoint"
            or policy.get("egress_policy_scope")
            != f"{REST_SOURCE_CONNECTOR_ID}:{profile.profile_id}"
            or policy.get("egress_policy_endpoint_target_sha256")
            != profile.endpoint_target_sha256
            or policy.get("egress_policy_private_endpoint_ref") != profile.private_endpoint_ref
        ):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        try:
            expires = datetime.fromisoformat(policy["credential_lease_expires_at"])
            if expires.tzinfo is None or expires <= datetime.now(UTC):
                raise ValueError("inactive lease")
        except (KeyError, ValueError, TypeError):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH) from None

    def authority(
        self, prepared: PreparedRestExtraction
    ) -> RestSourceAuthority:
        profile = prepared.profile
        policy = prepared.execution.egress_policy_evidence
        lease = prepared.execution.credential_lease_result
        return RestSourceAuthority(
            tenant_id=profile.tenant_id,
            connector_id=REST_SOURCE_CONNECTOR_ID,
            credential_lease_id=prepared.credential_lease_id,
            egress_policy_id=prepared.egress_policy_id,
            lease_status=str(lease.get("status", "")),
            lease_ref=str(lease.get("provider_lease_ref", "")),
            lease_secret_material_returned=str(lease.get("secret_material_returned", True)),
            lease_expires_at=policy["credential_lease_expires_at"],
            egress_mode=str(policy.get("egress_policy_mode", "")),
            egress_endpoint_target_sha256=str(
                policy.get("egress_policy_endpoint_target_sha256", "")
            ),
            pinned_origin=profile.pinned_origin,
            allow_insecure_local=profile.allow_insecure_local,
            registered_endpoint_profile_revision=profile.source.endpoint_profile_revision,
        )

    def resolve_bearer(self, profile: RestHostProfile, execution) -> SecretStr:
        try:
            lease = execution.credential_lease_result
            resolved = self.resolver.resolve(
                SecretResolutionRequest(
                    connector_id=execution.connector_id,
                    connection_profile_id=profile.profile_id,
                    credential_access_mode="lease_scoped_secret_ref",
                    secret_provider=execution.credential_secret_provider,
                    secret_ref=execution.credential_secret_ref,
                    lease_status=str(lease.get("status", "")),
                    lease_ref=str(lease.get("provider_lease_ref", "")),
                    secret_material_returned=str(
                        lease.get("secret_material_returned", True)
                    ).lower(),
                )
            )
            credentials = RestCredentials.model_validate_json(resolved.dsn)
            if not credentials.bearer_token.get_secret_value():
                raise ValueError("empty credentials")
        except (SecretResolutionError, ValidationError, ValueError):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH) from None
        return credentials.bearer_token

    @staticmethod
    def context(prepared: PreparedRestExtraction) -> OperationContext:
        execution = prepared.execution
        return OperationContext(
            tenant_id=execution.tenant_id,
            connector_id=execution.connector_id,
            actor_id=execution.requested_by,
            operation_id=execution.verification_id,
            credential_lease_id=prepared.credential_lease_id,
            egress_policy_id=prepared.egress_policy_id,
        )

    def prepare_selection(
        self,
        repository: AxisPersistenceRepository,
        *,
        tenant_id: str,
        connector_id: str,
        request_id: str,
        binding_id: str,
        resource_name: str,
        pinned_schema_fingerprint: str,
        executed_by: str,
        lock_current: bool = False,
    ) -> PreparedRestExtraction:
        if connector_id != REST_SOURCE_CONNECTOR_ID or any(
            not _IDENTIFIER.fullmatch(value)
            for value in (tenant_id, request_id, binding_id)
        ):
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)
        binding = repository.get_connector_source_binding(
            tenant_id, binding_id, for_update=lock_current
        )
        if binding is None or binding.status != "active" or binding.connector_id != connector_id:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        profile = self.profile(tenant_id, binding.connection_profile_id)
        if (
            binding.resource_name != resource_name
            or resource_name != profile.resource_name
            or binding.schema_fingerprint != pinned_schema_fingerprint
            or pinned_schema_fingerprint != profile.source.schema_fingerprint
        ):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        observation = repository.get_data_resource_observation(
            tenant_id, connector_id, resource_name
        )
        if (
            observation is None
            or observation.schema_fingerprint != pinned_schema_fingerprint
            or observation.last_source_kind != REST_DECLARED_OBSERVATION_KIND
        ):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        request = SimpleNamespace(
            tenant_id=tenant_id,
            connector_id=connector_id,
            connection_profile_id=profile.profile_id,
            credential_lease_id=binding.credential_lease_id,
            egress_policy_id=binding.egress_policy_id,
        )
        lease, policy = _resolve_operation_evidence(repository, request, for_update=lock_current)
        execution = ConnectorSourceVerificationExecution(
            tenant_id=tenant_id,
            connector_id=connector_id,
            verification_id=request_id,
            requested_by=executed_by,
            connection_profile_id=profile.profile_id,
            credential_lease_id=binding.credential_lease_id,
            egress_policy_id=binding.egress_policy_id,
            credential_lease_result=dict(lease.lease_result),
            credential_secret_provider=lease.secret_provider,
            credential_secret_ref=lease.secret_ref,
            egress_policy_evidence=policy,
        )
        self.validate_execution_profile(profile, execution)
        stewardship = repository.get_current_data_asset_stewardship(
            tenant_id, f"source:{connector_id}:default"
        )
        return PreparedRestExtraction(
            tenant_id,
            request_id,
            binding_id,
            profile,
            binding.credential_lease_id,
            binding.egress_policy_id,
            execution,
            binding.source_checkpoint_revision,
            binding.source_checkpoint,
            stewardship.classification if stewardship else "undeclared",
            executed_by,
        )

    @staticmethod
    def _load_state(previous: dict | None) -> dict | None:
        if previous is None:
            return None
        if not isinstance(previous, dict) or set(previous) != _STATE_KEYS:
            raise ConnectorError(ErrorCode.INVALID_CHECKPOINT)
        pages = previous["pages_committed"]
        traversal = previous["traversal"]
        visited = previous["visited"]
        cursor = previous["cursor"]
        if (
            type(pages) is not int
            or pages < 0
            or traversal not in {_TRAVERSAL_IN_PROGRESS, *_TERMINAL_TRAVERSALS}
            or not isinstance(visited, list)
            or len(visited) > _VISITED_CURSOR_WINDOW
            or any(not isinstance(item, str) for item in visited)
            or (cursor is not None and not isinstance(cursor, dict))
            or (traversal == _TRAVERSAL_IN_PROGRESS and cursor is None and pages > 0)
        ):
            raise ConnectorError(ErrorCode.INVALID_CHECKPOINT)
        return {
            "pages_committed": pages,
            "traversal": traversal,
            "visited": list(visited),
            "cursor": cursor,
        }

    def extract_prepared(self, prepared: PreparedRestExtraction) -> CompletedRestExtraction:
        if self.object_store is None:
            raise ConnectorError(ErrorCode.UNSUPPORTED_CAPABILITY)
        state = self._load_state(prepared.checkpoint_state)
        if state is not None and state["traversal"] in _TERMINAL_TRAVERSALS:
            # Never silently restart a finished traversal at page one; a new
            # explicit activation is the operator's recovery path.
            raise RestSourceFailure(ErrorCode.INVALID_CHECKPOINT)
        protocol = self.negotiate(prepared.profile)
        bearer = self.resolve_bearer(prepared.profile, prepared.execution)
        try:
            authority = self.authority(prepared)
        except (ValidationError, KeyError, TypeError, ValueError):
            # Fail closed: malformed lease/policy evidence never dials.
            raise RestSourceFailure(ErrorCode.RESOURCE_MISMATCH) from None
        try:
            # A missing, foreign-tenant or resource-mismatched checkpoint must be
            # a fixed terminal code, never a raw model error that looks retryable.
            checkpoint = (
                Checkpoint.model_validate(state["cursor"])
                if state is not None and state["cursor"] is not None
                else None
            )
            request = ReadRequest(
                context=self.context(prepared),
                resource=self._resource(prepared.profile),
                checkpoint=checkpoint,
                limits=self._limits(prepared.profile),
            )
        except ValidationError:
            raise RestSourceFailure(ErrorCode.INVALID_CHECKPOINT) from None
        started = self.clock()
        with RestPageSource(
            profile=prepared.profile.source,
            authority=authority,
            credential_bearer=bearer,
            path_values=prepared.profile.path_values,
            query_values=prepared.profile.query_values,
            transport_factory=self.transport_factory,
        ) as source:
            try:
                batch = source.read(request)
                batch.validate_for(request)
            except ConnectorError as exc:
                raise RestSourceFailure(
                    exc.code,
                    retry_after_seconds=source.progress.retry_after_seconds,
                    source_dial_performed=True,
                ) from None
        if batch.completion == "truncated":
            # A capped, unresumable page: never commit progress that would skip rows.
            raise RestSourceFailure(ErrorCode.LIMIT_EXCEEDED)
        next_state = self._next_state(prepared.profile, state, batch)
        return self._record(prepared, batch, next_state, protocol, started)

    def _limits(self, profile: RestHostProfile) -> ReadLimits:
        return ReadLimits(
            max_records=min(self.settings.source_ingestion_extraction_max_rows, 1_000),
            max_bytes=min(self.settings.source_ingestion_extraction_max_bytes, 8_388_608),
            time_budget_seconds=min(
                self.settings.source_ingestion_extraction_time_budget_seconds,
                profile.source.limits.page.time_budget_seconds,
                300,
            ),
        )

    @staticmethod
    def _resource(profile: RestHostProfile) -> ResourceSelection:
        return ResourceSelection(
            resource_id=profile.source.collection_id,
            schema_fingerprint=profile.source.schema_fingerprint,
            source_revision=profile.source.endpoint_profile_revision,
        )

    def _next_state(
        self,
        profile: RestHostProfile,
        state: dict | None,
        batch: ReadBatch,
    ) -> dict:
        pages = (state["pages_committed"] if state else 0) + 1
        visited = list(state["visited"] if state else [])
        completed = batch.completion == "complete"
        cursor = batch.checkpoint
        if cursor is not None:
            digest = _cursor_digest(cursor)
            if digest in visited:
                # A repeated next-link/cursor loops forever; terminal, not a retry.
                raise RestSourceFailure(ErrorCode.NO_PROGRESS) from None
            visited = [*visited, digest][-_VISITED_CURSOR_WINDOW:]
        if completed:
            traversal = _TRAVERSAL_COMPLETE
            stored = None
        elif pages >= profile.source.limits.max_pages:
            # The traversal ceiling is reached; stop with an honest terminal state.
            traversal = _TRAVERSAL_PAGE_LIMIT
            stored = None
        else:
            traversal = _TRAVERSAL_IN_PROGRESS
            stored = cursor.storage_record() if cursor is not None else None
            if stored is None:
                raise RestSourceFailure(ErrorCode.INVALID_CHECKPOINT)
        return {
            "cursor": stored,
            "pages_committed": pages,
            "traversal": traversal,
            "visited": visited,
        }

    def _record(
        self,
        prepared: PreparedRestExtraction,
        batch: ReadBatch,
        next_state: dict,
        protocol,
        started: float,
    ) -> CompletedRestExtraction:
        evidence = batch.evidence()
        envelope = {
            "schema_version": 1,
            "tenant_id": prepared.tenant_id,
            "connector_id": REST_SOURCE_CONNECTOR_ID,
            "request_id": prepared.request_id,
            "binding_id": prepared.binding_id,
            "resource_name": prepared.profile.resource_name,
            "profile_revision": prepared.profile.revision,
            "endpoint_profile_revision": prepared.profile.source.endpoint_profile_revision,
            "protocol": {"major": protocol.major, "minor": protocol.minor},
            "ordering_mode": "none",
            "completion": batch.completion,
            "checkpoint_revision": prepared.revision + 1,
            "page_number": next_state["pages_committed"],
            "truncated": batch.completion != "complete",
            "row_count": len(batch.records),
            "rows": list(batch.records),
        }
        encoded = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        key = (
            f"tenants/{prepared.tenant_id}/source-ingestion/{prepared.request_id}/"
            f"{prepared.binding_id}/{digest}.json"
        )
        stored = self.object_store.put_json(key, envelope)
        if stored.checksum_sha256 != digest or stored.size_bytes != len(encoded):
            raise ConnectorError(ErrorCode.SOURCE_UNAVAILABLE)
        cursor_digests = next_state["visited"]
        outcome = SourceExtractionOutcome(
            ok=True,
            source_dial_performed=True,
            extraction_performed=True,
            ordering_mode="none",
            cursor_watermark={
                "checkpoint_revision": prepared.revision + 1,
                "page_number": next_state["pages_committed"],
                "traversal": next_state["traversal"],
                "cursor_sha256": cursor_digests[-1] if cursor_digests else None,
            },
            row_count=len(batch.records),
            byte_size=evidence.byte_size,
            truncated=False,
            duration_ms=int((self.clock() - started) * 1000),
            digest_sha256=digest,
            observed_schema_fingerprint=prepared.profile.source.schema_fingerprint,
            payload_envelope=envelope,
            stored={
                **stored.model_dump(),
                "stored_size_bytes": stored.size_bytes,
                "classification": prepared.classification,
                "executed_by": prepared.executed_by,
            },
        )
        return CompletedRestExtraction(prepared, outcome, next_state)

    def commit(
        self, repository: AxisPersistenceRepository, result: CompletedRestExtraction
    ) -> None:
        """Revalidate current grants and CAS the checkpoint inside the host transaction."""
        prepared = result.prepared
        repository.get_connector_manifest(
            prepared.tenant_id, REST_SOURCE_CONNECTOR_ID, for_update=True
        )
        current = self.prepare_selection(
            repository,
            tenant_id=prepared.tenant_id,
            connector_id=REST_SOURCE_CONNECTOR_ID,
            request_id=prepared.request_id,
            binding_id=prepared.binding_id,
            resource_name=prepared.profile.resource_name,
            pinned_schema_fingerprint=prepared.profile.source.schema_fingerprint,
            executed_by=prepared.executed_by,
            lock_current=True,
        )
        if (
            current.revision != prepared.revision
            or not repository.advance_connector_source_checkpoint(
                tenant_id=prepared.tenant_id,
                connector_id=REST_SOURCE_CONNECTOR_ID,
                binding_id=prepared.binding_id,
                expected_revision=prepared.revision,
                checkpoint=result.checkpoint_state,
            )
        ):
            raise RestCheckpointConflict()
        outcome = result.outcome
        batch_key = result.batch_key
        event = repository.append_audit_event(
            AuditEventCreate(
                tenant_id=prepared.tenant_id,
                actor_id=prepared.executed_by,
                event_type="connector.source.extraction.batch_recorded",
                payload={
                    "request_id": prepared.request_id,
                    "connector_id": REST_SOURCE_CONNECTOR_ID,
                    "binding_id": prepared.binding_id,
                    "resource_name": prepared.profile.resource_name,
                    "batch_key": batch_key,
                    "row_count": str(outcome.row_count),
                    "truncated": "false",
                    "digest_sha256": outcome.digest_sha256,
                    "storage_uri": outcome.stored["storage_uri"],
                    "checkpoint_revision": str(prepared.revision + 1),
                    "traversal": str(result.checkpoint_state["traversal"]),
                },
            )
        )
        repository.create_connector_source_extraction_batch(
            ConnectorSourceExtractionBatchCreate(
                tenant_id=prepared.tenant_id,
                connector_id=REST_SOURCE_CONNECTOR_ID,
                request_id=prepared.request_id,
                batch_key=batch_key,
                binding_id=prepared.binding_id,
                resource_name=prepared.profile.resource_name,
                pinned_schema_fingerprint=prepared.profile.source.schema_fingerprint,
                observed_schema_fingerprint=prepared.profile.source.schema_fingerprint,
                ordering_mode="none",
                cursor_watermark=outcome.cursor_watermark,
                row_count=outcome.row_count,
                byte_size=outcome.byte_size,
                truncated=False,
                limit_reason=None,
                duration_ms=outcome.duration_ms,
                limits_applied={
                    "max_pages": prepared.profile.source.limits.max_pages,
                    "page_max_records": prepared.profile.source.limits.page.max_records,
                    "page_max_bytes": prepared.profile.source.limits.page.max_bytes,
                },
                provenance={
                    "stage": "extract",
                    "source_adapter": REST_ADAPTER,
                    "checkpoint_revision": prepared.revision + 1,
                    "traversal": result.checkpoint_state["traversal"],
                },
                digest_sha256=outcome.digest_sha256,
                storage_adapter=outcome.stored["storage_adapter"],
                storage_key=outcome.stored["storage_key"],
                storage_uri=outcome.stored["storage_uri"],
                content_type=outcome.stored["content_type"],
                stored_size_bytes=outcome.stored["stored_size_bytes"],
                classification=current.classification,
                executed_by=prepared.executed_by,
                audit_event_id=event.id,
                audit_event_type=event.event_type,
            )
        )


__all__ = [
    "CompletedRestExtraction",
    "PreparedRestExtraction",
    "RestCheckpointConflict",
    "RestCredentials",
    "RestIngestionRuntime",
    "RestSourceFailure",
    "record_rest_declared_observation",
]