"""Provider-agnostic model invocation runtime port.

The runtime boundary mirrors the connector execution adapters: the API core
talks to a :class:`ModelInvocationRuntime` protocol and never to a provider SDK
directly. Two adapters ship here:

* :class:`SelfHostedOpenAICompatibleRuntime` invokes an OpenAI-compatible
  chat-completions endpoint (vLLM, Ollama, llama.cpp server, TGI in
  OpenAI-compat mode) over HTTP with a strict timeout and no silent retries.
  Any transport, timeout or protocol failure raises a typed
  :class:`ModelProviderInvocationError`; the adapter never fabricates output.
* :class:`DeferredModelInvocationRuntime` is the fail-safe default when
  ``AXIS_MODEL_ROUTING_EXECUTION_ENABLED`` is off: it returns a typed
  ``model_invocation_deferred`` result and performs zero network activity.
"""

from __future__ import annotations

import time
from typing import Protocol

import httpx
from pydantic import BaseModel, Field

MODEL_INVOCATION_COMPLETED_STATUS = "model_invocation_completed"
MODEL_INVOCATION_DEFERRED_STATUS = "model_invocation_deferred"
OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"


class ModelProviderInvocationError(RuntimeError):
    """A provider call failed; the failure is typed, never masked or retried."""

    def __init__(self, message: str, error_code: str, latency_ms: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.latency_ms = latency_ms


class ModelInvocationRuntimeRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    invocation_id: str = Field(min_length=1)
    endpoint_id: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    max_output_tokens: int | None = Field(default=None, ge=1, le=32_768)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class ModelInvocationRuntimeResult(BaseModel):
    adapter: str = Field(min_length=1)
    status: str = Field(min_length=1)
    output_text: str = Field(default="")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    provider_request_ref: str = Field(default="")
    error_code: str = Field(default="")
    error_message: str = Field(default="")
    notes: list[str] = Field(default_factory=list)


class ModelInvocationRuntime(Protocol):
    async def invoke(
        self,
        request: ModelInvocationRuntimeRequest,
    ) -> ModelInvocationRuntimeResult:
        ...

    def describe(self) -> dict[str, str]:
        ...


class DeferredModelInvocationRuntime:
    adapter_name = "axis-deferred-model-invocation-adapter"

    async def invoke(
        self,
        request: ModelInvocationRuntimeRequest,
    ) -> ModelInvocationRuntimeResult:
        return ModelInvocationRuntimeResult(
            adapter=self.adapter_name,
            status=MODEL_INVOCATION_DEFERRED_STATUS,
            provider_request_ref=(
                f"deferred-model-invocation://{request.tenant_id}/{request.invocation_id}"
            ),
            notes=[
                "Model invocation is deferred by the Axis runtime adapter.",
                "No provider call, prompt egress or token consumption was started.",
            ],
        )

    def describe(self) -> dict[str, str]:
        return {
            "adapter": self.adapter_name,
            "execution_mode": "deferred",
        }


class SelfHostedOpenAICompatibleRuntime:
    """Invoke a self-hosted OpenAI-compatible ``/v1/chat/completions`` endpoint.

    The adapter performs exactly one HTTP request per invocation with a strict
    configurable timeout and no silent retries. Failures raise
    :class:`ModelProviderInvocationError` with a stable ``error_code`` so the
    router core records a ``failed`` invocation instead of fabricating output.
    """

    adapter_name = "axis-self-hosted-openai-compatible-adapter"

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        bearer_token: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.bearer_token = bearer_token

    async def invoke(
        self,
        request: ModelInvocationRuntimeRequest,
    ) -> ModelInvocationRuntimeResult:
        url = (
            request.base_url.rstrip("/") + OPENAI_COMPATIBLE_CHAT_COMPLETIONS_PATH
        )
        payload: dict = {
            "model": request.model_id,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ModelProviderInvocationError(
                "The model provider did not respond within the configured timeout.",
                "provider_timeout",
                latency_ms=_elapsed_ms(started),
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelProviderInvocationError(
                "The model provider endpoint could not be reached.",
                "provider_unreachable",
                latency_ms=_elapsed_ms(started),
            ) from exc

        latency_ms = _elapsed_ms(started)
        if response.status_code < 200 or response.status_code >= 300:
            raise ModelProviderInvocationError(
                f"The model provider returned HTTP {response.status_code}.",
                f"provider_http_{response.status_code}",
                latency_ms=latency_ms,
            )

        return self._result_from_response(response, latency_ms=latency_ms)

    def describe(self) -> dict[str, str]:
        return {
            "adapter": self.adapter_name,
            "execution_mode": "self_hosted_openai_compatible",
            "timeout_seconds": str(self.timeout_seconds),
        }

    def _result_from_response(
        self,
        response: httpx.Response,
        *,
        latency_ms: int,
    ) -> ModelInvocationRuntimeResult:
        try:
            body = response.json()
        except ValueError as exc:
            raise ModelProviderInvocationError(
                "The model provider response was not valid JSON.",
                "provider_response_malformed",
                latency_ms=latency_ms,
            ) from exc

        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ModelProviderInvocationError(
                "The model provider response did not include any completion choices.",
                "provider_response_malformed",
                latency_ms=latency_ms,
            )
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        output_text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(output_text, str):
            raise ModelProviderInvocationError(
                "The model provider response did not include message content.",
                "provider_response_malformed",
                latency_ms=latency_ms,
            )

        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        notes = ["Model invocation executed against a self-hosted OpenAI-compatible endpoint."]
        if not usage:
            notes.append("The provider did not report token usage; token counts default to 0.")
        return ModelInvocationRuntimeResult(
            adapter=self.adapter_name,
            status=MODEL_INVOCATION_COMPLETED_STATUS,
            output_text=output_text,
            input_tokens=_usage_tokens(usage, "prompt_tokens"),
            output_tokens=_usage_tokens(usage, "completion_tokens"),
            latency_ms=latency_ms,
            provider_request_ref=str(body.get("id", "")),
            notes=notes,
        )


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _usage_tokens(usage: dict, key: str) -> int:
    value = usage.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)
