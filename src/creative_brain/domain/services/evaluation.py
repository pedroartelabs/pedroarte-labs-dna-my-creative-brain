"""Pure evaluation services: novelty, creative distance, diversity, saturation.

These are the measurements the engine trusts even when every external service
is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.domain.entities.memory import Obsession
from creative_brain.domain.services.similarity import max_similarity, similarity, token_set
from creative_brain.domain.value_objects.creative_distance import CreativeDistance
from creative_brain.domain.value_objects.scores import CreativeScore


@dataclass(frozen=True, slots=True)
class NoveltyAssessment:
    """How new an idea looks against everything the engine has already thought."""

    novelty: CreativeScore
    closest_id: str
    closest_similarity: float
    is_duplicate: bool

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "novelty": self.novelty.value,
            "closest_id": self.closest_id,
            "closest_similarity": round(self.closest_similarity, 4),
            "is_duplicate": self.is_duplicate,
        }


@dataclass(frozen=True, slots=True)
class NoveltyService:
    """Compares a candidate against prior work, prior ideas and the graveyard."""

    duplicate_threshold: float = 0.62

    def assess(self, text: str, corpus: dict[str, str]) -> NoveltyAssessment:
        """Score novelty against a ``{id: text}`` corpus."""
        if not corpus:
            return NoveltyAssessment(CreativeScore(85.0), "", 0.0, False)
        best_id, best_score = max(
            ((key, similarity(text, value)) for key, value in corpus.items()),
            key=lambda kv: kv[1],
        )
        novelty = CreativeScore.clamped((1.0 - best_score) * 100.0)
        return NoveltyAssessment(
            novelty=novelty,
            closest_id=best_id,
            closest_similarity=best_score,
            is_duplicate=best_score >= self.duplicate_threshold,
        )

    def duplicate_rate(self, texts: list[str]) -> float:
        """Share of a batch that duplicates another member of the same batch, 0..1."""
        if len(texts) < 2:
            return 0.0
        duplicates = 0
        for index, text in enumerate(texts):
            others = texts[:index] + texts[index + 1 :]
            if max_similarity(text, others) >= self.duplicate_threshold:
                duplicates += 1
        return round(duplicates / len(texts), 4)


@dataclass(frozen=True, slots=True)
class CreativeDistanceService:
    """Measures how far an idea sits from the established DNA.

    Familiarity is measured two ways, because either one alone is misleading:

    * **coverage** — how much of the idea's vocabulary the DNA already owns.
      This is the discriminating signal. An idea built from *cartório* and
      *herança* is recognisably this author; one about electric fish is not.
    * **closeness** — similarity to any single DNA statement, which catches an
      idea that restates one principle almost verbatim.

    Comparing a whole concept only against individual short DNA phrases would
    saturate: every idea would score near-zero overlap and land in the
    UNKNOWN_ZONE, making the zone allocation meaningless.
    """

    def measure(self, text: str, dna_vocabulary: tuple[str, ...]) -> CreativeDistance:
        """Distance of ``text`` from the DNA corpus, 0..100."""
        if not dna_vocabulary:
            return CreativeDistance(50.0)
        familiarity = max(
            self._coverage(text, dna_vocabulary),
            max_similarity(text, list(dna_vocabulary)),
        )
        return CreativeDistance.clamped((1.0 - familiarity) * 100.0)

    def measure_against_canon(
        self, text: str, dna_vocabulary: tuple[str, ...], canon: dict[str, str]
    ) -> CreativeDistance:
        """Distance from DNA *and* from finished work — the stricter of the two wins."""
        dna_distance = self.measure(text, dna_vocabulary).value
        if not canon:
            return CreativeDistance.clamped(dna_distance)
        canon_overlap = max_similarity(text, list(canon.values()))
        return CreativeDistance.clamped(min(dna_distance, (1.0 - canon_overlap) * 100.0))

    @staticmethod
    def _coverage(text: str, vocabulary: tuple[str, ...]) -> float:
        """Share of the idea's content words the DNA already contains, 0..1."""
        idea = token_set(text)
        if not idea:
            return 0.0
        known: set[str] = set()
        for entry in vocabulary:
            known |= token_set(entry)
        return len(idea & known) / len(idea)


@dataclass(frozen=True, slots=True)
class DiversityService:
    """Guards against 'a hundred nearly identical ideas'."""

    def score(self, texts: list[str]) -> float:
        """Average pairwise distinctness of a batch, 0..100."""
        if len(texts) < 2:
            return 100.0
        pairs = [
            similarity(texts[i], texts[j])
            for i in range(len(texts))
            for j in range(i + 1, len(texts))
        ]
        mean_similarity = sum(pairs) / len(pairs)
        return round(max(0.0, min(100.0, (1.0 - mean_similarity) * 100.0)), 2)

    def most_redundant(self, texts: dict[str, str]) -> tuple[str, float]:
        """The entry closest to everything else — the first one worth cutting."""
        if len(texts) < 2:
            return "", 0.0
        scores = {
            key: max_similarity(value, [v for k, v in texts.items() if k != key])
            for key, value in texts.items()
        }
        worst = max(scores.items(), key=lambda kv: kv[1])
        return worst[0], round(worst[1], 4)


@dataclass(frozen=True, slots=True)
class SaturationService:
    """Tells a real obsession apart from disguised repetition."""

    saturation_threshold: float = 60.0

    def build(self, theme_angles: dict[str, list[str]], *, at: str) -> list[Obsession]:
        """Turn ``{theme: [angles]}`` history into obsession records."""
        obsessions: list[Obsession] = []
        for theme, angles in theme_angles.items():
            obsession = Obsession(theme=theme)
            for angle in angles:
                obsession.observe(angle, at)
            obsessions.append(obsession)
        return sorted(obsessions, key=lambda o: o.saturation, reverse=True)

    def saturated_themes(self, obsessions: list[Obsession]) -> tuple[str, ...]:
        """Themes the engine should stop mining until it finds a new angle."""
        return tuple(o.theme for o in obsessions if o.saturation >= self.saturation_threshold)

    def is_new_angle(self, theme_history: list[str], candidate: str) -> bool:
        """Whether a candidate explores a genuinely different dimension of a theme."""
        if not theme_history:
            return True
        return max_similarity(candidate, theme_history) < 0.5

    def unexplored_terms(self, corpus: list[str], vocabulary: list[str]) -> tuple[str, ...]:
        """Vocabulary the engine owns but has never actually used."""
        used = set().union(*(token_set(text) for text in corpus)) if corpus else set()
        return tuple(term for term in vocabulary if not token_set(term) & used)
