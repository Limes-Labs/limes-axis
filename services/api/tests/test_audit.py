from axis_api.audit import AuditEventCreate


def test_audit_event_requires_tenant_actor_and_type() -> None:
    event = AuditEventCreate(
        tenant_id="tenant_demo",
        actor_id="actor_ops",
        event_type="ACTION_PROPOSED",
        payload={"action_id": "create_risk"},
    )
    assert event.tenant_id == "tenant_demo"
    assert event.actor_id == "actor_ops"
    assert event.event_type == "ACTION_PROPOSED"
