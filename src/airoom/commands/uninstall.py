"""AIroom uninstall command implementation."""

import json
import shutil
import subprocess
import sys
from typing import Optional


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


def get_installed_version() -> str:
    """Get the currently installed AIroom version."""
    from airoom import __version__

    return __version__


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
            print(f"pipx uninstall failed: {result.stderr}", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print("pipx uninstall timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"pipx uninstall error: {e}", file=sys.stderr)
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


def uninstall_command(args) -> int:
    """Uninstall the global AIroom CLI.

    Returns:
        0 on success
        1 on error
        2 if cancelled by user
        3 if not installed via supported method
    """
    skip_confirmation = getattr(args, "yes", False)

    print("AIroom CLI Uninstall")
    print("====================")

    # Get installed version first (for display)
    installed_version = get_installed_version()
    print(f"Installed version: {installed_version}")

    # Check installation method
    pipx_path = get_pipx_path()
    if not pipx_path:
        print("Error: pipx not found in PATH", file=sys.stderr)
        print("AIroom was installed via pipx, but pipx is no longer available.", file=sys.stderr)
        print("Install pipx: https://pipx.pypa.io/stable/installation/", file=sys.stderr)
        return 3

    if not is_installed_via_pipx():
        print("Error: AIroom does not appear to be installed via pipx", file=sys.stderr)
        print("Cannot verify installation method. Aborting for safety.", file=sys.stderr)
        print("If you installed AIroom differently, please uninstall it manually.", file=sys.stderr)
        return 3

    print(f"Detected installation method: pipx ({pipx_path})")
    print()
    print("This will uninstall the global AIroom CLI only.")
    print("Project-level AIroom resources (airoom/ directories, AGENTS.md, etc.)")
    print("will NOT be affected.")
    print()

    # Handle confirmation
    if not skip_confirmation:
        if not is_interactive():
            print("Error: Running in non-interactive mode without --yes flag.", file=sys.stderr)
            print("Use 'airoom uninstall --yes' to skip confirmation.", file=sys.stderr)
            return 2

        if not prompt_confirmation():
            print("Uninstall cancelled.")
            return 2

    print("Uninstalling AIroom via pipx...")

    # Perform uninstall
    if not uninstall_via_pipx(pipx_path):
        print("Uninstall failed.", file=sys.stderr)
        return 1

    # Verify uninstallation
    print("Verifying uninstallation...")
    if verify_uninstallation():
        print("AIroom has been successfully uninstalled.")
    else:
        print("Warning: AIroom may still be installed. Please verify manually.", file=sys.stderr)
        return 1

    return 0


def add_uninstall_parser(subparsers):
    """Add the uninstall subcommand parser."""
    parser = subparsers.add_parser("uninstall", help="Uninstall the global CLI")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    parser.set_defaults(func=uninstall_command)
