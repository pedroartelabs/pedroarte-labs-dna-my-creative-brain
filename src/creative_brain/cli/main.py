"""The command-line adapter.

An inbound adapter and nothing more: it parses arguments, calls the runtime and
renders the result. No business rule lives here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from creative_brain import __acronym__, __system_name__, __version__
from creative_brain.application.use_cases.exporting import ExportToVault
from creative_brain.composition import Brain, build_brain, build_vault_exporter
from creative_brain.domain.exceptions import CreativeBrainError

BANNER = f"""
  ╔══════════════════════════════════════════════════════════════╗
  ║   {__system_name__}   ║
  ║   {__acronym__} · cérebro criativo multiagente · v{__version__}            ║
  ║   CONFIDENTIAL · PRIVATE · PROPRIETARY                       ║
  ╚══════════════════════════════════════════════════════════════╝
""".rstrip()


def build_parser() -> argparse.ArgumentParser:
    """Define the CLI surface."""
    parser = argparse.ArgumentParser(
        prog="creative-brain",
        description="PEDRO ARTE CREATIVE MIND ENGINE — autonomous creative operating system.",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root")
    parser.add_argument(
        "--mock", action="store_true", help="use the deterministic offline provider (no API calls)"
    )
    parser.add_argument("--seed", type=int, default=None, help="override the random seed")
    parser.add_argument("--quiet", action="store_true", help="suppress structured logs")
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="run the autonomous creative loop")
    start.add_argument("--cycles", type=int, default=None, help="stop after N cycles")
    start.add_argument(
        "--single-cycle", action="store_true", help="run exactly one full circadian cycle"
    )
    start.add_argument(
        "--autonomous", action="store_true", help="keep the runtime alive indefinitely"
    )

    sub.add_parser("demo", help="run one complete cycle offline and print the winner")
    sub.add_parser("status", help="show the current state of the mind")
    sub.add_parser("stop", help="request a graceful shutdown of a running brain")

    cycle = sub.add_parser("cycle", help="cycle operations")
    cycle_sub = cycle.add_subparsers(dest="cycle_command", required=True)
    cycle_run = cycle_sub.add_parser("run", help="run one cycle")
    cycle_run.add_argument("--cycles", type=int, default=1)

    memory = sub.add_parser("memory", help="memory operations")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    memory_inspect = memory_sub.add_parser("inspect", help="inspect memory records")
    memory_inspect.add_argument("--limit", type=int, default=20)

    graveyard = sub.add_parser("graveyard", help="graveyard operations")
    graveyard_sub = graveyard.add_subparsers(dest="graveyard_command", required=True)
    graveyard_inspect = graveyard_sub.add_parser("inspect", help="inspect buried ideas")
    graveyard_inspect.add_argument("--limit", type=int, default=20)

    tournament = sub.add_parser("tournament", help="tournament operations")
    tournament_sub = tournament.add_subparsers(dest="tournament_command", required=True)
    tournament_inspect = tournament_sub.add_parser("inspect", help="inspect a tournament")
    tournament_inspect.add_argument("--id", dest="tournament_id", default=None)

    agents = sub.add_parser("agents", help="agent operations")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)
    agents_sub.add_parser("list", help="list every declared agent")

    clock = sub.add_parser("clock", help="biological clock operations")
    clock_sub = clock.add_subparsers(dest="clock_command", required=True)
    clock_sub.add_parser("status", help="show the circadian state")

    export = sub.add_parser("export", help="export the creative mind elsewhere")
    export_sub = export.add_subparsers(dest="export_command", required=True)
    export_vault = export_sub.add_parser("vault", help="export to an Obsidian vault")
    export_vault.add_argument(
        "--to", dest="vault_path", type=Path, required=True, help="destination vault folder"
    )
    export_vault.add_argument("--limit", type=int, default=200, help="max records per kind")
    export_vault.add_argument(
        "--no-graveyard", action="store_true", help="skip buried ideas"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except CreativeBrainError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("\ninterrupted; the brain shut down gracefully", file=sys.stderr)
        return 130


def _dispatch(args: argparse.Namespace) -> int:
    root: Path = args.root.resolve()
    mock = bool(args.mock) or args.command == "demo"

    if args.command == "demo":
        return _demo(root, args)

    brain = build_brain(root, mock=mock, quiet=args.quiet, seed=args.seed)

    if args.command == "start":
        cycles = 1 if args.single_cycle else args.cycles
        if args.autonomous:
            cycles = None
        brain.runtime.install_signal_handlers()
        brain.runtime.start(cycles=cycles)
        return _emit(args, brain.runtime.last_outcome.as_dict() if brain.runtime.last_outcome else {})

    if args.command == "cycle":
        brain.runtime.install_signal_handlers()
        brain.runtime.start(cycles=args.cycles)
        return _emit(args, brain.runtime.last_outcome.as_dict() if brain.runtime.last_outcome else {})

    if args.command == "status":
        return _status(brain, args)

    if args.command == "stop":
        brain.runtime.stop()
        brain.runtime.shutdown()
        print("shutdown requested; state and checkpoint persisted")
        return 0

    if args.command == "memory":
        records = [
            r.as_dict() for r in brain.context.repositories.memory.list_all(limit=args.limit)
        ]
        return _emit(args, records, renderer=_render_memory)

    if args.command == "graveyard":
        buried = [
            {
                "id": str(c.id),
                "title": c.title,
                "rejected_at": c.rejected_at,
                "reasons": list(c.rejection_reasons),
                "mutation_potential": c.mutation_potential,
                "score": c.total_score.value,
            }
            for c in brain.context.repositories.concepts.graveyard(limit=args.limit)
        ]
        return _emit(args, buried, renderer=_render_graveyard)

    if args.command == "tournament":
        repo = brain.context.repositories.tournaments
        record = (
            repo.get(args.tournament_id)
            if args.tournament_id
            else next(iter(repo.recent(limit=1)), None)
        )
        if record is None:
            print("no tournaments recorded yet")
            return 0
        return _emit(args, record.as_dict(), renderer=_render_tournament)

    if args.command == "agents":
        return _emit(args, brain.context.society.catalogue(), renderer=_render_agents)

    if args.command == "clock":
        return _emit(
            args,
            brain.clock_agent.report(brain.runtime.state),
            renderer=_render_clock,
        )

    if args.command == "export":
        return _export_vault(brain, args)

    return 0


def _export_vault(brain: Brain, args: argparse.Namespace) -> int:
    """Render the creative mind into an Obsidian vault."""
    adapter = build_vault_exporter(args.vault_path.resolve())
    report = ExportToVault(ctx=brain.context, vault=adapter).execute(
        limit=args.limit,
        include_graveyard=not args.no_graveyard,
    )
    return _emit(args, report.as_dict(), renderer=_render_export)


def _render_export(payload: dict[str, Any]) -> None:
    print(f"  Vault      : {payload['vault_path']}")
    print(f"  Notas      : {payload['notes_written']}")
    print(f"  Mapas      : {payload['canvases_written']}")
    if payload.get("skipped"):
        print(f"  Ignoradas  : {payload['skipped']}")
    print("\n  Abra a pasta no Obsidian e veja 'Mapa Criativo.canvas'.")


def _demo(root: Path, args: argparse.Namespace) -> int:
    """Run one complete offline cycle and print the winner."""
    if not args.json:
        print(BANNER)
        print("\n  Executando um ciclo criativo completo em modo offline (MockLLM).\n")

    # With --json the output must stay machine-readable, so the run goes quiet.
    brain = build_brain(root, mock=True, quiet=args.json or args.quiet, seed=args.seed)
    outcome = brain.runtime.run_single_cycle()

    if args.json:
        print(json.dumps(outcome, indent=2, ensure_ascii=False))
        return 0

    counts = outcome.get("counts", {})
    print("\n" + "─" * 66)
    print(f"  CICLO {outcome.get('cycle_id')}")
    print("─" * 66)
    print(f"  Fases percorridas : {' → '.join(outcome.get('phases', []))}")
    print(f"  Foco do ciclo     : {outcome.get('focus', '')[:60]}")
    print(
        "  Produção          : "
        f"{counts.get('observations', 0)} observações · "
        f"{counts.get('questions', 0)} perguntas · "
        f"{counts.get('seeds', 0)} sementes · "
        f"{counts.get('concepts', 0)} conceitos"
    )
    print(
        "  Seleção           : "
        f"{counts.get('rejected', 0)} rejeitados · "
        f"{counts.get('graveyard', 0)} no cemitério · "
        f"diversidade {outcome.get('diversity', 0):.1f}"
    )
    print(f"  EVOLVING_DNA      : v{outcome.get('dna_version', 0)}")
    print("─" * 66)
    winner = outcome.get("winner_title")
    if winner:
        print(f"  VENCEDOR: {winner}")
        print(f"  Projeto : {outcome.get('project_id')}")
        print(f"\n  Artefatos em: outputs/<data>/{outcome.get('cycle_id')}/winner/")
    else:
        print("  Nenhum vencedor neste ciclo — o júri rejeitou todos os finalistas.")
        print("  (Isso é um resultado legítimo: qualidade vence quantidade.)")
    print("─" * 66 + "\n")
    return 0


def _status(brain: Brain, args: argparse.Namespace) -> int:
    """Render ``creative-brain status``."""
    state = brain.context.repositories.circadian.load() or brain.runtime.state
    checkpoint = brain.context.repositories.checkpoints.load() or {}
    last = checkpoint.get("last_outcome") or {}
    counts = last.get("counts") or {}
    payload = {
        "running": False,
        "phase": str(state.phase),
        "cycle_number": state.cycle_number,
        "cycle_id": state.cycle_id,
        "energy": state.energy.as_dict(),
        "counts": counts,
        "focus": last.get("focus", ""),
        "last_winner": last.get("winner_title", ""),
        "dream_mode": "scheduled dynamically"
        if brain.context.flags.dream_mode_enabled
        else "disabled",
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    energy = state.energy
    print(f"\nCreative Brain: {'RUNNING' if payload['running'] else 'IDLE'}")
    print(f"Phase: {state.phase}")
    print(f"Creative Energy: {energy.creative.value:.0f}")
    print(f"Current Cycle: {state.cycle_number:04d}")
    print()
    print(f"Seeds: {counts.get('seeds', 0)}")
    print(f"Concepts: {counts.get('concepts', 0)}")
    print(f"Candidates: {counts.get('finalists', 0)}")
    print(f"Projects: {counts.get('projects', 0)}")
    print()
    print("Next Biological Decision: dynamic")
    print()
    print("Current Focus:")
    print(f'"{payload["focus"] or "(nenhum foco registrado ainda)"}"')
    print()
    print(f"Dream Mode: {payload['dream_mode']}")
    if payload["last_winner"]:
        print(f"Last Winner: {payload['last_winner']}")
    print()
    return 0


# --- renderers --------------------------------------------------------------


def _emit(args: argparse.Namespace, payload: Any, renderer: Any = None) -> int:
    if args.json or renderer is None:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        renderer(payload)
    return 0


def _render_memory(records: list[dict[str, Any]]) -> None:
    if not records:
        print("memory is empty")
        return
    print(f"\n{len(records)} memory records\n")
    for record in records:
        marker = "PRINCIPLE" if record.get("is_principle") else record.get("kind", "").upper()
        print(f"  [{marker:<10}] {record.get('summary', '')[:88]}")
        if record.get("detail"):
            print(f"               {record['detail'][:88]}")
    print()


def _render_graveyard(buried: list[dict[str, Any]]) -> None:
    if not buried:
        print("the graveyard is empty")
        return
    print(f"\n{len(buried)} buried ideas (nothing here is ever deleted)\n")
    for idea in buried:
        print(f"  {idea['title'][:52]:<52} score {idea['score']:>5.1f}  "
              f"mutação {idea['mutation_potential']:>5.1f}")
        for reason in idea["reasons"][:2]:
            print(f"     └─ {reason[:88]}")
    print()


def _render_tournament(record: dict[str, Any]) -> None:
    print(f"\nTournament {record['id']} (cycle {record['cycle_id']})")
    print(f"  entrants: {len(record['entrants'])}  diversity: {record['diversity_score']:.1f}")
    for round_ in record["rounds"]:
        print(
            f"  {round_['stage']:<10} {len(round_['entrants']):>3} → "
            f"{len(round_['survivors']):>3}  (eliminated {len(round_['eliminated'])})"
        )
    print(f"  winner: {record['winner_id'] or '(none — the judge rejected every finalist)'}\n")


def _render_agents(catalogue: list[dict[str, Any]]) -> None:
    print(f"\n{len(catalogue)} declared agents\n")
    for agent in sorted(catalogue, key=lambda a: a["id"]):
        live = "live" if agent["live"] else "policy" if "CLOCK" in agent["id"] else "disabled"
        rights = ",".join(agent["decision_rights"])
        print(f"  {agent['id']:<28} {live:<8} {agent['model_role']:<12} [{rights}]")
        print(f"    {agent['objective'][:92]}")
    print()


def _render_clock(report: dict[str, Any]) -> None:
    print(f"\nBiological clock — phase {report['phase']} (cycle {report['cycle_number']:04d})")
    print("\n  energy")
    for gauge, value in report["energy"].items():
        bar = "█" * int(value / 5)
        print(f"    {gauge:<20} {value:>6.1f}  {bar}")
    print("\n  backlogs")
    for name, value in report["backlogs"].items():
        print(f"    {name:<20} {value}")
    print("\n  budgets")
    for name, value in report["budgets"].items():
        print(f"    {name:<28} {value}")
    decision = report.get("last_decision")
    if decision:
        print(f"\n  last decision: {decision['phase']} — {decision['reason']}")
    print(f"  next decision: {report['next_decision']}\n")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
