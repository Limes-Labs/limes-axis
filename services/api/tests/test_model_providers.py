"""Unit tests for the self-hosted OpenAI-compatible runtime adapter.

The critical contract under test is base-URL normalization: operators
register endpoints both as ``http://host:11434`` and as
``http://host:11434/v1`` (the shape Ollama documents), and both must resolve
to a single ``/v1/chat/completions`` request path — never
``/v1/v1/chat/completions``.
"""

import httpx
import pytest

from axis_api import model_providers
from axis_api.model_providers import (
    ModelInvocationRuntimeRequest,
    SelfHostedOpenAICompatibleRuntime,
    openai_compatible_chat_completions_url,
)


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434/v1/chat/completions"),
        ("http://127.0.0.1:11434/", "http://127.0.0.1:11434/v1/chat/completions"),
        ("http://127.0.0.1:11434/v1", "http://127.0.0.1:11434/v1/chat/completions"),
        ("http://127.0.0.1:11434/v1/", "http://127.0.0.1:11434/v1/chat/completions"),
        ("http://127.0.0.1:11434/V1", "http://127.0.0.1:11434/v1/chat/completions"),
        (
            "https://models.internal/openai/v1",
            "https://models.internal/openai/v1/chat/completions",
        ),
        (
            "https://models.internal/openai",
            "https://models.internal/openai/v1/chat/completions",
        ),
    ],
)
def test_chat_completions_url_never_doubles_v1(base_url: str, expected: str) -> None:
    assert openai_compatible_chat_completions_url(base_url) == expected


def _runtime_request(base_url: str) -> ModelInvocationRuntimeRequest:
    return ModelInvocationRuntimeRequest(
        tenant_id="tenant_demo_manufacturing",
        invocation_id="unit-check",
        endpoint_id="ollama_local",
        base_url=base_url,
        model_id="llama3.2",
        prompt="Reply with the single word: ready",
    )


def _install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(**kwargs)

    monkeypatch.setattr(model_providers.httpx, "AsyncClient", client_factory)


@pytest.mark.parametrize(
    "base_url",
    ["http://models.local:11434", "http://models.local:11434/v1"],
)
async def test_invoke_posts_to_single_v1_path_for_both_base_url_shapes(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-unit-1",
                "choices": [{"message": {"role": "assistant", "content": "ready"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 1},
            },
        )

    _install_mock_transport(monkeypatch, handler)
    runtime = SelfHostedOpenAICompatibleRuntime(timeout_seconds=5.0)
    result = await runtime.invoke(_runtime_request(base_url))

    assert seen_paths == ["/v1/chat/completions"]
    assert result.status == "model_invocation_completed"
    assert result.output_text == "ready"
    assert result.input_tokens == 7
    assert result.output_tokens == 1


async def test_invoke_surfaces_provider_http_errors_as_typed_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    _install_mock_transport(monkeypatch, handler)
    runtime = SelfHostedOpenAICompatibleRuntime(timeout_seconds=5.0)

    with pytest.raises(model_providers.ModelProviderInvocationError) as excinfo:
        await runtime.invoke(_runtime_request("http://models.local:11434/v1"))

    assert excinfo.value.error_code == "provider_http_404"
