"""Research adapters.

External research is **off by default** (``external_research_enabled: false``).
The offline provider reasons over the private corpus and the model's own
knowledge instead of reaching out to the network — which keeps a private
creative corpus private.
"""

from __future__ import annotations

from typing import Callable, TypeAlias

from creative_brain.domain.exceptions import ResearchFailure
from creative_brain.ports.outbound.knowledge import (
    KnowledgeSourcePort,
    ResearchQuery,
    ResearchResult,
    SearchProviderPort,
)
from creative_brain.ports.outbound.llm import LLMRequest, LLMResponse, ModelRole

#: The router's ``complete`` method, injected so research never picks a provider itself.
CompleteFn: TypeAlias = Callable[[LLMRequest], LLMResponse]


class OfflineResearchAdapter:
    """Researches a topic using only the LLM and the locally ingested corpus."""

    def __init__(
        self,
        complete: CompleteFn,
        *,
        corpus: KnowledgeSourcePort | None = None,
        max_context_chars: int = 2000,
    ) -> None:
        self._complete = complete
        self._corpus = corpus
        self._max_context = max_context_chars

    @property
    def provider(self) -> str:
        """Provider name."""
        return "offline"

    def investigate(self, query: ResearchQuery) -> ResearchResult:
        """Research one topic without leaving the machine."""
        context = self._local_context(query.topic)
        response = self._complete(
            LLMRequest(
                task="research.investigate",
                role=ModelRole.RESEARCH,
                agent_id="RESEARCH_AGENT",
                system=(
                    "You are a research agent for a creative engine. Investigate the topic "
                    "with precision, focusing on mechanisms, incentives and second-order "
                    "effects rather than on news. Do not invent sources."
                ),
                user=(
                    f"Topic: {query.topic}\nDepth: {query.depth}\n"
                    f"Context from the private corpus:\n{context or '(no local material)'}"
                ),
                schema=RESEARCH_SCHEMA,
                temperature=0.4,
                metadata={"topic": query.topic, "depth": str(query.depth)},
            )
        )
        data = response.data or {}
        summary = str(data.get("summary") or response.text).strip()
        if not summary:
            raise ResearchFailure(f"research on '{query.topic}' produced no summary")
        return ResearchResult(
            topic=query.topic,
            summary=summary,
            key_facts=tuple(str(f) for f in data.get("key_facts") or []),
            implications=tuple(str(i) for i in data.get("implications") or []),
            sources=(),
            confidence=float(data.get("confidence", 50.0)),
            provider="offline",
        )

    def _local_context(self, topic: str) -> str:
        if self._corpus is None:
            return ""
        chunks: list[str] = []
        for document in self._corpus.documents():
            if topic.lower() in document.content.lower():
                chunks.append(document.content[: self._max_context // 2])
            if sum(len(c) for c in chunks) >= self._max_context:
                break
        return "\n---\n".join(chunks)[: self._max_context]


class WebResearchAdapter:
    """Research backed by a search provider.

    Only used when ``external_research_enabled`` is true *and* a search
    provider is configured. Sending corpus content outward is never done here:
    only the topic string leaves the machine.
    """

    def __init__(self, search: SearchProviderPort, complete: CompleteFn) -> None:
        self._search = search
        self._complete = complete

    @property
    def provider(self) -> str:
        """Provider name."""
        return "web"

    def investigate(self, query: ResearchQuery) -> ResearchResult:
        """Search, then summarise the results into a structured finding."""
        try:
            results = self._search.search(query.topic, query.max_results)
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain failure
            raise ResearchFailure(f"search failed for '{query.topic}': {exc}") from exc
        rendered = "\n".join(
            f"- {r.get('title', '')}: {r.get('snippet', '')} ({r.get('url', '')})" for r in results
        )
        response = self._complete(
            LLMRequest(
                task="research.investigate",
                role=ModelRole.RESEARCH,
                agent_id="RESEARCH_AGENT",
                system=(
                    "Summarise search results into a structured research finding. "
                    "Only cite URLs that appear in the input."
                ),
                user=f"Topic: {query.topic}\n\nResults:\n{rendered}",
                schema=RESEARCH_SCHEMA,
                temperature=0.3,
                metadata={"topic": query.topic},
            )
        )
        data = response.data or {}
        return ResearchResult(
            topic=query.topic,
            summary=str(data.get("summary") or response.text),
            key_facts=tuple(str(f) for f in data.get("key_facts") or []),
            implications=tuple(str(i) for i in data.get("implications") or []),
            sources=tuple(str(r.get("url", "")) for r in results if r.get("url")),
            confidence=float(data.get("confidence", 50.0)),
            provider="web",
        )


class NullSearchProvider:
    """A search provider that returns nothing. The safe default."""

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Always empty: no network access is configured."""
        return []


RESEARCH_SCHEMA = {
    "type": "object",
    "required": ["summary"],
    "properties": {
        "summary": {"type": "string"},
        "key_facts": {"type": "array", "items": {"type": "string"}},
        "implications": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 100},
    },
}


__all__ = [
    "CompleteFn",
    "NullSearchProvider",
    "OfflineResearchAdapter",
    "WebResearchAdapter",
]
