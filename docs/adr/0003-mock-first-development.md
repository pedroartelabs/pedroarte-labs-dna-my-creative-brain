# ADR-0003: Mock-First Development
Status: Accepted
Date: 2026-08-17

## Context
Desenvolvimento e testes contra LLMs reais são caros, lentos, não-determinísticos e requerem conexão. O PACME tem 33 agentes — rodar o pipeline completo contra a API a cada teste seria inviável. Precisamos de um caminho de desenvolvimento que seja reproduzível, offline e gratuito.

## Decision
MockLLM é o **primary development and testing path**. O flag `--mock` ativa o adapter de mock em todo o sistema. Quando `max_calls=0`, o modo mock permite chamadas ilimitadas (significado invertido: zero = sem limite). MockLLM retorna respostas determinísticas baseadas em templates, permitindo assertions exatas nos testes. O adapter real de LLM é usado apenas em integração e produção.

## Consequences
- **Positivo:** Testes 100% reproduzíveis — mesmo input, mesmo output, sempre.
- **Positivo:** Zero custo de API durante desenvolvimento e CI/CD.
- **Positivo:** Demos offline funcionam sem credenciais.
- **Positivo:** Velocidade — sem latência de rede nos testes.
- **Negativo:** Mock pode divergir do comportamento real da LLM; testes de integração ainda são necessários.
- **Negativo:** `max_calls=0` como "ilimitado" é contra-intuitivo; requer documentação clara.
