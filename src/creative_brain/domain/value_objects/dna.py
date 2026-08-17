"""Creative DNA: the two-tier memory of *how* this author creates.

``CoreDna`` is protected. The engine may read it, cite it, measure against it —
never rewrite it. ``EvolvingDna`` is the part the engine is allowed to grow on
its own, and it is versioned so every change is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from creative_brain.domain.exceptions import ImmutableCoreDnaViolation


class DnaLayer(StrEnum):
    """Which tier a DNA fragment belongs to."""

    CORE = "CORE_DNA"
    EVOLVING = "EVOLVING_DNA"


@dataclass(frozen=True, slots=True)
class DnaPrinciple:
    """One named creative principle with the weight it carries in judgement."""

    key: str
    statement: str
    category: str = "general"
    weight: float = 1.0

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "key": self.key,
            "statement": self.statement,
            "category": self.category,
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class InstitutionalPillar:
    """One pillar from an institutional lens that colours creative judgement."""

    key: str
    statement: str
    creative_application: str = ""

    def as_dict(self) -> dict[str, object]:
        return {"key": self.key, "statement": self.statement, "creative_application": self.creative_application}


@dataclass(frozen=True, slots=True)
class InstitutionalLens:
    """An external culture whose values refine how the engine thinks."""

    label: str
    purpose: str
    pillars: tuple[InstitutionalPillar, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {"label": self.label, "purpose": self.purpose, "pillars": [p.as_dict() for p in self.pillars]}

    def summary_for_prompt(self) -> str:
        """A compact block agents can receive as context."""
        lines = [f"## {self.label}", "", self.purpose, ""]
        for pillar in self.pillars:
            lines.append(f"- **{pillar.statement}**")
            if pillar.creative_application:
                lines.append(f"  → {pillar.creative_application}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class CoreDna:
    """The protected identity of the creative mind. Never auto-modified."""

    identity: str
    philosophy: tuple[str, ...] = ()
    principles: tuple[DnaPrinciple, ...] = ()
    narrative_patterns: tuple[str, ...] = ()
    aesthetics: tuple[str, ...] = ()
    signature_mechanisms: tuple[str, ...] = ()
    forbidden_moves: tuple[str, ...] = ()
    institutional_lenses: dict[str, InstitutionalLens] = field(default_factory=dict)

    def principle(self, key: str) -> DnaPrinciple | None:
        """Look up a principle by key."""
        return next((p for p in self.principles if p.key == key), None)

    def mutate(self, **_: object) -> CoreDna:
        """Always raises: CORE_DNA is outside the engine's autonomy envelope."""
        raise ImmutableCoreDnaViolation(
            "CORE_DNA is protected; only a human author may change it. "
            "Autonomous learning must target EVOLVING_DNA."
        )

    def vocabulary(self) -> tuple[str, ...]:
        """Every phrase that defines this author, used to measure creative distance."""
        return (
            *self.philosophy,
            *(p.statement for p in self.principles),
            *self.narrative_patterns,
            *self.aesthetics,
            *self.signature_mechanisms,
        )

    def lens_context(self) -> str:
        """Concatenated institutional lens summaries for agent prompts."""
        return "\n\n".join(lens.summary_for_prompt() for lens in self.institutional_lenses.values())

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "identity": self.identity,
            "philosophy": list(self.philosophy),
            "principles": [p.as_dict() for p in self.principles],
            "narrative_patterns": list(self.narrative_patterns),
            "aesthetics": list(self.aesthetics),
            "signature_mechanisms": list(self.signature_mechanisms),
            "forbidden_moves": list(self.forbidden_moves),
            "institutional_lenses": {k: v.as_dict() for k, v in self.institutional_lenses.items()},
        }


@dataclass(frozen=True, slots=True)
class EvolvingDna:
    """What the engine has learned about itself. Autonomously updatable."""

    version: int = 0
    discoveries: tuple[str, ...] = ()
    emergent_patterns: tuple[str, ...] = ()
    promising_territories: tuple[str, ...] = ()
    saturated_themes: tuple[str, ...] = ()
    successful_combinations: tuple[str, ...] = ()
    techniques: tuple[str, ...] = ()
    updated_at: str = ""
    change_log: tuple[str, ...] = field(default=())

    MAX_ENTRIES_PER_BUCKET = 64

    def learn(
        self,
        *,
        discoveries: tuple[str, ...] = (),
        emergent_patterns: tuple[str, ...] = (),
        promising_territories: tuple[str, ...] = (),
        saturated_themes: tuple[str, ...] = (),
        successful_combinations: tuple[str, ...] = (),
        techniques: tuple[str, ...] = (),
        reason: str = "",
        at: str = "",
    ) -> EvolvingDna:
        """Fold new learning in, de-duplicating and capping each bucket."""
        return replace(
            self,
            version=self.version + 1,
            discoveries=_extend(self.discoveries, discoveries, self.MAX_ENTRIES_PER_BUCKET),
            emergent_patterns=_extend(
                self.emergent_patterns, emergent_patterns, self.MAX_ENTRIES_PER_BUCKET
            ),
            promising_territories=_extend(
                self.promising_territories, promising_territories, self.MAX_ENTRIES_PER_BUCKET
            ),
            saturated_themes=_extend(
                self.saturated_themes, saturated_themes, self.MAX_ENTRIES_PER_BUCKET
            ),
            successful_combinations=_extend(
                self.successful_combinations, successful_combinations, self.MAX_ENTRIES_PER_BUCKET
            ),
            techniques=_extend(self.techniques, techniques, self.MAX_ENTRIES_PER_BUCKET),
            updated_at=at or self.updated_at,
            change_log=_extend(
                self.change_log, (f"v{self.version + 1}: {reason}",) if reason else (), 200
            ),
        )

    def is_saturated(self, theme: str) -> bool:
        """Whether a theme has been flagged as over-explored."""
        return theme.strip().lower() in {t.strip().lower() for t in self.saturated_themes}

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "version": self.version,
            "discoveries": list(self.discoveries),
            "emergent_patterns": list(self.emergent_patterns),
            "promising_territories": list(self.promising_territories),
            "saturated_themes": list(self.saturated_themes),
            "successful_combinations": list(self.successful_combinations),
            "techniques": list(self.techniques),
            "updated_at": self.updated_at,
            "change_log": list(self.change_log),
        }


@dataclass(frozen=True, slots=True)
class CreativeDna:
    """Both tiers together — what agents actually receive as context."""

    core: CoreDna
    evolving: EvolvingDna

    def vocabulary(self) -> tuple[str, ...]:
        """Union of core vocabulary and learned patterns, for distance measurement."""
        return (*self.core.vocabulary(), *self.evolving.emergent_patterns)


def _extend(current: tuple[str, ...], new: tuple[str, ...], cap: int) -> tuple[str, ...]:
    """Append unseen entries (case-insensitive) and keep only the newest ``cap``."""
    seen = {item.strip().lower() for item in current}
    merged = list(current)
    for item in new:
        normalised = item.strip()
        if normalised and normalised.lower() not in seen:
            merged.append(normalised)
            seen.add(normalised.lower())
    return tuple(merged[-cap:])
