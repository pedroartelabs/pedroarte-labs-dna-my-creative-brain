"""OpenAI provider.

Exists to prove the abstraction: the engine must never be tied to a single
vendor (see ADR-003). Install with ``pip install -e ".[openai]"``.
"""

from __future__ import annotations

import json
from typing import Any

from creative_brain.adapters.llm.anthropic_adapter import parse_json_object
from creative_brain.domain.exceptions import ConfigurationError, ExecutionFailure
from creative_brain.ports.outbound.llm import LLMRequest, LLMResponse

#: USD per 1M tokens.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
}
DEFAULT_PRICING = (2.00, 8.00)


class OpenAIAdapter:
    """Talks to the OpenAI Chat Completions API and returns structured JSON."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4.1",
        base_url: str | None = None,
        timeout_seconds: float = 90.0,
    ) -> None:
        if not api_key:
            raise ConfigurationError("OPENAI_API_KEY is empty")
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ConfigurationError(
                "the 'openai' package is not installed; run: pip install -e \".[openai]\""
            ) from exc
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout_seconds}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = openai.OpenAI(**kwargs)
        self._model = model

    @property
    def provider(self) -> str:
        """Provider name."""
        return "openai"

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one completion, requesting a JSON object when a schema was declared."""
        system = request.system
        payload: dict[str, Any] = {
            "model": self._model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.schema is not None:
            system = (
                f"{system}\n\nAnswer with a single JSON object satisfying this schema:\n"
                f"{json.dumps(request.schema, ensure_ascii=False)}"
            )
            payload["response_format"] = {"type": "json_object"}
        try:
            completion = self._client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": request.user},
                ],
                **payload,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain-level failure
            raise ExecutionFailure(f"openai call failed for '{request.task}': {exc}") from exc

        text = completion.choices[0].message.content or ""
        usage = getattr(completion, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        in_price, out_price = PRICING.get(self._model, DEFAULT_PRICING)
        return LLMResponse(
            text=text,
            model=self._model,
            data=parse_json_object(text) if request.schema is not None else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(
                (input_tokens * in_price + output_tokens * out_price) / 1_000_000, 8
            ),
            provider="openai",
        )


__all__ = ["OpenAIAdapter"]
