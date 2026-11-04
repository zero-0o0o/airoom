"""AIroom CLI entry point (Typer-based)."""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from airoom import __version__
from airoom.commands.init import init_command
from airoom.commands.update import update_command
from airoom.commands.upgrade import upgrade_command
from airoom.commands.uninstall import uninstall_command
from airoom.commands_typer.status import status
from airoom.commands_typer.doctor import doctor
from airoom.commands_typer.registry import registry_app
from airoom.commands_typer.discover import discover

console = Console()

app = typer.Typer(
    name="airoom",
    help="AIroom - Shared infrastructure for AI agents and tools",
    rich_markup_mode="rich",
    add_completion=False,
)

legacy_app = typer.Typer(
    name="legacy",
    help="Legacy commands (argparse-based)",
    rich_markup_mode="rich",
    add_completion=False,
)


class GlobalOptions:
    """Container for global CLI options."""

    def __init__(
        self,
        path: Optional[Path] = None,
        verbose: int = 0,
        json_output: bool = False,
        dry_run: bool = False,
    ):
        self.path = path
        self.verbose = verbose
        self.json_output = json_output
        self.dry_run = dry_run


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"airoom {__version__}")
        raise typer.Exit(0)


def global_options_callback(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option("--verbose", "-v", count=True, help="Increase verbosity"),
    ] = 0,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing"),
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", callback=version_callback, is_eager=True, help="Show version and exit"),
    ] = False,
) -> None:
    """Store global options in context object."""
    ctx.obj = GlobalOptions(
        path=path,
        verbose=verbose,
        json_output=json_output,
        dry_run=dry_run,
    )
    # If no command is invoked, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


# Apply global options callback to main app
app.callback(invoke_without_command=True)(global_options_callback)


@legacy_app.callback(invoke_without_command=True)
def legacy_callback(
    ctx: typer.Context,
    path: Annotated[
        Optional[Path],
        typer.Option("--path", "-p", help="Project directory"),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option("--verbose", "-v", count=True, help="Increase verbosity"),
    ] = 0,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output JSON"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing"),
    ] = False,
) -> None:
    """Store global options in context object for legacy commands."""
    # Inherit from parent context if available
    parent_obj = ctx.parent.obj if ctx.parent and ctx.parent.obj else None
    if parent_obj:
        ctx.obj = GlobalOptions(
            path=path or parent_obj.path,
            verbose=verbose or parent_obj.verbose,
            json_output=json_output or parent_obj.json_output,
            dry_run=dry_run or parent_obj.dry_run,
        )
    else:
        ctx.obj = GlobalOptions(
            path=path,
            verbose=verbose,
            json_output=json_output,
            dry_run=dry_run,
        )
    # If no subcommand is invoked, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


def _create_args_namespace(**kwargs):
    """Create a simple namespace object for argparse commands."""
    from types import SimpleNamespace
    return SimpleNamespace(**kwargs)


def _legacy_init(ctx: typer.Context) -> int:
    """Initialize AIroom in a project."""
    global_opts = ctx.obj if ctx.obj else GlobalOptions()
    args = _create_args_namespace(path=str(global_opts.path) if global_opts.path else None)
    return init_command(args)


def _legacy_update(ctx: typer.Context) -> int:
    """Update project resources."""
    global_opts = ctx.obj if ctx.obj else GlobalOptions()
    args = _create_args_namespace(path=str(global_opts.path) if global_opts.path else None)
    return update_command(args)


def _legacy_upgrade(
    ctx: typer.Context,
    version: Annotated[
        Optional[str],
        typer.Option("--version", help="Specific version to upgrade to (e.g., 0.2.0)"),
    ] = None,
    prerelease: Annotated[
        bool,
        typer.Option("--prerelease", help="Allow upgrading to prerelease versions"),
    ] = False,
) -> int:
    """Upgrade the global CLI."""
    global_opts = ctx.obj if ctx.obj else GlobalOptions()
    args = _create_args_namespace(version=version, prerelease=prerelease)
    return upgrade_command(args)


def _legacy_uninstall(
    ctx: typer.Context,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt"),
    ] = False,
) -> int:
    """Uninstall the global CLI."""
    global_opts = ctx.obj if ctx.obj else GlobalOptions()
    args = _create_args_namespace(yes=yes)
    return uninstall_command(args)


# Register Typer commands
app.command("status", help="Show project health summary")(status)
app.command("doctor", help="Diagnose and repair common issues")(doctor)
app.command("discover", help="Discover AI artifacts and registry discrepancies")(discover)
app.add_typer(registry_app, name="registry")

# Register legacy commands at top level (for backward compatibility)
app.command("init", help="Initialize AIroom in a project")(_legacy_init)
app.command("update", help="Update project resources")(_legacy_update)
app.command("upgrade", help="Upgrade the global CLI")(_legacy_upgrade)
app.command("uninstall", help="Uninstall the global CLI")(_legacy_uninstall)

# Register legacy commands under legacy subcommand group
legacy_app.command("init", help="Initialize AIroom in a project")(_legacy_init)
legacy_app.command("update", help="Update project resources")(_legacy_update)
legacy_app.command("upgrade", help="Upgrade the global CLI")(_legacy_upgrade)
legacy_app.command("uninstall", help="Uninstall the global CLI")(_legacy_uninstall)

# Register legacy app as subcommand group on main app
app.add_typer(legacy_app, name="legacy")


# Main entry point
def main() -> int:
    """Main entry point for the Typer CLI."""
    try:
        return app(standalone_mode=False)
    except typer.Exit as e:
        return e.exit_code
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())