"""The vault export must produce something Obsidian can actually open."""

from __future__ import annotations

import json
from pathlib import Path

from creative_brain.adapters.vault import (
    ObsidianVaultAdapter,
    render_canvas,
    render_frontmatter,
    render_note,
    safe_filename,
)
from creative_brain.application.use_cases.exporting import ExportToVault
from creative_brain.ports.outbound.vault import (
    VaultCanvas,
    VaultCanvasEdge,
    VaultCanvasNode,
    VaultExportPort,
    VaultNote,
)


class TestFilenameSafety:
    def test_it_strips_characters_obsidian_rejects(self):
        assert safe_filename('a/b:c*d?e"f<g>h|i') == "abcdefghi"

    def test_it_falls_back_when_nothing_survives(self):
        assert safe_filename("///", fallback="anon") == "anon"

    def test_it_collapses_whitespace(self):
        assert safe_filename("a    b") == "a b"

    def test_it_caps_length(self):
        assert len(safe_filename("x" * 500)) == 120


class TestFrontmatter:
    def test_an_empty_mapping_produces_no_block(self):
        assert render_frontmatter({}) == ""

    def test_scalars_round_trip(self):
        out = render_frontmatter({"type": "concept", "score": 67.28, "immutable": True})
        assert "type: concept" in out
        assert "score: 67.28" in out
        assert "immutable: true" in out

    def test_lists_become_yaml_sequences(self):
        out = render_frontmatter({"tags": ["a", "b"]})
        assert "tags:\n  - a\n  - b" in out

    def test_empty_lists_stay_inline(self):
        assert "tags: []" in render_frontmatter({"tags": []})

    def test_dicts_become_nested_mappings(self):
        out = render_frontmatter({"scores": {"depth": 63.3, "originality": 56.6}})
        assert "scores:\n  depth: 63.3\n  originality: 56.6" in out

    def test_values_needing_quotes_get_them(self):
        out = render_frontmatter({"created": "2026-08-08T11:50:44Z"})
        assert '"2026-08-08T11:50:44Z"' in out

    def test_it_opens_and_closes_the_block(self):
        out = render_frontmatter({"a": "b"})
        assert out.startswith("---")
        assert out.endswith("---")


class TestNoteRendering:
    def test_a_note_carries_title_body_and_links(self):
        note = VaultNote(
            path="Conceitos/x.md",
            title="Certidão de Identidade",
            body="Uma premissa.",
            frontmatter={"type": "concept"},
            links=("CORE_DNA", "Outra"),
        )
        out = render_note(note)
        assert "# Certidão de Identidade" in out
        assert "Uma premissa." in out
        assert "[[CORE_DNA]]" in out
        assert "[[Outra]]" in out

    def test_a_note_without_links_has_no_connection_section(self):
        out = render_note(VaultNote(path="a.md", title="T", body="B"))
        assert "Conexões" not in out

    def test_a_note_always_ends_with_a_newline(self):
        assert render_note(VaultNote(path="a.md", title="T", body="B")).endswith("\n")


class TestCanvasRendering:
    def test_a_canvas_is_valid_json(self):
        canvas = VaultCanvas(
            name="Mapa",
            nodes=(VaultCanvasNode(node_id="n1", label="A", x=0, y=0),),
            edges=(),
        )
        parsed = json.loads(render_canvas(canvas))
        assert parsed["nodes"][0]["id"] == "n1"
        assert parsed["nodes"][0]["type"] == "text"

    def test_a_node_pointing_at_a_file_is_a_file_node(self):
        canvas = VaultCanvas(
            name="Mapa",
            nodes=(VaultCanvasNode(node_id="n1", label="A", x=0, y=0, file="DNA/CORE_DNA.md"),),
        )
        node = json.loads(render_canvas(canvas))["nodes"][0]
        assert node["type"] == "file"
        assert node["file"] == "DNA/CORE_DNA.md"

    def test_edges_carry_their_endpoints_and_label(self):
        canvas = VaultCanvas(
            name="Mapa",
            nodes=(),
            edges=(VaultCanvasEdge(edge_id="e1", from_node="a", to_node="b", label="origina"),),
        )
        edge = json.loads(render_canvas(canvas))["edges"][0]
        assert edge["fromNode"] == "a"
        assert edge["toNode"] == "b"
        assert edge["label"] == "origina"


class TestObsidianAdapter:
    def test_it_satisfies_the_port(self, tmp_path: Path):
        assert isinstance(ObsidianVaultAdapter(tmp_path), VaultExportPort)

    def test_writing_a_note_creates_parent_folders(self, tmp_path: Path):
        adapter = ObsidianVaultAdapter(tmp_path)
        adapter.write_note(VaultNote(path="Deep/Nested/x.md", title="T", body="B"))
        assert (tmp_path / "Deep" / "Nested" / "x.md").exists()

    def test_writing_a_canvas_produces_a_canvas_file(self, tmp_path: Path):
        adapter = ObsidianVaultAdapter(tmp_path)
        adapter.write_canvas(VaultCanvas(name="Mapa Criativo"))
        assert (tmp_path / "Mapa Criativo.canvas").exists()

    def test_export_reports_what_it_wrote(self, tmp_path: Path):
        adapter = ObsidianVaultAdapter(tmp_path)
        report = adapter.export(
            [VaultNote(path="a.md", title="A", body="")],
            [VaultCanvas(name="M")],
        )
        assert report.notes_written == 1
        assert report.canvases_written == 1

    def test_a_note_without_a_path_is_skipped_not_crashed(self, tmp_path: Path):
        adapter = ObsidianVaultAdapter(tmp_path)
        report = adapter.export([VaultNote(path="", title="A", body="")], [])
        assert report.skipped == 1
        assert report.notes_written == 0


class TestExportUseCase:
    def test_it_exports_a_walkable_vault(self, brain, tmp_path: Path):
        brain.runtime.run_single_cycle()
        adapter = ObsidianVaultAdapter(tmp_path / "vault")
        report = ExportToVault(ctx=brain.context, vault=adapter).execute()

        assert report.notes_written > 0
        assert report.canvases_written == 1
        assert (tmp_path / "vault" / "DNA" / "CORE_DNA.md").exists()
        assert (tmp_path / "vault" / "README.md").exists()
        assert (tmp_path / "vault" / "Mapa Criativo.canvas").exists()

    def test_the_dna_note_carries_the_institutional_lens(self, brain, tmp_path: Path):
        adapter = ObsidianVaultAdapter(tmp_path / "vault")
        ExportToVault(ctx=brain.context, vault=adapter).execute()
        dna = (tmp_path / "vault" / "DNA" / "CORE_DNA.md").read_text(encoding="utf-8")
        assert "Itaú" in dna

    def test_the_canvas_links_questions_to_concepts(self, brain, tmp_path: Path):
        brain.runtime.run_single_cycle()
        adapter = ObsidianVaultAdapter(tmp_path / "vault")
        ExportToVault(ctx=brain.context, vault=adapter).execute()
        canvas = json.loads(
            (tmp_path / "vault" / "Mapa Criativo.canvas").read_text(encoding="utf-8")
        )
        assert any(e["label"] == "responde" for e in canvas["edges"])

    def test_the_graveyard_can_be_excluded(self, brain, tmp_path: Path):
        brain.runtime.run_single_cycle()
        adapter = ObsidianVaultAdapter(tmp_path / "vault")
        ExportToVault(ctx=brain.context, vault=adapter).execute(include_graveyard=False)
        assert not (tmp_path / "vault" / "Cemitério").exists()
