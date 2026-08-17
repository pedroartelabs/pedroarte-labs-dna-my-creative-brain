# Architecture

PACME usa **Hexagonal Architecture** (Ports & Adapters) com inversão de
dependência estrita e Domain-Driven Design.

## Camadas

```
src/creative_brain/
├── domain/            # Entidades, Value Objects, Policies, Services, Events
│   ├── entities/      # Aggregates: Concept, Tournament, Memory, Observation...
│   ├── value_objects/  # Immutable: CreativeScore, DNA, Energy, Genome, Lineage
│   ├── policies/       # Decisões: Circadian, Scoring, Mutation, Autonomy
│   ├── services/       # Stateless: Similarity, Novelty, Distance, Diversity
│   ├── events/         # Domain events publicados via EventBus
│   ├── specifications/ # Composable queries: InStage, IsAlive, InZone...
│   └── exceptions.py   # Erros tipados do domínio
│
├── application/       # Use Cases + Orchestrator
│   ├── use_cases/     # Observing, Generating, Evaluating, Competing, Learning
│   ├── orchestration/ # O loop criativo: decide a fase, despacha o use case
│   └── context.py     # BrainContext: todos os ports injetados num único objeto
│
├── adapters/          # Implementações concretas dos ports
│   ├── persistence/   # Filesystem JSON repositories + serialization
│   ├── llm/           # MockLLM, Anthropic, OpenAI + ModelRouter
│   ├── prompts/       # FilePromptLibrary (markdown com YAML front matter)
│   ├── observability/ # StructuredLogger, InMemoryMetrics
│   ├── resilience.py  # RateLimiter, CircuitBreaker, RetryPolicy
│   └── ...            # Clock, Events, Research, Production, Randomness
│
├── agents/            # A sociedade de 33 agentes
│   ├── definitions.py # Cadastro: prompt, model role, temperature, rights
│   ├── base.py        # Agent<T>: render prompt → call model → validate schema
│   ├── schemas.py     # Pydantic output models
│   └── society.py     # AgentSociety: registry + builder
│
├── composition/       # Wiring layer (o hexágono se fecha aqui)
│   ├── config.py      # Lê os 6 YAMLs de configuração
│   └── container.py   # build_brain(): monta tudo, retorna BrainContext
│
├── cli/               # Inbound adapter: argparse CLI
│   └── main.py        # Commands: demo, start, status, inspect...
│
└── ports/             # Contratos (Protocol classes)
    ├── inbound/       # (reservado para futuros adapters: API, MCP)
    └── outbound/      # LLM, Repositories, Prompts, Infrastructure, Knowledge
```

## Regra de dependência

```
domain ← application ← adapters/agents ← composition ← cli
```

- O **domain** não importa nada de fora de si mesmo.
- A **application** importa apenas ports e domain.
- Os **adapters** implementam ports e podem importar bibliotecas externas.
- A **composition** é o único lugar que conhece todas as implementações concretas.
- O **CLI** é um adapter inbound que chama `build_brain()` e o orchestrator.

Essa regra é verificada automaticamente por `tests/architecture/test_dependency_rule.py`.

## Fluxo de um ciclo criativo

```
BOOT → AWAKEN → OBSERVE → QUESTION → HUNT (research)
  → GENERATE SEEDS → BUILD CONCEPTS → EVALUATE
  → TOURNAMENT (funnel: 30→10→5→4→3 finalists)
  → JUDGE (picks winner or rejects all)
  → SAVE WINNER → CONSOLIDATE MEMORY
  → DREAM (subconscious recombination)
  → DEEP_SLEEP (energy restored)
```

O relógio biológico (CircadianPolicy) decide a fase com base nos níveis de
energia, pressão de memória, taxa de novidade e orçamento restante.

## Decisões arquiteturais

Veja `docs/adr/` para os ADRs completos.
