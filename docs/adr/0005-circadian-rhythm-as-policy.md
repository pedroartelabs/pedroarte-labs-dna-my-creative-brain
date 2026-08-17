# ADR-0005: Circadian Rhythm as Policy
Status: Accepted
Date: 2026-08-17

## Context
Criatividade humana não é constante — há picos e vales de energia. O PACME simula esse padrão biológico para produzir trabalho mais natural e evitar "burnout" do sistema (loops infinitos de geração sem qualidade). Precisamos separar a decisão de QUANDO trabalhar da decisão de O QUE/COMO fazer.

## Decision
O sistema implementa um relógio circadiano com **12 fases** (dawn, morning, midday, afternoon, dusk, evening, night, late_night, etc.), cada uma com um energy gauge (0.0–1.0). **CircadianPolicy** decide QUANDO agentes podem operar — os agentes decidem O QUE, COMO e POR QUÊ. Energy floors impedem trabalho quando energia está abaixo do threshold (ex: < 0.2). A fase de sleep restaura energia gradualmente.

## Consequences
- **Positivo:** Separação clara entre policy (quando) e agency (o quê) — single responsibility.
- **Positivo:** Previne geração exaustiva sem qualidade.
- **Positivo:** Simula ritmo criativo natural, produzindo output mais orgânico.
- **Negativo:** Adiciona complexidade temporal ao scheduling de tarefas.
- **Negativo:** Energy floors podem bloquear trabalho urgente se o clock estiver em fase de baixa energia.
