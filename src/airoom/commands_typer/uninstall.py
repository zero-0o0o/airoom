"""AIroom uninstall command implementation (Typer-based)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from airoom import __version__
from airoom.core.logging import configure_logging, get_logger
from airoom.core.types import GlobalOptions
from airoom.core.version import get_installed_version

console = Console()
log = get_logger(__name__)


def get_pipx_path() -> Optional[str]:
    """Get the path to pipx executable."""
    try:
        return shutil.which("pipx")
    except Exception:
        pass
    return None


def is_installed_via_pipx() -> bool:
    """Check if AIroom was installed via pipx."""
    try:
        result = subprocess.run(["pipx", "list", "--json"], capture_output=True, text=True)
        if result.returncode == 0:
            venvs = json.loads(result.stdout).get("venvs", {})
            return isinstance(venvs, dict) and "airoom" in venvs
    except Exception:
        pass
    return False


def uninstall_via_pipx(pipx_path: str = "pipx") -> bool:
    """Uninstall AIroom using pipx.

    Returns:
        True on success, False on failure
    """
    try:
        result = subprocess.run(
            [pipx_path, "uninstall", "airoom"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            log.error("pipx uninstall failed: %s", result.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("pipx uninstall timed out")
        return False
    except Exception as e:
        log.error("pipx uninstall error: %s", e)
        return False


def verify_uninstallation() -> bool:
    """Verify that AIroom has been uninstalled."""
    try:
        result = subprocess.run(
            ["pipx", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False
        return "airoom" not in json.loads(result.stdout).get("venvs", {})
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return False
    except Exception:
        return False


def is_interactive() -> bool:
    """Check if running in an interactive terminal."""
    return sys.stdin.isatty()


def prompt_confirmation() -> bool:
    """Prompt user for confirmation.

    Returns:
        True if user confirms, False otherwise
    """
    while True:
        try:
            response = input("Are you sure you want to uninstall AIroom? [y/N]: ").strip().lower()
            if response in ("y", "yes"):
                return True
            elif response in ("n", "no", ""):
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")
        except (EOFError, KeyboardInterrupt):
            print()  # New line after ^C or ^D
            return False


def _output_json(
    status: str,
    message: str,
    installed_version: str | None = None,
) -> None:
    """Output uninstall result as JSON."""
    result = {
        "status": status,
        "message": message,
    }
    if installed_version:
        result["installed_version"] = installed_version
    print(json.dumps(result, indent=2))


def uninstall(
    ctx: typer.Context,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Uninstall the global AIroom CLI."""
    # Get global options from context
    global_opts: GlobalOptions | None = ctx.obj

    # Use global options
    json_output = global_opts.json_output if global_opts else False
    dry_run = global_opts.dry_run if global_opts else False
    verbose = global_opts.verbose if global_opts else 0

    if dry_run:
        log.info("Dry run: skipping uninstall")
        if not json_output:
            console.print("[yellow]Dry run:[/yellow] Would uninstall the global AIroom CLI")
        if json_output:
            _output_json("dry_run", "Dry run: would uninstall the global AIroom CLI")
        raise typer.Exit(0)

    # Get installed version first (for display)
    installed_version = get_installed_version()

    if not json_output:
        console.print("AIroom CLI Uninstall")
        console.print("====================")
        console.print(f"Installed version: {installed_version}")

    # Check installation method
    pipx_path = get_pipx_path()
    if not pipx_path:
        if json_output:
            _output_json("error", "pipx not found in PATH", installed_version)
        else:
            console.print("[red]Error:[/red] pipx not found in PATH")
            console.print("AIroom was installed via pipx, but pipx is no longer available.")
            console.print("Install pipx: https://pipx.pypa.io/stable/installation/")
        raise typer.Exit(3)

    if not is_installed_via_pipx():
        if json_output:
            _output_json("error", "AIroom does not appear to be installed via pipx", installed_version)
        else:
            console.print("[red]Error:[/red] AIroom does not appear to be installed via pipx")
            console.print("Cannot verify installation method. Aborting for safety.")
            console.print("If you installed AIroom differently, please uninstall it manually.")
        raise typer.Exit(3)

    if not json_output:
        console.print(f"Detected installation method: pipx ({pipx_path})")
        console.print()
        console.print("This will uninstall the global AIroom CLI only.")
        console.print("Project-level AIroom resources (airoom/ directories, AGENTS.md, etc.)")
        console.print("will NOT be affected.")
        console.print()

    # Handle confirmation
    if not yes:
        if not is_interactive():
            if json_output:
                _output_json("cancelled", "Running in non-interactive mode without --yes flag", installed_version)
            else:
                console.print("[red]Error:[/red] Running in non-interactive mode without --yes flag.")
                console.print("Use 'airoom uninstall --yes' to skip confirmation.")
            raise typer.Exit(2)

        if not prompt_confirmation():
            if json_output:
                _output_json("cancelled", "Uninstall cancelled by user", installed_version)
            else:
                console.print("Uninstall cancelled.")
            raise typer.Exit(2)

    if not json_output:
        console.print("Uninstalling AIroom via pipx...")

    # Perform uninstall
    if not uninstall_via_pipx(pipx_path):
        if json_output:
            _output_json("error", "Uninstall failed", installed_version)
        else:
            console.print("[red]Error:[/red] Uninstall failed.")
        raise typer.Exit(1)

    # Verify uninstallation
    if not json_output:
        console.print("Verifying uninstallation...")
    if verify_uninstallation():
        if json_output:
            _output_json("success", "AIroom has been successfully uninstalled", installed_version)
        else:
            console.print("[green]AIroom has been successfully uninstalled.[/green]")
    else:
        if json_output:
            _output_json("error", "AIroom may still be installed. Please verify manually.", installed_version)
        else:
            console.print("[yellow]Warning:[/yellow] AIroom may still be installed. Please verify manually.")
        raise typer.Exit(1)

    raise typer.Exit(0)


uninstall_app = typer.Typer(name="uninstall", help="Uninstall the global CLI", invoke_without_command=True)
uninstall_app.callback()(uninstall)


__all__ = [
    "uninstall",
    "get_pipx_path",
    "is_installed_via_pipx",
    "uninstall_via_pipx",
    "verify_uninstallation",
    "is_interactive",
    "prompt_confirmation",
    "uninstall_app",
]