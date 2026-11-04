"""AIroom config command implementation (Typer-based)."""

import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from airoom.core.config import ConfigManager
from airoom.core.project import Project

console = Console()

config_app = typer.Typer(name="config", help="Manage project configuration.")


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


def _render_config_human(config) -> None:
    """Render config as a Rich table."""
    table = Table(title="AIroom Configuration", show_header=True, header_style="bold")
    table.add_column("Key", style="cyan", min_width=20)
    table.add_column("Value", style="dim")

    # Top-level keys
    table.add_row("skips", str(config.skips))
    table.add_row("dry_run", str(config.dry_run))
    table.add_row("verbose", str(config.verbose))

    # Defaults (nested)
    if config.defaults:
        for key, value in sorted(config.defaults.items()):
            table.add_row(f"defaults.{key}", str(value))
    else:
        table.add_row("defaults", "(empty)")

    console.print(table)


def _render_config_json(config) -> None:
    """Render config as JSON."""
    output = {
        "skips": config.skips,
        "defaults": config.defaults,
        "dry_run": config.dry_run,
        "verbose": config.verbose,
    }
    print(json.dumps(output, indent=2))


@config_app.command("show")
def config_show(
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
    """Show current configuration."""
    use_json = _get_json_output(ctx, json_output)

    project = _get_project(ctx, path)

    # Verify project has been initialized
    if not project.airoom_dir.exists():
        if use_json:
            print(json.dumps({
                "error": "Project not initialized",
                "details": f"AIroom directory not found at {project.airoom_dir}. Run 'airoom init' first."
            }, indent=2))
        else:
            console.print(f"[red]Error:[/red] Project not initialized at {project.root}")
            console.print("Run 'airoom init' to initialize AIroom in this project.")
        raise typer.Exit(1)

    config_manager = ConfigManager(project)
    config = config_manager.read()

    if use_json:
        _render_config_json(config)
    else:
        _render_config_human(config)


@config_app.command("set")
def config_set(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Configuration key (dot notation)")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Set a configuration value using dot notation."""
    use_json = _get_json_output(ctx, json_output)
    project = _get_project(ctx, path)

    # Verify project has been initialized
    if not project.airoom_dir.exists():
        if use_json:
            print(json.dumps({
                "error": "Project not initialized",
                "details": f"AIroom directory not found at {project.airoom_dir}. Run 'airoom init' first."
            }, indent=2))
        else:
            console.print(f"[red]Error:[/red] Project not initialized at {project.root}")
            console.print("Run 'airoom init' to initialize AIroom in this project.")
        raise typer.Exit(1)

    # Parse value - try to convert to appropriate type
    parsed_value = _parse_value(value)

    config_manager = ConfigManager(project)
    try:
        config_manager.set(key, parsed_value)
    except Exception as exc:
        if use_json:
            print(json.dumps({
                "error": "Failed to set config",
                "details": str(exc)
            }, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if use_json:
        print(json.dumps({
            "status": "ok",
            "key": key,
            "value": parsed_value
        }, indent=2))
    else:
        console.print(f"[green]Set:[/green] {key} = {parsed_value}")


@config_app.command("unset")
def config_unset(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Configuration key (dot notation)")],
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
) -> None:
    """Unset a configuration value using dot notation."""
    use_json = _get_json_output(ctx, json_output)
    project = _get_project(ctx, path)

    # Verify project has been initialized
    if not project.airoom_dir.exists():
        if use_json:
            print(json.dumps({
                "error": "Project not initialized",
                "details": f"AIroom directory not found at {project.airoom_dir}. Run 'airoom init' first."
            }, indent=2))
        else:
            console.print(f"[red]Error:[/red] Project not initialized at {project.root}")
            console.print("Run 'airoom init' to initialize AIroom in this project.")
        raise typer.Exit(1)

    config_manager = ConfigManager(project)
    try:
        config_manager.unset(key)
    except Exception as exc:
        if use_json:
            print(json.dumps({
                "error": "Failed to unset config",
                "details": str(exc)
            }, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if use_json:
        print(json.dumps({
            "status": "ok",
            "key": key
        }, indent=2))
    else:
        console.print(f"[green]Unset:[/green] {key}")


def _parse_value(value: str):
    """Parse a string value into appropriate Python type."""
    # Boolean
    if value.lower() in ("true", "false"):
        return value.lower() == "true"

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    # Float
    try:
        return float(value)
    except ValueError:
        pass

    # JSON array/object
    if value.startswith("[") or value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

    # Null/None
    if value.lower() in ("null", "none"):
        return None

    # String (default)
    return value


if __name__ == "__main__":
    import sys
    from typer.testing import CliRunner

    # Quick manual test
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        from airoom.cli import app
        result = runner.invoke(app, ["--path", tmpdir, "legacy", "init"])
        print("init:", result.exit_code, result.stdout)
        result = runner.invoke(app, ["--path", tmpdir, "config", "show"])
        print("show:", result.exit_code, result.stdout)