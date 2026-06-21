import pytest

from axis_api.models_router import ModelEgressBlocked, ModelRouter, ModelRouteRequest


def test_external_model_egress_blocked_by_default() -> None:
    router = ModelRouter(external_egress_enabled=False)
    request = ModelRouteRequest(
        tenant_id="tenant_demo",
        provider="external-openai-compatible",
        model="example-model",
        prompt="Summarize this operational event.",
    )
    with pytest.raises(ModelEgressBlocked):
        router.route(request)


def test_local_model_route_allowed_without_external_egress() -> None:
    router = ModelRouter(external_egress_enabled=False)
    request = ModelRouteRequest(
        tenant_id="tenant_demo",
        provider="local-vllm",
        model="example-local-model",
        prompt="Summarize this operational event.",
    )
    assert router.route(request) == "local-vllm"
