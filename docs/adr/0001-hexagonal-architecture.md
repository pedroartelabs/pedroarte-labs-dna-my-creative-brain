# ADR-0001: Hexagonal Architecture (Ports & Adapters)
Status: Accepted
Date: 2026-08-17

## Context
PACME precisa de uma arquitetura onde o domínio criativo seja completamente isolado de infraestrutura — LLMs, bancos de dados, APIs externas. Consideramos layered architecture e clean architecture, mas ambas permitem dependências transitivas que contaminam o domínio. O sistema possui 33 agentes e múltiplos adapters (MockLLM, real LLM, file storage, in-memory) que precisam ser trocados sem tocar no core.

## Decision
Adotamos hexagonal architecture. O domínio (entities, value objects, domain services) tem **zero outward imports** — nenhum import de infraestrutura, framework ou adapter. Toda comunicação externa passa por ports (interfaces definidas no domínio) e adapters (implementações na camada de infraestrutura). Use cases orquestram o fluxo chamando ports, nunca implementações concretas.

## Consequences
- **Positivo:** Adapters são 100% substituíveis (MockLLM ↔ real LLM, InMemory ↔ Postgres) sem alterar domínio.
- **Positivo:** Domain pode ser testado unitariamente sem nenhuma dependência externa.
- **Positivo:** Cada agente é um domain service puro, facilitando composição e teste.
- **Negativo:** Mais interfaces e indireção — overhead de boilerplate para cada novo port/adapter.
- **Negativo:** Desenvolvedores novos precisam entender a separação rigorosa entre camadas.
