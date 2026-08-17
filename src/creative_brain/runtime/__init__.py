"""The autonomous runtime: the loop that keeps the mind alive.

The loop is deliberately small. It asks the clock what to do, executes it,
publishes what happened, checkpoints, and checks its own health. Everything
interesting happens inside the phases, not inside the loop.
"""

from __future__ import annotations

import signal
from dataclasses import dataclass, field
from typing import Any

from creative_brain.application.context import BrainContext
from creative_brain.application.orchestration.orchestrator import CreativeOrchestrator, CycleOutcome
from creative_brain.biological_clock import BiologicalClockAgent
from creative_brain.domain.entities.circadian import BiologicalPhase, CircadianState
from creative_brain.domain.exceptions import BudgetExceeded, CreativeBrainError
from creative_brain.domain.value_objects.identifiers import CycleId, SessionId
from creative_brain.ports.inbound import RuntimeStatus
from creative_brain.ports.outbound.llm import BudgetPort

#: Hard stop so a mis-configured policy can never spin forever inside one cycle.
MAX_PHASES_PER_CYCLE = 40


@dataclass
class RuntimeHealth:
    """What ``evaluate_health`` reports back to the loop."""

    healthy: bool = True
    unhealthy_agents: list[str] = field(default_factory=list)
    dead_letters: int = 0
    failure_rate: float = 0.0
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Serialisation-friendly view."""
        return {
            "healthy": self.healthy,
            "unhealthy_agents": list(self.unhealthy_agents),
            "dead_letters": self.dead_letters,
            "failure_rate": self.failure_rate,
            "notes": self.notes,
        }


@dataclass
class AutonomousCreativeRuntime:
    """Runs the creative mind unattended.

    Autonomy here means creative autonomy: the loop never asks a human whether
    an idea is good. It also never touches credentials, publishes anything or
    spends outside the configured budget — those live outside the envelope.
    """

    context: BrainContext
    orchestrator: CreativeOrchestrator
    clock_agent: BiologicalClockAgent
    #: The router's accounting, so the clock can see spend without knowing the router.
    budget: BudgetPort | None = None
    session_id: str = ""
    state: CircadianState = field(default_factory=CircadianState)
    running: bool = False
    stop_requested: bool = False
    cycles_completed: int = 0
    last_outcome: CycleOutcome | None = None

    # ------------------------------------------------------------- lifecycle

    def bootstrap(self) -> None:
        """Validate configuration, restore state, ingest the corpus, index memory."""
        ctx = self.context
        self.session_id = self.session_id or str(ctx.new_id(SessionId))
        ctx.logger.info("runtime.bootstrap", session_id=self.session_id, seed=ctx.random.seed())

        # 1-2. configuration and persistence are already wired by composition.
        # 3-4. corpus ingestion and indexing.
        documents = ctx.corpus.ingest()
        for document in documents:
            for index, chunk in enumerate(ctx.corpus.chunk(document)):
                ctx.vectors.index(
                    f"{document.doc_id}#{index}",
                    chunk,
                    {"kind": "corpus", "source": document.source},
                )
        # 5-6. DNA and clock.
        ctx.repositories.dna.load_core()
        restored = ctx.repositories.circadian.load()
        if restored is not None:
            self.state = restored
            ctx.logger.info(
                "runtime.resumed",
                cycle_number=self.state.cycle_number,
                phase=str(self.state.phase),
            )
        # 7-8. agents are built by composition; pending state is the checkpoint.
        checkpoint = ctx.repositories.checkpoints.load()
        if checkpoint:
            self.cycles_completed = int(checkpoint.get("cycles_completed", 0) or 0)
        ctx.logger.info(
            "runtime.ready",
            documents_ingested=len(documents),
            indexed=ctx.vectors.size(),
            agents=len(ctx.society.agents),
        )

    def install_signal_handlers(self) -> None:
        """Ask for a graceful shutdown on Ctrl-C instead of dying mid-cycle."""
        def handler(_signum: int, _frame: Any) -> None:
            self.context.logger.warning("runtime.stop_requested")
            self.stop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):  # pragma: no cover - not available off the main thread
                continue

    def start(self, *, cycles: int | None = None) -> None:
        """Run the autonomous loop, optionally bounded to a number of cycles."""
        self.bootstrap()
        self.running = True
        try:
            while self.is_running():
                if cycles is not None and self.cycles_completed >= cycles:
                    break
                self.run_cycle()
        finally:
            self.shutdown()

    def is_running(self) -> bool:
        """Whether the loop should keep going."""
        return self.running and not self.stop_requested

    def stop(self) -> None:
        """Request a graceful shutdown after the current atomic operation."""
        self.stop_requested = True

    def shutdown(self) -> None:
        """Finish cleanly: persist state, flush events, save the checkpoint."""
        ctx = self.context
        self.running = False
        ctx.repositories.circadian.save(self.state)
        ctx.repositories.checkpoints.save(self.checkpoint())
        ctx.logger.info(
            "runtime.shutdown",
            cycles_completed=self.cycles_completed,
            session_id=self.session_id,
        )

    # ----------------------------------------------------------------- loop

    def run_cycle(self) -> CycleOutcome:
        """Execute exactly one full circadian cycle, from AWAKENING to DEEP_SLEEP."""
        ctx = self.context
        cycle_id = str(ctx.new_id(CycleId))
        self.orchestrator.begin_cycle(self.state, cycle_id)

        for _ in range(MAX_PHASES_PER_CYCLE):
            decision = self.clock_agent.decide(self.state)
            self.state.enter(decision)
            ctx.publish(self.state)

            try:
                self.orchestrator.execute_phase(decision.phase, self.state)
            except BudgetExceeded as exc:
                ctx.logger.warning("cycle.budget_exceeded", error=str(exc), cycle_id=cycle_id)
                self._force_sleep(cycle_id)
                break
            except CreativeBrainError as exc:
                # A failed phase must not kill the mind: record it and move on.
                ctx.logger.error(
                    "phase.failed",
                    phase=str(decision.phase),
                    error=str(exc),
                    cycle_id=cycle_id,
                )
                ctx.metrics.increment("phase_failures", phase=str(decision.phase))

            self._sync_budget()
            self.checkpoint_now()

            duration = self.clock_agent.phase_duration(decision.phase)
            if duration > 0:
                ctx.clock.sleep(duration)

            if decision.ends_cycle:
                break

        self.state.end_cycle(at=ctx.now())
        ctx.publish(self.state)
        self.cycles_completed += 1
        self.last_outcome = self.orchestrator.outcome
        self.checkpoint_now()

        health = self.evaluate_health()
        if not health.healthy:
            ctx.logger.warning("runtime.unhealthy", **health.as_dict())
        return self.last_outcome

    def run_single_cycle(self) -> dict[str, Any]:
        """Bootstrap, run exactly one cycle, shut down. Used by ``--single-cycle``."""
        self.bootstrap()
        self.running = True
        try:
            outcome = self.run_cycle()
        finally:
            self.shutdown()
        return outcome.as_dict()

    # ---------------------------------------------------------- persistence

    def checkpoint(self) -> dict[str, Any]:
        """The resume payload."""
        return {
            "session_id": self.session_id,
            "cycles_completed": self.cycles_completed,
            "current_phase": str(self.state.phase),
            "circadian_state": self.state.as_dict(),
            "random_seed": self.context.random.seed(),
            "last_outcome": self.last_outcome.as_dict() if self.last_outcome else None,
            "pending_events": len(self.context.bus.history()),
            "saved_at": self.context.now(),
        }

    def checkpoint_now(self) -> None:
        """Persist both the clock and the whole-runtime checkpoint."""
        self.context.repositories.circadian.save(self.state)
        self.context.repositories.checkpoints.save(self.checkpoint())

    # --------------------------------------------------------------- health

    def evaluate_health(self) -> RuntimeHealth:
        """Detect broken agents, dead letters and elevated failure rates."""
        ctx = self.context
        unhealthy = ctx.society.unhealthy()
        dead_letters = len(ctx.bus.dead_letters())
        health = RuntimeHealth(
            healthy=not unhealthy and dead_letters == 0 and self.state.failure_rate < 0.3,
            unhealthy_agents=unhealthy,
            dead_letters=dead_letters,
            failure_rate=self.state.failure_rate,
        )
        if unhealthy:
            health.notes = f"agents failing repeatedly: {', '.join(unhealthy)}"
        elif dead_letters:
            health.notes = f"{dead_letters} events could not be handled"
        return health

    def status(self) -> RuntimeStatus:
        """What ``creative-brain status`` renders."""
        ctx = self.context
        counts = self.last_outcome.counts if self.last_outcome else {}
        return RuntimeStatus(
            running=self.running,
            phase=str(self.state.phase),
            cycle_number=self.state.cycle_number,
            cycle_id=self.state.cycle_id,
            energy=self.state.energy.as_dict(),
            counts=counts,
            current_focus=self.orchestrator.outcome.focus,
            next_decision="dynamic",
            dream_mode=(
                "scheduled dynamically" if ctx.flags.dream_mode_enabled else "disabled"
            ),
            last_winner=self.last_outcome.winner_title if self.last_outcome else "",
            llm_calls=self.state.llm_calls_this_cycle,
            estimated_cost_usd=self.state.estimated_cost_usd,
        )

    # -------------------------------------------------------------- helpers

    def _force_sleep(self, cycle_id: str) -> None:
        """Skip straight to DEEP_SLEEP when the budget is gone."""
        from creative_brain.domain.entities.circadian import CircadianDecision

        decision = CircadianDecision(
            phase=BiologicalPhase.DEEP_SLEEP,
            reason="budget exhausted mid-cycle",
            decided_at=self.context.now(),
            ends_cycle=True,
        )
        self.state.enter(decision)
        self.orchestrator.execute_phase(BiologicalPhase.DEEP_SLEEP, self.state)
        self.context.publish(self.state)

    def _sync_budget(self) -> None:
        """Copy the router's accounting into the clock's view of the world."""
        if self.budget is not None:
            self.state.llm_calls_this_cycle = int(self.budget.calls)
            self.state.estimated_cost_usd = float(self.budget.cost_usd)


__all__ = ["MAX_PHASES_PER_CYCLE", "AutonomousCreativeRuntime", "RuntimeHealth"]
