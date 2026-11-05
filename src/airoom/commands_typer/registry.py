"""AIroom registry command implementation (Typer-based)."""

import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from airoom.core.project import Project
from airoom.core.registry import RegistryManager, RegistryError

console = Console(width=120)

registry_app = typer.Typer(name="registry", help="Manage artifact registry.")


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


def _get_json_output(ctx: typer.Context, local_json: bool) -> bool:
    """Determine JSON output from global and local options."""
    global_opts = ctx.obj
    if global_opts and global_opts.json_output and not local_json:
        return True
    return local_json


def _require_project(
    ctx: typer.Context, path: Optional[Path] = None, json_output: bool = False
) -> tuple[Project, RegistryManager, bool]:
    """Get project and registry manager, verifying project is initialized.

    Returns:
        Tuple of (project, registry_manager, use_json)

    Raises:
        typer.Exit: If project is not initialized.
    """
    project = _get_project(ctx, path)
    use_json = _get_json_output(ctx, json_output)

    if not project.airoom_dir.exists():
        if use_json:
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

    registry_manager = RegistryManager(project)
    return project, registry_manager, use_json


def _render_artifact_table(artifacts: dict) -> None:
    """Render artifacts as a Rich table."""
    if not artifacts:
        console.print("[dim]No artifacts registered[/dim]")
        return

    table = Table(title="AIroom Registry Artifacts", show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", min_width=15)
    table.add_column("Owner", style="green", min_width=12)
    table.add_column("Path", style="dim", min_width=20)
    table.add_column("Type", justify="center", min_width=6)
    table.add_column("Mgmt", justify="center", min_width=6)
    table.add_column("Status", justify="center", min_width=10)

    for artifact_id, entry in sorted(artifacts.items()):
        status = entry.get("status", "unknown")
        status_color = (
            "green" if status == "active" else "yellow" if status == "inactive" else "red"
        )

        table.add_row(
            artifact_id,
            entry.get("owner", ""),
            entry.get("path", ""),
            entry.get("type", ""),
            entry.get("management", ""),
            f"[{status_color}]{status}[/{status_color}]",
        )

    console.print(table)


def _render_artifact_json(artifacts: dict) -> None:
    """Render artifacts as JSON."""
    output = {"artifacts": []}
    for artifact_id, entry in sorted(artifacts.items()):
        artifact_data = {"id": artifact_id}
        artifact_data.update(entry)
        output["artifacts"].append(artifact_data)
    print(json.dumps(output, indent=2))


def _render_single_artifact_human(artifact_id: str, entry: dict) -> None:
    """Render a single artifact in human-readable format."""
    console.print(f"[bold cyan]Artifact:[/bold cyan] {artifact_id}")
    console.print(f"  [green]Owner:[/green] {entry.get('owner', '')}")
    console.print(f"  [dim]Path:[/dim] {entry.get('path', '')}")
    console.print(f"  Type: {entry.get('type', '')}")
    console.print(f"  Management: {entry.get('management', '')}")
    status = entry.get("status", "")
    status_color = "green" if status == "active" else "yellow" if status == "inactive" else "red"
    console.print(f"  Status: [{status_color}]{status}[/{status_color}]")

    if entry.get("original_path"):
        console.print(f"  [dim]Original Path:[/dim] {entry['original_path']}")
    if entry.get("version"):
        console.print(f"  [dim]Version:[/dim] {entry['version']}")
    if entry.get("output_setting"):
        console.print(f"  [dim]Output Setting:[/dim] {entry['output_setting']}")


def _render_single_artifact_json(artifact_id: str, entry: dict) -> None:
    """Render a single artifact as JSON."""
    output = {"id": artifact_id}
    output.update(entry)
    print(json.dumps(output, indent=2))


@registry_app.command("list")
def registry_list(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """List all artifacts in the registry."""
    project, registry_manager, use_json = _require_project(ctx, path, json_output)

    try:
        registry = registry_manager.read()
    except RegistryError as exc:
        if use_json:
            print(json.dumps({"error": "Registry error", "details": str(exc)}, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    artifacts = registry.get("artifacts", {})

    if use_json:
        _render_artifact_json(artifacts)
    else:
        _render_artifact_table(artifacts)


@registry_app.command("add")
def registry_add(
    ctx: typer.Context,
    artifact_id: Annotated[str, typer.Argument(help="Unique artifact identifier")],
    owner: Annotated[str, typer.Option("--owner", help="Owner/tool name")],
    artifact_path: Annotated[
        str, typer.Option("--artifact-path", help="Project-relative artifact path")
    ],
    type: Annotated[str, typer.Option("--type", help="Artifact type: file or directory")],
    management: Annotated[
        str, typer.Option("--management", help="Management mode: managed or external")
    ],
    status: Annotated[str, typer.Option("--status", help="Status: active or inactive")] = "active",
    original_path: Annotated[
        Optional[str], typer.Option("--original-path", help="Original source path")
    ] = None,
    version: Annotated[Optional[str], typer.Option("--version", help="Artifact version")] = None,
    output_setting: Annotated[
        Optional[str], typer.Option("--output-setting", help="Output setting")
    ] = None,
    project_path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Add an artifact to the registry."""
    global_opts = ctx.obj
    dry_run = global_opts.dry_run if global_opts else False
    if dry_run:
        from airoom.core.logging import get_logger

        log = get_logger(__name__)
        log.info("Dry run: skipping registry add")
        if use_json := _get_json_output(ctx, json_output):
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "dry_run": True,
                        "message": "Dry run: would add artifact",
                        "artifact_id": artifact_id,
                    },
                    indent=2,
                )
            )
        else:
            console.print(f"[yellow]Dry run:[/yellow] Would add artifact {artifact_id!r}")
        return

    project, registry_manager, use_json = _require_project(ctx, project_path, json_output)

    # Build artifact entry
    entry = {
        "owner": owner,
        "path": artifact_path,
        "type": type,
        "management": management,
        "status": status,
    }
    if original_path is not None:
        entry["original_path"] = original_path
    if version is not None:
        entry["version"] = version
    if output_setting is not None:
        entry["output_setting"] = output_setting

    try:
        registry_manager.add_artifact(artifact_id, entry)
    except RegistryError as exc:
        if use_json:
            print(json.dumps({"error": "Failed to add artifact", "details": str(exc)}, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if use_json:
        print(
            json.dumps(
                {"status": "ok", "added": artifact_id, "artifact": {"id": artifact_id, **entry}},
                indent=2,
            )
        )
    else:
        console.print(f"[green]Added artifact:[/green] {artifact_id}")


@registry_app.command("remove")
def registry_remove(
    ctx: typer.Context,
    artifact_id: Annotated[str, typer.Argument(help="Artifact identifier to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Alias for --force, for scripted use")
    ] = False,
    project_path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Remove an artifact from the registry."""
    global_opts = ctx.obj
    dry_run = global_opts.dry_run if global_opts else False
    if dry_run:
        from airoom.core.logging import get_logger

        log = get_logger(__name__)
        log.info("Dry run: skipping registry remove")
        if use_json := _get_json_output(ctx, json_output):
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "dry_run": True,
                        "message": "Dry run: would remove artifact",
                        "artifact_id": artifact_id,
                    },
                    indent=2,
                )
            )
        else:
            console.print(f"[yellow]Dry run:[/yellow] Would remove artifact {artifact_id!r}")
        return

    project, registry_manager, use_json = _require_project(ctx, project_path, json_output)

    # Check if artifact exists first (let remove_artifact handle "not found" in one read)
    # We still need to check for confirmation prompt logic
    registry = registry_manager.read()
    if artifact_id not in registry.get("artifacts", {}):
        if use_json:
            print(
                json.dumps(
                    {
                        "error": "Artifact not found",
                        "details": f"Artifact {artifact_id!r} does not exist in registry",
                    },
                    indent=2,
                )
            )
        else:
            console.print(f"[red]Error:[/red] Artifact {artifact_id!r} not found in registry")
        raise typer.Exit(1)

    # Confirmation prompt if not forced (--force, -f, or --yes, -y)
    is_forced = force or yes
    if not is_forced:
        if use_json:
            print(
                json.dumps(
                    {
                        "error": "Confirmation required",
                        "details": "Use --force or --yes to skip confirmation prompt",
                    },
                    indent=2,
                )
            )
            raise typer.Exit(1)
        else:
            confirm = typer.confirm(f"Remove artifact {artifact_id!r} from registry?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(1)

    try:
        registry_manager.remove_artifact(artifact_id)
    except RegistryError as exc:
        if use_json:
            print(json.dumps({"error": "Failed to remove artifact", "details": str(exc)}, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if use_json:
        print(json.dumps({"status": "ok", "removed": artifact_id}, indent=2))
    else:
        console.print(f"[green]Removed artifact:[/green] {artifact_id}")


@registry_app.command("validate")
def registry_validate(
    ctx: typer.Context,
    project_path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Validate the registry schema and structure."""
    project, registry_manager, use_json = _require_project(ctx, project_path, json_output)

    try:
        is_valid, errors = registry_manager.validate()
    except RegistryError as exc:
        if use_json:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if use_json:
        print(json.dumps({"valid": is_valid, "errors": errors}, indent=2))
        if not is_valid:
            raise typer.Exit(1)
    else:
        if is_valid:
            console.print("[green]✓[/green] Registry is valid")
        else:
            console.print("[red]✗[/red] Registry is invalid")
            for error in errors:
                console.print(f"  [red]•[/red] {error}")
            raise typer.Exit(1)


@registry_app.command("show")
def registry_show(
    ctx: typer.Context,
    artifact_id: Annotated[str, typer.Argument(help="Artifact identifier to show")],
    project_path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Show details of a specific artifact."""
    project, registry_manager, use_json = _require_project(ctx, project_path, json_output)

    try:
        registry = registry_manager.read()
    except RegistryError as exc:
        if use_json:
            print(json.dumps({"error": "Registry error", "details": str(exc)}, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    artifacts = registry.get("artifacts", {})
    if artifact_id not in artifacts:
        if use_json:
            print(
                json.dumps(
                    {
                        "error": "Artifact not found",
                        "details": f"Artifact {artifact_id!r} does not exist in registry",
                    },
                    indent=2,
                )
            )
        else:
            console.print(f"[red]Error:[/red] Artifact {artifact_id!r} not found in registry")
        raise typer.Exit(1)

    entry = artifacts[artifact_id]

    if use_json:
        _render_single_artifact_json(artifact_id, entry)
    else:
        _render_single_artifact_human(artifact_id, entry)
