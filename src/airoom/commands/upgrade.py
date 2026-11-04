"""AIroom upgrade command implementation."""

import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional


@dataclass
class Release:
    """Represents a GitHub release."""

    tag_name: str
    version: str  # Semantic version without 'v' prefix
    prerelease: bool
    published_at: str


def get_installed_version() -> str:
    """Get the currently installed AIroom version."""
    from airoom import __version__

    return __version__


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


def upgrade_command(args) -> int:
    """Upgrade the global AIroom CLI.

    Returns:
        0 on success
        1 on error
        2 if already up to date
        3 if invalid version specified
    """
    repo = "zero-0o0o/airoom"
    include_prereleases = getattr(args, "prerelease", False)
    target_version = getattr(args, "version", None)

    print("AIroom CLI Upgrade")
    print("==================")

    # Check installation method
    pipx_path = get_pipx_path()
    if not pipx_path:
        print("Error: pipx not found in PATH", file=sys.stderr)
        print("AIroom requires pipx for installation and upgrades.", file=sys.stderr)
        print("Install pipx: https://pipx.pypa.io/stable/installation/", file=sys.stderr)
        return 1

    if not is_installed_via_pipx():
        print(
            "Error: AIroom is not verified as a pipx installation; refusing to upgrade.",
            file=sys.stderr,
        )
        return 1

    # Get installed version
    installed_version = get_installed_version()
    print(f"Installed version: {installed_version}")

    # Determine target version
    if target_version:
        # Validate explicit version
        target_version = target_version.lstrip("v")
        try:
            parse_version(target_version)
        except ValueError:
            print(f"Error: Invalid version format: {target_version}", file=sys.stderr)
            print("Expected format: X.Y.Z (e.g., 0.2.0)", file=sys.stderr)
            return 3

        # Verify the version exists as a release
        print(f"Checking for version v{target_version}...")
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
                    print("Error: Release API returned an unexpected response", file=sys.stderr)
                    return 1
                if data.get("tag_name") not in (f"v{target_version}", target_version):
                    print(
                        "Error: Release API returned a different tag than requested",
                        file=sys.stderr,
                    )
                    return 3
                if data.get("draft"):
                    print(f"Error: Version {target_version} is a draft release", file=sys.stderr)
                    return 3
                if data.get("prerelease") and not include_prereleases:
                    print(
                        f"Error: Version {target_version} is a prerelease. Use --prerelease to allow.",
                        file=sys.stderr,
                    )
                    return 3
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"Error: Version {target_version} not found in releases", file=sys.stderr)
                return 3
            print(f"Error: Failed to verify release: {e}", file=sys.stderr)
            return 1
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            print(f"Error: Failed to verify release: {e}", file=sys.stderr)
            return 1

        latest_version = target_version
        tag_name = f"v{target_version}"
    else:
        # Fetch latest stable release
        print("Checking for latest release...")
        try:
            release = fetch_latest_release(repo, include_prereleases=include_prereleases)
            if not release:
                print("Error: No releases found", file=sys.stderr)
                return 1
            latest_version = release.version
            tag_name = release.tag_name
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    print(f"Latest version:    {latest_version}")

    # Compare versions
    cmp = compare_versions(installed_version, latest_version)
    if cmp >= 0:
        print("Already at the latest version.")
        return 2

    # Check if latest is prerelease
    if is_prerelease(latest_version) and not include_prereleases:
        print("Latest version is a prerelease. Use --prerelease to upgrade to it.")
        return 2

    print(f"Upgrading to {tag_name}...")

    # Perform upgrade
    if not upgrade_via_pipx(tag_name, repo):
        print("Upgrade failed.", file=sys.stderr)
        print(
            "You can try manually: pipx upgrade airoom --spec git+https://github.com/{repo}.git@{tag_name}",
            file=sys.stderr,
        )
        return 1

    # Verify upgrade
    print("Verifying installation...")
    new_version = verify_installation()
    if new_version != latest_version:
        print(
            f"Error: Upgrade installed version {new_version or 'unknown'}; expected {latest_version}.",
            file=sys.stderr,
        )
        return 1
    print(f"Successfully upgraded to version {new_version}")

    return 0


def add_upgrade_parser(subparsers):
    """Add the upgrade subcommand parser."""
    parser = subparsers.add_parser("upgrade", help="Upgrade the global CLI")
    parser.add_argument(
        "--version",
        help="Specific version to upgrade to (e.g., 0.2.0)",
    )
    parser.add_argument(
        "--prerelease",
        action="store_true",
        help="Allow upgrading to prerelease versions",
    )
    parser.set_defaults(func=upgrade_command)
