# PACME — Pedro Arte Creative Mind Engine

## What this is
Autonomous multi-agent creative operating system simulating Pedro Arte's creative process.
Hexagonal architecture, 33 agents, biological clock, creative tournament, two-tier DNA.

## Classification
CONFIDENTIAL PRIVATE PROPRIETARY EXPERIMENTAL

## Security boundaries — NEVER
- Make the repository public or change its visibility
- Publish contents, prompts, creative DNA, memories or artifacts to another repository
- Version API keys, tokens, credentials, secrets, or private data
- Modify: CORE_DNA, CREATIVE_CONSTITUTION, security policies, source code permissions, credentials

## Architecture
- Hexagonal (Ports and Adapters) with strict dependency inversion
- Domain layer has ZERO outward imports
- `src/creative_brain/domain/` — entities, value objects, policies, services, events
- `src/creative_brain/application/` — use cases, orchestrator, context
- `src/creative_brain/adapters/` — persistence, LLM, prompts, observability, resilience
- `src/creative_brain/agents/` — agent definitions, schemas, society, base runtime
- `src/creative_brain/composition/` — container, config (wiring layer)
- `src/creative_brain/cli/` — CLI inbound adapter

## Running
- `make demo` — one creative cycle offline
- `make test` — full test suite (501+ tests)
- `--mock` flag enables offline mode (MockLLM, no external APIs)

## Skills
- `/itau-thinking` — Activate the Itaú Thinking Framework for structured decision analysis using the 6 cultural pillars
