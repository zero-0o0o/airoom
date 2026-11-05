"""AIroom CLI entry point (Typer-based)."""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from airoom import __version__
from airoom.commands_typer.status import status
from airoom.commands_typer.doctor import doctor
from airoom.commands_typer.registry import registry_app
from airoom.commands_typer.discover import discover
from airoom.commands_typer.organize import organize
from airoom.commands_typer.config import config_app
from airoom.commands_typer.completion import completion_app
from airoom.commands_typer.init import init_app
from airoom.commands_typer.update import update_app
from airoom.commands_typer.upgrade import upgrade_app
from airoom.commands_typer.uninstall import uninstall_app
from airoom.core.logging import configure_logging
from airoom.core.types import GlobalOptions

console = Console()

app = typer.Typer(
    name="airoom",
    help="AIroom - Shared infrastructure for AI agents and tools",
    rich_markup_mode="rich",
    add_completion=False,
)


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
    # Configure logging based on global options
    configure_logging(ctx.obj)
    # If no command is invoked, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


# Apply global options callback to main app
app.callback(invoke_without_command=True)(global_options_callback)


# Register Typer commands
app.command("status", help="Show project health summary")(status)
app.command("doctor", help="Diagnose and repair common issues")(doctor)
app.command("discover", help="Discover AI artifacts and registry discrepancies")(discover)
app.command("organize", help="Organize artifacts under airoom/artifacts/")(organize)
app.add_typer(registry_app, name="registry")
app.add_typer(config_app, name="config")
app.add_typer(completion_app, name="completion")
app.add_typer(init_app, name="init")
app.add_typer(update_app, name="update")
app.add_typer(upgrade_app, name="upgrade")
app.add_typer(uninstall_app, name="uninstall")


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
