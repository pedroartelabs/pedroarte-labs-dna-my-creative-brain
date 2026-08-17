# Security Policy

## Classificação

Este repositório é **CONFIDENTIAL PRIVATE PROPRIETARY EXPERIMENTAL**.

## Regras invioláveis

1. O repositório deve permanecer **PRIVATE** no GitHub.
2. Nunca publicar conteúdos, prompts, DNA criativo, memórias ou artefatos
   deste sistema em outro repositório.
3. Nunca versionar: API keys, tokens, credenciais, secrets, dados privados.
4. Creative DNA, memórias e outputs podem conter propriedade intelectual sensível.
5. O Creative Corpus deve permanecer local ou em providers explicitamente configurados.

## O que o motor nunca pode modificar

- `CORE_DNA` — protegido por `ImmutableCoreDnaViolation`
- `CREATIVE_CONSTITUTION` — asset protegido
- Security policies
- Código-fonte
- Permissões do repositório
- Credenciais

## Gestão de credenciais

- Credenciais ficam em `.env` (nunca commitado — está no `.gitignore`).
- O `.env.example` documenta as variáveis necessárias sem valores reais.
- O script `scripts/check_secrets.py` escaneia o repositório por credenciais
  acidentalmente commitadas. Roda como `make security` e no CI.

## Padrões de detecção

O secret scanner procura:
- AWS access keys (`AKIA...`)
- Anthropic API keys (`sk-ant-...`)
- OpenAI API keys (`sk-...`)
- GitHub tokens (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`)
- Private key headers (`-----BEGIN ... PRIVATE KEY-----`)
- Bearer tokens
- Assignments genéricos de secrets em código

## Autonomy boundary

Veja `config/autonomy.yaml` para a lista completa de ações autônomas vs.
restritas. Ações restritas incluem:

- `delete_repository`
- `change_repository_visibility`
- `push_to_remote`
- `publish_externally`
- `manage_credentials`
- `modify_core_dna`
- `spend_money`

## Reporting vulnerabilities

Este é um projeto pessoal experimental. Se encontrar uma vulnerabilidade,
entre em contato diretamente com o autor.
