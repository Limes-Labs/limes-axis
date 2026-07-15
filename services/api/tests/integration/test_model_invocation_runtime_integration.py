"""Opt-in integration test against a real local OpenAI-compatible endpoint.

Run with a local vLLM/Ollama/llama.cpp server exposing ``/v1/chat/completions``:

    AXIS_RUN_INTEGRATION=1 \
    AXIS_INTEGRATION_MODEL_BASE_URL=http://127.0.0.1:11434 \
    AXIS_INTEGRATION_MODEL_ID=llama3.2 \
    uv run pytest tests/integration/test_model_invocation_runtime_integration.py
"""

import os

import pytest

from axis_api.model_providers import (
    ModelInvocationRuntimeRequest,
    SelfHostedOpenAICompatibleRuntime,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
    pytest.mark.skipif(
        not os.getenv("AXIS_INTEGRATION_MODEL_BASE_URL"),
        reason=(
            "set AXIS_INTEGRATION_MODEL_BASE_URL to a local OpenAI-compatible "
            "endpoint (vLLM/Ollama/llama.cpp)"
        ),
    ),
]


async def test_self_hosted_openai_compatible_runtime_round_trip() -> None:
    runtime = SelfHostedOpenAICompatibleRuntime(
        timeout_seconds=float(os.getenv("AXIS_INTEGRATION_MODEL_TIMEOUT_SECONDS", "60")),
        bearer_token=os.getenv("AXIS_INTEGRATION_MODEL_BEARER_TOKEN") or None,
        allowed_base_urls=[os.environ["AXIS_INTEGRATION_MODEL_BASE_URL"]],
    )
    result = await runtime.invoke(
        ModelInvocationRuntimeRequest(
            tenant_id="tenant_demo_manufacturing",
            invocation_id="integration-check",
            endpoint_id="integration_local_endpoint",
            base_url=os.environ["AXIS_INTEGRATION_MODEL_BASE_URL"],
            model_id=os.getenv("AXIS_INTEGRATION_MODEL_ID", "llama3.2"),
            prompt="Reply with the single word: ready",
            max_output_tokens=16,
            temperature=0.0,
        )
    )

    assert result.status == "model_invocation_completed"
    assert result.output_text.strip() != ""
    assert result.latency_ms >= 0
