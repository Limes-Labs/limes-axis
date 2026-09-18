"""Runtime dependency manifest (#869, parent #473).

One versioned, machine-readable inventory of the network dependencies the
shipped capabilities actually have: which component needs it, under which
configuration key, whether it is required/optional/conditional, whether a
supported local replacement exists, and what stops working when it is
unavailable.

Honesty boundaries, per the issue:

- This is inventory plus configuration validation. It is **not** runtime
  isolation evidence and makes no deployment accreditation claim: static
  checks flag unknown or new settings for review; they do not prove absence
  of hidden network calls. A future live network rehearsal (#870) is a
  separate evidence kind and is explicitly recorded as not performed here.
- Build/install/upgrade dependencies (package registries, base images) are
  separate entries with their own phase; offline bundle production stays
  #474.
- The manifest never carries secret values or customer-specific endpoints:
  entries name configuration keys and protocol facts only, and validation
  rejects material that looks like a secret.
- Profile-specific omissions carry an explicit reason per component — the
  schema deliberately has no boolean "sovereign" flag.
- The settings inventory is scanned from the existing settings registry
  (``axis_api.config.Settings``); this module is not a second settings
  registry.
"""

from __future__ import annotations

import re
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel
from pydantic import Field, model_validator

MANIFEST_FORMAT = "axis.runtime-dependency-manifest"
MANIFEST_VERSION = (1, 0)

DependencyComponent = Literal[
    "api",
    "web",
    "worker",
    "postgres",
    "typedb",
    "temporal",
    "identity",
    "object_storage",
    "model_inference",
    "network_baseline",
    "telemetry",
    "static_assets",
    "diagnostics",
]
DependencyPhase = Literal["build_install_upgrade", "normal_runtime"]
DependencyStatus = Literal["required", "optional", "conditional"]

_MAX_ENTRIES = 256
_MAX_PROFILES = 32

# Endpoint-shaped settings live in the existing settings registry under these
# alias shapes. The scan is deliberately narrow; anything endpoint-like that
# does not match must be added here and to an entry (or reviewed into
# REVIEWED_NON_ENDPOINT_KEYS with a reason) — a new key failing the check is
# the intended behavior, not a gap.
_ENDPOINT_SCAN_PATTERN = re.compile(
    r"AXIS_.*(ENDPOINT|URL|ADDRESS|HOST|DSN|ISSUER|EXPORTER|BASE_URLS?)", re.I
)

# Keys the endpoint scan flags that review confirmed are not network
# dependencies. Mapping key → review reason; the validator keeps this list
# closed so a removed reason is caught too.
REVIEWED_NON_ENDPOINT_KEYS: dict[str, str] = {
    "AXIS_OIDC_SESSION_COOKIE_HOST_PREFIX": (
        "cookie attribute (host prefix), not a network endpoint"
    ),
    "AXIS_EXTERNAL_DB_LIVE_QUERY_ENDPOINT_TARGET_SHA256": (
        "integrity pin over the configured endpoint value, not a network"
        " destination; the endpoint itself is AXIS_EXTERNAL_DB_LIVE_QUERY_DSN"
    ),
    "AXIS_EXTERNAL_DB_LIVE_QUERY_PRIVATE_ENDPOINT_REF": (
        "secret-manager reference that resolves the endpoint value, not a"
        " network destination; no secret values enter this manifest"
    ),
}


class RuntimeDependencyManifestError(ValueError):
    """Raised for manifest construction/validation misuse."""

    UNCLASSIFIED_ENDPOINT_SETTING = "unclassified_endpoint_setting"
    ENTRY_INVALID = "dependency_entry_invalid"
    DUPLICATE_ENTRY = "duplicate_dependency_entry"
    PACKAGED_COMPONENT_UNCOVERED = "packaged_component_uncovered"
    OMISSION_INVALID = "profile_omission_invalid"
    SECRET_MATERIAL = "secret_material_detected"
    REVIEWED_KEY_DRIFT = "reviewed_non_endpoint_key_drift"

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class SchemaVersion(ContractModel):
    major: int = Field(ge=0, le=99, strict=True)
    minor: int = Field(ge=0, le=99, strict=True)


class DependencyEntry(ContractModel):
    """One network dependency of one shipped capability."""

    entry_id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    component: DependencyComponent
    capability_owner: str = Field(min_length=2, max_length=60)
    purpose: str = Field(min_length=3, max_length=300)
    configuration_key: str = Field(min_length=3, max_length=120)
    phase: DependencyPhase = "normal_runtime"
    status: DependencyStatus
    direction: str = Field(min_length=3, max_length=60)
    protocol: str = Field(min_length=2, max_length=60)
    port: int | None = Field(default=None, ge=1, le=65535, strict=True)
    local_service_reference: str | None = Field(default=None, max_length=200)
    local_replacement: str | None = Field(default=None, max_length=300)
    failure_behavior: str = Field(min_length=3, max_length=300)
    evidence_reference: str = Field(min_length=3, max_length=200)

    @model_validator(mode="after")
    def coherent_entry(self) -> DependencyEntry:
        if self.phase == "normal_runtime" and not self.failure_behavior:
            raise ValueError("runtime entries require an explicit failure behavior")
        return self


class ProfileOmission(ContractModel):
    """One component intentionally absent from a deployment profile."""

    component: DependencyComponent
    reason: str = Field(min_length=8, max_length=300)


class ManifestProfile(ContractModel):
    """A named deployment profile with explicit, reasoned omissions."""

    profile_id: str = Field(min_length=3, max_length=60, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    omissions: tuple[ProfileOmission, ...] = Field(default=(), max_length=24)


class RuntimeDependencyManifest(ContractModel):
    """The frozen, versioned dependency inventory for one release."""

    schema_version: SchemaVersion
    release: str = Field(min_length=1, max_length=80)
    entries: tuple[DependencyEntry, ...] = Field(max_length=_MAX_ENTRIES)
    endpoint_settings: tuple[str, ...] = Field(default=(), max_length=128)
    reviewed_non_endpoint_keys: tuple[str, ...] = Field(default=(), max_length=32)
    packaged_components: tuple[DependencyComponent, ...] = Field(default=(), max_length=32)
    profiles: tuple[ManifestProfile, ...] = Field(default=(), max_length=_MAX_PROFILES)
    inventory_evidence_reference: str = Field(min_length=3, max_length=200)
    configuration_validation_reference: str = Field(min_length=3, max_length=200)
    live_rehearsal_reference: str | None = Field(default=None, max_length=200)


# --- The curated inventory ----------------------------------------------------
# (The tuples below are the reviewable source of truth; keys name settings,
# never values.)

def dependency_entries() -> tuple[DependencyEntry, ...]:
    """The reviewed inventory. Edit here, then regenerate the matrix doc."""

    def entry(
        entry_id: str,
        component: DependencyComponent,
        owner: str,
        purpose: str,
        key: str,
        status: DependencyStatus,
        direction: str,
        protocol: str,
        port: int | None,
        failure: str,
        evidence: str,
        *,
        local_service: str | None = None,
        local_replacement: str | None = None,
        phase: DependencyPhase = "normal_runtime",
    ) -> DependencyEntry:
        return DependencyEntry(
            entry_id=entry_id,
            component=component,
            capability_owner=owner,
            purpose=purpose,
            configuration_key=key,
            phase=phase,
            status=status,
            direction=direction,
            protocol=protocol,
            port=port,
            local_service_reference=local_service,
            local_replacement=local_replacement,
            failure_behavior=failure,
            evidence_reference=evidence,
        )

    return (
        # --- api: primary stores -------------------------------------------------
        entry(
            "api-postgres", "api", "operational-model", "Primary relational store",
            "AXIS_POSTGRES_DSN", "required", "outbound", "postgresql/tcp", 5432,
            "Startup blocked; readiness reports the store not ready.",
            "services/api/tests/test_runtime_readiness.py",
            local_service="postgres primary service (compose/helm profile)",
        ),
        entry(
            "api-redis", "api", "trust", "Distributed rate limiting backend",
            "AXIS_REDIS_URL", "conditional", "outbound", "redis/tcp", 6379,
            "Production requires redis (fail-closed); development falls back.",
            "services/api/tests/test_rate_limit.py",
            local_service="redis local service",
        ),
        entry(
            "api-typedb", "api", "operational-model", "Ontology graph store",
            "AXIS_TYPEDB_ADDRESS", "required", "outbound", "typedb/tcp", 1729,
            "Ontology queries fail; readiness reports the store not ready.",
            "services/api/src/axis_api/ontology/queries.py",
            local_service="TypeDB local service",
        ),
        entry(
            "api-temporal", "api", "workflow", "Workflow engine connectivity",
            "AXIS_TEMPORAL_ADDRESS", "conditional", "outbound", "grpc/tcp", 7233,
            "Workflow signals unavailable; governed domain flows degrade per feature flags.",
            "services/api/tests/test_runtime_readiness.py",
            local_service="Temporal local service",
        ),
        entry(
            "api-external-db-live-query", "api", "data",
            "Connector live query against an approved external database",
            "AXIS_EXTERNAL_DB_LIVE_QUERY_DSN", "conditional", "outbound",
            "postgresql/tcp", 5432,
            "Live query stays disabled; no implicit fallback.",
            "services/api/tests/test_connector_configurations.py",
            local_service="customer-provided database reachable over the approved network path",
        ),
        # --- identity (owner: trust) --------------------------------------------
        entry(
            "identity-jwks", "identity", "trust", "OIDC token signature validation (JWKS)",
            "AXIS_OIDC_JWKS_URL", "conditional", "outbound", "https", 443,
            "Token validation fails closed when keys cannot be refreshed.",
            "services/api/src/axis_api/main.py",
            local_service="locally hosted identity provider",
            local_replacement="self-hosted OIDC provider with API-side JWKS caching",
        ),
        entry(
            "identity-token-endpoint", "identity", "trust", "OIDC code exchange",
            "AXIS_OIDC_TOKEN_URL", "conditional", "outbound", "https", 443,
            "Login cannot complete new sessions; existing sessions unaffected until expiry.",
            "services/api/src/axis_api/main.py",
            local_service="locally hosted identity provider",
            local_replacement="self-hosted OIDC provider",
        ),
        entry(
            "identity-authorization-endpoint", "identity", "trust",
            "Browser authorization redirect",
            "AXIS_OIDC_AUTHORIZATION_URL", "conditional", "outbound", "https", 443,
            "Login cannot start; API reachable for already-authenticated sessions.",
            "services/api/src/axis_api/main.py",
            local_service="locally hosted identity provider",
            local_replacement="self-hosted OIDC provider",
        ),
        entry(
            "identity-end-session", "identity", "trust", "Logout (end-session) redirect",
            "AXIS_OIDC_END_SESSION_URL", "optional", "outbound", "https", 443,
            "Logout stays local-only; provider-side termination skipped.",
            "services/api/src/axis_api/main.py",
            local_service="locally hosted identity provider",
            local_replacement="self-hosted OIDC provider",
        ),
        entry(
            "identity-issuer", "identity", "trust", "OIDC issuer discovery fallback",
            "AXIS_OIDC_ISSUER", "conditional", "outbound", "https", 443,
            "Discovery fallback unavailable; explicit endpoint configuration still works.",
            "services/api/src/axis_api/main.py",
            local_service="locally hosted identity provider",
            local_replacement="self-hosted OIDC provider",
        ),
        # --- object storage ------------------------------------------------------
        entry(
            "object-storage-export", "object_storage", "data",
            "Canonical object store for connector export envelopes",
            "AXIS_CONNECTOR_EXPORT_S3_ENDPOINT", "conditional", "outbound",
            "http/https", 9000,
            "Connector export disabled; readiness reports the store not ready when required.",
            "services/api/tests/test_runtime_readiness.py",
            local_service="S3-compatible local object store (e.g. MinIO fixture)",
        ),
        # --- model inference -----------------------------------------------------
        entry(
            "model-inference-routing", "model_inference", "intelligence",
            "Model routing to allowlisted inference base URLs",
            "AXIS_MODEL_INVOCATION_ALLOWED_BASE_URLS", "optional", "outbound",
            "https", None,
            "Model features stay disabled; no implicit fallback route.",
            "services/api/src/axis_api/model_invocations.py",
            local_replacement="self-hosted inference endpoint inside the allowlist",
        ),
        # --- telemetry -----------------------------------------------------------
        entry(
            "telemetry-otlp", "telemetry", "deployment",
            "OTLP telemetry export",
            "AXIS_OTEL_EXPORTER_OTLP_ENDPOINT", "optional", "outbound",
            "otlp/grpc+http", 4317,
            "Telemetry dropped locally; service unaffected.",
            "services/api/src/axis_api/telemetry.py",
            local_service="local OTLP collector endpoint",
            local_replacement="self-hosted collector",
        ),
        # --- web -----------------------------------------------------------------
        entry(
            "web-public-base-url", "web", "experience",
            "Advertised public URL of the web console",
            "AXIS_PUBLIC_BASE_URL", "required", "inbound (advertised)", "http/https",
            None,
            "Redirects and absolute links break until reconfigured.",
            "services/api/src/axis_api/config.py",
        ),
        entry(
            "web-api-base-url", "web", "experience",
            "Browser calls from the web console to the API",
            "AXIS_API_BASE_URL", "required", "inbound (to api)", "http/https", None,
            "Console cannot reach the API; API itself unaffected.",
            "services/api/src/axis_api/config.py",
        ),
        # --- static assets -------------------------------------------------------
        entry(
            "static-assets-fonts", "static_assets", "experience",
            "Browser font and static asset delivery",
            "none (self-hosted build output)", "optional", "inbound (browser)",
            "https", None,
            "Self-hosted via the build output; a remote font CDN is an"
            " unsupported state, not a hidden dependency.",
            "apps/web/next.config.ts",
            local_replacement="self-hosted assets served by the web deployment",
        ),
        # --- network baseline (DNS / time / PKI) ---------------------------------
        entry(
            "network-dns", "network_baseline", "deployment",
            "Name resolution for every outbound dependency",
            "none (resolver configuration)", "required", "outbound", "dns udp/tcp", 53,
            "Name resolution failure blocks hostname-based dependencies;"
            " IP-pinned local services keep working.",
            "infra/helm/limes-axis/templates/networkpolicy.yaml",
        ),
        entry(
            "network-ntp", "network_baseline", "deployment",
            "Clock discipline for token and lease validity",
            "none (host time sync)", "required", "outbound", "ntp/udp", 123,
            "Clock skew invalidates tokens and fenced leases; local RTC bounds drift.",
            "services/api/src/axis_api/portability_restore_runner.py",
        ),
        entry(
            "network-pki", "network_baseline", "deployment",
            "TLS trust anchors for outbound https",
            "none (host trust store)", "required", "outbound", "x509/https", None,
            "Untrusted chain fails closed; no bypass.",
            "services/api/src/axis_api/config.py",
        ),
        # --- diagnostics ---------------------------------------------------------
        entry(
            "diagnostics-status-page", "diagnostics", "trust",
            "Operator-facing status page link",
            "AXIS_SUPPORT_STATUS_PAGE_URL", "optional", "outbound (browser-side)",
            "https", 443,
            "Link unreachable; no functional impact on the platform.",
            "services/api/src/axis_api/support_diagnostics.py",
        ),
        entry(
            "diagnostics-runbook", "diagnostics", "trust",
            "Operator-facing runbook link",
            "AXIS_SUPPORT_CUSTOMER_RUNBOOK_URL", "optional", "outbound (browser-side)",
            "https", 443,
            "Link unreachable; no functional impact on the platform.",
            "services/api/src/axis_api/support_diagnostics.py",
        ),
        # --- build/install/upgrade (separate from runtime; #474 owns bundles) ----
        entry(
            "build-language-packages", "api", "deployment",
            "Language package registries at image build time",
            "none (build tooling)", "required", "outbound", "https", 443,
            "Build fails; runtime of already-built images unaffected.",
            "services/api/pyproject.toml",
            phase="build_install_upgrade",
        ),
        entry(
            "build-container-base-images", "web", "deployment",
            "Container base image retrieval at build time",
            "none (build tooling)", "required", "outbound", "https", 443,
            "Build fails; runtime of already-built images unaffected.",
            "apps/web/Dockerfile",
            phase="build_install_upgrade",
        ),
        # --- worker --------------------------------------------------------------
        entry(
            "worker-temporal", "worker", "workflow",
            "Worker dispatch connectivity to the workflow engine",
            "AXIS_TEMPORAL_ADDRESS", "required", "outbound", "grpc/tcp", 7233,
            "Worker cannot claim activities; queued work waits, no data loss.",
            "services/worker/src/axis_worker/connector_live_sync_activities.py",
            local_service="Temporal local service",
        ),
    )


def scan_endpoint_setting_keys() -> tuple[str, ...]:
    """Scan the existing settings registry for endpoint-shaped keys."""

    from axis_api.config import Settings

    keys = set()
    for name, field in Settings.model_fields.items():
        alias = field.alias or name
        if _ENDPOINT_SCAN_PATTERN.match(alias):
            keys.add(alias)
    return tuple(sorted(keys))


def build_runtime_dependency_manifest(*, release: str) -> RuntimeDependencyManifest:
    """Build the manifest for one release from the curated inventory and
    the live settings registry scan."""

    entries = dependency_entries()
    endpoint_keys = scan_endpoint_setting_keys()
    covered = {entry.configuration_key for entry in entries}
    reviewed = set(REVIEWED_NON_ENDPOINT_KEYS)
    unclassified = sorted(set(endpoint_keys) - covered - reviewed)
    if unclassified:
        raise RuntimeDependencyManifestError(
            RuntimeDependencyManifestError.UNCLASSIFIED_ENDPOINT_SETTING,
            ", ".join(unclassified),
        )
    drifted = sorted(reviewed - set(endpoint_keys))
    if drifted:
        raise RuntimeDependencyManifestError(
            RuntimeDependencyManifestError.REVIEWED_KEY_DRIFT,
            ", ".join(drifted),
        )
    return RuntimeDependencyManifest(
        schema_version=SchemaVersion(major=MANIFEST_VERSION[0], minor=MANIFEST_VERSION[1]),
        release=release,
        entries=entries,
        endpoint_settings=endpoint_keys,
        reviewed_non_endpoint_keys=tuple(sorted(reviewed)),
        packaged_components=tuple(
            sorted({entry.component for entry in entries})
        ),
        profiles=(),
        inventory_evidence_reference=(
            "services/api/tests/test_runtime_dependency_manifest.py"
        ),
        configuration_validation_reference=(
            "axis_api.runtime_dependency_manifest.validate_runtime_dependency_manifest"
        ),
        live_rehearsal_reference=None,
    )


_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*="),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def _assert_no_secret_material(manifest: RuntimeDependencyManifest) -> None:
    for entry in manifest.entries:
        fields = [
            entry.purpose,
            entry.failure_behavior,
            entry.evidence_reference,
            entry.local_service_reference or "",
            entry.local_replacement or "",
        ]
        for value in fields:
            for pattern in _SECRET_PATTERNS:
                if pattern.search(value):
                    raise RuntimeDependencyManifestError(
                        RuntimeDependencyManifestError.SECRET_MATERIAL,
                        entry.entry_id,
                    )


def validate_runtime_dependency_manifest(
    manifest: RuntimeDependencyManifest,
    *,
    scanned_endpoint_keys: tuple[str, ...] | None = None,
) -> None:
    """Consistency-check the manifest against its own claims and, when
    provided, an externally scanned endpoint key list (so a test can
    simulate a brand-new unreviewed setting)."""

    ids: set[str] = set()
    covered_keys: set[str] = set()
    components: set[str] = set()
    for entry in manifest.entries:
        if entry.entry_id in ids:
            raise RuntimeDependencyManifestError(
                RuntimeDependencyManifestError.DUPLICATE_ENTRY, entry.entry_id
            )
        ids.add(entry.entry_id)
        covered_keys.add(entry.configuration_key)
        components.add(entry.component)
    _assert_no_secret_material(manifest)

    endpoint_keys = set(
        scanned_endpoint_keys
        if scanned_endpoint_keys is not None
        else manifest.endpoint_settings
    )
    unclassified = sorted(
        endpoint_keys
        - covered_keys
        - set(manifest.reviewed_non_endpoint_keys)
    )
    if unclassified:
        raise RuntimeDependencyManifestError(
            RuntimeDependencyManifestError.UNCLASSIFIED_ENDPOINT_SETTING,
            ", ".join(unclassified),
        )
    ghosted = sorted(set(manifest.reviewed_non_endpoint_keys) - endpoint_keys)
    if ghosted:
        raise RuntimeDependencyManifestError(
            RuntimeDependencyManifestError.REVIEWED_KEY_DRIFT,
            ", ".join(ghosted),
        )
    declared_components = set(manifest.packaged_components)
    if declared_components and declared_components != components:
        missing = sorted(declared_components - components)
        raise RuntimeDependencyManifestError(
            RuntimeDependencyManifestError.PACKAGED_COMPONENT_UNCOVERED,
            ", ".join(missing) if missing else "packaged components drift",
        )
    manifest_components = components
    for profile in manifest.profiles:
        for omission in profile.omissions:
            if omission.component not in manifest_components:
                raise RuntimeDependencyManifestError(
                    RuntimeDependencyManifestError.OMISSION_INVALID,
                    f"{profile.profile_id}:{omission.component}",
                )


def unclassified_endpoint_settings(
    manifest: RuntimeDependencyManifest,
    *,
    scanned_endpoint_keys: tuple[str, ...],
) -> tuple[str, ...]:
    """Endpoint-shaped settings the manifest does not account for yet."""

    covered = {entry.configuration_key for entry in manifest.entries}
    return tuple(
        sorted(
            set(scanned_endpoint_keys)
            - covered
            - set(manifest.reviewed_non_endpoint_keys)
        )
    )


def render_dependency_matrix(manifest: RuntimeDependencyManifest) -> str:
    """Deterministic human-readable matrix (sorted, fixed columns, LF)."""

    lines = [
        "# Runtime dependency matrix",
        "",
        f"Release: {manifest.release} · manifest {MANIFEST_FORMAT} v"
        f"{manifest.schema_version.major}.{manifest.schema_version.minor}",
        "",
        "Generated from `axis_api/runtime_dependency_manifest.py`; edit the",
        "curated inventory there, never this file. Static inventory only —",
        "not runtime isolation evidence and not a deployment accreditation.",
        "",
        "| Entry | Component | Owner | Purpose | Configuration key | Phase |"
        " Status | Direction | Protocol/Port | Local replacement | Failure behavior |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for entry in sorted(manifest.entries, key=lambda e: (e.component, e.entry_id)):
        port = str(entry.port) if entry.port is not None else "—"
        local = entry.local_replacement or entry.local_service_reference or "—"
        row = (
            "| {id} | {component} | {owner} | {purpose} | `{key}` | {phase} |"
            " {status} | {direction} | {protocol}/{port} | {local} | {failure} |"
        )
        lines.append(
            row.format(
                id=entry.entry_id,
                component=entry.component,
                owner=entry.capability_owner,
                purpose=entry.purpose.replace("|", "\\|"),
                key=entry.configuration_key,
                phase=entry.phase,
                status=entry.status,
                direction=entry.direction,
                protocol=entry.protocol,
                port=port,
                local=local.replace("|", "\\|"),
                failure=entry.failure_behavior.replace("|", "\\|"),
            )
        )
    lines.extend(
        [
            "",
            "## Endpoint settings accounted for",
            "",
        ]
    )
    lines.extend(f"- `{key}`" for key in manifest.endpoint_settings)
    if manifest.reviewed_non_endpoint_keys:
        lines.extend(
            [
                "",
                "## Reviewed non-endpoint keys",
                "",
            ]
        )
        lines.extend(f"- `{key}`" for key in manifest.reviewed_non_endpoint_keys)
    lines.append("")
    return "\n".join(lines)


def local_only_sample_profile(
    manifest: RuntimeDependencyManifest,
) -> ManifestProfile:
    """The documented local-only sample profile: optional external features
    are omitted with explicit reasons; nothing else changes."""

    return ManifestProfile(
        profile_id="local-only-sample",
        omissions=(
            ProfileOmission(
                component="model_inference",
                reason="sample profile runs without external model routing;"
                " the feature stays disabled",
            ),
            ProfileOmission(
                component="telemetry",
                reason="sample profile exports no telemetry; a local"
                " collector may be attached without code changes",
            ),
            ProfileOmission(
                component="diagnostics",
                reason="sample profile carries no external status-page/runbook links",
            ),
        ),
    )
