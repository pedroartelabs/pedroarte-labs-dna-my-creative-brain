# ADR-0007: Institutional Lenses
Status: Accepted
Date: 2026-08-17

## Context
Quando o PACME trabalha para uma instituição (ex: Itau com seus 6 pilares culturais), o output criativo precisa respeitar os valores dessa organização. Porém, modificar o CORE_DNA para cada cliente violaria a identidade autoral. Precisamos de um mecanismo que injete valores externos sem contaminar o DNA.

## Decision
**Institutional Lenses** são conjuntos de valores culturais externos injetados nos prompts dos agentes via `FilePromptLibrary` defaults. Uma lens (ex: `itau_lens.yaml`) define pilares, tom de voz e restrições que são adicionados ao contexto dos agentes como informação suplementar. Lenses são **aditivas, não substitutivas** — elas adicionam critérios de avaliação, nunca removem ou sobrescrevem o CORE_DNA.

## Consequences
- **Positivo:** Calibra o raciocínio criativo para o contexto institucional sem tocar no DNA.
- **Positivo:** Múltiplas lenses podem coexistir (swap por cliente/projeto).
- **Positivo:** Configuração via arquivo — sem mudança de código para adicionar uma nova instituição.
- **Negativo:** Lenses mal escritas podem conflitar com o DNA (requer validação).
- **Negativo:** Agentes precisam processar mais contexto nos prompts, aumentando token usage.
