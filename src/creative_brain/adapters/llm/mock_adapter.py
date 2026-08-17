"""The deterministic mock LLM provider.

``--mock`` must be able to run the *entire* engine: every phase, every agent,
every scoring path, with no network and no API key. That is what makes the test
suite meaningful and what lets a developer see a real cycle in one command.

Determinism comes from two places: a seeded ``SeededRandom`` and a CRC-based
pseudo-quality derived from each text. Python's built-in ``hash()`` is
deliberately avoided because it is randomised per process.
"""

from __future__ import annotations

import zlib
from typing import Any, Callable

from creative_brain.adapters.llm import content_bank as bank
from creative_brain.adapters.randomness import SeededRandom
from creative_brain.ports.outbound.llm import LLMRequest, LLMResponse

Handler = Callable[["MockLLMAdapter", LLMRequest], dict[str, Any]]

_HANDLERS: dict[str, Handler] = {}


def handles(task: str) -> Callable[[Handler], Handler]:
    """Register a handler for one agent task."""

    def decorator(func: Handler) -> Handler:
        _HANDLERS[task] = func
        return func

    return decorator


def stable_quality(text: str, salt: str = "") -> float:
    """A reproducible 0..1 pseudo-quality for a piece of text.

    Deterministic across processes and machines, so a cycle replays identically.
    """
    digest = zlib.crc32(f"{salt}|{text}".encode())
    return (digest % 10_000) / 10_000.0


class MockLLMAdapter:
    """Offline provider that answers every agent task with schema-shaped content."""

    def __init__(self, random_source: SeededRandom | None = None, *, model: str = "mock-1") -> None:
        self._random = random_source or SeededRandom()
        self._model = model
        self.calls: list[str] = []

    @property
    def provider(self) -> str:
        """Provider name."""
        return "mock"

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Answer one request. Unknown tasks degrade to a generic critique."""
        self.calls.append(request.task)
        handler = _HANDLERS.get(request.task, MockLLMAdapter._generic)
        data = handler(self, request)
        text = str(data.get("summary") or data.get("rationale") or data.get("text") or request.task)
        input_tokens = max(1, len(request.system) + len(request.user)) // 4
        output_tokens = max(1, len(str(data))) // 4
        return LLMResponse(
            text=text,
            model=self._model,
            data=data,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            # A nominal price so budget accounting is exercised offline too.
            estimated_cost_usd=round((input_tokens * 3e-6) + (output_tokens * 15e-6), 8),
            provider="mock",
        )

    # ------------------------------------------------------------- OBSERVE

    @handles("observer.capture")
    def _observe(self, request: LLMRequest) -> dict[str, Any]:
        count = _requested(request, "count", 6)
        domains = (
            "society",
            "technology",
            "economy",
            "institutions",
            "behaviour",
            "human_relations",
            "social_change",
            "culture",
        )
        kinds = ("fact", "trend", "oddity", "contradiction", "weak_signal")
        observations = []
        for _ in range(count):
            institution = self._random.pick(bank.INSTITUTIONS)
            abstraction = self._random.pick(bank.ABSTRACTIONS)
            force = self._random.pick(bank.SOCIAL_FORCES)
            statement = bank.render(
                self._random.pick(bank.SIGNAL_TEMPLATES),
                institution=institution,
                abstraction=abstraction,
                force=force,
            )
            observations.append(
                {
                    "statement": statement,
                    "domain": self._random.pick(domains),
                    "kind": self._random.pick(kinds),
                    "tension": self._random.pick(bank.TENSIONS),
                    "tags": [abstraction, institution],
                    "salience": round(40 + stable_quality(statement, "salience") * 60, 2),
                }
            )
        return {"observations": observations}

    @handles("research.investigate")
    def _research(self, request: LLMRequest) -> dict[str, Any]:
        topic = _requested(request, "topic", "identidade digital")
        institution = self._random.pick(bank.INSTITUTIONS)
        return {
            "summary": (
                f"'{topic}' já existe de forma parcial: {institution} opera hoje uma versão "
                "informal do mecanismo, sustentada por contrato de adesão e falta de alternativa."
            ),
            "key_facts": [
                f"o registro de {topic} hoje é feito por intermediários privados sem padronização",
                "o custo de sair do sistema é maior que o custo de permanecer nele",
                "existe jurisprudência ambígua sobre quem é o proprietário do registro",
            ],
            "implications": [
                "a transição para obrigatoriedade não exigiria nenhuma lei nova",
                f"a primeira classe a sentir o efeito seria {self._random.pick(bank.SOCIAL_FORCES)}",
            ],
            "confidence": round(45 + stable_quality(topic, "conf") * 45, 2),
        }

    # ------------------------------------------------------------- QUESTION

    @handles("curiosity.questions")
    def _questions(self, request: LLMRequest) -> dict[str, Any]:
        count = _requested(request, "count", 4)
        source = _requested(request, "observation", "")
        questions = []
        for _ in range(count):
            abstraction = self._random.pick(bank.ABSTRACTIONS)
            institution = self._random.pick(bank.INSTITUTIONS)
            questions.append(
                {
                    "text": self._random.pick(
                        (
                            f"Quem realmente é dono da sua {abstraction}?",
                            f"O que acontece quando {institution} passa a decidir "
                            f"o valor da sua {abstraction}?",
                            f"Por que aceitamos que {abstraction} tenha preço, "
                            "mas não que tenha dono?",
                            f"Quanto custa recusar {abstraction} num país onde "
                            "recusar é um privilégio?",
                        )
                    ),
                    "provocation": source[:200],
                    "tags": [abstraction],
                }
            )
        return {"questions": questions}

    # ------------------------------------------------------------- GENERATE

    @handles("what_if.hypotheses")
    def _what_if(self, request: LLMRequest) -> dict[str, Any]:
        return {"hypotheses": self._seed_batch(request, bank.WHAT_IF_TEMPLATES, "what_if")}

    @handles("collider.collide")
    def _collide(self, request: LLMRequest) -> dict[str, Any]:
        count = _requested(request, "count", 4)
        collisions = []
        for _ in range(count):
            institution = self._random.pick(bank.INSTITUTIONS)
            first, second = self._random.sample(bank.ABSTRACTIONS, 2)
            statement = (
                f"Um {institution} que registra, avalia e transfere {first} — "
                f"e descobre tarde demais que {second} vem junto no mesmo processo."
            )
            collisions.append(
                {
                    "statement": statement,
                    "ingredients": [institution, first, second],
                    "themes": [first, second],
                    "heat": round(35 + stable_quality(statement, "heat") * 65, 2),
                }
            )
        return {"collisions": collisions}

    @handles("inversion.invert")
    def _invert(self, request: LLMRequest) -> dict[str, Any]:
        count = _requested(request, "count", 3)
        inversions = []
        for _ in range(count):
            left, right = self._random.pick(bank.INVERSION_PAIRS)
            institution = self._random.pick(bank.INSTITUTIONS)
            statement = (
                f"Inverta {left} e {right}: num país onde {right} é o estado natural, "
                f"{institution} existe para conceder {left} por prazo determinado."
            )
            inversions.append(
                {
                    "statement": statement,
                    "axis": f"{left} <-> {right}",
                    "themes": [left, right],
                    "heat": round(40 + stable_quality(statement, "heat") * 60, 2),
                }
            )
        return {"inversions": inversions}

    @handles("paradox.find")
    def _paradox(self, request: LLMRequest) -> dict[str, Any]:
        count = _requested(request, "count", 3)
        paradoxes = []
        for _ in range(count):
            paradox = self._random.pick(bank.PARADOXES)
            force = self._random.pick(bank.SOCIAL_FORCES)
            statement = (
                f"'{paradox}' não é contradição, é política pública: {force} vive "
                "dentro dela todos os dias e chama isso de normalidade."
            )
            paradoxes.append(
                {
                    "statement": statement,
                    "paradox": paradox,
                    "themes": [paradox.split()[0]],
                    "heat": round(45 + stable_quality(statement, "heat") * 55, 2),
                }
            )
        return {"paradoxes": paradoxes}

    @handles("unknown.propose")
    def _unknown(self, request: LLMRequest) -> dict[str, Any]:
        count = _requested(request, "count", 2)
        proposals = []
        for _ in range(count):
            abstraction = self._random.pick(bank.ABSTRACTIONS)
            statement = (
                f"E se o conflito não fosse contra o sistema, mas contra a própria "
                f"vontade de sair dele? Uma história em que {abstraction} é a coisa "
                "que o protagonista escolhe entregar, e ninguém o obrigou."
            )
            proposals.append(
                {
                    "statement": statement,
                    "why_unthought": (
                        "a obra anterior sempre colocou a instituição como antagonista; "
                        "aqui o antagonista é o alívio de obedecer"
                    ),
                    "themes": [abstraction, "consentimento"],
                    "heat": round(50 + stable_quality(statement, "heat") * 50, 2),
                }
            )
        return {"proposals": proposals}

    @handles("concept.draft")
    def _concept(self, request: LLMRequest) -> dict[str, Any]:
        seed = _requested(request, "seed", "")
        institution = self._random.pick(bank.INSTITUTIONS)
        abstraction = self._random.pick(bank.ABSTRACTIONS)
        template = self._random.pick(bank.TITLE_TEMPLATES)
        title = bank.title_for(
            institution, abstraction, template, self._random.pick(bank.VERBS)
        )
        force = self._random.pick(bank.SOCIAL_FORCES)
        return {
            "title": title,
            "logline": (
                f"Quando {institution} passa a registrar {abstraction} como patrimônio, "
                f"{force} precisa decidir o que vale mais: manter o que é seu ou "
                "conseguir pagar o que deve."
            ),
            "central_question": f"A quem pertence {abstraction} depois que ela vira registro?",
            "premise": (
                f"O ponto de partida é administrativo, não tecnológico. {institution.capitalize()} "
                f"recebe autorização para registrar {abstraction} em nome de terceiros. "
                f"A regra é aplicada de forma impecável e é exatamente por isso que ela "
                f"destrói uma família: {seed[:180]}"
            ),
            "themes": [abstraction, "classe social", "família"],
            "tone": [self._random.pick(bank.TONES)],
            "structure": [self._random.pick(bank.STRUCTURES)],
        }

    @handles("premise.build")
    def _premise(self, request: LLMRequest) -> dict[str, Any]:
        title = _requested(request, "title", "a obra")
        return {
            "text": (
                f"{title} parte de um mecanismo administrativo plausível e o segue até o "
                "ponto em que ele deixa de ser absurdo e passa a ser rotina. O drama não "
                "está na regra, está em quem assina por quem."
            )
        }

    @handles("pitch.build")
    def _pitch(self, request: LLMRequest) -> dict[str, Any]:
        title = _requested(request, "title", "a obra")
        logline = _requested(request, "logline", "")
        return {
            "text": (
                f"{title} — {logline}\n\n"
                "Um thriller doméstico de classe média sobre o momento em que a "
                "burocracia deixa de ser chata e passa a ser fatal. Para leitores de "
                "distopia próxima, com apelo audiovisual direto: poucos cenários, "
                "muitos rostos, uma regra que todo brasileiro reconhece."
            )
        }

    @handles("synopsis.build")
    def _synopsis(self, request: LLMRequest) -> dict[str, Any]:
        title = _requested(request, "title", "a obra")
        force = self._random.pick(bank.SOCIAL_FORCES)
        return {
            "text": (
                f"Ato I — {title} apresenta a regra nova como conveniência. "
                f"{force.capitalize()} adere porque é mais barato aderir.\n\n"
                "Ato II — A primeira cobrança chega. A regra é aplicada corretamente, "
                "e é essa correção que torna tudo irreversível. A família se divide "
                "entre quem quer sair e quem já depende de ficar.\n\n"
                "Ato III — A saída existe, tem preço, e o preço é outra pessoa. "
                "O final não resolve a regra: amplia a pergunta que a abriu."
            )
        }

    @handles("world_architect.build")
    def _world(self, request: LLMRequest) -> dict[str, Any]:
        institution = self._random.pick(bank.INSTITUTIONS)
        abstraction = self._random.pick(bank.ABSTRACTIONS)
        return {
            "rules": [
                f"todo registro de {abstraction} é válido por 24 meses e precisa de renovação",
                "quem não renova entra em 'situação irregular', não em ilegalidade",
                "a transferência entre pessoas é permitida, a extinção não",
            ],
            "economy": (
                f"um mercado secundário de {abstraction} registrada, com corretoras, "
                "spread e seguro contra inadimplência"
            ),
            "institutions": f"{institution}, agências reguladoras e um ouvidor sem poder de veto",
            "technology": "nada além de cadastro, biometria e integração de bancos de dados",
            "culture": "orgulho de estar regular; vergonha silenciosa de estar irregular",
            "language": "'está em dia?', 'segunda via', 'situação irregular', 'firma reconhecida'",
            "classes": [
                "regulares vitalícios",
                "regulares por assinatura",
                "irregulares tolerados",
                "irregulares reincidentes",
            ],
            "taboos": [f"perguntar a alguém o valor da própria {abstraction}"],
            "power": "quem controla o prazo de renovação controla a vida das pessoas",
        }

    @handles("character_architect.build")
    def _characters(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "characters": [
                {
                    "name": "Vera",
                    "position": "assina por toda a família há vinte anos",
                    "want": "sair do sistema sem que ninguém perceba que ela entrou",
                    "fear": "descobrir que a filha já a usou como garantia",
                    "contradiction": "defende a regra em público e a burla em casa",
                },
                {
                    "name": "Aldo",
                    "position": "funcionário do balcão que aplica a regra corretamente",
                    "want": "uma promoção que o tire do atendimento ao público",
                    "fear": "ser lembrado como o rosto do sistema",
                    "contradiction": "é gentil com cada pessoa e implacável com todas",
                },
                {
                    "name": "Dani",
                    "position": "nasceu já registrada e não conhece o mundo anterior",
                    "want": "usar o próprio registro como capital inicial",
                    "fear": "ser a única da geração que não conseguiu lucrar com isso",
                    "contradiction": "chama de liberdade exatamente aquilo que a prende",
                },
            ]
        }

    # ------------------------------------------------------------- CRITIQUE

    @handles("red_team.attack")
    def _red_team(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "red")
        attacks = self._random.sample(bank.RED_TEAM_ATTACKS, 3)
        return {
            "verdict": "REJECT" if quality < 0.55 else "NEUTRAL",
            "rationale": f"Onde isso quebra: {attacks[0]}.",
            "evidence": attacks,
            "scores": {
                "originality": round(20 + quality * 55, 2),
                "depth": round(25 + quality * 50, 2),
                "plausibility": round(30 + quality * 45, 2),
            },
            "confidence": round(60 + quality * 35, 2),
        }

    @handles("blue_team.defend")
    def _blue_team(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "blue")
        defences = self._random.sample(bank.BLUE_TEAM_DEFENCES, 3)
        return {
            "verdict": "SUPPORT",
            "rationale": f"Por que isso se sustenta: {defences[0]}.",
            "evidence": defences,
            "scores": {
                "narrative_potential": round(45 + quality * 50, 2),
                "expandability": round(40 + quality * 55, 2),
            },
            "confidence": round(55 + quality * 30, 2),
        }

    @handles("anti_cliche.attack")
    def _anti_cliche(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "cliche")
        pattern = self._random.pick(bank.CLICHE_PATTERNS)
        derivative = quality < 0.35
        return {
            "verdict": "REJECT" if derivative else "NEUTRAL",
            "rationale": (
                f"Comparado estruturalmente com '{pattern}'. "
                + (
                    "A diferença é apenas de vocabulário."
                    if derivative
                    else "A diferença está em quem paga a conta, e isso é estrutural."
                )
            ),
            "evidence": [f"padrão mais próximo: {pattern}"],
            "closest_pattern": pattern,
            "what_is_new": (
                ""
                if derivative
                else "o antagonista é um procedimento correto, não uma vilania"
            ),
            "scores": {"originality": round(25 + quality * 65, 2)},
            "confidence": round(65 + quality * 25, 2),
        }

    @handles("reality_anchor.check")
    def _reality_anchor(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "anchor")
        return {
            "verdict": "SUPPORT" if quality > 0.3 else "NEUTRAL",
            "rationale": (
                "O caminho da realidade atual até esta distopia não exige lei nova: "
                "exige apenas que uma prática já existente seja padronizada."
            ),
            "evidence": ["contrato de adesão", "ausência de alternativa", "custo de saída alto"],
            "scores": {"plausibility": round(40 + quality * 55, 2)},
            "confidence": round(55 + quality * 35, 2),
        }

    @handles("brazilian_reality.localize")
    def _brazilian(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "br")
        return {
            "verdict": "SUPPORT" if quality > 0.25 else "REJECT",
            "rationale": (
                "Não é história americana traduzida: o conflito depende de fila, "
                "de fiador e de uma relação de classe que só existe aqui."
            ),
            "evidence": [
                "o antagonista real é a exigência de segunda via",
                "a solidariedade familiar funciona como garantia bancária informal",
                "o poder local é exercido por síndico, não por Estado",
            ],
            "localized_details": [
                "boleto com vencimento em dia de pagamento",
                "grupo de WhatsApp do condomínio como tribunal",
                "consignado como forma de chantagem afetiva",
            ],
            "scores": {
                "authorial_identity": round(45 + quality * 50, 2),
                "plausibility": round(45 + quality * 45, 2),
            },
            "confidence": round(60 + quality * 30, 2),
        }

    @handles("human_drama.ground")
    def _human_drama(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "drama")
        return {
            "verdict": "SUPPORT" if quality > 0.28 else "REJECT",
            "rationale": (
                "Um ser humano se importa porque a regra chega em forma de pedido "
                "de um parente, não em forma de decreto."
            ),
            "evidence": ["dívida", "família", "vergonha de classe", "amor como garantia"],
            "human_stakes": [
                "a mãe que assina para não humilhar o filho",
                "o irmão que lucra com a assinatura dela",
            ],
            "scores": {"emotional_impact": round(40 + quality * 55, 2)},
            "confidence": round(58 + quality * 32, 2),
        }

    @handles("elegance.evaluate")
    def _elegance(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "elegance")
        return {
            "verdict": "SUPPORT" if quality > 0.4 else "NEUTRAL",
            "rationale": (
                "A tensão vem do que não é dito no balcão. Nenhum choque gratuito, "
                "nenhuma explicação a mais."
            ),
            "evidence": ["subtexto no atendimento", "atmosfera seca", "recusa da exposição fácil"],
            "scores": {
                "depth": round(38 + quality * 55, 2),
                "audiovisual_potential": round(42 + quality * 52, 2),
            },
            "confidence": round(52 + quality * 30, 2),
        }

    @handles("pedro_dna.evaluate")
    def _dna(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "dna")
        mechanism = quality > 0.4
        return {
            "verdict": "SUPPORT" if mechanism else "REJECT",
            "rationale": (
                "Isto reproduz o mecanismo criativo esperado: instituição comum levada "
                "às últimas consequências lógicas."
                if mechanism
                else "Isto imita a superfície da obra anterior sem reproduzir o mecanismo "
                "que a gerou."
            ),
            "evidence": [
                "parte de um procedimento, não de uma tecnologia",
                "a consequência é social antes de ser individual",
            ],
            "scores": {
                "authorial_identity": round(30 + quality * 62, 2),
                "depth": round(35 + quality * 55, 2),
            },
            "confidence": round(62 + quality * 30, 2),
        }

    @handles("market.evaluate")
    def _market(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "market")
        return {
            "verdict": "NEUTRAL",
            "rationale": "Título comunica sozinho; a capa é óbvia; o trailer cabe em 30 segundos.",
            "evidence": ["conceito explicável em uma frase", "poucos cenários", "elenco pequeno"],
            "pitch_line": "Uma regra nova. Uma família. Uma assinatura que não pode ser desfeita.",
            "audience": "leitores de distopia próxima e drama social brasileiro, 25-45",
            "scores": {
                "commercial_potential": round(35 + quality * 58, 2),
                "audiovisual_potential": round(40 + quality * 55, 2),
            },
            "confidence": round(50 + quality * 30, 2),
        }

    @handles("novelty.evaluate")
    def _novelty(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "novelty")
        return {
            "verdict": "SUPPORT" if quality > 0.35 else "REJECT",
            "rationale": "Comparado com o histórico interno e com os padrões conhecidos do gênero.",
            "evidence": ["nenhum concorrente interno acima do limiar de duplicidade"],
            "scores": {"originality": round(30 + quality * 62, 2)},
            "confidence": round(60 + quality * 28, 2),
        }

    @handles("title.propose")
    def _titles(self, request: LLMRequest) -> dict[str, Any]:
        count = _requested(request, "count", 3)
        titles = []
        for _ in range(count):
            institution = self._random.pick(bank.INSTITUTIONS)
            abstraction = self._random.pick(bank.ABSTRACTIONS)
            title = bank.title_for(
                institution,
                abstraction,
                self._random.pick(bank.TITLE_TEMPLATES),
                self._random.pick(bank.VERBS),
            )
            titles.append(
                {
                    "title": title,
                    "reason": "curto, conceitual e lido em duas camadas",
                    "double_meaning": (
                        f"'{abstraction}' como sentimento e como item registrável"
                    ),
                }
            )
        return {"titles": titles}

    @handles("lore.connect")
    def _lore(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "connections": [
                {
                    "kind": "SHARED_COMPANY",
                    "note": "a mesma corretora de consignado pode aparecer ao fundo, sem destaque",
                },
                {
                    "kind": "SHARED_PHRASE",
                    "note": "'está em dia?' funciona como cumprimento em mais de uma obra",
                },
            ],
            "force_shared_universe": False,
        }

    @handles("consequence.simulate")
    def _consequences(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "horizons": [
                {"horizon": horizon, "effect": effect}
                for horizon, effect in bank.CONSEQUENCE_HORIZONS
            ],
            "systemic_risk": (
                "o mecanismo se torna invisível porque a geração seguinte não conhece "
                "o estado anterior"
            ),
        }

    # ---------------------------------------------------------------- JUDGE

    @handles("judge.verdict")
    def _judge(self, request: LLMRequest) -> dict[str, Any]:
        subject = _requested(request, "subject", "")
        quality = stable_quality(subject, "judge")
        approve = quality > 0.3
        return {
            "decision": "APPROVE" if approve else "REJECT",
            "rationale": (
                "As evidências dos agentes convergem: o mecanismo é original, a "
                "consequência é social e o drama não depende da tecnologia."
                if approve
                else "As evidências dos agentes divergem no essencial: o conceito não "
                "produz consequência além da própria premissa."
            ),
            "evidence": [
                "anti-clichê não encontrou equivalente estrutural",
                "reality anchor confirmou caminho plausível",
                "human drama identificou aposta emocional concreta",
            ],
            "scores": {
                "narrative_potential": round(40 + quality * 55, 2),
                "expandability": round(35 + quality * 58, 2),
                "emotional_impact": round(38 + quality * 55, 2),
            },
            "confidence": round(65 + quality * 30, 2),
        }

    # ------------------------------------------------------------ SUBCONSCIOUS

    @handles("dream.associate")
    def _dream(self, request: LLMRequest) -> dict[str, Any]:
        count = _requested(request, "count", 5)
        fragments = []
        for _ in range(count):
            first, second = self._random.sample(bank.ABSTRACTIONS, 2)
            institution = self._random.pick(bank.INSTITUTIONS)
            fragments.append(
                f"Um {institution} onde {first} é pesada em balança de padaria e "
                f"trocada por {second} sem recibo."
            )
        return {
            "fragments": fragments,
            "strangeness": round(60 + stable_quality(str(fragments), "dream") * 40, 2),
            "notes": "nenhum critério de plausibilidade aplicado nesta fase",
        }

    @handles("mutation.mutate")
    def _mutate(self, request: LLMRequest) -> dict[str, Any]:
        operator = _requested(request, "operator", "invert_rule")
        original = _requested(request, "title", "Original")
        abstraction = self._random.pick(bank.ABSTRACTIONS)
        return {
            "title": bank.title_for(
                self._random.pick(bank.INSTITUTIONS),
                abstraction,
                self._random.pick(bank.TITLE_TEMPLATES),
                self._random.pick(bank.VERBS),
            ),
            "logline": (
                f"A mesma regra de '{original}', vista de onde ela dá lucro: agora quem "
                f"conta a história é quem cobra, e {abstraction} é o produto."
            ),
            "premise": (
                f"Operador aplicado: {operator}. A dimensão estrutural alterada muda quem "
                "paga o preço, e com isso muda o gênero da obra inteira."
            ),
            "central_question": f"E se {abstraction} fosse um bom negócio para alguém que amamos?",
            "changed_dimension": operator,
            "rationale": "mutação estrutural, não reescrita cosmética",
            "themes": [abstraction, "cumplicidade"],
        }

    # --------------------------------------------------------------- LEARNING

    @handles("memory.consolidate")
    def _consolidate(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "principles": [
                {
                    "summary": "Instituições comuns produzem distopias mais plausíveis que tecnologias novas",
                    "detail": (
                        "Os candidatos mais fortes do ciclo partiram de procedimentos "
                        "administrativos existentes, não de invenções."
                    ),
                    "tags": ["mecanismo", "plausibilidade"],
                },
                {
                    "summary": "O drama sobrevive quando a regra chega pela família",
                    "detail": (
                        "Sempre que a regra chegou por via institucional direta, o "
                        "impacto emocional avaliado caiu."
                    ),
                    "tags": ["drama", "estrutura"],
                },
            ],
            "note": "princípios extraídos de eventos repetidos, não de ocorrência única",
        }

    @handles("learning.reflect")
    def _learning(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "discoveries": [
                "colisão institucional + abstração íntima produz os maiores desvios criativos"
            ],
            "emergent_patterns": [
                "o antagonista mais eficaz é um procedimento correto",
                "finais que ampliam a pergunta pontuam mais que finais que a resolvem",
            ],
            "promising_territories": [
                "consentimento como mercadoria",
                "herança de obrigações em vez de bens",
            ],
            "saturated_themes": ["vigilância", "identidade digital"],
            "successful_combinations": ["cartório + memória + herança"],
            "techniques": ["inverter quem paga a conta antes de inverter a regra"],
            "reason": "consolidação do ciclo",
        }

    @handles("obsession.analyze")
    def _obsession(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "obsessions": [
                {"theme": "memória", "angle": "propriedade legal", "is_new_angle": True},
                {"theme": "dívida", "angle": "herança afetiva", "is_new_angle": True},
                {"theme": "identidade", "angle": "vigilância", "is_new_angle": False},
            ],
            "note": "identidade repete sem ângulo novo: tratar como repetição, não obsessão",
        }

    @handles("meta_cognition.analyze")
    def _meta(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "dominant_mechanism": "collision",
            "diversity_note": (
                "três agentes convergiram para a mesma leitura institucional; "
                "isso é concordância, não confirmação"
            ),
            "recommendation": "elevar o peso do UNKNOWN_ZONE no próximo ciclo",
            "risk": "a sociedade de agentes está pensando com um único vocabulário",
        }

    # -------------------------------------------------------------- fallback

    def _generic(self, request: LLMRequest) -> dict[str, Any]:
        """Any unregistered task still returns a schema-shaped critique."""
        quality = stable_quality(request.user, request.task)
        return {
            "verdict": "NEUTRAL",
            "rationale": f"[mock:{request.task}] resposta genérica determinística",
            "evidence": [],
            "scores": {"depth": round(30 + quality * 50, 2)},
            "confidence": round(40 + quality * 30, 2),
        }

    # --------------------------------------------------------------- helpers

    def _seed_batch(
        self, request: LLMRequest, templates: tuple[str, ...], key: str
    ) -> list[dict[str, Any]]:
        count = _requested(request, "count", 4)
        items = []
        for _ in range(count):
            abstraction = self._random.pick(bank.ABSTRACTIONS)
            institution = self._random.pick(bank.INSTITUTIONS)
            force = self._random.pick(bank.SOCIAL_FORCES)
            statement = bank.render(
                self._random.pick(templates),
                abstraction=abstraction,
                institution=institution,
                force=force,
            )
            items.append(
                {
                    "statement": statement,
                    "themes": [abstraction],
                    "heat": round(35 + stable_quality(statement, key) * 65, 2),
                }
            )
        return items


def _requested(request: LLMRequest, key: str, default: Any) -> Any:
    """Read a hint the application passed through request metadata."""
    raw = request.metadata.get(key)
    if raw is None:
        return default
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    return raw


__all__ = ["MockLLMAdapter", "stable_quality"]
