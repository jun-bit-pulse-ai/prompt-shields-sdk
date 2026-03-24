import time
from typing import Any
from openai import OpenAI
from prompt_shields.telemetry import TelemetrySender
from prompt_shields.types import PSMetadata


class ShieldsClient:
    """Drop-in wrapper around OpenAI client that sends telemetry to Prompt Shields."""

    def __init__(
        self,
        api_key: str,
        ps_api_key: str,
        ps_collector_url: str = "http://localhost:8000",
        business_unit: str | None = None,
        use_case: str | None = None,
        owner: str | None = None,
        data_classification: str | None = None,
        environment: str | None = None,
        **openai_kwargs,
    ):
        self._openai = OpenAI(api_key=api_key, **openai_kwargs)
        self._ps_api_key = ps_api_key
        self._telemetry = TelemetrySender(ps_collector_url, ps_api_key)
        self._metadata = {
            k: v for k, v in {
                "business_unit": business_unit,
                "use_case": use_case,
                "owner": owner,
                "data_classification": data_classification,
                "environment": environment,
            }.items() if v is not None
        }
        self.chat = _ChatNamespace(self)

    def _build_event(self, model: str, messages: list, response: Any,
                     latency_ms: int, ps_metadata: PSMetadata | None = None) -> dict:
        prompt_text = " ".join(m.get("content", "") for m in messages if isinstance(m, dict))
        event = {
            "vendor": "openai",
            "model": model,
            "source": "sdk",
            "tokens_in": getattr(response.usage, "prompt_tokens", None) if response.usage else None,
            "tokens_out": getattr(response.usage, "completion_tokens", None) if response.usage else None,
            "latency_ms": latency_ms,
            "prompt_text": prompt_text,
        }
        # Map SDK field names to collector field names
        field_mapping = {"use_case": "use_case_name", "owner": "owner_email"}
        for sdk_key, collector_key in field_mapping.items():
            if sdk_key in self._metadata:
                event[collector_key] = self._metadata[sdk_key]
        # Copy remaining metadata directly
        for k, v in self._metadata.items():
            if k not in field_mapping:
                event[k] = v
        return event


class _ChatNamespace:
    def __init__(self, parent: ShieldsClient):
        self._parent = parent
        self.completions = _CompletionsNamespace(parent)


class _CompletionsNamespace:
    def __init__(self, parent: ShieldsClient):
        self._parent = parent

    def create(self, *, model: str, messages: list, ps_metadata: PSMetadata | None = None, **kwargs):
        start = time.monotonic()
        response = self._parent._openai.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        event = self._parent._build_event(model, messages, response, latency_ms, ps_metadata)
        self._parent._telemetry.enqueue(event)
        self._parent._telemetry.flush_sync()

        return response
