"""The creative tournament: a configurable elimination funnel.

The engine deliberately over-produces and then kills most of what it made.
Selection pressure — not prompt quality — is what makes the output good.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from creative_brain.domain.events import DomainEvent, EventEmitter, EventName
from creative_brain.domain.exceptions import EmptyTournamentError, TournamentFailure
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.domain.value_objects.identifiers import TournamentId


@dataclass(frozen=True, slots=True)
class FunnelStep:
    """One elimination round: keep ``survivors`` artifacts at ``stage``."""

    stage: CreativeStage
    survivors: int

    def __post_init__(self) -> None:
        if self.survivors < 1:
            raise TournamentFailure(f"funnel step {self.stage} must keep at least 1 artifact")


@dataclass(frozen=True, slots=True)
class TournamentFunnel:
    """The whole ladder, e.g. 100 seeds -> 30 -> 10 -> 5 -> 3 -> 1."""

    steps: tuple[FunnelStep, ...]

    def __post_init__(self) -> None:
        if not self.steps:
            raise TournamentFailure("a tournament funnel needs at least one step")
        widths = [s.survivors for s in self.steps]
        if any(b > a for a, b in zip(widths, widths[1:], strict=False)):
            raise TournamentFailure(f"funnel must narrow monotonically, got {widths}")

    @classmethod
    def from_pairs(cls, pairs: list[tuple[str, int]]) -> TournamentFunnel:
        """Build from configuration, e.g. ``[("CONCEPT", 30), ("PREMISE", 10)]``."""
        return cls(tuple(FunnelStep(CreativeStage(name), int(n)) for name, n in pairs))

    @property
    def winners(self) -> int:
        """How many artifacts survive the final round."""
        return self.steps[-1].survivors


@dataclass(slots=True)
class TournamentRound:
    """The outcome of one elimination round."""

    stage: CreativeStage
    entrants: tuple[str, ...]
    survivors: tuple[str, ...]
    eliminated: tuple[str, ...]
    finished_at: str

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "stage": str(self.stage),
            "entrants": list(self.entrants),
            "survivors": list(self.survivors),
            "eliminated": list(self.eliminated),
            "finished_at": self.finished_at,
        }


@dataclass(slots=True)
class CreativeTournament(EventEmitter):
    """One full run of the funnel, from the seed pool to a single winner."""

    id: TournamentId
    cycle_id: str
    funnel: TournamentFunnel
    started_at: str
    entrants: tuple[str, ...] = ()
    rounds: list[TournamentRound] = field(default_factory=list)
    winner_id: str = ""
    finished_at: str = ""
    diversity_score: float = 0.0
    _pending: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def start(
        cls,
        *,
        tournament_id: TournamentId,
        cycle_id: str,
        funnel: TournamentFunnel,
        entrants: tuple[str, ...],
        at: str,
    ) -> CreativeTournament:
        """Open a tournament with the given competitor ids."""
        if not entrants:
            raise EmptyTournamentError("cannot run a tournament without entrants")
        tournament = cls(
            id=tournament_id,
            cycle_id=cycle_id,
            funnel=funnel,
            started_at=at,
            entrants=entrants,
        )
        tournament.record_event(
            DomainEvent(
                name=EventName.TOURNAMENT_STARTED,
                occurred_at=at,
                cycle_id=cycle_id,
                subject_id=str(tournament_id),
                payload={"entrants": len(entrants), "steps": len(funnel.steps)},
            )
        )
        return tournament

    def record_round(
        self,
        *,
        stage: CreativeStage,
        entrants: tuple[str, ...],
        survivors: tuple[str, ...],
        at: str,
    ) -> TournamentRound:
        """Store the outcome of one round and emit the corresponding event."""
        eliminated = tuple(e for e in entrants if e not in set(survivors))
        round_ = TournamentRound(stage, entrants, survivors, eliminated, at)
        self.rounds.append(round_)
        self.record_event(
            DomainEvent(
                name=EventName.TOURNAMENT_ROUND_FINISHED,
                occurred_at=at,
                cycle_id=self.cycle_id,
                subject_id=str(self.id),
                payload={
                    "stage": str(stage),
                    "entrants": len(entrants),
                    "survivors": len(survivors),
                    "eliminated": len(eliminated),
                },
            )
        )
        return round_

    def finish(self, *, winner_id: str, at: str, diversity: float = 0.0) -> None:
        """Close the tournament. Idempotent: re-finishing with the same winner is a no-op."""
        if self.finished_at:
            if self.winner_id != winner_id:
                raise TournamentFailure(
                    f"tournament {self.id} already finished with winner {self.winner_id}"
                )
            return
        self.winner_id = winner_id
        self.finished_at = at
        self.diversity_score = diversity
        self.record_event(
            DomainEvent(
                name=EventName.TOURNAMENT_FINISHED,
                occurred_at=at,
                cycle_id=self.cycle_id,
                subject_id=str(self.id),
                payload={
                    "winner_id": winner_id,
                    "rounds": len(self.rounds),
                    "diversity": diversity,
                },
            )
        )

    @property
    def is_finished(self) -> bool:
        """Whether a winner has been declared."""
        return bool(self.finished_at)

    @property
    def eliminated_ids(self) -> tuple[str, ...]:
        """Everyone who fell along the way, in elimination order."""
        return tuple(cid for round_ in self.rounds for cid in round_.eliminated)

    def as_dict(self) -> dict[str, object]:
        """Serialisation-friendly view."""
        return {
            "id": str(self.id),
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "winner_id": self.winner_id,
            "diversity_score": self.diversity_score,
            "entrants": list(self.entrants),
            "funnel": [
                {"stage": str(s.stage), "survivors": s.survivors} for s in self.funnel.steps
            ],
            "rounds": [r.as_dict() for r in self.rounds],
        }
