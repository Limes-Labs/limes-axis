import secrets

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import Actor, AuditEvent, Base, Tenant, TenantQuota
from axis_api.oidc_code_flow import session_cookie_name, sign_cookie
from axis_api.persistence import (
    AxisPersistenceRepository,
    TenantCreate,
    TenantQuotaUpsert,
)
from axis_api.platform_tenants import TenantQuotaKey

OPERATOR_ACTOR = "axis-platform-operator-role"
OPERATOR_SCOPES = [
    "platform:tenant:operator",
    "platform:tenant:provision",
    "platform:tenant:suspend",
    "platform:tenant:read",
    "platform:tenant:quota",
]
TENANT_ID = "tenant_acme_manufacturing"


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


def build_test_client(
    settings: Settings | None = None,
) -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    app = create_app(settings or Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = factory
    return TestClient(app), factory


def provision_payload(
    *,
    tenant_id: str = TENANT_ID,
    display_name: str = "Acme Manufacturing",
    idempotency_key: str = "idem_provision_acme_v1",
    actor_scopes: list[str] | None = None,
    bootstrap_admin: dict | None = None,
) -> dict:
    payload = {
        "tenant_id": tenant_id,
        "display_name": display_name,
        "description": "Reference multi-tenant SaaS design partner.",
        "requested_by": OPERATOR_ACTOR,
        "actor_scopes": actor_scopes if actor_scopes is not None else OPERATOR_SCOPES,
        "idempotency_key": idempotency_key,
        "notes": ["Provisioned during platform tenant tests."],
    }
    payload["bootstrap_admin"] = (
        bootstrap_admin
        if bootstrap_admin is not None
        else {
            "actor_id": "acme-platform-admin-role",
            "display_name": "Acme platform admin",
            "scopes": ["platform:policy:author", "audit:read"],
        }
    )
    return payload


def suspend_payload(*, actor_scopes: list[str] | None = None) -> dict:
    return {
        "requested_by": OPERATOR_ACTOR,
        "actor_scopes": actor_scopes if actor_scopes is not None else OPERATOR_SCOPES,
        "reason": "Suspicious usage pending design-partner review.",
        "notes": ["Suspended during platform tenant tests."],
    }


def reactivate_payload(*, actor_scopes: list[str] | None = None) -> dict:
    return {
        "requested_by": OPERATOR_ACTOR,
        "actor_scopes": actor_scopes if actor_scopes is not None else OPERATOR_SCOPES,
        "reason": "Review completed.",
    }


def quota_payload(
    *,
    quotas: dict | None = None,
    actor_scopes: list[str] | None = None,
) -> dict:
    return {
        "requested_by": OPERATOR_ACTOR,
        "actor_scopes": actor_scopes if actor_scopes is not None else OPERATOR_SCOPES,
        "quotas": quotas
        if quotas is not None
        else {
            "api_requests_per_window": 50,
            "max_concurrent_sessions": 2,
        },
    }


def audit_events(
    session: Session,
    tenant_id: str,
    event_type: str | None = None,
) -> list[AuditEvent]:
    statement = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
    if event_type is not None:
        statement = statement.where(AuditEvent.event_type == event_type)
    return list(session.scalars(statement.order_by(AuditEvent.created_at.asc())))


def session_cookie_for(
    settings: Settings,
    *,
    tenant_id: str,
    actor_id: str = "acme-console-user-role",
) -> tuple[str, str]:
    cookie_value = sign_cookie(
        {
            "kind": "oidc_session",
            "session_id": secrets.token_urlsafe(48),
            "actor_id": actor_id,
            "tenant_id": tenant_id,
            "scopes": ["audit:read"],
            "expires_at": 4102444800,
        },
        settings,
    )
    return session_cookie_name(settings), cookie_value


def test_provision_endpoint_creates_tenant_bootstrap_admin_and_audit() -> None:
    client, factory = build_test_client()

    response = client.post("/platform/tenants", json=provision_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == TENANT_ID
    assert body["status"] == "active"
    assert body["created_by"] == OPERATOR_ACTOR
    assert body["bootstrap_admin_actor_id"] == "acme-platform-admin-role"
    assert body["provision_idempotency_key"] == "idem_provision_acme_v1"
    assert body["audit_event_type"] == "platform.tenant.provisioned"
    assert body["idempotent_replay"] is False
    assert body["permission_decision"]["allowed"] is True

    with factory() as session:
        tenant = session.get(Tenant, TENANT_ID)
        assert tenant is not None
        assert tenant.status == "active"
        actor = session.get(Actor, "acme-platform-admin-role")
        assert actor is not None
        assert actor.tenant_id == TENANT_ID
        events = audit_events(session, TENANT_ID, "platform.tenant.provisioned")
        assert len(events) == 1
        assert events[0].actor_id == OPERATOR_ACTOR
        assert events[0].payload["bootstrap_admin_actor_id"] == "acme-platform-admin-role"
        assert events[0].payload["bootstrap_admin_requested_scopes"] == [
            "platform:policy:author",
            "audit:read",
        ]
        assert events[0].payload["permission_decision"]["allowed"] is True


def test_provision_endpoint_replays_idempotent_request() -> None:
    client, factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201

    replay = client.post("/platform/tenants", json=provision_payload())

    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    with factory() as session:
        assert len(list(session.scalars(select(Tenant)))) == 1
        assert len(list(session.scalars(select(Actor)))) == 1
        assert len(audit_events(session, TENANT_ID, "platform.tenant.provisioned")) == 1


def test_provision_endpoint_rejects_idempotency_conflict() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201

    conflict = client.post(
        "/platform/tenants",
        json=provision_payload(display_name="Acme Manufacturing Renamed"),
    )

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["reason"] == "provision_idempotency_conflict"


def test_provision_endpoint_rejects_duplicate_tenant() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201

    duplicate = client.post(
        "/platform/tenants",
        json=provision_payload(idempotency_key="idem_provision_acme_v2"),
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["reason"] == "tenant_already_exists"


def test_provision_endpoint_rejects_existing_bootstrap_admin_actor() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).create_tenant(
            TenantCreate(
                tenant_id="tenant_other",
                display_name="Other tenant",
                created_by=OPERATOR_ACTOR,
            )
        )
        session.add(
            Actor(
                id="acme-platform-admin-role",
                tenant_id="tenant_other",
                display_name="Existing actor",
                actor_type="human",
            )
        )

    response = client.post("/platform/tenants", json=provision_payload())

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "bootstrap_admin_actor_exists"


def test_provision_endpoint_rejects_missing_operator_scope() -> None:
    client, factory = build_test_client()

    response = client.post(
        "/platform/tenants",
        json=provision_payload(actor_scopes=["platform:tenant:provision"]),
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["required_permission"] == "platform:tenant:operator"
    assert detail["reason"] == "missing_required_scope"
    with factory() as session:
        assert session.get(Tenant, TENANT_ID) is None


def test_provision_endpoint_rejects_missing_provision_scope() -> None:
    client, _factory = build_test_client()

    response = client.post(
        "/platform/tenants",
        json=provision_payload(actor_scopes=["platform:tenant:operator"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["required_permission"] == "platform:tenant:provision"


def test_provision_endpoint_rejects_invalid_tenant_id() -> None:
    client, _factory = build_test_client()

    response = client.post(
        "/platform/tenants",
        json=provision_payload(tenant_id="Tenant Invalid Id"),
    )

    assert response.status_code == 422


def test_registry_endpoint_lists_tenants_with_status_filter() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201
    assert (
        client.post(
            "/platform/tenants",
            json=provision_payload(
                tenant_id="tenant_beta_manufacturing",
                display_name="Beta Manufacturing",
                idempotency_key="idem_provision_beta_v1",
                bootstrap_admin={
                    "actor_id": "beta-platform-admin-role",
                    "display_name": "Beta platform admin",
                    "scopes": [],
                },
            ),
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/platform/tenants/{TENANT_ID}/suspend",
            json=suspend_payload(),
        ).status_code
        == 200
    )

    registry = client.get("/platform/tenants").json()
    assert registry["tenant_count"] == 2
    assert registry["active_tenant_count"] == 1

    suspended = client.get("/platform/tenants", params={"status": "suspended"}).json()
    assert suspended["tenant_count"] == 1
    assert suspended["tenants"][0]["tenant_id"] == TENANT_ID
    assert suspended["tenants"][0]["suspension_reason"] == (
        "Suspicious usage pending design-partner review."
    )


def test_registry_endpoint_requires_operator_read_scopes_when_authenticated() -> None:
    client, _factory = build_test_client()
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:read"],
        )
    )

    denied = client.get(
        "/platform/tenants",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["required_permission"] == "platform:tenant:operator"

    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:operator", "platform:tenant:read"],
        )
    )
    allowed = client.get(
        "/platform/tenants",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert allowed.status_code == 200


def test_suspended_tenant_requests_are_rejected_fail_closed_and_reactivate_restores() -> None:
    client, factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="acme-console-user-role",
            tenant_id=TENANT_ID,
            scopes=["platform:policy:read"],
        )
    )
    bearer = {"Authorization": "Bearer valid-token"}

    before = client.get(
        "/platform/policies",
        params={"tenant_id": TENANT_ID},
        headers=bearer,
    )
    assert before.status_code == 200

    suspended = client.post(
        f"/platform/tenants/{TENANT_ID}/suspend",
        json=suspend_payload(),
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    assert suspended.json()["suspended_by"] == OPERATOR_ACTOR

    denied = client.get(
        "/platform/policies",
        params={"tenant_id": TENANT_ID},
        headers=bearer,
    )
    assert denied.status_code == 403
    detail = denied.json()["detail"]
    assert detail["reason"] == "tenant_suspended"
    assert detail["tenant_status"] == "suspended"

    with factory() as session:
        suspend_events = audit_events(session, TENANT_ID, "platform.tenant.suspended")
        assert len(suspend_events) == 1
        assert suspend_events[0].payload["reason"] == (
            "Suspicious usage pending design-partner review."
        )
        denial_events = audit_events(
            session,
            TENANT_ID,
            "platform.tenant.suspended_request.denied",
        )
        assert len(denial_events) == 1
        assert denial_events[0].actor_id == "acme-console-user-role"
        assert denial_events[0].payload["path"] == "/platform/policies"
        assert denial_events[0].payload["reason"] == "tenant_suspended"

    reactivated = client.post(
        f"/platform/tenants/{TENANT_ID}/reactivate",
        json=reactivate_payload(),
    )
    assert reactivated.status_code == 200
    body = reactivated.json()
    assert body["status"] == "active"
    assert body["reactivated_by"] == OPERATOR_ACTOR
    assert body["suspended_at"] is None
    assert body["suspension_reason"] is None

    restored = client.get(
        "/platform/policies",
        params={"tenant_id": TENANT_ID},
        headers=bearer,
    )
    assert restored.status_code == 200
    with factory() as session:
        assert len(audit_events(session, TENANT_ID, "platform.tenant.reactivated")) == 1


def test_suspend_endpoint_rejects_unknown_tenant_and_lifecycle_conflicts() -> None:
    client, _factory = build_test_client()

    missing = client.post(
        "/platform/tenants/tenant_missing/suspend",
        json=suspend_payload(),
    )
    assert missing.status_code == 404

    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201
    already_active = client.post(
        f"/platform/tenants/{TENANT_ID}/reactivate",
        json=reactivate_payload(),
    )
    assert already_active.status_code == 409
    assert already_active.json()["detail"]["reason"] == "tenant_already_active"

    assert (
        client.post(
            f"/platform/tenants/{TENANT_ID}/suspend",
            json=suspend_payload(),
        ).status_code
        == 200
    )
    second_suspend = client.post(
        f"/platform/tenants/{TENANT_ID}/suspend",
        json=suspend_payload(),
    )
    assert second_suspend.status_code == 409
    assert second_suspend.json()["detail"]["reason"] == "tenant_not_active"


def test_suspend_endpoint_rejects_missing_scopes_and_actor_impersonation() -> None:
    client, factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201

    unscoped = client.post(
        f"/platform/tenants/{TENANT_ID}/suspend",
        json=suspend_payload(actor_scopes=["platform:tenant:suspend"]),
    )
    assert unscoped.status_code == 403
    assert unscoped.json()["detail"]["required_permission"] == "platform:tenant:operator"

    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="another-operator-role",
            tenant_id="tenant_axis_platform_ops",
            scopes=OPERATOR_SCOPES,
        )
    )
    impersonation = client.post(
        f"/platform/tenants/{TENANT_ID}/suspend",
        json=suspend_payload(),
        headers={"Authorization": "Bearer valid-token"},
    )
    assert impersonation.status_code == 403
    assert impersonation.json()["detail"]["reason"] == "actor_mismatch"

    with factory() as session:
        tenant = session.get(Tenant, TENANT_ID)
        assert tenant is not None
        assert tenant.status == "active"


def test_authenticated_operator_manages_other_tenant_with_operator_scopes() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=OPERATOR_SCOPES,
        )
    )

    suspended = client.post(
        f"/platform/tenants/{TENANT_ID}/suspend",
        json=suspend_payload(actor_scopes=[]),
        headers={"Authorization": "Bearer valid-token"},
    )

    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    assert suspended.json()["suspended_by"] == OPERATOR_ACTOR


def test_quota_endpoint_updates_clears_and_audits_changes() -> None:
    client, factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201

    updated = client.put(
        f"/platform/tenants/{TENANT_ID}/quotas",
        json=quota_payload(),
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["quotas"] == {
        "api_requests_per_window": 50,
        "max_concurrent_sessions": 2,
    }
    assert {change["quota_key"]: change["new_value"] for change in body["changes"]} == {
        "api_requests_per_window": 50,
        "max_concurrent_sessions": 2,
    }
    assert all(
        change["audit_event_type"] == "platform.tenant.quota.updated"
        for change in body["changes"]
    )

    fetched = client.get(f"/platform/tenants/{TENANT_ID}/quotas")
    assert fetched.status_code == 200
    assert fetched.json()["quotas"] == body["quotas"]

    revised = client.put(
        f"/platform/tenants/{TENANT_ID}/quotas",
        json=quota_payload(
            quotas={
                "api_requests_per_window": 75,
                "max_connector_sync_rows_per_run": 3,
            }
        ),
    )
    assert revised.status_code == 200
    revised_body = revised.json()
    assert revised_body["quotas"] == {
        "api_requests_per_window": 75,
        "max_connector_sync_rows_per_run": 3,
    }
    changes = {change["quota_key"]: change for change in revised_body["changes"]}
    assert changes["api_requests_per_window"]["previous_value"] == 50
    assert changes["api_requests_per_window"]["new_value"] == 75
    assert changes["max_concurrent_sessions"]["previous_value"] == 2
    assert changes["max_concurrent_sessions"]["new_value"] is None
    assert changes["max_connector_sync_rows_per_run"]["previous_value"] is None
    assert changes["max_connector_sync_rows_per_run"]["new_value"] == 3

    with factory() as session:
        events = audit_events(session, TENANT_ID, "platform.tenant.quota.updated")
        assert len(events) == 5
        stored = {
            quota.quota_key: quota.quota_value
            for quota in session.scalars(select(TenantQuota))
        }
        assert stored == {
            "api_requests_per_window": 75,
            "max_connector_sync_rows_per_run": 3,
        }


def test_quota_endpoint_rejects_missing_scope_unknown_tenant_and_bad_values() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201

    unscoped = client.put(
        f"/platform/tenants/{TENANT_ID}/quotas",
        json=quota_payload(actor_scopes=["platform:tenant:operator"]),
    )
    assert unscoped.status_code == 403
    assert unscoped.json()["detail"]["required_permission"] == "platform:tenant:quota"

    missing = client.put(
        "/platform/tenants/tenant_missing/quotas",
        json=quota_payload(),
    )
    assert missing.status_code == 404
    assert client.get("/platform/tenants/tenant_missing/quotas").status_code == 404

    invalid = client.put(
        f"/platform/tenants/{TENANT_ID}/quotas",
        json=quota_payload(quotas={"api_requests_per_window": 0}),
    )
    assert invalid.status_code == 422


def test_quota_read_requires_operator_read_scopes_when_authenticated() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:operator"],
        )
    )

    denied = client.get(
        f"/platform/tenants/{TENANT_ID}/quotas",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert denied.status_code == 403
    assert denied.json()["detail"]["required_permission"] == "platform:tenant:read"


def test_tenant_detail_endpoint_returns_record() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201

    response = client.get(f"/platform/tenants/{TENANT_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == TENANT_ID
    assert body["display_name"] == "Acme Manufacturing"
    assert body["status"] == "active"
    assert body["bootstrap_admin_actor_id"] == "acme-platform-admin-role"
    assert body["audit_event_type"] == "platform.tenant.provisioned"


def test_tenant_detail_endpoint_returns_404_for_unknown_tenant() -> None:
    client, _factory = build_test_client()

    response = client.get("/platform/tenants/tenant_missing")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "NOT_FOUND"
    assert detail["tenant_id"] == "tenant_missing"


def test_tenant_detail_requires_operator_read_scopes_when_authenticated() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201

    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:read"],
        )
    )
    missing_operator = client.get(
        f"/platform/tenants/{TENANT_ID}",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert missing_operator.status_code == 403
    assert (
        missing_operator.json()["detail"]["required_permission"]
        == "platform:tenant:operator"
    )

    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:operator"],
        )
    )
    missing_read = client.get(
        f"/platform/tenants/{TENANT_ID}",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert missing_read.status_code == 403
    assert (
        missing_read.json()["detail"]["required_permission"] == "platform:tenant:read"
    )

    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:operator", "platform:tenant:read"],
        )
    )
    allowed = client.get(
        f"/platform/tenants/{TENANT_ID}",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["tenant_id"] == TENANT_ID


def test_tenant_detail_is_isolated_per_tenant_for_cross_tenant_operator() -> None:
    client, _factory = build_test_client()
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201
    assert (
        client.post(
            "/platform/tenants",
            json=provision_payload(
                tenant_id="tenant_beta_manufacturing",
                display_name="Beta Manufacturing",
                idempotency_key="idem_provision_beta_v1",
                bootstrap_admin={
                    "actor_id": "beta-platform-admin-role",
                    "display_name": "Beta platform admin",
                    "scopes": [],
                },
            ),
        ).status_code
        == 201
    )

    # A platform operator authenticated under a third ops tenant reads each
    # tenant across the tenant boundary and gets exactly the requested record,
    # never another tenant's data.
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:operator", "platform:tenant:read"],
        )
    )
    headers = {"Authorization": "Bearer valid-token"}

    acme = client.get(f"/platform/tenants/{TENANT_ID}", headers=headers)
    assert acme.status_code == 200
    assert acme.json()["tenant_id"] == TENANT_ID
    assert acme.json()["display_name"] == "Acme Manufacturing"

    beta = client.get(
        "/platform/tenants/tenant_beta_manufacturing", headers=headers
    )
    assert beta.status_code == 200
    assert beta.json()["tenant_id"] == "tenant_beta_manufacturing"
    assert beta.json()["display_name"] == "Beta Manufacturing"


def test_registry_endpoint_paginates_with_cursor() -> None:
    client, _factory = build_test_client()
    tenant_ids = [f"tenant_pager_{index:03d}" for index in range(5)]
    for index, tenant_id in enumerate(tenant_ids):
        assert (
            client.post(
                "/platform/tenants",
                json=provision_payload(
                    tenant_id=tenant_id,
                    display_name=f"Pager {index}",
                    idempotency_key=f"idem_pager_{index}",
                    bootstrap_admin={
                        "actor_id": f"pager-admin-{index}",
                        "display_name": f"Pager admin {index}",
                        "scopes": [],
                    },
                ),
            ).status_code
            == 201
        )

    seen: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        params: dict[str, str | int] = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        page = client.get("/platform/tenants", params=params).json()
        pages += 1
        page_ids = [tenant["tenant_id"] for tenant in page["tenants"]]
        seen.extend(page_ids)
        assert len(page_ids) <= 2
        if page["has_more"]:
            assert page["next_cursor"] is not None
            assert len(page_ids) == 2
            cursor = page["next_cursor"]
        else:
            assert page["next_cursor"] is None
            break

    # Keyset walk visited every tenant exactly once, in ascending id order.
    assert seen == sorted(tenant_ids)
    assert len(seen) == len(set(seen))
    assert pages == 3  # 2 + 2 + 1


def test_registry_endpoint_rejects_invalid_cursor() -> None:
    client, _factory = build_test_client()

    response = client.get("/platform/tenants", params={"cursor": "!!!not-base64!!!"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_FAILED"
    assert detail["reason"] == "invalid_tenant_cursor"


def rate_limited_settings() -> Settings:
    return Settings(
        postgres_dsn="sqlite+pysqlite://",
        api_rate_limit_enabled=True,
        api_rate_limit_requests=5,
        api_rate_limit_window_seconds=60,
        api_rate_limit_paths=["/health"],
        oidc_session_cookie_signing_secret="a-secure-cookie-signing-secret",
        tenant_state_cache_ttl_seconds=0,
    )


def seed_tenant_with_request_quota(
    factory: sessionmaker[Session],
    *,
    quota_value: int | None,
) -> None:
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        repository.create_tenant(
            TenantCreate(
                tenant_id=TENANT_ID,
                display_name="Acme Manufacturing",
                created_by=OPERATOR_ACTOR,
            )
        )
        if quota_value is not None:
            repository.upsert_tenant_quota(
                TenantQuotaUpsert(
                    tenant_id=TENANT_ID,
                    quota_key=TenantQuotaKey.API_REQUESTS_PER_WINDOW.value,
                    quota_value=quota_value,
                    updated_by=OPERATOR_ACTOR,
                )
            )


def test_rate_limit_enforces_tenant_quota_before_global_limit() -> None:
    settings = rate_limited_settings()
    client, factory = build_test_client(settings)
    seed_tenant_with_request_quota(factory, quota_value=2)
    cookie_name, cookie_value = session_cookie_for(settings, tenant_id=TENANT_ID)
    client.cookies.set(cookie_name, cookie_value)

    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    limited = client.get("/health")

    assert limited.status_code == 429
    detail = limited.json()["detail"]
    assert detail["scope"] == "tenant_quota"
    assert detail["limit"] == 2
    assert limited.headers["Retry-After"]


def test_rate_limit_falls_back_to_global_limit_without_tenant_quota() -> None:
    settings = rate_limited_settings()
    client, factory = build_test_client(settings)
    seed_tenant_with_request_quota(factory, quota_value=None)
    cookie_name, cookie_value = session_cookie_for(settings, tenant_id=TENANT_ID)
    client.cookies.set(cookie_name, cookie_value)

    for _ in range(5):
        assert client.get("/health").status_code == 200
    limited = client.get("/health")

    assert limited.status_code == 429
    assert limited.json()["detail"]["scope"] == "client_endpoint"
    assert limited.json()["detail"]["limit"] == 5


def test_rate_limit_bearer_token_does_not_select_tenant_quota() -> None:
    settings = rate_limited_settings()
    client, factory = build_test_client(settings)
    seed_tenant_with_request_quota(factory, quota_value=1)
    bearer = {"Authorization": "Bearer valid-token"}

    # A bearer request carrying a tenant claim must fall back to the global
    # limit (5), never the tenant's api_requests_per_window quota (1): the
    # middleware only resolves the tenant from the HMAC-verified session cookie,
    # so an unverified token claim can never select a higher per-tenant limit.
    for _ in range(5):
        assert client.get("/health", headers=bearer).status_code == 200
    limited = client.get("/health", headers=bearer)

    assert limited.status_code == 429
    assert limited.json()["detail"]["scope"] == "client_endpoint"
    assert limited.json()["detail"]["limit"] == 5


def test_rate_limit_ignores_unverifiable_session_cookies() -> None:
    settings = rate_limited_settings()
    client, factory = build_test_client(settings)
    seed_tenant_with_request_quota(factory, quota_value=1)
    cookie_name, _cookie_value = session_cookie_for(settings, tenant_id=TENANT_ID)
    client.cookies.set(cookie_name, "tampered-cookie-value")

    # A cookie that fails HMAC verification must never select a tenant limit.
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200


def test_tenant_state_cache_serves_stale_status_within_ttl() -> None:
    settings = Settings(
        postgres_dsn="sqlite+pysqlite://",
        tenant_state_cache_ttl_seconds=60,
    )
    client, factory = build_test_client(settings)
    assert client.post("/platform/tenants", json=provision_payload()).status_code == 201
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="acme-console-user-role",
            tenant_id=TENANT_ID,
            scopes=["platform:policy:read"],
        )
    )
    bearer = {"Authorization": "Bearer valid-token"}
    assert (
        client.get(
            "/platform/policies",
            params={"tenant_id": TENANT_ID},
            headers=bearer,
        ).status_code
        == 200
    )

    # Suspend behind the API's back: the cached active status keeps serving
    # until the TTL elapses or the entry is invalidated by a lifecycle route.
    with session_scope(factory) as session:
        tenant = session.get(Tenant, TENANT_ID)
        assert tenant is not None
        tenant.status = "suspended"
    stale = client.get(
        "/platform/policies",
        params={"tenant_id": TENANT_ID},
        headers=bearer,
    )
    assert stale.status_code == 200

    client.app.state.tenant_state_cache.invalidate(TENANT_ID)
    fresh = client.get(
        "/platform/policies",
        params={"tenant_id": TENANT_ID},
        headers=bearer,
    )
    assert fresh.status_code == 403
    assert fresh.json()["detail"]["reason"] == "tenant_suspended"
