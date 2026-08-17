"""Export the creative mind into a human-navigable vault.

The engine already knows how ideas relate to each other: a concept descends
from a seed, answers a question, carries themes, and either wins a tournament
or ends in the graveyard. This use case renders that structure as notes and a
mind map, so a person can walk the graph instead of reading JSON.
"""

from __future__ import annotations

from dataclasses import dataclass

from creative_brain.application.context import BrainContext
from creative_brain.domain.policies.lifecycle import CreativeStage
from creative_brain.ports.outbound.vault import (
    VaultCanvas,
    VaultCanvasEdge,
    VaultCanvasNode,
    VaultExportPort,
    VaultExportReport,
    VaultNote,
)

#: Obsidian canvas colours: 1 red, 2 orange, 3 yellow, 4 green, 5 cyan, 6 purple.
_COLOUR_WINNER = "4"
_COLOUR_CONCEPT = "5"
_COLOUR_QUESTION = "6"
_COLOUR_GRAVEYARD = "1"
_COLOUR_DNA = "2"

_COLUMN_X = {"dna": -900, "question": -300, "concept": 300, "project": 900}
_ROW_HEIGHT = 160


def _slug(title: str, fallback: str) -> str:
    """Name a note after its title. The adapter sanitises for the filesystem."""
    cleaned = " ".join(str(title).split())
    return cleaned[:120] or fallback


@dataclass
class ExportToVault:
    """Render the engine's creative state as vault notes and a mind map."""

    ctx: BrainContext
    vault: VaultExportPort

    def execute(self, *, limit: int = 200, include_graveyard: bool = True) -> VaultExportReport:
        """Build every note and canvas, then hand them to the vault adapter."""
        notes: list[VaultNote] = []
        nodes: list[VaultCanvasNode] = []
        edges: list[VaultCanvasEdge] = []

        core = self.ctx.repositories.dna.load_core()
        evolving = self.ctx.repositories.dna.load_evolving()

        notes.append(self._dna_note(core, evolving))
        nodes.append(
            VaultCanvasNode(
                node_id="dna",
                label="CORE_DNA",
                x=_COLUMN_X["dna"],
                y=0,
                file="DNA/CORE_DNA.md",
                colour=_COLOUR_DNA,
            )
        )

        questions = self.ctx.repositories.questions.recent(limit=limit)
        question_slugs: dict[str, str] = {}
        for row, question in enumerate(questions):
            slug = _slug(question.text[:60], f"pergunta-{row}")
            question_slugs[str(question.id)] = slug
            notes.append(self._question_note(question, slug))
            node_id = f"q-{question.id}"
            nodes.append(
                VaultCanvasNode(
                    node_id=node_id,
                    label=question.text[:80],
                    x=_COLUMN_X["question"],
                    y=row * _ROW_HEIGHT,
                    file=f"Perguntas/{slug}.md",
                    colour=_COLOUR_QUESTION,
                )
            )
            edges.append(
                VaultCanvasEdge(
                    edge_id=f"e-dna-{question.id}",
                    from_node="dna",
                    to_node=node_id,
                    label="origina",
                )
            )

        concepts = self.ctx.repositories.concepts.list_recent(limit=limit)
        for row, concept in enumerate(concepts):
            buried = concept.stage == CreativeStage.GRAVEYARD
            if buried and not include_graveyard:
                continue
            slug = _slug(concept.title, f"conceito-{row}")
            folder = "Cemitério" if buried else "Conceitos"
            notes.append(self._concept_note(concept, slug, folder, question_slugs))
            node_id = f"c-{concept.id}"
            nodes.append(
                VaultCanvasNode(
                    node_id=node_id,
                    label=concept.title,
                    x=_COLUMN_X["concept"],
                    y=row * _ROW_HEIGHT,
                    file=f"{folder}/{slug}.md",
                    colour=_COLOUR_GRAVEYARD if buried else _COLOUR_CONCEPT,
                )
            )
            parent = question_slugs.get(concept.question_id)
            if parent:
                edges.append(
                    VaultCanvasEdge(
                        edge_id=f"e-q-{concept.id}",
                        from_node=f"q-{concept.question_id}",
                        to_node=node_id,
                        label="responde",
                    )
                )

        projects = self.ctx.repositories.projects.list_all(limit=limit)
        for row, project in enumerate(projects):
            slug = _slug(project.title, f"projeto-{row}")
            notes.append(self._project_note(project, slug))
            node_id = f"p-{project.id}"
            nodes.append(
                VaultCanvasNode(
                    node_id=node_id,
                    label=f"🏆 {project.title}",
                    x=_COLUMN_X["project"],
                    y=row * _ROW_HEIGHT,
                    file=f"Projetos/{slug}.md",
                    colour=_COLOUR_WINNER,
                )
            )
            if project.concept_id:
                edges.append(
                    VaultCanvasEdge(
                        edge_id=f"e-c-{project.id}",
                        from_node=f"c-{project.concept_id}",
                        to_node=node_id,
                        label="venceu",
                    )
                )

        notes.append(self._index_note(len(questions), len(concepts), len(projects)))

        canvas = VaultCanvas(
            name="Mapa Criativo",
            nodes=tuple(nodes),
            edges=tuple(edges),
        )
        return self.vault.export(notes, [canvas])

    # ------------------------------------------------------------------ notes

    def _dna_note(self, core: object, evolving: object) -> VaultNote:
        body_parts = [
            f"**Identidade:** {getattr(core, 'identity', '')}",
            "## Filosofia",
            "\n".join(f"- {p}" for p in getattr(core, "philosophy", ())),
            "## Princípios",
            "\n".join(
                f"- **{p.key}** — {p.statement} *(peso {p.weight})*"
                for p in getattr(core, "principles", ())
            ),
            "## Mecanismos de assinatura",
            "\n".join(f"- {m}" for m in getattr(core, "signature_mechanisms", ())),
            "## Movimentos proibidos",
            "\n".join(f"- {m}" for m in getattr(core, "forbidden_moves", ())),
        ]
        lenses = getattr(core, "institutional_lenses", {}) or {}
        for lens in lenses.values():
            body_parts.append(lens.summary_for_prompt())
        body_parts.append("## EVOLVING_DNA")
        body_parts.append(f"Versão {getattr(evolving, 'version', 0)}")
        discoveries = getattr(evolving, "discoveries", ())
        if discoveries:
            body_parts.append("\n".join(f"- {d}" for d in discoveries))

        return VaultNote(
            path="DNA/CORE_DNA.md",
            title="CORE_DNA",
            body="\n\n".join(part for part in body_parts if part.strip()),
            frontmatter={
                "type": "dna",
                "tier": "core",
                "immutable": True,
                "tags": ["pacme", "dna"],
            },
        )

    def _question_note(self, question: object, slug: str) -> VaultNote:
        return VaultNote(
            path=f"Perguntas/{slug}.md",
            title=getattr(question, "text", "")[:120],
            body=getattr(question, "provocation", ""),
            frontmatter={
                "type": "question",
                "id": str(getattr(question, "id", "")),
                "cycle": getattr(question, "cycle_id", ""),
                "depth": getattr(question, "depth", 1),
                "created": getattr(question, "created_at", ""),
                "tags": ["pacme", "pergunta", *getattr(question, "tags", ())],
            },
            links=("CORE_DNA",),
        )

    def _concept_note(
        self, concept: object, slug: str, folder: str, question_slugs: dict[str, str]
    ) -> VaultNote:
        artifacts = getattr(concept, "artifacts", {}) or {}
        body_parts = [f"> {getattr(concept, 'logline', '')}"]
        central = getattr(concept, "central_question", "")
        if central:
            body_parts.append(f"**Pergunta central:** {central}")
        for key in ("premise", "pitch", "synopsis", "world_bible", "characters"):
            value = artifacts.get(key)
            if value:
                body_parts.append(f"## {key.replace('_', ' ').title()}")
                body_parts.append(value)
        reasons = getattr(concept, "rejection_reasons", ())
        if reasons:
            body_parts.append("## Motivos da rejeição")
            body_parts.append("\n".join(f"- {r}" for r in reasons))

        genome = getattr(concept, "genome", None)
        scoreboard = getattr(concept, "scoreboard", None)
        links = ["CORE_DNA"]
        parent = question_slugs.get(getattr(concept, "question_id", ""))
        if parent:
            links.append(parent)

        return VaultNote(
            path=f"{folder}/{slug}.md",
            title=getattr(concept, "title", "Sem título"),
            body="\n\n".join(part for part in body_parts if str(part).strip()),
            frontmatter={
                "type": "concept",
                "id": str(getattr(concept, "id", "")),
                "stage": str(getattr(concept, "stage", "")),
                "cycle": getattr(concept, "cycle_id", ""),
                "created": getattr(concept, "created_at", ""),
                "score": round(float(getattr(getattr(concept, "total_score", None), "value", 0.0)), 2),
                "creative_distance": round(
                    float(getattr(getattr(genome, "creative_distance", None), "value", 0.0)), 2
                )
                if genome
                else 0.0,
                "zone": str(getattr(getattr(genome, "creative_distance", None), "zone", ""))
                if genome
                else "",
                "themes": list(getattr(concept, "themes", ())),
                "scores": (scoreboard.as_dict() if scoreboard else {}),
                "tags": ["pacme", "conceito"],
            },
            links=tuple(links),
        )

    def _project_note(self, project: object, slug: str) -> VaultNote:
        artifacts = getattr(project, "artifacts", {}) or {}
        body_parts = [f"> {getattr(project, 'logline', '')}"]
        central = getattr(project, "central_question", "")
        if central:
            body_parts.append(f"**Pergunta central:** {central}")
        for key, value in artifacts.items():
            body_parts.append(f"## {key.replace('_', ' ').title()}")
            body_parts.append(value)

        traces = getattr(project, "decision_traces", []) or []
        if traces:
            body_parts.append("## Rastro de decisões")
            body_parts.append(
                "\n".join(f"- **{t.who}** — {t.what}: {t.why}" for t in traces)
            )

        scoreboard = getattr(project, "scoreboard", None)
        return VaultNote(
            path=f"Projetos/{slug}.md",
            title=getattr(project, "title", "Sem título"),
            body="\n\n".join(part for part in body_parts if str(part).strip()),
            frontmatter={
                "type": "project",
                "id": str(getattr(project, "id", "")),
                "status": getattr(project, "status", ""),
                "cycle": getattr(project, "cycle_id", ""),
                "created": getattr(project, "created_at", ""),
                "total_score": round(float(getattr(project, "total_score", 0.0)), 2),
                "scores": (scoreboard.as_dict() if scoreboard else {}),
                "engines": list(getattr(project, "recommended_engines", ())),
                "tags": ["pacme", "projeto", "vencedor"],
            },
            links=("CORE_DNA",),
        )

    def _index_note(self, questions: int, concepts: int, projects: int) -> VaultNote:
        body = "\n".join(
            [
                "Este vault é exportado automaticamente pelo PACME.",
                "",
                "## Conteúdo",
                f"- **{questions}** perguntas criativas",
                f"- **{concepts}** conceitos",
                f"- **{projects}** projetos aprovados",
                "",
                "## Navegação",
                "- [[CORE_DNA]] — a identidade criativa protegida",
                "- Abra `Mapa Criativo.canvas` para ver o grafo completo.",
                "",
                "## Pastas",
                "- `DNA/` — identidade e aprendizado",
                "- `Perguntas/` — perguntas centrais que abriram territórios",
                "- `Conceitos/` — ideias vivas",
                "- `Cemitério/` — ideias enterradas (nunca apagadas)",
                "- `Projetos/` — vencedores de torneio",
            ]
        )
        return VaultNote(
            path="README.md",
            title="Cérebro Criativo — Pedro Arte",
            body=body,
            frontmatter={"type": "index", "tags": ["pacme"]},
        )


__all__ = ["ExportToVault"]
