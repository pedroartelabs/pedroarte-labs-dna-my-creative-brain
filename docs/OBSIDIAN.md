# Obsidian Integration

O PACME exporta seu estado criativo como um **vault Obsidian**: pastas de
arquivos markdown com frontmatter YAML, `[[wikilinks]]` e um mapa mental
`.canvas`. Nenhum banco de dados, nenhuma API — só arquivos.

## Por que Obsidian

O motor já sabe como as ideias se relacionam: um conceito descende de uma
semente, responde a uma pergunta, carrega temas, e ou vence um torneio ou
termina no cemitério. O Obsidian transforma esse grafo em algo navegável:
graph view, backlinks, busca e mapas mentais visuais.

## Exportar

```bash
make vault VAULT=~/Documents/MeuVault
```

Ou diretamente:

```bash
python -m creative_brain.cli.main --mock --quiet export vault --to ~/Documents/MeuVault
```

Opções:

| Flag | Efeito |
|---|---|
| `--to PATH` | pasta de destino (obrigatório) |
| `--limit N` | máximo de registros por tipo (padrão 200) |
| `--no-graveyard` | pula ideias enterradas |
| `--json` | saída legível por máquina |

## Estrutura gerada

```
MeuVault/
├── README.md                  # índice com contagens e navegação
├── Mapa Criativo.canvas       # mapa mental visual
├── DNA/
│   └── CORE_DNA.md            # identidade, princípios, lentes institucionais
├── Perguntas/                 # perguntas centrais que abriram territórios
├── Conceitos/                 # ideias vivas
├── Cemitério/                 # ideias enterradas (nunca apagadas)
└── Projetos/                  # vencedores de torneio
```

## Formato das notas

Cada nota carrega frontmatter navegável por Dataview:

```markdown
---
type: concept
id: concept_h522jnvv
stage: PRODUCTION_READY
score: 67.28
creative_distance: 94.62
zone: UNKNOWN_ZONE
themes:
  - herança
  - classe social
scores:
  originality: 56.61
  depth: 63.35
tags:
  - pacme
  - conceito
---

# Certidão de Identidade

> Logline aqui.

## Premise
...

## Conexões
- [[CORE_DNA]]
- [[A pergunta que originou isso]]
```

## O mapa mental

O arquivo `Mapa Criativo.canvas` posiciona os nós em colunas:

```
CORE_DNA  →  Perguntas  →  Conceitos  →  Projetos
```

Cores: DNA laranja, perguntas roxas, conceitos ciano, vencedores verdes,
cemitério vermelho. As arestas carregam o tipo de relação (`origina`,
`responde`, `venceu`).

Abra o arquivo no Obsidian para ver o grafo completo.

## Consultas Dataview

Com o plugin Dataview instalado:

```dataview
TABLE score, zone, stage
FROM #conceito
WHERE score > 60
SORT score DESC
```

```dataview
LIST
FROM #conceito
WHERE zone = "UNKNOWN_ZONE"
```

## MCP Server (opcional)

Para leitura/escrita bidirecional a partir do Claude Code, existe um servidor
MCP comunitário. Adicione ao `settings.json`:

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "npx",
      "args": ["-y", "mcp-obsidian", "/caminho/para/MeuVault"]
    }
  }
}
```

Isso permite que o Claude leia e busque no vault diretamente. A exportação do
PACME continua sendo unidirecional (motor → vault) por design: o vault é uma
projeção do estado, não a fonte da verdade.

## Segurança

O vault contém DNA criativo, conceitos e projetos — propriedade intelectual
sensível. Não o versione em repositório público nem o sincronize com serviços
de terceiros sem avaliar a política de privacidade.
