"""AIroom upgrade command implementation (Typer-based)."""

import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
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


@dataclass
class Release:
    """Represents a GitHub release."""

    tag_name: str
    version: str  # Semantic version without 'v' prefix
    prerelease: bool
    published_at: str


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


def parse_version(version_str: str) -> tuple:
    """Parse a semantic version string into a tuple for comparison.

    Handles versions like: 0.1.0, 1.0.0, 0.2.0-alpha, 1.0.0-rc.1
    Returns tuple that sorts correctly: prereleases before final releases.
    """
    match = re.fullmatch(
        r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?",
        version_str,
    )
    if not match:
        raise ValueError(f"Invalid semantic version: {version_str!r}")
    major, minor, patch = (int(part) for part in match.group(1, 2, 3))
    prerelease = match.group(4)
    if prerelease is None:
        return (major, minor, patch, 1)
    identifiers = tuple(
        (0, int(part)) if part.isdigit() else (1, part) for part in prerelease.split(".")
    )
    return (major, minor, patch, 0, identifiers)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings.

    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    t1 = parse_version(v1)
    t2 = parse_version(v2)

    if t1 < t2:
        return -1
    elif t1 > t2:
        return 1
    return 0


def is_prerelease(version_str: str) -> bool:
    """Check if a version string represents a prerelease."""
    return "-" in version_str.lstrip("v")


def fetch_latest_release(
    repo: str = "zero-0o0o/airoom", include_prereleases: bool = False
) -> Optional[Release]:
    """Fetch the latest release from GitHub API.

    Args:
        repo: GitHub repository in format "owner/repo"
        include_prereleases: Whether to include prerelease versions

    Returns:
        Release object or None if not found/error
    """
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "airoom-upgrade",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to fetch releases from GitHub: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse GitHub API response: {e}")

    if not isinstance(data, list):
        raise RuntimeError("GitHub releases response must be a JSON list")
    if not data:
        return None

    # Filter releases
    releases = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("draft"):
            continue
        prerelease = item.get("prerelease", False)
        if prerelease and not include_prereleases:
            continue

        tag_name = item.get("tag_name", "")
        if not isinstance(tag_name, str) or not tag_name:
            continue
        version = tag_name[1:] if tag_name.startswith("v") else tag_name
        try:
            parse_version(version)
        except ValueError:
            continue

        releases.append(
            Release(
                tag_name=tag_name,
                version=version,
                prerelease=prerelease,
                published_at=item.get("published_at", ""),
            )
        )

    if not releases:
        return None

    # Sort by version (newest first)
    releases.sort(key=lambda r: parse_version(r.version), reverse=True)
    return releases[0]


def upgrade_via_pipx(version: str, repo: str = "zero-0o0o/airoom") -> bool:
    """Upgrade AIroom using pipx.

    Args:
        version: Version tag to install (e.g., "v0.2.0")
        repo: GitHub repository

    Returns:
        True on success, False on failure
    """
    install_spec = f"git+https://github.com/{repo}.git@{version}"

    try:
        result = subprocess.run(
            ["pipx", "install", install_spec, "--force"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"pipx install failed: {result.stderr}", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print("pipx upgrade timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"pipx upgrade error: {e}", file=sys.stderr)
        return False


def verify_installation() -> Optional[str]:
    """Verify the AIroom installation and return version."""
    try:
        result = subprocess.run(
            ["airoom", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Output format: "airoom X.Y.Z"
            match = re.search(r"(\d+\.\d+\.\d+(?:-[\w.]+)?)", result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def _output_json(
    installed_version: str,
    latest_version: str,
    status: str,
    message: str,
    tag_name: str | None = None,
) -> None:
    """Output upgrade result as JSON."""
    result = {
        "installed_version": installed_version,
        "latest_version": latest_version,
        "status": status,
        "message": message,
    }
    if tag_name:
        result["tag_name"] = tag_name
    print(json.dumps(result, indent=2))


def upgrade(
    ctx: typer.Context,
    version: Annotated[
        Optional[str],
        typer.Option("--version", help="Specific version to upgrade to (e.g., 0.2.0)"),
    ] = None,
    prerelease: Annotated[
        bool,
        typer.Option("--prerelease", help="Allow upgrading to prerelease versions"),
    ] = False,
) -> None:
    """Upgrade the global AIroom CLI."""
    # Get global options from context
    global_opts: GlobalOptions | None = ctx.obj

    # Use global options
    json_output = global_opts.json_output if global_opts else False
    dry_run = global_opts.dry_run if global_opts else False
    verbose = global_opts.verbose if global_opts else 0

    if dry_run:
        log.info("Dry run: skipping upgrade")
        if not json_output:
            console.print("[yellow]Dry run:[/yellow] Would upgrade the global AIroom CLI")
        raise typer.Exit(0)

    repo = "zero-0o0o/airoom"
    include_prereleases = prerelease
    target_version = version

    if not json_output:
        console.print("AIroom CLI Upgrade")
        console.print("==================")

    # Check installation method
    pipx_path = get_pipx_path()
    if not pipx_path:
        if json_output:
            _output_json("", "", "error", "pipx not found in PATH")
        else:
            console.print("[red]Error:[/red] pipx not found in PATH")
            console.print("AIroom requires pipx for installation and upgrades.")
            console.print("Install pipx: https://pipx.pypa.io/stable/installation/")
        raise typer.Exit(1)

    if not is_installed_via_pipx():
        if json_output:
            _output_json("", "", "error", "AIroom not verified as pipx installation")
        else:
            console.print(
                "[red]Error:[/red] AIroom is not verified as a pipx installation; refusing to upgrade."
            )
        raise typer.Exit(1)

    # Get installed version
    installed_version = get_installed_version()
    if not json_output:
        console.print(f"Installed version: {installed_version}")

    # Determine target version
    if target_version:
        # Validate explicit version
        target_version = target_version.lstrip("v")
        try:
            parse_version(target_version)
        except ValueError:
            if json_output:
                _output_json(installed_version, "", "error", f"Invalid version format: {target_version}")
            else:
                console.print(f"[red]Error:[/red] Invalid version format: {target_version}")
                console.print("Expected format: X.Y.Z (e.g., 0.2.0)")
            raise typer.Exit(3)

        # Verify the version exists as a release
        if not json_output:
            console.print(f"Checking for version v{target_version}...")
        try:
            # Check if the specific version exists
            url = f"https://api.github.com/repos/{repo}/releases/tags/v{target_version}"
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "airoom-upgrade",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                if not isinstance(data, dict):
                    if json_output:
                        _output_json(installed_version, "", "error", "Release API returned unexpected response")
                    else:
                        console.print("[red]Error:[/red] Release API returned an unexpected response")
                    raise typer.Exit(1)
                if data.get("tag_name") not in (f"v{target_version}", target_version):
                    if json_output:
                        _output_json(installed_version, "", "error", "Release tag mismatch")
                    else:
                        console.print(
                            "[red]Error:[/red] Release API returned a different tag than requested"
                        )
                    raise typer.Exit(3)
                if data.get("draft"):
                    if json_output:
                        _output_json(installed_version, "", "error", f"Version {target_version} is a draft release")
                    else:
                        console.print(f"[red]Error:[/red] Version {target_version} is a draft release")
                    raise typer.Exit(3)
                if data.get("prerelease") and not include_prereleases:
                    if json_output:
                        _output_json(installed_version, target_version, "error", f"Version {target_version} is a prerelease. Use --prerelease to allow.")
                    else:
                        console.print(
                            f"[red]Error:[/red] Version {target_version} is a prerelease. Use --prerelease to allow."
                        )
                    raise typer.Exit(3)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                if json_output:
                    _output_json(installed_version, target_version, "error", f"Version {target_version} not found in releases")
                else:
                    console.print(f"[red]Error:[/red] Version {target_version} not found in releases")
                raise typer.Exit(3)
            if json_output:
                _output_json(installed_version, target_version, "error", f"Failed to verify release: {e}")
            else:
                console.print(f"[red]Error:[/red] Failed to verify release: {e}")
            raise typer.Exit(1)
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            if json_output:
                _output_json(installed_version, target_version, "error", f"Failed to verify release: {e}")
            else:
                console.print(f"[red]Error:[/red] Failed to verify release: {e}")
            raise typer.Exit(1)

        latest_version = target_version
        tag_name = f"v{target_version}"
    else:
        # Fetch latest stable release
        if not json_output:
            console.print("Checking for latest release...")
        try:
            release = fetch_latest_release(repo, include_prereleases=include_prereleases)
            if not release:
                if json_output:
                    _output_json(installed_version, "", "error", "No releases found")
                else:
                    console.print("[red]Error:[/red] No releases found")
                raise typer.Exit(1)
            latest_version = release.version
            tag_name = release.tag_name
        except RuntimeError as e:
            if json_output:
                _output_json(installed_version, "", "error", str(e))
            else:
                console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    if not json_output:
        console.print(f"Latest version:    {latest_version}")

    # Compare versions
    cmp = compare_versions(installed_version, latest_version)
    if cmp >= 0:
        if json_output:
            _output_json(installed_version, latest_version, "up_to_date", "Already at the latest version", tag_name)
        else:
            console.print("Already at the latest version.")
        raise typer.Exit(2)

    # Check if latest is prerelease
    if is_prerelease(latest_version) and not include_prereleases:
        if json_output:
            _output_json(installed_version, latest_version, "prerelease_blocked", "Latest version is a prerelease. Use --prerelease to upgrade to it.", tag_name)
        else:
            console.print("Latest version is a prerelease. Use --prerelease to upgrade to it.")
        raise typer.Exit(2)

    if not json_output:
        console.print(f"Upgrading to {tag_name}...")

    # Perform upgrade
    if not upgrade_via_pipx(tag_name, repo):
        if json_output:
            _output_json(installed_version, latest_version, "error", "Upgrade failed", tag_name)
        else:
            console.print("[red]Error:[/red] Upgrade failed.")
            console.print(
                f"You can try manually: pipx upgrade airoom --spec git+https://github.com/{repo}.git@{tag_name}"
            )
        raise typer.Exit(1)

    # Verify upgrade
    if not json_output:
        console.print("Verifying installation...")
    new_version = verify_installation()
    if new_version != latest_version:
        if json_output:
            _output_json(installed_version, latest_version, "error", f"Upgrade installed version {new_version or 'unknown'}; expected {latest_version}", tag_name)
        else:
            console.print(
                f"[red]Error:[/red] Upgrade installed version {new_version or 'unknown'}; expected {latest_version}."
            )
        raise typer.Exit(1)

    if not json_output:
        console.print(f"[green]Successfully upgraded to version {new_version}[/green]")

    if json_output:
        _output_json(installed_version, new_version, "success", f"Successfully upgraded to version {new_version}", tag_name)

    raise typer.Exit(0)


upgrade_app = typer.Typer(name="upgrade", help="Upgrade the global CLI", invoke_without_command=True)
upgrade_app.callback()(upgrade)


__all__ = [
    "upgrade",
    "get_pipx_path",
    "is_installed_via_pipx",
    "parse_version",
    "compare_versions",
    "is_prerelease",
    "fetch_latest_release",
    "upgrade_via_pipx",
    "verify_installation",
    "Release",
    "upgrade_app",
]