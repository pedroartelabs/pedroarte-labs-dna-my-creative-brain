# Contributing

PACME é um projeto pessoal experimental de Pedro Arte Labs.
Contribuições externas são bem-vindas via Pull Request.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # ou .venv\Scripts\activate no Windows
pip install -e ".[dev]"
```

## Workflow

1. Crie uma branch a partir de `main`.
2. Faça suas alterações.
3. Rode `make check` (lint + typecheck + tests + coverage + security).
4. Abra um PR com descrição clara do que mudou e por quê.

## Regras do código

- **Hexagonal boundary**: o domain não importa nada externo. Rode
  `make architecture-test` para verificar.
- **Sem pseudocódigo**: toda implementação deve ser funcional e testável.
- **Sem secrets**: rode `make security` antes de commitar.
- **Português brasileiro** nos prompts e conteúdo criativo; inglês no código.
- **Testes**: adicione testes para novas funcionalidades. A cobertura mínima
  de domain + application é 85%.

## Estrutura de testes

```
tests/
├── architecture/   # Hexagonal dependency rules
├── contract/       # Adapters satisfy their ports
├── unit/           # Value objects, entities, policies, services
├── integration/    # Repositories, CLI, event bus, prompts
├── property/       # Hypothesis invariants
├── regression/     # Guarantees that must never break
└── e2e/            # Full creative cycle
```

## O que não fazer

- Não modifique `memory/core_dna/core_dna.json` sem discussão explícita.
- Não adicione dependências sem justificativa.
- Não commite `.env` ou credenciais.
- Não torne o repositório público.
