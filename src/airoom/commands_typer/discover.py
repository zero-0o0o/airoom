"""AIroom discover command implementation (Typer-based)."""

import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from airoom.core.discovery import DiscoveryEngine
from airoom.core.project import Project
from airoom.core.registry import RegistryManager

console = Console()

discover_app = typer.Typer(
    name="discover", help="Discover AI artifacts and registry discrepancies."
)


def _get_project(ctx: typer.Context, path: Optional[Path] = None) -> Project:
    """Get project from context or path argument."""
    project_path = path
    if project_path is None:
        global_opts = ctx.obj
        if global_opts and global_opts.path:
            project_path = global_opts.path
    if project_path is None:
        project_path = Path.cwd()
    return Project(project_path)


def _filter_candidates_by_type(candidates: list, type_filter: str) -> list:
    """Filter candidates by owner type."""
    if type_filter == "all":
        return candidates
    if type_filter == "graphify":
        return [c for c in candidates if c.likely_owner == "Graphify"]
    if type_filter == "superpowers":
        return [c for c in candidates if c.likely_owner == "Superpowers"]
    return candidates


def _render_human(report) -> None:
    """Render discovery report as Rich tables."""
    # Inspected Locations
    if report.inspected_locations:
        table = Table(title="Inspected Locations", show_header=True, header_style="bold")
        table.add_column("Location", style="cyan")
        for loc in report.inspected_locations:
            table.add_row(loc)
        console.print(table)
        console.print()

    # Registered Artifacts
    table = Table(title="Registered Artifacts", show_header=True, header_style="bold")
    table.add_column("Artifact ID", style="cyan")
    table.add_column("Exists", justify="center")
    if report.registered_artifacts:
        for artifact_id, exists in report.registered_artifacts:
            status = "✓" if exists else "✗"
            color = "green" if exists else "red"
            table.add_row(artifact_id, f"[{color}]{status}[/{color}]")
    else:
        table.add_row("[dim]No registered artifacts[/dim]", "")
    console.print(table)
    console.print()

    # Unregistered Candidates
    table = Table(title="Unregistered Candidates", show_header=True, header_style="bold")
    table.add_column("Path", style="cyan")
    table.add_column("Owner", style="green")
    table.add_column("Type", justify="center")
    table.add_column("Mgmt", justify="center")
    table.add_column("Feasibility", style="dim")
    if report.unregistered_candidates:
        for candidate in report.unregistered_candidates:
            table.add_row(
                candidate.path,
                candidate.likely_owner,
                candidate.type,
                candidate.recommended_mode,
                candidate.relocation_feasibility,
            )
    else:
        table.add_row("[dim]No unregistered candidates found[/dim]", "", "", "", "")
    console.print(table)
    console.print()

    # Discrepancies
    table = Table(title="Registry Discrepancies", show_header=True, header_style="bold")
    table.add_column("Kind", style="yellow")
    table.add_column("Details", style="dim")
    if report.discrepancies:
        for disc in report.discrepancies:
            table.add_row(disc.kind, disc.details)
    else:
        table.add_row("[dim]No discrepancies found[/dim]", "")
    console.print(table)
    console.print()

    # Recommendations
    if report.recommendations:
        table = Table(title="Recommendations", show_header=True, header_style="bold")
        table.add_column("#", justify="right", style="dim", width=3)
        table.add_column("Recommendation", style="dim")
        for i, rec in enumerate(report.recommendations, 1):
            table.add_row(str(i), rec)
        console.print(table)


def _render_json(report) -> None:
    """Render discovery report as JSON."""
    output = {
        "inspected_locations": report.inspected_locations,
        "registered_artifacts": [
            {"id": aid, "exists": exists} for aid, exists in report.registered_artifacts
        ],
        "unregistered_candidates": [
            {
                "path": c.path,
                "likely_owner": c.likely_owner,
                "evidence": c.evidence,
                "type": c.type,
                "recommended_mode": c.recommended_mode,
                "relocation_feasibility": c.relocation_feasibility,
            }
            for c in report.unregistered_candidates
        ],
        "discrepancies": [{"kind": d.kind, "details": d.details} for d in report.discrepancies],
        "recommendations": report.recommendations,
    }
    print(json.dumps(output, indent=2))


@discover_app.command()
def discover(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    type: Annotated[
        str,
        typer.Option("--type", help="Filter candidates: graphify|superpowers|all"),
    ] = "all",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Discover AI artifacts and registry discrepancies."""
    # Use global --json flag if local --json not explicitly set
    global_opts = ctx.obj
    if global_opts and global_opts.json_output and not json_output:
        json_output = True

    # Validate type filter
    if type not in ("graphify", "superpowers", "all"):
        if json_output:
            print(
                json.dumps(
                    {
                        "error": "Invalid type filter",
                        "details": f"Unknown type filter: {type}. Must be one of: graphify, superpowers, all",
                    },
                    indent=2,
                )
            )
        else:
            console.print(
                f"[red]Error:[/red] Unknown type filter: {type}. Must be one of: graphify, superpowers, all"
            )
        raise typer.Exit(1)

    project = _get_project(ctx, path)

    # Verify project has been initialized
    if not project.airoom_dir.exists():
        if json_output:
            print(
                json.dumps(
                    {
                        "error": "Project not initialized",
                        "details": f"AIroom directory not found at {project.airoom_dir}. Run 'airoom init' first.",
                    },
                    indent=2,
                )
            )
        else:
            console.print(f"[red]Error:[/red] Project not initialized at {project.root}")
            console.print("Run 'airoom init' to initialize AIroom in this project.")
        raise typer.Exit(1)

    # Run discovery scan
    registry_manager = RegistryManager(project)
    engine = DiscoveryEngine(project, registry_manager)
    report = engine.scan()

    # Filter candidates by type
    report.unregistered_candidates = _filter_candidates_by_type(
        report.unregistered_candidates, type
    )

    if json_output:
        _render_json(report)
    else:
        _render_human(report)

    # Always exit 0 for discovery - results are in the output
