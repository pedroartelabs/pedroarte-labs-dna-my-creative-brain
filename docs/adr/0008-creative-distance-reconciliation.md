# ADR-0008: Creative Distance Reconciliation (Intent 65% + Measurement 35%)
Status: Accepted
Date: 2026-08-17

## Context
O PACME precisa classificar ideias por "distância criativa" — quão longe do familiar uma ideia está. Duas abordagens competem: (1) intent-based, onde a exploration policy atribui zonas (safe/stretch/wild); (2) measurement-based, onde métricas lexicais calculam distância por overlap de palavras. Nenhuma sozinha é suficiente — intent sem medição é subjetiva demais, medição sem intent é superficial.

## Decision
Reconciliação ponderada: **Intent (zone assignment) = 65%** + **Lexical measurement = 35%**. A exploration policy define a zona pretendida; a medição lexical corrige desvios. Measurement nunca override intent — ela ajusta dentro da zona, não reclassifica entre zonas. O peso 65/35 reflete que raw word overlap é um proxy fraco para familiaridade autoral real.

## Consequences
- **Positivo:** Combina o melhor dos dois mundos — intenção estratégica + verificação empírica.
- **Positivo:** Measurement corrige quando o intent é otimista demais sobre a distância real.
- **Positivo:** Pesos são configuráveis no EVOLVING_DNA para refinamento futuro.
- **Negativo:** O ratio 65/35 é heurístico — pode precisar de calibração por domínio criativo.
- **Negativo:** Métricas lexicais são limitadas (não capturam distância semântica profunda).
