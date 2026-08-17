# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Unreleased]

### Added

- Exportação para vault Obsidian: notas markdown com frontmatter YAML,
  `[[wikilinks]]` e mapa mental `.canvas`.
- `VaultExportPort` + `ObsidianVaultAdapter` seguindo a arquitetura hexagonal.
- Use case `ExportToVault` que mapeia DNA, perguntas, conceitos, cemitério e
  projetos para uma estrutura navegável.
- Comando CLI `export vault --to PATH` com `--limit` e `--no-graveyard`.
- Target `make vault VAULT=path`.
- `docs/OBSIDIAN.md` com formato, consultas Dataview e setup do MCP server.
- 26 testes de integração para renderização de notas, canvas e export.

## [0.1.0] — 2026-08-17

### Added

- Arquitetura hexagonal completa: domain, application, adapters, ports, agents,
  composition, CLI.
- 33 agentes com prompts versionados (30 agents + 2 critics + 1 judge).
- Relógio biológico com 12 fases e gauges de energia.
- Torneio criativo com funnel configurável (termina em 3 finalistas).
- DNA de dois níveis: CORE_DNA (imutável) + EVOLVING_DNA (versionado).
- Lente institucional Itaú com 6 pilares culturais integrados nos prompts.
- Itaú Thinking Framework como Claude Code skill (`/itau-thinking`).
- MockLLM para desenvolvimento e testes offline (`--mock`).
- CLI com comandos: demo, start, status, cycle, memory, graveyard, tournament,
  agents, clock.
- 501+ testes em 7 camadas (unit, architecture, contract, integration, property,
  regression, e2e).
- 90% cobertura geral, 94% domain + application.
- Reconciliação de creative distance: intent 65% + measurement 35%.
- Dream mode com ressurreição de ideias do graveyard.
- Mutation engine para variação genética de conceitos.
- Meta-cognition agent para detectar pensamento convergente.
- Scripts utilitários: check_secrets, clean, reset_state.
- Docker + docker-compose para execução containerizada.
- GitHub Actions CI com lint, typecheck, testes e coverage.
- Documentação: ARCHITECTURE, CREATIVE_CONSTITUTION, SECURITY, CONTRIBUTING.
- 8 Architecture Decision Records (ADRs).
- CLAUDE.md com classificação e referência à skill Itaú.
