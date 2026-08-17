# ADR-0004: Creative Tournament Funnel (3 Finalists)
Status: Accepted
Date: 2026-08-17

## Context
O torneio criativo do PACME gera múltiplas ideias e as refina em rounds eliminatórios. A pergunta central: o funil deve convergir para 1 vencedor ou para N finalistas? Um único sobrevivente remove a possibilidade de escolha significativa pelo Judge — ele apenas carimba o resultado do processo.

## Decision
O funil multi-round converge para **3 finalistas**, não 1. O Judge (agente ou humano) faz a seleção final entre os 3. Cada round elimina candidatos por scoring e comparação, mas o último corte para de eliminar em 3. O Judge recebe os 3 finalistas com seus scores, justificativas e histórico de rounds.

## Consequences
- **Positivo:** O Judge tem escolha real — pode priorizar por critérios que o scoring automatizado não captura.
- **Positivo:** Preserva diversidade criativa até o final (3 abordagens distintas sobrevivem).
- **Positivo:** Permite que o humano injete intuição na decisão final.
- **Negativo:** Requer um passo adicional de decisão (não é fully autonomous).
- **Negativo:** 3 é um magic number — pode precisar de ajuste para domínios diferentes.
