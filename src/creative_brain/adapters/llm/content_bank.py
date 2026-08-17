"""Combinatorial creative substrate for the deterministic mock provider.

This is **not** a creativity engine — it is a fixture. Its job is to give the
mock adapter enough structured Brazilian-institutional raw material that a full
offline cycle produces artifacts a human can actually read and judge, so the
orchestration, scoring, tournament and memory logic can be exercised end to end
without a single external API call.

Real creative work happens through ``LLMPort`` implementations that call actual
models. Nothing here ever runs when a real provider is configured.
"""

from __future__ import annotations

from typing import Sequence

# --- Brazilian institutional texture ----------------------------------------

INSTITUTIONS: tuple[str, ...] = (
    "cartório",
    "condomínio fechado",
    "agência bancária",
    "fila do INSS",
    "posto de saúde",
    "escola pública",
    "seguradora",
    "junta comercial",
    "corretora de consignado",
    "central de atendimento",
    "sindicato",
    "igreja de bairro",
    "delegacia de plantão",
    "aplicativo de entrega",
    "cooperativa de crédito",
    "loteamento irregular",
    "faculdade a distância",
    "concurso público",
)

ABSTRACTIONS: tuple[str, ...] = (
    "memória",
    "identidade",
    "herança",
    "luto",
    "dívida",
    "sobrenome",
    "voz",
    "rosto",
    "sono",
    "perdão",
    "silêncio",
    "sorte",
    "tempo de espera",
    "saudade",
    "reputação",
    "consentimento",
    "vergonha",
    "paciência",
)

SOCIAL_FORCES: tuple[str, ...] = (
    "a classe média endividada",
    "o trabalhador por aplicativo",
    "a família que subiu de classe",
    "o herdeiro sem herança",
    "o funcionário público de carreira",
    "a diarista com dois celulares",
    "o síndico com poder de polícia",
    "o pequeno empresário informal",
    "a mãe que assina por todos",
    "o filho que virou fiador",
)

INVERSION_PAIRS: tuple[tuple[str, str], ...] = (
    ("vida", "morte"),
    ("riqueza", "dívida"),
    ("liberdade", "obrigação"),
    ("identidade", "propriedade"),
    ("lembrar", "esquecer"),
    ("herdar", "pagar"),
    ("cuidar", "cobrar"),
    ("nascer", "ser registrado"),
    ("votar", "ser votado"),
    ("dormir", "produzir"),
)

PARADOXES: tuple[str, ...] = (
    "privacidade pública",
    "liberdade obrigatória",
    "democracia hereditária",
    "pobreza premium",
    "consentimento compulsório",
    "esquecimento certificado",
    "luto parcelado",
    "cidadania por assinatura",
    "aposentadoria antecipada da infância",
    "anonimato registrado",
)

TENSIONS: tuple[str, ...] = (
    "todo mundo aceita porque a alternativa é pior",
    "a regra é justa no papel e cruel na fila",
    "quem reclama perde o lugar",
    "a exceção virou o procedimento padrão",
    "o sistema funciona bem demais para quem já está dentro",
    "ninguém decidiu isso, e mesmo assim aconteceu",
    "o custo é invisível até a primeira vez que você precisa",
)

TONES: tuple[str, ...] = (
    "burocrático-onírico",
    "realismo frio",
    "melancolia administrativa",
    "sátira contida",
    "tensão doméstica",
    "elegância seca",
    "intimidade sob vigilância",
)

STRUCTURES: tuple[str, ...] = (
    "três atos com inversão no segundo",
    "mosaico de protocolos",
    "contagem regressiva burocrática",
    "narrativa em depoimentos",
    "linha do tempo fraturada",
    "espiral de consequências",
    "dossiê montado pelo leitor",
)

TITLE_TEMPLATES: tuple[str, ...] = (
    "O {institution_head} das {abstraction_plural}",
    "{abstraction_title} Vitalícia",
    "Protocolo {abstraction_title}",
    "{abstraction_title} em Nome de Terceiros",
    "A Segunda Via da {abstraction_title}",
    "Inventário de {abstraction_title}",
    "{abstraction_title} com Firma Reconhecida",
    "O Direito de {verb}",
    "Certidão de {abstraction_title}",
    "{abstraction_title} Sem Fiador",
)

VERBS: tuple[str, ...] = (
    "Esquecer",
    "Recusar",
    "Herdar",
    "Sumir",
    "Assinar",
    "Não Comparecer",
    "Ser Ninguém",
)

_INSTITUTION_HEAD: dict[str, str] = {
    "cartório": "Cartório",
    "condomínio fechado": "Condomínio",
    "agência bancária": "Banco",
    "fila do INSS": "Balcão",
    "posto de saúde": "Posto",
    "escola pública": "Colégio",
    "seguradora": "Seguro",
    "junta comercial": "Registro",
    "corretora de consignado": "Consignado",
    "central de atendimento": "Atendimento",
    "sindicato": "Sindicato",
    "igreja de bairro": "Templo",
    "delegacia de plantão": "Plantão",
    "aplicativo de entrega": "Aplicativo",
    "cooperativa de crédito": "Cooperativa",
    "loteamento irregular": "Loteamento",
    "faculdade a distância": "Campus",
    "concurso público": "Concurso",
}

_PLURALS: dict[str, str] = {
    "memória": "Memórias",
    "identidade": "Identidades",
    "herança": "Heranças",
    "luto": "Lutos",
    "dívida": "Dívidas",
    "sobrenome": "Sobrenomes",
    "voz": "Vozes",
    "rosto": "Rostos",
    "sono": "Sonos",
    "perdão": "Perdões",
    "silêncio": "Silêncios",
    "sorte": "Sortes",
    "tempo de espera": "Esperas",
    "saudade": "Saudades",
    "reputação": "Reputações",
    "consentimento": "Consentimentos",
    "vergonha": "Vergonhas",
    "paciência": "Paciências",
}

SIGNAL_TEMPLATES: tuple[str, ...] = (
    "{institution} passou a tratar {abstraction} como um dado cadastrável, "
    "e ninguém foi consultado sobre isso.",
    "{force} descobriu que {abstraction} agora tem prazo de validade "
    "definido por {institution}.",
    "Uma atualização de sistema em {institution} transformou {abstraction} "
    "em algo que pode ser transferido entre pessoas.",
    "{institution} começou a cobrar por algo que sempre foi gratuito: {abstraction}.",
    "{force} passou a usar {abstraction} como garantia de crédito, e o mercado aceitou.",
)

WHAT_IF_TEMPLATES: tuple[str, ...] = (
    "E se {abstraction} pudesse ser registrada em {institution} e, a partir daí, penhorada?",
    "E se {force} precisasse provar {abstraction} para continuar existindo legalmente?",
    "E se {institution} tivesse o poder de declarar {abstraction} de uma pessoa como vencida?",
    "E se {abstraction} fosse herdada junto com as dívidas, e não com os bens?",
    "E se recusar {abstraction} custasse exatamente o que ela vale?",
)

CONSEQUENCE_HORIZONS: tuple[tuple[str, str], ...] = (
    ("T+1 ano", "a prática vira exceção tolerada e aparece o primeiro caso na imprensa"),
    ("T+10 anos", "a exceção vira produto, com planos, taxas e uma classe que não pode pagar"),
    ("T+50 anos", "a geração nascida dentro do sistema não consegue imaginar o mundo anterior"),
    ("T+100 anos", "o mecanismo vira folclore e ninguém lembra que ele foi uma decisão"),
)

RED_TEAM_ATTACKS: tuple[str, ...] = (
    "o segundo ato depende de uma instituição se comportar de forma implausível",
    "o protagonista tem posição moral, não desejo — isso não sustenta um terceiro ato",
    "a regra do mundo é interessante, mas nunca cobra nada de quem a criou",
    "a premissa já foi feita com outro nome; o que muda é o vocabulário, não a estrutura",
    "o leitor entende o conceito na página cinco e não recebe mais nenhuma virada",
    "a tecnologia carrega o drama que deveria ser humano",
)

BLUE_TEAM_DEFENCES: tuple[str, ...] = (
    "a instituição não precisa ser vilã: basta ser eficiente, e isso é o desconforto",
    "o desejo do protagonista é concreto e mesquinho, e é justamente por isso que funciona",
    "a regra cobra caro de quem a criou no terceiro ato — o custo é o motor",
    "a estrutura conhecida é o disfarce; a inversão acontece em quem paga a conta",
    "o conceito é claro cedo porque a pergunta não é 'o quê', é 'até onde'",
    "a tecnologia é cenário; o que quebra são as relações de família",
)

CLICHE_PATTERNS: tuple[str, ...] = (
    "distopia de vigilância com resistência clandestina",
    "IA que ganha consciência e ameaça a humanidade",
    "escolhido que descobre ser especial",
    "apocalipse seguido de comunidade de sobreviventes",
    "sistema de castas com prova de aptidão na adolescência",
)


def title_for(
    institution: str, abstraction: str, template: str, verb: str
) -> str:
    """Render one title template with the given raw material."""
    return (
        template.replace("{institution_head}", _INSTITUTION_HEAD.get(institution, "Registro"))
        .replace("{abstraction_plural}", _PLURALS.get(abstraction, abstraction.title()))
        .replace("{abstraction_title}", abstraction.title())
        .replace("{verb}", verb)
    )


def render(template: str, **parts: str) -> str:
    """Fill a template with named parts, leaving unknown placeholders untouched."""
    text = template
    for key, value in parts.items():
        text = text.replace("{" + key + "}", value)
    return text


def cycle_pick(items: Sequence[str], index: int) -> str:
    """Deterministic round-robin pick — used where variety matters more than surprise."""
    return items[index % len(items)]
