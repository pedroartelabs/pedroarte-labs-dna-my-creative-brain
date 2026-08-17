"""Anthropic provider.

Imported lazily: the engine runs fully without the ``anthropic`` package
installed. Install with ``pip install -e ".[anthropic]"`` and set
``CREATIVE_BRAIN_LLM_PROVIDER=anthropic``.
"""

from __future__ import annotations

import json
from typing import Any

from creative_brain.domain.exceptions import ConfigurationError, ExecutionFailure
from creative_brain.ports.outbound.llm import LLMRequest, LLMResponse

#: USD per 1M tokens. Kept here (not in the domain) because it is vendor pricing.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-5": (5.00, 25.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
DEFAULT_PRICING = (3.00, 15.00)


class AnthropicAdapter:
    """Talks to the Anthropic Messages API and returns structured JSON."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        base_url: str | None = None,
        timeout_seconds: float = 90.0,
    ) -> None:
        if not api_key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is empty. Set it in .env or switch "
                "CREATIVE_BRAIN_LLM_PROVIDER back to 'mock'."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ConfigurationError(
                "the 'anthropic' package is not installed; run: pip install -e \".[anthropic]\""
            ) from exc
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout_seconds}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**kwargs)
        self._model = model

    @property
    def provider(self) -> str:
        """Provider name."""
        return "anthropic"

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Run one completion, asking for JSON when the agent declared a schema."""
        system = request.system
        if request.schema is not None:
            system = (
                f"{system}\n\nAnswer with a single JSON object and nothing else. "
                f"It must satisfy this JSON schema:\n{json.dumps(request.schema, ensure_ascii=False)}"
            )
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=system,
                messages=[{"role": "user", "content": request.user}],
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain-level failure
            raise ExecutionFailure(f"anthropic call failed for '{request.task}': {exc}") from exc

        text = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        )
        usage = getattr(message, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return LLMResponse(
            text=text,
            model=self._model,
            data=parse_json_object(text) if request.schema is not None else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimate_cost(self._model, input_tokens, output_tokens),
            provider="anthropic",
        )


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Approximate USD cost of one call."""
    in_price, out_price = PRICING.get(model, DEFAULT_PRICING)
    return round((input_tokens * in_price + output_tokens * out_price) / 1_000_000, 8)


def parse_json_object(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from a model answer, tolerating code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
        cleaned = cleaned.removeprefix("json").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


__all__ = ["AnthropicAdapter", "estimate_cost", "parse_json_object"]
