# ADR-0002: Two-Tier DNA (CORE + EVOLVING)
Status: Accepted
Date: 2026-08-17

## Context
O PACME precisa aprender e evoluir autonomamente, mas sem perder a identidade autoral do Pedro Arte. Um único DNA mutável arriscaria corromper valores fundamentais. Um DNA totalmente imutável impediria aprendizado. Precisamos de um mecanismo que preserve a essência criativa enquanto permite adaptação.

## Decision
DNA é dividido em dois tiers:
- **CORE_DNA**: Imutável. Qualquer tentativa de modificação levanta uma domain exception (`CoreDNAViolationError`). Contém identidade autoral, valores estéticos fundamentais e princípios inegociáveis.
- **EVOLVING_DNA**: Versionado e autonomamente atualizável. Cada mutação gera uma nova versão com timestamp e razão. Contém preferências aprendidas, calibrações de estilo e parâmetros adaptativos.

## Consequences
- **Positivo:** Identidade autoral é blindada — nenhum agente ou processo pode corrompê-la.
- **Positivo:** O sistema aprende e refina seu comportamento criativo ao longo do tempo.
- **Positivo:** Histórico completo de evolução do EVOLVING_DNA via versionamento.
- **Negativo:** Requer disciplina para classificar corretamente o que é CORE vs EVOLVING.
- **Negativo:** Domain exception adiciona um guard rail que pode surpreender em runtime se mal configurado.
