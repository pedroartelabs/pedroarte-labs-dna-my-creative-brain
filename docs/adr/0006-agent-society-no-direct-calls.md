# ADR-0006: Agent Society — No Direct Calls
Status: Accepted
Date: 2026-08-17

## Context
Com 33 agentes, permitir chamadas diretas entre eles criaria uma teia de dependências impossível de manter e testar. Agent A chamando B que chama C gera spaghetti, ciclos e acoplamento invisível. Precisamos de um modelo de coordenação que mantenha cada agente isolado.

## Decision
Agentes **nunca chamam outros agentes diretamente**. Toda coordenação acontece através de:
1. **Use cases** — orquestram a sequência de agentes necessária para um fluxo.
2. **Domain events** — agentes publicam eventos; outros reagem via subscribers.
3. **Orchestrator** — coordena workflows complexos multi-agente sem que nenhum agente conheça os demais.

## Consequences
- **Positivo:** Cada agente é independentemente testável — basta mockar seus ports.
- **Positivo:** Zero acoplamento entre agentes; adicionar/remover agentes não quebra os demais.
- **Positivo:** Fluxo de coordenação é explícito e rastreável nos use cases.
- **Negativo:** Comunicação indireta adiciona overhead de eventos e mediação.
- **Negativo:** Debugar fluxos multi-agente requer seguir a cadeia de eventos, não um call stack direto.
