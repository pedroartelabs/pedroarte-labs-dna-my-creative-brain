"""The composition root.

This is the **only** module allowed to know both the ports and the adapters.
Everything above it — domain, application, agents, runtime — sees contracts
only. If you want to swap storage, provider or clock, this is the single file
you touch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from creative_brain.adapters.clock import FakeClock, SystemClock
from creative_brain.adapters.events import InMemoryEventBus
from creative_brain.adapters.filesystem import FileCorpusIngestor, FileOutputWriter
from creative_brain.adapters.llm.mock_adapter import MockLLMAdapter
from creative_brain.adapters.llm.router import CallBudget, ModelRouter
from creative_brain.adapters.observability import InMemoryMetrics, NullLogger, StructuredLogger
from creative_brain.adapters.persistence import (
    FileAgentDecisionRepository,
    FileCheckpointRepository,
    FileCircadianStateRepository,
    FileConceptRepository,
    FileDnaRepository,
    FileDreamRepository,
    FileMemoryRepository,
    FileObservationRepository,
    FileProjectRepository,
    FileQuestionRepository,
    FileResearchRepository,
    FileSeedRepository,
    FileTournamentRepository,
    InMemoryKnowledgeGraph,
    LexicalVectorMemory,
)
from creative_brain.adapters.production import FilesystemProductionAdapter
from creative_brain.adapters.prompts import FilePromptLibrary
from creative_brain.adapters.randomness import SeededRandom
from creative_brain.adapters.research import (
    NullSearchProvider,
    OfflineResearchAdapter,
    WebResearchAdapter,
)
from creative_brain.adapters.resilience import CircuitBreaker, RateLimiter, RetryPolicy
from creative_brain.agents.base import AgentContext
from creative_brain.agents.society import AgentSociety
from creative_brain.application.context import (
    BrainContext,
    Policies,
    Repositories,
    Services,
)
from creative_brain.application.orchestration.orchestrator import CreativeOrchestrator
from creative_brain.biological_clock import BiologicalClockAgent
from creative_brain.composition.config import BrainConfig
from creative_brain.domain.entities.project import KNOWN_ENGINES
from creative_brain.domain.exceptions import ConfigurationError
from creative_brain.domain.services.evaluation import (
    CreativeDistanceService,
    DiversityService,
    NoveltyService,
    SaturationService,
)
from creative_brain.domain.services.tournament_service import TournamentService
from creative_brain.ports.outbound.llm import LLMPort, ModelRole
from creative_brain.runtime import AutonomousCreativeRuntime


@dataclass
class Brain:
    """A fully wired creative mind, ready to run."""

    config: BrainConfig
    context: BrainContext
    runtime: AutonomousCreativeRuntime
    orchestrator: CreativeOrchestrator
    clock_agent: BiologicalClockAgent
    budget: CallBudget
    bus: InMemoryEventBus
    metrics: InMemoryMetrics


def build_brain(
    root: Path,
    *,
    mock: bool = True,
    quiet: bool = False,
    fake_clock: bool = False,
    seed: int | None = None,
    log_format: str | None = None,
) -> Brain:
    """Wire every adapter behind every port and return a runnable brain."""
    config = BrainConfig.load(root)
    flags = config.feature_flags()
    state_dir = root / "memory" / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # --- infrastructure ----------------------------------------------------
    clock = FakeClock() if fake_clock else SystemClock()
    random_source = SeededRandom(seed if seed is not None else config.random_seed())
    metrics = InMemoryMetrics()
    logger = (
        NullLogger()
        if quiet
        else StructuredLogger(
            level=os.environ.get("CREATIVE_BRAIN_LOG_LEVEL", "INFO"),
            fmt=log_format or os.environ.get("CREATIVE_BRAIN_LOG_FORMAT", "json"),
            file_path=root / "logs" / "creative_brain.log",
        )
    )
    bus = InMemoryEventBus(dead_letter_dir=root / "memory" / "dead_letter")

    # --- persistence -------------------------------------------------------
    memory_root = root / "memory"
    repositories = Repositories(
        observations=FileObservationRepository(memory_root / "episodic" / "observations"),
        research=FileResearchRepository(memory_root / "episodic" / "research"),
        questions=FileQuestionRepository(memory_root / "creative" / "questions"),
        seeds=FileSeedRepository(memory_root / "creative" / "seeds"),
        concepts=FileConceptRepository(
            memory_root / "creative" / "concepts", memory_root / "graveyard"
        ),
        tournaments=FileTournamentRepository(memory_root / "experiments" / "tournaments"),
        projects=FileProjectRepository(memory_root / "canon" / "projects"),
        memory=FileMemoryRepository(memory_root),
        dreams=FileDreamRepository(memory_root / "experiments" / "dreams"),
        dna=FileDnaRepository(memory_root / "core_dna", memory_root / "evolving_dna"),
        circadian=FileCircadianStateRepository(state_dir),
        checkpoints=FileCheckpointRepository(state_dir),
        decisions=FileAgentDecisionRepository(memory_root / "episodic" / "decisions"),
    )

    vectors = LexicalVectorMemory(state_dir / "vector_index.json")
    graph = InMemoryKnowledgeGraph(state_dir / "creative_graph.json")
    corpus = FileCorpusIngestor(root / "input", state_dir, clock_iso=clock.iso_now())
    output = FileOutputWriter(root / "outputs", date_folder=clock.now().date().isoformat())

    # --- LLM routing -------------------------------------------------------
    limits = config.model_limits()
    budget = CallBudget(
        max_calls_per_cycle=config.circadian_policy().max_llm_calls_per_cycle,
        max_cost_usd_per_cycle=config.circadian_policy().max_cost_usd_per_cycle,
    )
    providers, model_names = _build_providers(config, random_source, mock=mock)
    rate = limits.get("rate_limit") or {}
    retry_cfg = limits.get("retry") or {}
    breaker_cfg = limits.get("circuit_breaker") or {}
    router = ModelRouter(
        providers=providers,
        default=providers.get(ModelRole.CREATIVE, MockLLMAdapter(random_source)),
        clock=clock,
        metrics=metrics,
        logger=logger,
        budget=budget,
        retry=RetryPolicy(
            max_attempts=int(retry_cfg.get("max_attempts", 3)),
            base_delay_seconds=float(retry_cfg.get("base_delay_seconds", 0.5)),
            max_delay_seconds=float(retry_cfg.get("max_delay_seconds", 8.0)),
        ),
        # Rate limiting exists to protect an external provider. In mock mode
        # there is none, and throttling an offline run would only make the demo
        # and the test suite sleep for no reason.
        rate_limiter=RateLimiter(
            max_calls=0 if mock else int(rate.get("max_calls", 120)),
            per_seconds=float(rate.get("per_seconds", 60.0)),
        ),
        breaker=CircuitBreaker(
            failure_threshold=int(breaker_cfg.get("failure_threshold", 5)),
            reset_after_seconds=float(breaker_cfg.get("reset_after_seconds", 60.0)),
        ),
        model_names=model_names,
    )

    # --- agents ------------------------------------------------------------
    core_dna = repositories.dna.load_core()
    prompt_defaults: dict[str, str] = {}
    lens_text = core_dna.lens_context()
    if lens_text:
        prompt_defaults["institutional_lens_context"] = lens_text
    prompts = FilePromptLibrary(root / "prompts", defaults=prompt_defaults)
    if not prompts.names():
        raise ConfigurationError(
            f"no prompts found under {root / 'prompts'}; the society cannot be built"
        )
    agent_context = AgentContext(
        prompts=prompts,
        complete=router.complete,
        logger=logger,
        metrics=metrics,
        correlation_id=random_source.token(10),
    )
    society = AgentSociety.build(agent_context, definitions=config.agent_definitions())

    # --- research ----------------------------------------------------------
    if flags.external_research_enabled:
        research = WebResearchAdapter(NullSearchProvider(), router.complete)
    else:
        research = OfflineResearchAdapter(router.complete, corpus=corpus)

    # --- policies and services --------------------------------------------
    policies = Policies(
        scoring=config.scoring_policy(),
        exploration=config.exploration_policy(),
        circadian=config.circadian_policy(),
        mutation=config.mutation_policy(),
        memory=config.memory_policy(),
        dna=config.dna_policy(),
        constitution=config.constitution_policy(),
        autonomy=config.autonomy_policy(),
    )
    services = Services(
        novelty=NoveltyService(duplicate_threshold=config.duplicate_threshold()),
        distance=CreativeDistanceService(),
        diversity=DiversityService(),
        saturation=SaturationService(),
        tournament=TournamentService(
            scoring=policies.scoring,
            max_similarity_between_survivors=config.max_similarity_between_survivors(),
        ),
    )

    production = tuple(
        FilesystemProductionAdapter(
            engine, root / "outputs" / "_handoff", enabled=flags.production_handoff_enabled
        )
        for engine in KNOWN_ENGINES
    )

    context = BrainContext(
        repositories=repositories,
        policies=policies,
        services=services,
        society=society,
        clock=clock,
        random=random_source,
        bus=bus,
        logger=logger,
        metrics=metrics,
        output=output,
        research=research,
        vectors=vectors,
        graph=graph,
        corpus=corpus,
        production=production,
        flags=flags,
        targets=config.cycle_targets(),
        correlation_id=agent_context.correlation_id,
        distance_measurement_weight=config.distance_measurement_weight(),
    )

    # The funnel is scaled to the number of concepts the cycle actually targets,
    # otherwise a 30-wide first round would promote every candidate.
    funnel = config.tournament_funnel(pool_size=context.targets.concepts)
    orchestrator = CreativeOrchestrator(context=context, funnel=funnel)
    clock_agent = BiologicalClockAgent(
        policy=policies.circadian, clock=clock, logger=logger, metrics=metrics
    )
    runtime = AutonomousCreativeRuntime(
        context=context, orchestrator=orchestrator, clock_agent=clock_agent, budget=budget
    )

    return Brain(
        config=config,
        context=context,
        runtime=runtime,
        orchestrator=orchestrator,
        clock_agent=clock_agent,
        budget=budget,
        bus=bus,
        metrics=metrics,
    )


def _build_providers(
    config: BrainConfig, random_source: SeededRandom, *, mock: bool
) -> tuple[dict[ModelRole, LLMPort], dict[ModelRole, str]]:
    """Instantiate one provider per model role.

    Roles are separated so CREATOR, CRITIC and JUDGE can be different models —
    the engine must never grade its own homework.
    """
    routing = config.routing()
    providers: dict[ModelRole, LLMPort] = {}
    names: dict[ModelRole, str] = {}
    cache: dict[tuple[str, str], LLMPort] = {}

    for role in ModelRole:
        entry = routing.get(role.value, {})
        provider_name = "mock" if mock else entry.get("provider", config.provider())
        model_name = entry.get("model") or f"mock-{role.value}"
        key = (provider_name, model_name)
        if key not in cache:
            cache[key] = _instantiate(provider_name, model_name, random_source)
        providers[role] = cache[key]
        names[role] = model_name
    return providers, names


def _instantiate(provider: str, model: str, random_source: SeededRandom) -> LLMPort:
    """Build one provider. Real SDKs are imported lazily, inside their adapters."""
    if provider == "mock":
        return MockLLMAdapter(random_source, model=model or "mock-1")
    if provider == "anthropic":
        from creative_brain.adapters.llm.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            model=model or "claude-sonnet-4-5",
            base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
        )
    if provider == "openai":
        from creative_brain.adapters.llm.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=model or "gpt-4.1",
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
        )
    raise ConfigurationError(
        f"unknown LLM provider '{provider}'. Expected one of: mock, anthropic, openai."
    )


__all__ = ["Brain", "build_brain"]
